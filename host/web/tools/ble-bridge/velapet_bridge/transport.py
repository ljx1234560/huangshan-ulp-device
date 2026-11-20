from __future__ import annotations

import asyncio
import logging
import struct
from abc import ABC, abstractmethod
from dataclasses import dataclass
from collections.abc import AsyncIterator
from typing import Any

from .protocol import (
    CONTROL_UUID,
    DATA_UUID,
    SERVICE_UUID,
    STATUS_UUID,
    Message,
    MessageType,
    CrcError,
    HEADER,
    NACK,
    MotionRecord,
    Reassembler,
    SYNC_ACK,
    SYNC_REQUEST,
    decode_frame,
    decode_json,
    decode_motion_records,
    fragment_message,
)

logger = logging.getLogger("velapet.bridge")


@dataclass(frozen=True)
class DiscoveredDevice:
    address: str
    name: str
    rssi: int | None = None


@dataclass(frozen=True)
class HistoryBatch:
    upload_id: str
    cursor: int
    next_cursor: int
    records: list[MotionRecord]
    final: bool
    session_id: int = 0
    sequence: int = 0


class BleTransport(ABC):
    @abstractmethod
    async def connect(self) -> None: ...

    @abstractmethod
    async def disconnect(self) -> None: ...

    @abstractmethod
    async def protocol_info(self) -> dict: ...

    @abstractmethod
    async def device_info(self) -> dict: ...

    @abstractmethod
    def history(self, max_records: int = 64, start_cursor: int = 0) -> AsyncIterator[HistoryBatch]: ...

    @abstractmethod
    async def ack(self, session_id: int, sequence: int, cursor: int) -> None: ...


class BleakTransport(BleTransport):
    def __init__(self, address: str, timeout: float = 12.0):
        self.address = address
        self.timeout = timeout
        self._client: Any = None
        self._queue: asyncio.Queue[Message] = asyncio.Queue(maxsize=8)
        self._reassembler = Reassembler(timeout_seconds=timeout, max_messages=4, max_buffered_bytes=64 * 1024)
        self._sequence = 1
        self._session = 0
        self._fragment_watchdog: asyncio.Task | None = None
        self._disconnected = asyncio.Event()

    @property
    def connected(self) -> bool:
        return bool(self._client is not None and self._client.is_connected)

    @staticmethod
    async def scan(seconds: float = 8.0) -> list[DiscoveredDevice]:
        from bleak import BleakScanner

        devices = await BleakScanner.discover(timeout=seconds, return_adv=True)
        found = []
        for address, (device, advertisement) in devices.items():
            name = device.name or advertisement.local_name or ""
            uuids = {item.lower() for item in (advertisement.service_uuids or [])}
            if name.startswith("VelaPet") or SERVICE_UUID.lower() in uuids:
                found.append(DiscoveredDevice(address, name or "VelaPet", advertisement.rssi))
        return found

    async def connect(self) -> None:
        from bleak import BleakClient

        logger.info("连接中 address=%s", self.address)
        self._disconnected.clear()
        self._client = BleakClient(self.address, timeout=self.timeout, disconnected_callback=self._on_disconnect)
        await self._client.connect()
        await self._client.start_notify(DATA_UUID, self._on_notification)
        await self._client.start_notify(STATUS_UUID, self._on_notification)
        self._fragment_watchdog = asyncio.create_task(self._watch_fragment_timeouts())
        logger.info("已连接 address=%s mtu=%s", self.address, getattr(self._client, "mtu_size", "unknown"))

    async def disconnect(self) -> None:
        if self._fragment_watchdog is not None:
            self._fragment_watchdog.cancel()
            try:
                await self._fragment_watchdog
            except asyncio.CancelledError:
                pass
            self._fragment_watchdog = None
        if self._client is not None:
            if self._client.is_connected:
                await self._client.disconnect()
            logger.info("设备断开 address=%s", self.address)
        self._client = None

    def _on_disconnect(self, _: Any) -> None:
        self._disconnected.set()

    def _on_notification(self, _: Any, data: bytearray) -> None:
        try:
            message = self._reassembler.add(decode_frame(bytes(data)))
            if message is not None:
                try:
                    self._queue.put_nowait(message)
                except asyncio.QueueFull:
                    logger.error("BLE message queue is full; requesting retransmission")
                    self._schedule_message_nack(message, 10)
        except CrcError as exc:
            logger.warning("BLE 帧 CRC 失败: %s", exc)
            self._schedule_nack(bytes(data), 3)
        except Exception as exc:  # callback must never escape into Bleak
            logger.warning("丢弃无效 BLE 帧: %s", exc)
            self._schedule_nack(bytes(data), 2)

    def _schedule_message_nack(self, message: Message, error_code: int) -> None:
        asyncio.create_task(self._write(
            MessageType.NACK,
            NACK.pack(message.sequence, 0, error_code),
            cursor=message.cursor,
            session_id=message.session_id,
        ))

    def _schedule_nack(self, data: bytes, error_code: int) -> None:
        if len(data) < HEADER.size:
            return
        try:
            _, _, _, session, sequence, fragment, _, _, cursor = HEADER.unpack_from(data)
            asyncio.create_task(self._write(
                MessageType.NACK,
                NACK.pack(sequence, fragment, error_code),
                cursor=cursor,
                session_id=session,
            ))
        except Exception:
            logger.debug("无法发送 NACK", exc_info=True)

    async def _watch_fragment_timeouts(self) -> None:
        interval = max(0.05, min(1.0, self.timeout / 4))
        while self.connected:
            await asyncio.sleep(interval)
            # Keep received fragments while requesting only the missing ones.
            for expired in self._reassembler.expire_details(discard=False):
                for fragment in expired.missing_fragments:
                    logger.warning(
                        "BLE 分片超时 session=%d sequence=%d missing=%d",
                        expired.session_id,
                        expired.sequence,
                        fragment,
                    )
                    await self._write(
                        MessageType.NACK,
                        NACK.pack(expired.sequence, fragment, 4),
                        cursor=expired.cursor,
                        session_id=expired.session_id,
                    )

    async def _next_message(self) -> Message:
        for attempt in range(3):
            queue_task = asyncio.create_task(self._queue.get())
            disconnect_task = asyncio.create_task(self._disconnected.wait())
            done, pending = await asyncio.wait(
                {queue_task, disconnect_task},
                timeout=self.timeout,
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in pending:
                task.cancel()
            if pending:
                await asyncio.gather(*pending, return_exceptions=True)
            if disconnect_task in done and disconnect_task.result():
                if queue_task in done:
                    queue_task.result()
                raise ConnectionError("BLE device disconnected")
            if queue_task in done:
                return queue_task.result()
            if attempt < 2:
                logger.warning("等待 BLE 数据超时，等待设备重传 (%d/3)", attempt + 2)
        raise TimeoutError("BLE batch timed out after retransmission requests")

    async def _write(
        self,
        message_type: MessageType,
        payload: bytes = b"",
        cursor: int = 0,
        sequence: int | None = None,
        session_id: int | None = None,
    ) -> tuple[int, int]:
        if self._client is None or not self._client.is_connected:
            raise ConnectionError("BLE device is not connected")
        if sequence is None:
            sequence = self._sequence
            self._sequence = 1 if self._sequence == 0xFFFF else self._sequence + 1
        frame_session = self._session if session_id is None else session_id
        max_size = max(20, int(getattr(self._client, "mtu_size", 23)) - 3)
        for frame in fragment_message(message_type, frame_session, sequence, cursor, payload, max_size):
            await self._client.write_gatt_char(CONTROL_UUID, frame, response=True)
        return frame_session, sequence

    async def _request(self, request_type: MessageType, response_type: MessageType, payload: bytes = b"") -> Message:
        _, sequence = await self._write(request_type, payload)
        while True:
            message = await self._next_message()
            if message.message_type == MessageType.ERROR:
                error = decode_json(message.payload)
                raise RuntimeError(error.get("message", "device returned an error"))
            if message.sequence == sequence and message.message_type == response_type:
                self._session = message.session_id
                return message

    async def protocol_info(self) -> dict:
        return decode_json((await self._request(MessageType.GET_PROTOCOL, MessageType.PROTOCOL_INFO)).payload)

    async def device_info(self) -> dict:
        return decode_json((await self._request(MessageType.GET_DEVICE_INFO, MessageType.DEVICE_INFO)).payload)

    async def history(self, max_records: int = 64, start_cursor: int = 0) -> AsyncIterator[HistoryBatch]:
        if not 1 <= max_records <= 256:
            raise ValueError("max_records must be between 1 and 256")
        _, sequence = await self._write(
            MessageType.SYNC_START,
            SYNC_REQUEST.pack(start_cursor, max_records, 0),
            cursor=start_cursor,
        )
        while True:
            message = await self._next_message()
            if message.sequence != sequence:
                continue
            if message.message_type == MessageType.ERROR:
                raise RuntimeError(decode_json(message.payload).get("message", "sync failed"))
            if message.message_type == MessageType.HISTORY_RECORDS:
                records = decode_motion_records(message.payload)
                if not records or len(records) > max_records:
                    raise RuntimeError("device returned an invalid history batch size")
                yield HistoryBatch(
                    upload_id=f"ble-{message.session_id:04x}-{sequence:04x}-{message.cursor:08x}",
                    cursor=message.cursor,
                    next_cursor=message.cursor + len(records),
                    records=records,
                    final=True,
                    session_id=message.session_id,
                    sequence=message.sequence,
                )
            elif message.message_type == MessageType.SYNC_COMPLETE:
                return

    async def ack(self, session_id: int, sequence: int, cursor: int) -> None:
        await self._write(
            MessageType.ACK,
            SYNC_ACK.pack(cursor, 0),
            cursor=cursor,
            sequence=sequence,
            session_id=session_id,
        )


class FakeBleTransport(BleTransport):
    """Deterministic test double; never presented as real hardware evidence."""

    def __init__(self, device_info: dict, batches: list[HistoryBatch], disconnect_once: bool = False):
        self.info = device_info
        self.batches = batches
        self.disconnect_once = disconnect_once
        self.connected = False
        self.connect_count = 0
        self.acked: list[int] = []

    async def connect(self) -> None:
        self.connect_count += 1
        self.connected = True

    async def disconnect(self) -> None:
        self.connected = False

    async def protocol_info(self) -> dict:
        return {"version": 1, "minimumBridgeVersion": 1, "maxFrameSize": 182}

    async def device_info(self) -> dict:
        return dict(self.info)

    async def history(self, max_records: int = 64, start_cursor: int = 0) -> AsyncIterator[HistoryBatch]:
        if self.disconnect_once:
            self.disconnect_once = False
            self.connected = False
            raise ConnectionError("fake disconnect")
        for batch in self.batches:
            if batch.next_cursor <= start_cursor:
                continue
            if len(batch.records) > max_records:
                raise RuntimeError("fake batch exceeds max_records")
            self._waiting_ack_cursor = batch.next_cursor
            yield batch
            if getattr(self, "_waiting_ack_cursor", None) is not None:
                raise RuntimeError("device emitted the next batch before ACK")

    async def ack(self, session_id: int, sequence: int, cursor: int) -> None:
        if not self.connected:
            raise ConnectionError("fake transport disconnected before ACK")
        expected = getattr(self, "_waiting_ack_cursor", None)
        if expected is not None and cursor != expected:
            raise RuntimeError(f"unexpected ACK cursor {cursor}; expected {expected}")
        self.acked.append(cursor)
        self.info["syncCursor"] = cursor
        self._waiting_ack_cursor = None
