import asyncio
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "ai-backend"))
from velapet_backend.chat_relay import ChatRelayClient
from velapet_bridge.chat import ChatBridgeRunner
from velapet_bridge.protocol import (
    Message, MessageType, NACK, ProtocolError, Reassembler, decode_frame, decode_json, encode_json,
    fragment_message,
)


class FakeTransport:
    max_frame_size = 20

    def __init__(self):
        self.sent = []

    async def send_chat_frames(self, frames):
        self.sent.extend(frames)


def request(sequence=3, ui_id=42):
    payload = encode_json({"request_id": ui_id, "body": {
        "device_id": "untrusted", "context": {"level": 8}, "prompt_type": "task"}})
    assembly = Reassembler()
    message = None
    for frame in reversed(fragment_message(MessageType.CHAT_REQUEST, 7, sequence, 0, payload, 20)):
        message = assembly.add(decode_frame(frame)) or message
    return message


@pytest.mark.parametrize("source", ["deepseek", "local_fallback"])
def test_fragmented_chat_roundtrip_and_nack(source):
    calls = []
    def handler(req):
        import json
        body = json.loads(req.content)
        assert body["device_id"] == "VP-1"
        assert body["context"]["level"] == 8
        calls.append(req.url.path)
        return httpx.Response(200, json={
            "request_id": "server-id", "source": source, "reply": "你好" * 40,
            "intent": "reminder", "emotion": "gentle",
            "conversation_id": "c" * 40, "persona_id": "nova",
        })

    async def scenario():
        transport = FakeTransport()
        relay = ChatRelayClient("http://127.0.0.1:8000", transport=httpx.MockTransport(handler))
        runner = ChatBridgeRunner(transport, relay, "VP-1")
        message = request()
        await runner.handle(message)
        assembly = Reassembler()
        reply = None
        frames = list(transport.sent)
        for raw in frames:
            reply = assembly.add(decode_frame(raw)) or reply
        result = decode_json(reply.payload)
        assert result["request_id"] == 42 and result["reply"]
        assert result["source"] == ("cloud" if source == "deepseek" else source)
        assert reply.message_type == MessageType.CHAT_RESULT
        assert reply.session_id == 7 and reply.sequence == 3
        assert all(len(frame) <= 20 for frame in frames)
        await runner.handle(message)
        assert transport.sent[len(frames):] == frames
        nack = Message(MessageType.NACK, 7, 99, 0, NACK.pack(3, 1, 4))
        await runner.handle(nack)
        assert transport.sent[-1] == frames[1]
        changed = request(ui_id=43)
        with pytest.raises(ProtocolError):
            await runner.handle(changed)
        assert calls == ["/api/v1/chat"]
    asyncio.run(scenario())


def test_timeout_result_uses_ui_id():
    def timeout(req):
        raise httpx.ReadTimeout("fixture", request=req)
    async def scenario():
        transport = FakeTransport()
        runner = ChatBridgeRunner(transport, ChatRelayClient(
            "http://127.0.0.1:8000", transport=httpx.MockTransport(timeout)), "VP-1")
        await runner.handle(request())
        assembly = Reassembler()
        result = None
        for raw in transport.sent:
            result = assembly.add(decode_frame(raw)) or result
        assert decode_json(result.payload) == {"request_id": 42, "source": "error", "error_code": -1}
    asyncio.run(scenario())
