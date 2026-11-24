import asyncio

import pytest

from velapet_bridge.protocol import (
    MessageType,
    MotionRecord,
    RecordSource,
    decode_frame,
    encode_motion_records,
    fragment_message,
)
from velapet_bridge.transport import BleakTransport


class FakeBleakClient:
    def __init__(self, mtu_size=185):
        self.mtu_size = mtu_size
        self.is_connected = True
        self.writes = []

    async def write_gatt_char(self, characteristic, data, response=True):
        self.writes.append((characteristic, bytes(data), response))


def record(record_id, day=20261119):
    return MotionRecord(record_id, 1_795_000_000, day, 480, 100, 1, 10000, RecordSource.TEST_INJECTED)


async def wait_for_write(client, message_type):
    for _ in range(100):
        for _, raw, _ in client.writes:
            frame = decode_frame(raw)
            if frame.message_type == message_type:
                return frame
        await asyncio.sleep(0)
    raise AssertionError(f"no {message_type.name} write observed")


def test_real_transport_streams_each_batch_before_receiving_the_next():
    async def scenario():
        transport = BleakTransport("FAKE", timeout=0.2)
        client = FakeBleakClient()
        transport._client = client
        stream = transport.history(max_records=2, start_cursor=100)

        first_task = asyncio.create_task(anext(stream))
        request = await wait_for_write(client, MessageType.SYNC_START)
        first_payload = encode_motion_records([record(100)])
        first_frames = fragment_message(
            MessageType.HISTORY_RECORDS, 7, request.sequence, 100, first_payload, 32
        )
        for raw in reversed(first_frames):
            transport._on_notification(None, bytearray(raw))
        first = await first_task
        assert first.cursor == 100 and first.next_cursor == 101

        # The async generator is suspended at yield. The bridge persists and
        # ACKs this batch before asking for the next one.
        await transport.ack(first.session_id, first.sequence, first.next_cursor)
        second_task = asyncio.create_task(anext(stream))
        second_payload = encode_motion_records([record(101)])
        for raw in fragment_message(
            MessageType.HISTORY_RECORDS, 7, request.sequence, 101, second_payload, 32
        ):
            transport._on_notification(None, bytearray(raw))
        second = await second_task
        assert second.cursor == 101 and second.next_cursor == 102
        await transport.ack(second.session_id, second.sequence, second.next_cursor)

        complete_task = asyncio.create_task(anext(stream))
        complete = fragment_message(MessageType.SYNC_COMPLETE, 7, request.sequence, 102, b"", 32)[0]
        transport._on_notification(None, bytearray(complete))
        with pytest.raises(StopAsyncIteration):
            await complete_task

        written_types = [decode_frame(raw).message_type for _, raw, _ in client.writes]
        assert written_types.count(MessageType.ACK) == 2

    asyncio.run(scenario())


def test_real_transport_watchdog_nacks_each_missing_fragment():
    async def scenario():
        transport = BleakTransport("FAKE", timeout=0.02)
        client = FakeBleakClient()
        transport._client = client
        frames = fragment_message(MessageType.HISTORY_RECORDS, 3, 4, 80, b"abcdefgh", 21)
        transport._on_notification(None, bytearray(frames[0]))
        watchdog = asyncio.create_task(transport._watch_fragment_timeouts())
        await asyncio.sleep(0.09)
        watchdog.cancel()
        with pytest.raises(asyncio.CancelledError):
            await watchdog
        nack_frames = [
            decode_frame(raw)
            for _, raw, _ in client.writes
            if decode_frame(raw).message_type == MessageType.NACK
        ]
        # ATT frame size 21 gives 3 bytes of payload, so this message has three
        # fragments and fragment 1/2 are both reported explicitly.
        assert len(nack_frames) == 2
        assert {frame.payload[2] for frame in nack_frames} == {1, 2}

    asyncio.run(scenario())
