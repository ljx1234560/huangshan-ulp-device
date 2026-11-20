from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import httpx

from .protocol import MotionRecord, RECORD_FLAG_TIME_TRUSTED, RecordSource


@dataclass(frozen=True)
class UploadResult:
    accepted: int
    duplicates: int
    next_upload_offset: int
    ack_cursor: int
    persisted_device_cursor: int
    complete: bool


class ApiClient:
    def __init__(self, base_url: str, bridge_token: str, timeout: float = 15.0, transport=None):
        self.base_url = base_url.rstrip("/")
        self.bridge_token = bridge_token
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=timeout,
            transport=transport,
            headers={"Authorization": f"Bearer {bridge_token}"},
        )

    @classmethod
    async def authorize(
        cls,
        base_url: str,
        email: str,
        password: str,
        serial_number: str,
        client_id: str,
        transport=None,
    ) -> "ApiClient":
        async with httpx.AsyncClient(base_url=base_url.rstrip("/"), timeout=15.0, transport=transport) as client:
            login = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
            login.raise_for_status()
            csrf = client.cookies.get("velapet_csrf")
            response = await client.post(
                f"/api/v1/devices/serial/{serial_number}/bridge-sessions",
                json={"clientId": client_id},
                headers={"X-CSRF-Token": csrf or ""},
            )
            response.raise_for_status()
            token = response.json()["token"]
        return cls(base_url, token, transport=transport)

    async def close(self) -> None:
        await self.client.aclose()

    async def update_status(
        self,
        serial_number: str,
        state: str,
        connected: bool,
        message: str = "",
        running: bool = True,
    ) -> None:
        response = await self.client.post(
            f"/api/v1/device-uploads/{serial_number}/bridge-status",
            json={"state": state, "connected": connected, "running": running, "message": message},
        )
        response.raise_for_status()

    async def upload(
        self,
        serial_number: str,
        upload_id: str,
        device_cursor: int,
        upload_offset: int,
        records: list[MotionRecord],
        firmware_version: str | None,
        protocol_version: int,
        bridge_client_id: str,
    ) -> UploadResult:
        response = await self.client.post(
            f"/api/v1/device-uploads/{serial_number}/activity-batches",
            json={
                "uploadId": upload_id,
                "uploadOffset": upload_offset,
                "deviceCursor": device_cursor,
                "final": True,
                "firmwareVersion": firmware_version,
                "protocolVersion": protocol_version,
                "bridgeClientId": bridge_client_id,
                "records": [self._record_payload(serial_number, item) for item in records],
            },
        )
        response.raise_for_status()
        data = response.json()
        return UploadResult(
            data["accepted"],
            data["duplicates"],
            data["nextUploadOffset"],
            data["ackCursor"],
            data["persistedDeviceCursor"],
            data["complete"],
        )

    @staticmethod
    def _record_payload(serial_number: str, record: MotionRecord) -> dict:
        date_text = str(record.local_date)
        if len(date_text) != 8:
            raise ValueError("device local date must be YYYYMMDD")
        occurred = datetime.fromtimestamp(record.occurred_at_epoch_s, timezone.utc)
        rtc_trusted = bool(record.flags & RECORD_FLAG_TIME_TRUSTED)
        if record.source == RecordSource.HARDWARE and not rtc_trusted:
            raise ValueError("hardware record RTC is not trusted; refusing to upload it as real activity")
        return {
            "recordId": f"{serial_number}-{record.record_id:016x}",
            "occurredAt": occurred.isoformat(),
            "localDate": f"{date_text[:4]}-{date_text[4:6]}-{date_text[6:]}",
            "timezoneOffsetMinutes": record.timezone_offset_minutes,
            "steps": record.steps,
            "activeMinutes": record.active_minutes,
            "goal": record.goal,
            "source": "hardware" if record.source == RecordSource.HARDWARE else "test_injected",
            "rtcTrusted": rtc_trusted,
        }
