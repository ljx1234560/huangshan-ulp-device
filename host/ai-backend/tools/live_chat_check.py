"""Make one bounded provider request without printing credentials."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
import sys

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from velapet_backend.config import Settings
from velapet_backend.main import build_reply
from velapet_backend.models import ChatRequest
from velapet_backend.provider import ChatProviderClient


async def run() -> None:
    settings = Settings.from_env()
    settings.validate_bind()
    client = ChatProviderClient(settings)
    request = ChatRequest(
        device_id="host-live-check",
        prompt_type="greeting",
        locale="zh-CN",
        max_chars=50,
        context={"pet_name": "NOVA"},
    )
    response = await build_reply(client, request)
    result = "PASS" if response.source == client.provider else "FALLBACK"
    print(
        "AI_LIVE_CHECK "
        + json.dumps(
            {
                "result": result,
                "provider": client.provider,
                "model": client.model,
                "source": response.source,
                "error_code": response.error_code,
                "reply": response.reply,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
    )


if __name__ == "__main__":
    asyncio.run(run())
