"""AI chat extension over the shared v1 framing and NACK transport."""
from __future__ import annotations

import asyncio
import hashlib
from collections import OrderedDict

from .protocol import MessageType, NACK, ProtocolError, decode_json, encode_json, fragment_message


class ChatBridgeRunner:
    def __init__(self, transport, relay, expected_serial: str):
        self.transport = transport
        self.relay = relay
        self.expected_serial = expected_serial
        self._results = OrderedDict()

    async def serve(self) -> None:
        self._results.clear()
        await self.transport.connect()
        try:
            protocol = await self.transport.protocol_info()
            if protocol.get("version") != 1 or "ai_chat_v1" not in protocol.get("capabilities", []):
                raise ProtocolError("device must advertise ai_chat_v1 capability")
            info = await self.transport.device_info()
            if info.get("serialNumber") != self.expected_serial:
                raise ProtocolError("BLE device does not match the configured serial")
            async for message in self.transport.chat_messages():
                await self.handle(message)
        finally:
            self._results.clear()
            await self.transport.disconnect()

    async def handle(self, message) -> None:
        if message.message_type == MessageType.NACK:
            if len(message.payload) != NACK.size:
                raise ProtocolError("invalid NACK")
            sequence, index, _ = NACK.unpack(message.payload)
            cached = self._results.get((message.session_id, sequence))
            if cached and index < len(cached[1]):
                if cached[2].get(index, 0) >= 3:
                    raise TimeoutError("chat retransmission limit exceeded")
                await self.transport.send_chat_frames([cached[1][index]])
                cached[2][index] = cached[2].get(index, 0) + 1
            return
        if message.message_type != MessageType.CHAT_REQUEST:
            return
        if len(message.payload) > 4096:
            raise ProtocolError("chat request exceeds 4096 bytes")
        key = (message.session_id, message.sequence)
        digest = hashlib.sha256(message.payload).digest()
        cached = self._results.get(key)
        if cached:
            if cached[0] != digest:
                raise ProtocolError("chat request changed within a sequence")
            await self.transport.send_chat_frames(cached[1])
            return

        request = decode_json(message.payload)
        ui_id = request.get("request_id")
        if type(ui_id) is not int or not 0 < ui_id <= 0xFFFFFFFF:
            raise ProtocolError("invalid UI request id")
        body = request.get("body")
        if not isinstance(body, dict):
            raise ProtocolError("chat body must be an object")
        # Binding is checked before HTTP; the packet cannot impersonate another device.
        body = {**body, "device_id": self.expected_serial}
        result = await asyncio.to_thread(self.relay.exchange, ui_id, body)
        payload = encode_json(result)
        # Default MTU allows only 510 payload bytes per message. Keep a complete
        # UTF-8 reply, shortening it by Unicode characters if necessary.
        capacity = (self.transport.max_frame_size - 18) * 255
        if len(payload) > capacity:
            result = {**result, "conversation_id": "", "persona_id": ""}
            payload = encode_json(result)
        while len(payload) > capacity and result.get("reply"):
            result["reply"] = result["reply"][:-1]
            payload = encode_json(result)
        if len(payload) > capacity:
            raise ProtocolError("chat envelope exceeds negotiated ATT capacity")
        # Frame fragmentation works on bytes; reassembly precedes UTF-8 decoding.
        frames = fragment_message(MessageType.CHAT_RESULT, message.session_id,
                                  message.sequence, 0, payload, self.transport.max_frame_size)
        self._results[key] = (digest, frames, {})
        while len(self._results) > 4:
            self._results.popitem(last=False)
        await self.transport.send_chat_frames(frames)
