import pytest

from velapet_bridge.protocol import (
    CrcError,
    Frame,
    MessageType,
    MotionRecord,
    ProtocolError,
    Reassembler,
    RecordSource,
    decode_frame,
    decode_motion_records,
    encode_frame,
    encode_motion_records,
    fragment_message,
)


def record(record_id: int = 1, source: RecordSource = RecordSource.HARDWARE):
    return MotionRecord(record_id, 1_795_000_000, 20261118, 480, 1234, 12, 10000, source)


def test_frame_round_trip():
    value = Frame(MessageType.HISTORY_RECORDS, 7, 9, 0, 1, 22, b"hello")
    assert decode_frame(encode_frame(value)) == value


def test_crc_failure_is_rejected():
    data = bytearray(encode_frame(Frame(MessageType.PING, 1, 1, 0, 1, 0, b"x")))
    data[-3] ^= 0x40
    with pytest.raises(CrcError):
        decode_frame(bytes(data))


def test_fragmentation_reassembles_out_of_order():
    payload = bytes(range(100))
    frames = fragment_message(MessageType.HISTORY_RECORDS, 5, 8, 30, payload, 32)
    reassembler = Reassembler()
    message = None
    for raw in reversed(frames):
        message = reassembler.add(decode_frame(raw)) or message
    assert message is not None
    assert message.payload == payload
    assert message.cursor == 30


def test_identical_duplicate_fragment_is_idempotent():
    frames = fragment_message(MessageType.DEVICE_INFO, 1, 2, 0, b"abcdef", 21)
    reassembler = Reassembler()
    first = decode_frame(frames[0])
    assert reassembler.add(first) is None
    assert reassembler.add(first) is None
    message = None
    for raw in frames[1:]:
        message = reassembler.add(decode_frame(raw)) or message
    assert message and message.payload == b"abcdef"


def test_changed_duplicate_fragment_is_rejected():
    reassembler = Reassembler()
    first = Frame(MessageType.DEVICE_INFO, 1, 2, 0, 2, 0, b"a")
    changed = Frame(MessageType.DEVICE_INFO, 1, 2, 0, 2, 0, b"b")
    assert reassembler.add(first) is None
    with pytest.raises(ProtocolError):
        reassembler.add(changed)


def test_missing_fragment_expires():
    reassembler = Reassembler(timeout_seconds=2)
    frame = Frame(MessageType.HISTORY_RECORDS, 4, 5, 0, 2, 8, b"part")
    assert reassembler.add(frame, now=10) is None
    assert reassembler.expire(now=12.1) == [(4, 5, MessageType.HISTORY_RECORDS)]


def test_timeout_reports_exact_missing_fragment_numbers():
    reassembler = Reassembler(timeout_seconds=2)
    reassembler.add(Frame(MessageType.HISTORY_RECORDS, 4, 6, 0, 4, 50, b"a"), now=10)
    reassembler.add(Frame(MessageType.HISTORY_RECORDS, 4, 6, 2, 4, 50, b"c"), now=10.5)
    expired = reassembler.expire_details(now=12.1)
    assert len(expired) == 1
    assert expired[0].missing_fragments == (1, 3)
    assert expired[0].cursor == 50


def test_nack_timeout_keeps_received_fragments_for_retransmission():
    reassembler = Reassembler(timeout_seconds=2)
    first = Frame(MessageType.HISTORY_RECORDS, 4, 7, 0, 2, 9, b"left")
    second = Frame(MessageType.HISTORY_RECORDS, 4, 7, 1, 2, 9, b"right")
    assert reassembler.add(first, now=10) is None
    expired = reassembler.expire_details(now=12.1, discard=False)
    assert expired[0].missing_fragments == (1,)
    message = reassembler.add(second, now=12.2)
    assert message is not None
    assert message.payload == b"leftright"


def test_fragment_buffer_has_hard_memory_limit():
    reassembler = Reassembler(max_messages=1, max_buffered_bytes=3)
    assert reassembler.add(Frame(MessageType.HISTORY_RECORDS, 1, 1, 0, 2, 0, b"ab")) is None
    with pytest.raises(ProtocolError, match="buffer limit"):
        reassembler.add(Frame(MessageType.HISTORY_RECORDS, 1, 1, 1, 2, 0, b"cd"))


def test_motion_record_binary_contract_preserves_source():
    values = [record(1), record(2, RecordSource.TEST_INJECTED)]
    assert decode_motion_records(encode_motion_records(values)) == values
