"""Explicit, billable Doubao Seedream image smoke test. Never runs from pytest."""

import os
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import Settings  # noqa: E402
from app.services.image_provider import get_image_provider, safety_identifier  # noqa: E402
from app.services.image_storage import get_image_storage  # noqa: E402


def main() -> int:
    if os.getenv("VELAPET_RUN_ONLINE_DOUBAO_IMAGE_SMOKE") != "1":
        print("已跳过：仅在显式设置 VELAPET_RUN_ONLINE_DOUBAO_IMAGE_SMOKE=1 时调用真实付费豆包接口。")
        return 2
    settings = Settings(_env_file=Path(__file__).resolve().parents[1] / ".env")
    provider = get_image_provider(settings)
    if provider.name != "doubao":
        print("配置错误：在线测试要求 VELAPET_IMAGE_AI_PROVIDER=doubao。")
        return 2
    provider.validate_configuration()
    started = time.perf_counter()
    result = provider.generate({
        "species": "fox", "color": "lavender", "style": "celestial",
        "personality": "curious", "name": "露米", "description": "尾巴带有原创星光纹理",
    }, safety_identifier("doubao-online-smoke-user"))
    storage = get_image_storage(settings)
    stored = storage.save(str(uuid.uuid4()), result.image_bytes, settings.image_ai_output_format)
    elapsed_ms = round((time.perf_counter() - started) * 1000)
    print(
        f"成功：provider={provider.name} model={result.model} format={stored.mime_type} "
        f"size={stored.width}x{stored.height} bytes={stored.byte_size} duration_ms={elapsed_ms}"
    )
    print(f"已保存：{storage.path_for(stored.storage_key)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
