from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from ..config import Settings


class ImageStorageError(RuntimeError):
    pass


@dataclass(frozen=True)
class StoredImage:
    storage_key: str
    mime_type: str
    byte_size: int
    width: int
    height: int
    sha256: str


class StorageProvider:
    def save(self, asset_id: str, data: bytes, expected_format: str) -> StoredImage:
        raise NotImplementedError

    def path_for(self, storage_key: str) -> Path:
        raise NotImplementedError


class WearableImageConverter:
    """Extension point for a future display-specific asset pipeline.

    Stage 4B-2 intentionally does not transfer or encode images for BLE.
    """

    def convert(self, source: Path, target_profile: str) -> bytes:
        raise NotImplementedError


class LocalImageStorage(StorageProvider):
    format_map = {"PNG": ("png", "image/png"), "WEBP": ("webp", "image/webp"), "JPEG": ("jpg", "image/jpeg")}

    def __init__(self, settings: Settings):
        configured = Path(settings.image_storage_dir)
        if not configured.is_absolute():
            configured = Path(__file__).resolve().parents[2] / configured
        self.root = configured.resolve()
        self.max_bytes = settings.image_max_bytes

    def save(self, asset_id: str, data: bytes, expected_format: str) -> StoredImage:
        if not data or len(data) > self.max_bytes:
            raise ImageStorageError("图片为空或超过服务端大小限制")
        try:
            with Image.open(io.BytesIO(data)) as probe:
                probe.verify()
            with Image.open(io.BytesIO(data)) as image:
                actual_format = image.format
                width, height = image.size
        except (UnidentifiedImageError, OSError, ValueError) as exc:
            raise ImageStorageError("生成结果不是有效图片") from exc
        if actual_format not in self.format_map:
            raise ImageStorageError(f"不支持的真实图片格式：{actual_format or 'unknown'}")
        extension, mime_type = self.format_map[actual_format]
        normalized_expected = "jpg" if expected_format == "jpeg" else expected_format
        if extension != normalized_expected:
            raise ImageStorageError(f"图片真实格式 {extension} 与请求格式 {normalized_expected} 不一致")
        if width < 64 or height < 64 or width > 4096 or height > 4096:
            raise ImageStorageError("图片尺寸必须在 64×64 到 4096×4096 之间")
        self.root.mkdir(parents=True, exist_ok=True)
        storage_key = f"{asset_id}.{extension}"
        target = (self.root / storage_key).resolve()
        if target.parent != self.root:
            raise ImageStorageError("非法存储路径")
        temporary = self.root / f".{asset_id}.tmp"
        temporary.write_bytes(data)
        temporary.replace(target)
        return StoredImage(
            storage_key=storage_key, mime_type=mime_type, byte_size=len(data), width=width, height=height,
            sha256=hashlib.sha256(data).hexdigest(),
        )

    def path_for(self, storage_key: str) -> Path:
        if not storage_key or Path(storage_key).name != storage_key:
            raise ImageStorageError("非法图片存储键")
        target = (self.root / storage_key).resolve()
        if target.parent != self.root or not target.is_file():
            raise ImageStorageError("图片文件不存在")
        return target


def get_image_storage(settings: Settings) -> StorageProvider:
    return LocalImageStorage(settings)
