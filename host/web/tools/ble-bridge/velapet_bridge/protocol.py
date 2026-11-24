from __future__ import annotations

import json
import struct
import time
from dataclasses import dataclass
from enum import IntEnum
from typing import Iterable

PROTOCOL_VERSION = 1
RECORD_FLAG_TIME_TRUSTED = 0x01
MAGIC = 0x5056  # bytes 56 50, ASCII "VP"

SERVICE_UUID = "7a820001-64d7-4c8d-a4c8-7a2f6f656c61"
CONTROL_UUID = "7a820002-64d7-4c8d-a4c8-7a2f6f656c61"
DATA_UUID = "7a820003-64d7-4c8d-a4c8-7a2f6f656c61"
INFO_UUID = "7a820004-64d7-4c8d-a4c8-7a2f6f656c61"
STATUS_UUID = "7a820005-64d7-4c8d-a4c8-7a2f6f656c61"

# magic, version, type, session, sequence, fragment index/count,
# fragment payload size, durable device cursor.
HEADER = struct.Struct("<HBBHHBBHI")
CRC = struct.Struct("<H")
MOTION_RECORD = struct.Struct("<QIIhIHHBB")
SYNC_REQUEST = struct.Struct("<IHB")
SYNC_ACK = struct.Struct("<IB")
NACK = struct.Struct("<HBB")


class ProtocolError(ValueError):
    pass


class CrcError(ProtocolError):
    pass


class MessageType(IntEnum):
    GET_PROTOCOL = 0x01
    GET_DEVICE_INFO = 0x02
    GET_MOTION_STATUS = 0x03
    SYNC_START = 0x10
    ACK = 0x11
    NACK = 0x12
    CHAT_RESULT = 0x30
    GET_PET_SNAPSHOT = 0x20
    PING = 0x7E
    CANCEL = 0x7F

    PROTOCOL_INFO = 0x81
    DEVICE_INFO = 0x82
    MOTION_STATUS = 0x83
    HISTORY_RECORDS = 0x90
    SYNC_COMPLETE = 0x91
    CHAT_REQUEST = 0xB0
    PET_SNAPSHOT = 0xA0
    ERROR = 0xE0


class RecordSource(IntEnum):
    HARDWARE = 1
    TEST_INJECTED = 2


@dataclass(frozen=True)
class Frame:
    message_type: MessageType
    session_id: int
    sequence: int
    fragment_index: int
    fragment_count: int
    cursor: int
    payload: bytes = b""
    version: int = PROTOCOL_VERSION


@dataclass(frozen=True)
class Message:
    message_type: MessageType
    session_id: int
    sequence: int
    cursor: int
    payload: bytes


@dataclass(frozen=True)
class MotionRecord:
    record_id: int
    occurred_at_epoch_s: int
    local_date: int
    timezone_offset_minutes: int
    steps: int
    active_minutes: int
    goal: int
    source: RecordSource = RecordSource.HARDWARE
    flags: int = 0


@dataclass(frozen=True)
class FragmentTimeout:
    session_id: int
    sequence: int
    message_type: MessageType
    cursor: int
    missing_fragments: tuple[int, ...]


@dataclass
class _Assembly:
    created_at: float
    fragment_count: int
    cursor: int
    parts: dict[int, bytes]
    buffered_bytes: int = 0


def crc16_ccitt(data: bytes, initial: int = 0xFFFF) -> int:
    value = initial
    for octet in data:
        value ^= octet << 8
        for _ in range(8):
            value = ((value << 1) ^ 0x1021) & 0xFFFF if value & 0x8000 else (value << 1) & 0xFFFF
    return value


def encode_frame(frame: Frame) -> bytes:
    if not 0 <= frame.fragment_index < frame.fragment_count <= 255:
        raise ProtocolError("invalid fragment index/count")
    if len(frame.payload) > 0xFFFF:
        raise ProtocolError("fragment payload is too large")
    header = HEADER.pack(
        MAGIC,
        frame.version,
        int(frame.message_type),
        frame.session_id,
        frame.sequence,
        frame.fragment_index,
        frame.fragment_count,
        len(frame.payload),
        frame.cursor,
    )
    body = header + frame.payload
    return body + CRC.pack(crc16_ccitt(body))


def decode_frame(data: bytes) -> Frame:
    minimum = HEADER.size + CRC.size
    if len(data) < minimum:
        raise ProtocolError("frame is shorter than the fixed header")
    unpacked = HEADER.unpack_from(data)
    magic, version, raw_type, session, sequence, index, count, payload_size, cursor = unpacked
    if magic != MAGIC:
        raise ProtocolError("invalid frame magic")
    if version != PROTOCOL_VERSION:
        raise ProtocolError(f"unsupported protocol version {version}")
    if count == 0 or index >= count:
        raise ProtocolError("invalid fragment index/count")
    if len(data) != HEADER.size + payload_size + CRC.size:
        raise ProtocolError("payload length does not match frame size")
    expected = CRC.unpack_from(data, len(data) - CRC.size)[0]
    actual = crc16_ccitt(data[:-CRC.size])
    if actual != expected:
        raise CrcError(f"CRC mismatch: expected {expected:04x}, got {actual:04x}")
    try:
        message_type = MessageType(raw_type)
    except ValueError as exc:
        raise ProtocolError(f"unknown message type {raw_type:#x}") from exc
    return Frame(message_type, session, sequence, index, count, cursor, data[HEADER.size:-CRC.size], version)


def fragment_message(
    message_type: MessageType,
    session_id: int,
    sequence: int,
    cursor: int,
    payload: bytes,
    max_frame_size: int,
) -> list[bytes]:
    payload_capacity = max_frame_size - HEADER.size - CRC.size
    if payload_capacity <= 0:
        raise ProtocolError("ATT payload is too small for the protocol header")
    count = max(1, (len(payload) + payload_capacity - 1) // payload_capacity)
    if count > 255:
        raise ProtocolError("message requires more than 255 fragments")
    return [
        encode_frame(Frame(
            message_type=message_type,
            session_id=session_id,
            sequence=sequence,
            fragment_index=index,
            fragment_count=count,
            cursor=cursor,
            payload=payload[index * payload_capacity:(index + 1) * payload_capacity],
        ))
        for index in range(count)
    ]


class Reassembler:
    def __init__(
        self,
        timeout_seconds: float = 8.0,
        max_messages: int = 4,
        max_buffered_bytes: int = 64 * 1024,
    ):
        self.timeout_seconds = timeout_seconds
        self.max_messages = max_messages
        self.max_buffered_bytes = max_buffered_bytes
        self._messages: dict[tuple[int, int, MessageType], _Assembly] = {}

    @property
    def buffered_bytes(self) -> int:
        return sum(item.buffered_bytes for item in self._messages.values())

    def expire_details(self, now: float | None = None, discard: bool = True) -> list[FragmentTimeout]:
        current = time.monotonic() if now is None else now
        expired: list[FragmentTimeout] = []
        for key, state in list(self._messages.items()):
            if current - state.created_at < self.timeout_seconds:
                continue
            session, sequence, message_type = key
            missing = tuple(index for index in range(state.fragment_count) if index not in state.parts)
            expired.append(FragmentTimeout(session, sequence, message_type, state.cursor, missing))
            if discard:
                del self._messages[key]
            else:
                state.created_at = current
        return expired

    def expire(self, now: float | None = None) -> list[tuple[int, int, MessageType]]:
        return [(item.session_id, item.sequence, item.message_type) for item in self.expire_details(now)]

    def add(self, frame: Frame, now: float | None = None) -> Message | None:
        current = time.monotonic() if now is None else now
        key = (frame.session_id, frame.sequence, frame.message_type)
        state = self._messages.get(key)
        if state is None:
            if len(self._messages) >= self.max_messages:
                raise ProtocolError("too many fragmented messages are buffered")
            state = _Assembly(current, frame.fragment_count, frame.cursor, {})
            self._messages[key] = state
        if state.fragment_count != frame.fragment_count or state.cursor != frame.cursor:
            del self._messages[key]
            raise ProtocolError("fragment metadata changed inside one message")
        previous = state.parts.get(frame.fragment_index)
        if previous is not None and previous != frame.payload:
            del self._messages[key]
            raise ProtocolError("duplicate fragment contains different bytes")
        if previous is None:
            if self.buffered_bytes + len(frame.payload) > self.max_buffered_bytes:
                del self._messages[key]
                raise ProtocolError("fragment buffer limit exceeded")
            state.parts[frame.fragment_index] = frame.payload
            state.buffered_bytes += len(frame.payload)
        if len(state.parts) != state.fragment_count:
            return None
        payload = b"".join(state.parts[index] for index in range(state.fragment_count))
        del self._messages[key]
        return Message(frame.message_type, frame.session_id, frame.sequence, state.cursor, payload)


def encode_motion_records(records: Iterable[MotionRecord]) -> bytes:
    items = list(records)
    if len(items) > 0xFFFF:
        raise ProtocolError("too many records")
    payload = bytearray(struct.pack("<H", len(items)))
    for record in items:
        payload.extend(MOTION_RECORD.pack(
            record.record_id,
            record.occurred_at_epoch_s,
            record.local_date,
            record.timezone_offset_minutes,
            record.steps,
            record.active_minutes,
            record.goal,
            int(record.source),
            record.flags,
        ))
    return bytes(payload)


def decode_motion_records(payload: bytes) -> list[MotionRecord]:
    if len(payload) < 2:
        raise ProtocolError("motion batch has no count")
    count = struct.unpack_from("<H", payload)[0]
    expected = 2 + count * MOTION_RECORD.size
    if len(payload) != expected:
        raise ProtocolError("motion record payload size mismatch")
    result = []
    offset = 2
    for _ in range(count):
        values = MOTION_RECORD.unpack_from(payload, offset)
        offset += MOTION_RECORD.size
        try:
            source = RecordSource(values[7])
        except ValueError as exc:
            raise ProtocolError(f"unknown record source {values[7]}") from exc
        result.append(MotionRecord(*values[:7], source=source, flags=values[8]))
    return result


def encode_json(value: dict) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def decode_json(payload: bytes) -> dict:
    try:
        result = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProtocolError("invalid UTF-8 JSON payload") from exc
    if not isinstance(result, dict):
        raise ProtocolError("JSON payload must be an object")
    return result
