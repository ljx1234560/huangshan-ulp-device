"""Ark image generation with bounded, validated binary responses."""
import base64
import io
import json
import warnings
from urllib.parse import urlsplit

import httpx
from PIL import Image, ImageOps

from .config import Settings

MAX_OUTPUT = 16 * 1024 * 1024


class SeedreamResponseError(ValueError):
    """The upstream response does not contain a usable image."""


def decode_image(raw: bytes) -> Image.Image:
    with warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        with Image.open(io.BytesIO(raw)) as image:
            if image.width * image.height > 16_000_000:
                raise ValueError("IMAGE_TOO_LARGE")
            if image.format not in {"PNG", "JPEG", "WEBP"}:
                raise ValueError("IMAGE_FORMAT_UNSUPPORTED")
            return ImageOps.exif_transpose(image).convert("RGB")


class SeedreamProviderClient:
    def __init__(self, settings: Settings, *, transport: httpx.BaseTransport | None = None):
        self.settings = settings
        self.transport = transport

    def generate(self, source: bytes, prompt: str) -> Image.Image:
        cfg = self.settings
        if not cfg.image_generation_enabled:
            raise ValueError("IMAGE_GENERATION_DISABLED")
        if not cfg.ark_api_key or not cfg.seedream_model:
            raise ValueError("SEEDREAM_NOT_CONFIGURED")
        base = cfg.ark_api_base_url.rstrip("/")
        url = urlsplit(base)
        if (url.scheme != "https" or not url.hostname or url.username is not None
                or url.password is not None or url.query or url.fragment):
            raise ValueError("SEEDREAM_NOT_CONFIGURED")
        endpoint = base if url.path.endswith("/images/generations") else base + "/images/generations"
        payload = {
            "model": cfg.seedream_model, "prompt": prompt,
            "image": "data:image/png;base64," + base64.b64encode(source).decode("ascii"),
            "size": "1K", "response_format": "b64_json", "watermark": True,
        }
        # No retries: a timed out generation may already be billable.
        kwargs = {} if self.transport is None else {"transport": self.transport}
        with httpx.Client(timeout=90, follow_redirects=False, **kwargs) as client:
            with client.stream("POST", endpoint,
                               headers={"Authorization": "Bearer " + cfg.ark_api_key},
                               json=payload) as response:
                response.raise_for_status()
                raw = bytearray()
                for chunk in response.iter_bytes(chunk_size=64 * 1024):
                    if len(raw) + len(chunk) > MAX_OUTPUT * 2:
                        raise SeedreamResponseError("PROVIDER_RESPONSE_TOO_LARGE")
                    raw.extend(chunk)

        try:
            # Receiving bytes in the response avoids arbitrary URL downloads or credential forwarding.
            item = json.loads(raw)["data"][0]
            result = base64.b64decode(item["b64_json"], validate=True)
            if len(result) > MAX_OUTPUT:
                raise ValueError("PROVIDER_IMAGE_TOO_LARGE")
            return decode_image(result)
        except (ValueError, KeyError, IndexError, TypeError, OSError,
                Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
            raise SeedreamResponseError("PROVIDER_IMAGE_INVALID") from exc
