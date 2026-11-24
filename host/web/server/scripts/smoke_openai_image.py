"""Explicit, billable OpenAI image smoke test. Never runs from pytest."""

import os
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import Settings  # noqa: E402
from app.services.image_provider import get_image_provider, safety_identifier  # noqa: E402
from app.services.image_storage import get_image_storage  # noqa: E402


def main() -> int:
    if os.getenv("VELAPET_RUN_ONLINE_IMAGE_SMOKE") != "1":
        print("已跳过：仅在显式设置 VELAPET_RUN_ONLINE_IMAGE_SMOKE=1 时调用真实付费图片接口。")
        return 2
    settings = Settings(_env_file=Path(__file__).resolve().parents[1] / ".env")
    provider = get_image_provider(settings)
    provider.validate_configuration()
    result = provider.generate({
        "species": "fox", "color": "lavender", "style": "celestial",
        "personality": "curious", "name": "露米", "description": "尾巴带有原创星光纹理",
    }, safety_identifier("online-smoke-user"))
    asset_id = str(uuid.uuid4())
    stored = get_image_storage(settings).save(asset_id, result.image_bytes, settings.image_ai_output_format)
    print(
        f"成功：provider={provider.name} model={result.model} format={stored.mime_type} "
        f"size={stored.width}x{stored.height} bytes={stored.byte_size} total_tokens={result.total_tokens}"
    )
    print(f"本地文件：{get_image_storage(settings).path_for(stored.storage_key)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
