import asyncio

import httpx
import pytest

from velapet_bridge.api import ApiClient, UploadResult
from velapet_bridge.bridge import BridgeRunner
from velapet_bridge.protocol import MotionRecord, RECORD_FLAG_TIME_TRUSTED, RecordSource
from velapet_bridge.transport import FakeBleTransport, HistoryBatch


def motion(record_id: int = 1, day: int = 20261118):
    return MotionRecord(record_id, 1_795_000_000, day, 480, 500, 5, 10000, RecordSource.TEST_INJECTED)


class FakeApi:
    def __init__(self, fail_uploads: int = 0):
        self.fail_uploads = fail_uploads
        self.upload_calls = 0
        self.statuses = []
        self.seen: set[str] = set()
        self.uploads = []

    async def update_status(self, serial, state, connected, message="", running=True):
        self.statuses.append((serial, state, connected, running, message))

    async def upload(self, serial, upload_id, device_cursor, upload_offset, records, firmware, protocol, client_id):
        self.upload_calls += 1
        if self.upload_calls <= self.fail_uploads:
            raise httpx.ConnectError("temporary")
        self.uploads.append((upload_id, device_cursor, upload_offset))
        accepted = 0
        duplicates = 0
        for item in records:
            key = f"{serial}:{item.record_id}"
            if key in self.seen:
                duplicates += 1
            else:
                self.seen.add(key)
                accepted += 1
        end_cursor = device_cursor + len(records)
        return UploadResult(accepted, duplicates, upload_offset + len(records), end_cursor, end_cursor, True)


def batch(records=None, cursor=0, final=True):
    values = records or [motion()]
    return HistoryBatch(f"ble-session-{cursor}", cursor, cursor + len(values), values, final, 7, 9)


def test_hardware_record_requires_trusted_rtc_before_http_upload():
    untrusted = MotionRecord(1, 1_795_000_000, 20261119, 480, 100, 1, 10000, RecordSource.HARDWARE, 0)
    with pytest.raises(ValueError, match="RTC is not trusted"):
        ApiClient._record_payload("VP-1", untrusted)

    trusted = MotionRecord(
        1, 1_795_000_000, 20261119, 480, 100, 1, 10000,
        RecordSource.HARDWARE, RECORD_FLAG_TIME_TRUSTED,
    )
    assert ApiClient._record_payload("VP-1", trusted)["rtcTrusted"] is True


def test_upload_failure_is_retried_before_ack():
    transport = FakeBleTransport({"serialNumber": "VP-1", "firmwareVersion": "0.4.0", "syncCursor": 0}, [batch()])
    api = FakeApi(fail_uploads=2)
    result = asyncio.run(BridgeRunner(transport, api).sync_once())
    assert api.upload_calls == 3
    assert transport.acked == [1]
    assert result.accepted == 1


def test_permanent_upload_failure_does_not_ack_device():
    transport = FakeBleTransport({"serialNumber": "VP-1", "syncCursor": 0}, [batch()])
    api = FakeApi(fail_uploads=5)
    with pytest.raises(httpx.ConnectError):
        asyncio.run(BridgeRunner(transport, api).sync_once())
    assert transport.acked == []
    assert any(state[1] == "failed" for state in api.statuses)


def test_disconnect_reconnect_resumes_and_acks_once():
    transport = FakeBleTransport({"serialNumber": "VP-1", "syncCursor": 0}, [batch()], disconnect_once=True)
    api = FakeApi()
    result = asyncio.run(BridgeRunner(transport, api).sync_with_reconnect(attempts=2))
    assert transport.connect_count == 2
    assert transport.acked == [1]
    assert result.accepted == 1


def test_ack_loss_causes_safe_duplicate_upload():
    api = FakeApi()
    first = FakeBleTransport({"serialNumber": "VP-1", "syncCursor": 0}, [batch()])

    async def lost_ack(*_):
        raise ConnectionError("ACK lost")

    first.ack = lost_ack
    with pytest.raises(ConnectionError):
        asyncio.run(BridgeRunner(first, api).sync_once())
    second = FakeBleTransport({"serialNumber": "VP-1", "syncCursor": 0}, [batch()])
    result = asyncio.run(BridgeRunner(second, api).sync_once())
    assert result.accepted == 0
    assert result.duplicates == 1
    assert second.acked == [1]


def test_cross_day_records_keep_independent_dates():
    values = [motion(1, 20261117), motion(2, 20261118)]
    transport = FakeBleTransport({"serialNumber": "VP-1", "syncCursor": 0}, [batch(values)])
    api = FakeApi()
    result = asyncio.run(BridgeRunner(transport, api).sync_once())
    assert result.accepted == 2
    assert result.acknowledged_cursor == 2


def test_non_zero_device_cursor_and_second_sync_use_zero_http_offsets():
    transport = FakeBleTransport(
        {"serialNumber": "VP-1", "syncCursor": 100},
        [batch([motion(100)], 100)],
    )
    api = FakeApi()
    first = asyncio.run(BridgeRunner(transport, api).sync_once())
    assert first.acknowledged_cursor == 101
    transport.batches.append(batch([motion(101)], 101))
    second = asyncio.run(BridgeRunner(transport, api).sync_once())
    assert second.acknowledged_cursor == 102
    assert api.uploads == [
        ("ble-session-100", 100, 0),
        ("ble-session-101", 101, 0),
    ]


def test_multiple_batches_are_uploaded_and_acked_in_order():
    events = []

    class OrderedApi(FakeApi):
        async def upload(self, *args, **kwargs):
            result = await super().upload(*args, **kwargs)
            events.append(f"upload:{result.ack_cursor}")
            return result

    class OrderedTransport(FakeBleTransport):
        async def ack(self, session_id, sequence, cursor):
            events.append(f"ack:{cursor}")
            await super().ack(session_id, sequence, cursor)

    transport = OrderedTransport(
        {"serialNumber": "VP-1", "syncCursor": 20},
        [batch([motion(20)], 20), batch([motion(21)], 21)],
    )
    result = asyncio.run(BridgeRunner(transport, OrderedApi()).sync_once())
    assert result.acknowledged_cursor == 22
    assert events == ["upload:21", "ack:21", "upload:22", "ack:22"]


def test_final_status_separates_last_success_from_current_connection():
    api = FakeApi()
    transport = FakeBleTransport({"serialNumber": "VP-1", "syncCursor": 0}, [batch()])
    asyncio.run(BridgeRunner(transport, api).sync_once())
    assert any(item[1] == "success" and item[2] is True for item in api.statuses)
    assert api.statuses[-1][1:4] == ("disconnected", False, False)
