"""Exercise widget callbacks + queue result delivery against a temporary server.

No paid calls, no user photos, and no persistent server. This is not visual QA.
"""
import hashlib
import io
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import tkinter as tk

import httpx
from PIL import Image

from desktop_demo import Demo

ROOT = Path(__file__).resolve().parents[1]


def main():
    with tempfile.TemporaryDirectory(prefix="velapet-desktop-") as temp:
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        base = f"http://127.0.0.1:{port}"
        env = dict(os.environ, VELAPET_DATA_ROOT=temp, VELAPET_HOST="127.0.0.1",
                   VELAPET_DEVICE_TOKENS="desktop-test", VELAPET_CHAT_PROVIDER="deepseek",
                   DEEPSEEK_API_KEY="", MIMO_API_KEY="", ARK_API_KEY="", VELAPET_IMAGE_PROVIDER="demo")
        process = subprocess.Popen([sys.executable, "-m", "uvicorn", "velapet_backend.main:app",
            "--host", "127.0.0.1", "--port", str(port)], cwd=ROOT, env=env,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        window = None
        try:
            with httpx.Client(trust_env=False, timeout=3) as client:
                deadline = time.monotonic() + 20
                while True:
                    try:
                        response = client.get(base + "/health")
                        response.raise_for_status()
                        break
                    except httpx.HTTPError:
                        if time.monotonic() > deadline or process.poll() is not None:
                            raise RuntimeError("Server startup failed")
                        time.sleep(.1)
                window = tk.Tk()
                window.withdraw()
                demo = Demo(window)
                demo.base.set(base)
                demo.token.set("desktop-test")
                demo.pet.set("mint-rabbit")
                demo.preview_default()
                assert demo.tk_image.width() == 240
                demo.save_default()
                wait_ui(window, demo)
                demo.pet.set("nova-cat")
                demo.load_default()
                wait_ui(window, demo)
                assert demo.pet.get() == "mint-rabbit"
                demo.chat("greeting")
                wait_ui(window, demo)
                assert demo.cid
                assert "local_fallback" in demo.log.get("1.0", "end")
                assert "你好" in demo.log.get("1.0", "end")
                demo.message.insert(0, "今天好累呀")
                demo.chat("custom")
                wait_ui(window, demo)
                assert "今天好累呀" in demo.log.get("1.0", "end")
                old_cid = demo.cid
                demo.persona.set("spark")
                demo.chat("greeting")
                wait_ui(window, demo)
                assert demo.cid and demo.cid != old_cid
                demo.clear()
                wait_ui(window, demo)
                assert demo.cid is None
                raw = io.BytesIO()
                Image.new("RGB", (320, 180), "orange").save(raw, format="PNG")
                headers = {"X-VelaPet-Token": "desktop-test"}
                response = client.post(base + "/api/v1/pet-assets/jobs", headers=headers,
                    files={"file": ("fixture.png", raw.getvalue())}, data={"device_id": "desktop-demo", "idempotency_key": "fixture"})
                response.raise_for_status()
                jid = response.json()["job_id"]
                for _ in range(100):
                    job = client.get(base + "/api/v1/pet-assets/jobs/" + jid,
                        headers=headers, params={"device_id": "desktop-demo"}).json()
                    if job["status"] in {"succeeded", "failed"}:
                        break
                    time.sleep(.05)
                assert job["status"] == "succeeded"
                asset = next(x for x in job["artifacts"] if x["kind"] == "home")
                image = client.get(base + asset["download_url"], headers=headers, params={"device_id": "desktop-demo"}).content
                assert hashlib.sha256(image).hexdigest() == asset["sha256"]
                demo.events.put(("result", ("image", image, job)))
                demo.poll()
                assert demo.tk_image.width() == 240
                print("DESKTOP_SMOKE PASS chinese_text=PASS quick_chat=PASS custom_chat=PASS clear=PASS photo_http=PASS preview_widget=PASS default_selection=PASS")
        finally:
            if window is not None:
                window.destroy()
            process.terminate()
            try:
                process.wait(5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


def wait_ui(window, demo):
    deadline = time.monotonic() + 10
    while demo.busy:
        window.update()
        if time.monotonic() > deadline:
            raise TimeoutError("UI completion timeout")
        time.sleep(.02)


if __name__ == "__main__":
    main()
