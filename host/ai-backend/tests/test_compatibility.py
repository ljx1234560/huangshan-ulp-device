"""Regressions against the existing product protocol and provider failures."""
import asyncio
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from velapet_backend.config import Settings
from velapet_backend.main import build_reply, create_app
from velapet_backend.models import ChatRequest
from velapet_backend.provider import ChatProviderClient


def test_existing_single_turn_device_payload_remains_accepted(tmp_path):
    original = {
        "device_id": "watch-01", "prompt_type": "task", "locale": "zh-CN", "max_chars": 50,
        "context": {"pet_name": "NOVA", "level": 2, "exp": 40, "exp_to_next": 250,
                    "current_skin": "sport_blue", "total_steps": 12345,
                    "tasks": [{"type": 0, "target": 3000, "progress": 100, "status": 1}]},
    }
    with TestClient(create_app(Settings(data_root=tmp_path))) as client:
        first = client.post('/api/v1/chat', json=original)
        assert first.status_code == 200
        data = first.json()
        expected = {'request_id', 'reply', 'intent', 'emotion', 'source', 'reward', 'error_code', 'created_at'}
        assert expected <= data.keys()
        assert len(data['reply']) <= 50
        assert data['source'] == 'local_fallback'
        assert data['conversation_id']
        assert client.post('/api/v1/chat', json=original).json()['conversation_id'] != data['conversation_id']


@pytest.mark.parametrize('reply', ['', '   ', 12, None, {'text': 'nested'}])
def test_invalid_structured_provider_reply_degrades_instead_of_empty_success(reply):
    def handler(_):
        return httpx.Response(200, json={'choices': [{'message': {'content': json.dumps({'reply': reply})}}]})

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            provider = ChatProviderClient(Settings(chat_provider='deepseek', deepseek_api_key='test-only'), http)
            result = await build_reply(provider, ChatRequest(device_id='compat-test', context={}))
            assert result.source == 'local_fallback'
            assert result.error_code == 'DEEPSEEK_INVALID_RESPONSE'
            assert result.reply
    asyncio.run(run())
