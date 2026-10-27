"""Start a temporary loopback backend and verify the real HTTP chat path."""

from __future__ import annotations

import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time

import httpx


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="velapet-chat-smoke-") as temp:
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]

        base_url = f"http://127.0.0.1:{port}"
        environment = dict(
            os.environ,
            VELAPET_HOST="127.0.0.1",
            VELAPET_PORT=str(port),
            VELAPET_DATA_ROOT=temp,
            VELAPET_DEVICE_TOKENS="smoke-device-token",
            MIMO_API_KEY="",
        )
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "velapet_backend.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
            ],
            cwd=ROOT,
            env=environment,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=flags,
        )
        try:
            with httpx.Client(timeout=5.0, follow_redirects=False) as client:
                deadline = time.monotonic() + 15.0
                while True:
                    try:
                        health = client.get(base_url + "/health")
                        health.raise_for_status()
                        break
                    except httpx.HTTPError:
                        if process.poll() is not None or time.monotonic() >= deadline:
                            raise RuntimeError("Temporary backend did not start")
                        time.sleep(0.1)

                payload = {
                    "device_id": "smoke-device",
                    "prompt_type": "greeting",
                    "context": {"pet_name": "NOVA"},
                }
                assert client.post(base_url + "/api/v1/chat", json=payload).status_code == 401
                response = client.post(
                    base_url + "/api/v1/chat",
                    json=payload,
                    headers={"X-VelaPet-Token": "smoke-device-token"},
                )
                response.raise_for_status()
                data = response.json()
                assert data["source"] == "local_fallback"
                assert data["error_code"] == "MIMO_NOT_CONFIGURED"
                print("AI_HTTP_SMOKE result=PASS auth=PASS fallback=PASS")
                return 0
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


if __name__ == "__main__":
    raise SystemExit(main())
