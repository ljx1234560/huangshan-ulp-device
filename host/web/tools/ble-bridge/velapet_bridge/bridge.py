from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

import httpx

from .api import ApiClient
from .transport import BleTransport

logger = logging.getLogger("velapet.bridge")


@dataclass(frozen=True)
class SyncResult:
    accepted: int
    duplicates: int
    acknowledged_cursor: int


class BridgeRunner:
    def __init__(self, transport: BleTransport, api: ApiClient, client_id: str = "windows-ble-bridge", expected_serial: str | None = None):
        self.transport = transport
        self.api = api
        self.client_id = client_id
        self.expected_serial = expected_serial

    async def sync_once(self) -> SyncResult:
        await self.transport.connect()
        info: dict = {}
        try:
            protocol = await self.transport.protocol_info()
            if protocol.get("version") != 1:
                raise RuntimeError(f"不支持设备协议版本 {protocol.get('version')}")
            info = await self.transport.device_info()
            serial = str(info["serialNumber"])
            if self.expected_serial and serial != self.expected_serial:
                raise RuntimeError(f"BLE 设备序列号 {serial} 与授权设备 {self.expected_serial} 不一致")
            await self.api.update_status(serial, "connected", True, "BLE 已连接", running=True)
            await self.api.update_status(serial, "syncing", True, "BLE 已连接，正在读取历史记录", running=True)
            logger.info("正在同步 serial=%s firmware=%s", serial, info.get("firmwareVersion", "unknown"))
            total_accepted = 0
            total_duplicates = 0
            acknowledged = int(info.get("syncCursor", 0))
            async for batch in self.transport.history(start_cursor=acknowledged):
                result = await self._upload_with_retry(serial, info, batch)
                # The device is acknowledged only after the backend committed the batch.
                if result.ack_cursor != batch.next_cursor:
                    raise RuntimeError(
                        f"服务端 ACK 游标 {result.ack_cursor} 与批次结束游标 {batch.next_cursor} 不一致"
                    )
                await self.transport.ack(batch.session_id, batch.sequence, result.ack_cursor)
                total_accepted += result.accepted
                total_duplicates += result.duplicates
                acknowledged = result.ack_cursor
            await self.api.update_status(serial, "success", True, f"同步成功，新增 {total_accepted} 条", running=True)
            logger.info("同步成功 accepted=%d duplicates=%d cursor=%d", total_accepted, total_duplicates, acknowledged)
            return SyncResult(total_accepted, total_duplicates, acknowledged)
        except Exception as exc:
            serial = str(info.get("serialNumber", "unknown"))
            if serial != "unknown":
                try:
                    await self.api.update_status(serial, "failed", self._is_connected(), str(exc)[:240], running=True)
                except Exception:
                    logger.debug("unable to report bridge failure", exc_info=True)
            logger.error("同步失败: %s", exc)
            raise
        finally:
            try:
                await self.transport.disconnect()
            finally:
                serial = str(info.get("serialNumber", "unknown"))
                if serial != "unknown":
                    try:
                        await self.api.update_status(serial, "disconnected", False, "BLE 已断开", running=False)
                    except Exception:
                        logger.debug("unable to report bridge disconnect", exc_info=True)

    async def sync_with_reconnect(self, attempts: int = 3) -> SyncResult:
        last_error: Exception | None = None
        for attempt in range(1, attempts + 1):
            try:
                return await self.sync_once()
            except (ConnectionError, TimeoutError, asyncio.TimeoutError) as exc:
                last_error = exc
                if attempt == attempts:
                    break
                delay = min(4.0, 0.5 * (2 ** (attempt - 1)))
                logger.warning("设备断开，%.1f 秒后重连 (%d/%d)", delay, attempt + 1, attempts)
                await asyncio.sleep(delay)
        assert last_error is not None
        raise last_error

    async def _upload_with_retry(self, serial: str, info: dict, batch):
        last_error: Exception | None = None
        for attempt in range(1, 4):
            try:
                return await self.api.upload(
                    serial,
                    batch.upload_id,
                    batch.cursor,
                    0,
                    batch.records,
                    info.get("firmwareVersion"),
                    1,
                    self.client_id,
                )
            except (httpx.TimeoutException, httpx.TransportError, httpx.HTTPStatusError) as exc:
                last_error = exc
                if isinstance(exc, httpx.HTTPStatusError) and 400 <= exc.response.status_code < 500:
                    raise
                if attempt < 3:
                    await asyncio.sleep(0.25 * (2 ** (attempt - 1)))
        assert last_error is not None
        raise last_error

    def _is_connected(self) -> bool:
        return bool(getattr(self.transport, "connected", getattr(getattr(self.transport, "_client", None), "is_connected", False)))
