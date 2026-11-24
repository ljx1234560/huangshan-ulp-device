"""One billable Ark URL-response request, download, and image validation."""
import base64
import hashlib
import io
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from velapet_backend.config import Settings
from velapet_backend.default_pets import render_pet
from velapet_backend.image_provider import decode_image, MAX_OUTPUT
from velapet_backend.images import STYLES

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    load_dotenv(args.env_file, override=True)
    cfg = Settings.from_env()
    if not cfg.ark_api_key:
        raise SystemExit("ARK_API_KEY is missing")
    args.output.mkdir(parents=True, exist_ok=True)
    base = cfg.ark_api_base_url.rstrip("/")
    endpoint = base if base.endswith("/images/generations") else base + "/images/generations"
    assert urlsplit(endpoint).scheme == "https"
    payload = {"model": cfg.seedream_model, "prompt": STYLES["cartoon"],
               "image": "data:image/png;base64," + base64.b64encode(render_pet("nova-cat", "home")).decode(),
               "size": "1K", "response_format": "url", "watermark": True}
    started = time.monotonic()
    report = {"timestamp": datetime.now().astimezone().isoformat(), "model": cfg.seedream_model,
              "generation_requests": 1}
    with httpx.Client(timeout=120, follow_redirects=False) as client:
        response = client.post(endpoint, json=payload, headers={"Authorization": "Bearer " + cfg.ark_api_key})
        report["http_status"] = response.status_code
        if response.status_code != 200:
            try:
                report["provider_error_code"] = response.json().get("error", {}).get("code")
            except ValueError:
                pass
            (args.output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
            print(json.dumps(report, ensure_ascii=False))
            return 1
        url = response.json()["data"][0]["url"]
        parsed = urlsplit(url)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("invalid provider image URL")
        # Download without forwarding the model credential.
        with client.stream("GET", url) as downloaded:
            downloaded.raise_for_status()
            raw = bytearray()
            for chunk in downloaded.iter_bytes(chunk_size=65536):
                if len(raw) + len(chunk) > MAX_OUTPUT:
                    raise ValueError("provider image too large")
                raw.extend(chunk)
    image = decode_image(bytes(raw))
    (args.output / "generated.png").write_bytes(raw)
    report.update(image_url=url, width=image.width, height=image.height,
                  byte_size=len(raw), sha256=hashlib.sha256(raw).hexdigest(),
                  elapsed_seconds=round(time.monotonic() - started, 2))
    image.close()
    (args.output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
