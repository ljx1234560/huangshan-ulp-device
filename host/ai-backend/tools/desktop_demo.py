"""Desktop-only Chinese chat/photo client. Run alongside the loopback backend."""
from __future__ import annotations

import hashlib
import io
import queue
from pathlib import Path
import sys
import threading
import time
import tkinter as tk
from tkinter import filedialog, ttk
from urllib.parse import urlsplit
from uuid import uuid4

import httpx
from PIL import Image, ImageTk

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from velapet_backend.default_pets import PETS, render_pet


class Demo:
    def __init__(self, root):
        self.root = root
        self.events = queue.Queue()
        self.cid = None
        self.conversation_scope = None
        self.busy = False
        root.title("VelaPet 电脑端联调 · 快捷聊天与照片")
        root.geometry("850x720")
        root.option_add("*Font", "{Microsoft YaHei UI} 10")
        self.base = tk.StringVar(value="http://127.0.0.1:8000")
        self.token = tk.StringVar()
        self.device = tk.StringVar(value="desktop-demo")
        self.persona = tk.StringVar(value="nova")
        self.style = tk.StringVar(value="cartoon")
        self.name = tk.StringVar(value="NOVA")
        self.pet = tk.StringVar(value="nova-cat")
        controls = ttk.Frame(root, padding=12)
        controls.pack(fill="x")
        for row, (label, variable) in enumerate([
            ("后端地址", self.base), ("设备 Token", self.token),
            ("设备标识", self.device), ("表宠名字", self.name),
        ]):
            ttk.Label(controls, text=label).grid(row=row, column=0, sticky="w")
            ttk.Entry(controls, textvariable=variable, width=65,
                      show="*" if row == 1 else "").grid(row=row, column=1, sticky="ew")
        ttk.Label(controls, text="人设（切换后开启新会话）").grid(row=4, column=0)
        choice = ttk.Combobox(controls, textvariable=self.persona,
                              values=["nova", "spark"], state="readonly")
        choice.grid(row=4, column=1, sticky="w")
        choice.bind("<<ComboboxSelected>>", lambda _: self.reset_local())
        self.log = tk.Text(root, height=12, wrap="word", state="disabled")
        self.log.pack(fill="both", expand=True, padx=12)
        bar = ttk.Frame(root, padding=12)
        bar.pack(fill="x")
        for label, kind in [("你好", "greeting"), ("鼓励我", "cheer"), ("今日任务", "task"), ("成长进度", "level")]:
            ttk.Button(bar, text=label, command=lambda k=kind: self.chat(k)).pack(side="left")
        ttk.Button(bar, text="清除会话", command=self.clear).pack(side="right")
        self.message = ttk.Entry(root)
        self.message.pack(fill="x", padx=12)
        self.message.bind("<Return>", lambda _: self.chat("custom"))
        ttk.Button(root, text="发送文字（未来语音转写也走此接口）", command=lambda: self.chat("custom")).pack(pady=4)
        images = ttk.Frame(root, padding=12)
        images.pack(fill="x")
        defaults = ttk.Frame(root, padding=12)
        defaults.pack(fill="x")
        ttk.Label(defaults, text="默认形象（本地可用）").pack(side="left")
        pet_choice = ttk.Combobox(defaults, textvariable=self.pet, values=list(PETS), state="readonly", width=18)
        pet_choice.pack(side="left")
        pet_choice.bind("<<ComboboxSelected>>", lambda _: self.preview_default())
        ttk.Button(defaults, text="保存默认形象", command=self.save_default).pack(side="left")
        ttk.Button(defaults, text="加载已保存形象", command=self.load_default).pack(side="left")
        ttk.Combobox(images, textvariable=self.style, values=["cartoon", "pixel"], state="readonly").pack(side="left")
        ttk.Button(images, text="选择照片并生成／处理", command=self.photo).pack(side="left")
        self.preview = ttk.Label(images, text="照片结果显示区；demo 模式仅缩放，不是 AI 生成")
        self.preview.pack(side="right")
        self.status = tk.StringVar(value="未连接 · 示例业务数据 · 不代表开发板")
        ttk.Label(root, textvariable=self.status).pack(pady=8)
        root.after(100, self.poll)
        self.preview_default()

    def preview_default(self):
        with Image.open(io.BytesIO(render_pet(self.pet.get(), "home"))) as image:
            self.tk_image = ImageTk.PhotoImage(image.copy())
        self.preview.configure(image=self.tk_image, text="")
        self.status.set(PETS[self.pet.get()]["name"] + " · 内置矢量形象 · 不调用 AI")

    def save_default(self):
        pet_id = self.pet.get()
        def work(base, headers, device):
            with httpx.Client(timeout=10, trust_env=False) as client:
                response = client.put(base + "/api/v1/appearance", headers=headers,
                                      json={"device_id": device, "pet_id": pet_id})
                response.raise_for_status()
            return ("appearance", pet_id)
        self.start(work)

    def load_default(self):
        def work(base, headers, device):
            with httpx.Client(timeout=10, trust_env=False) as client:
                response = client.get(base + "/api/v1/appearance", headers=headers,
                                      params={"device_id": device})
                response.raise_for_status()
                pet_id = response.json()["pet_id"]
                if pet_id not in PETS:
                    raise ValueError("Unknown built-in appearance")
            return ("appearance", pet_id)
        self.start(work)

    def reset_local(self):
        if not self.busy:
            self.cid = None

    def settings(self):
        base = self.base.get().rstrip("/")
        parsed = urlsplit(base)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username:
            raise ValueError("请填写有效 HTTP(S) 后端地址")
        return base, {"X-VelaPet-Token": self.token.get()}, self.device.get()

    def start(self, work):
        if self.busy:
            self.status.set("已有任务进行中，请等待")
            return
        try:
            settings = self.settings()
        except ValueError as exc:
            self.status.set(str(exc))
            return
        self.busy = True
        self.status.set("处理中…")
        def run():
            try:
                self.events.put(("result", work(*settings)))
            except Exception as exc:
                self.events.put(("error", "请求失败：" + type(exc).__name__ + "；请检查后端、鉴权及任务状态"))
        threading.Thread(target=run, daemon=True).start()

    def chat(self, kind):
        if self.busy:
            self.status.set("已有任务进行中，请等待")
            return
        text = self.message.get().strip()
        if kind == "custom" and not text:
            return
        scope = self.chat_scope()
        if scope != self.conversation_scope:
            self.cid = None
        self.conversation_scope = scope
        payload = {"device_id": "", "prompt_type": kind, "message": text if kind == "custom" else "",
                   "conversation_id": self.cid, "persona_id": self.persona.get(),
                   "context": {"pet_name": self.name.get()}, "max_chars": 50}
        def work(base, headers, device):
            payload["device_id"] = device
            with httpx.Client(timeout=45, follow_redirects=False, trust_env=False) as client:
                response = client.post(base + "/api/v1/chat", headers=headers, json=payload)
                response.raise_for_status()
                result = response.json()
            return ("chat", text or kind, result, scope)
        self.start(work)

    def chat_scope(self):
        return (self.base.get().rstrip("/"), self.device.get(), self.token.get(),
                self.persona.get(), self.name.get())

    def clear(self):
        if not self.cid:
            return
        cid = self.cid
        def work(base, headers, device):
            response = httpx.delete(base + "/api/v1/conversations/" + cid,
                                    headers=headers, params={"device_id": device}, timeout=10, trust_env=False)
            response.raise_for_status()
            return ("clear",)
        self.start(work)

    def photo(self):
        if self.busy:
            return
        path = filedialog.askopenfilename(filetypes=[("照片", "*.png *.jpg *.jpeg *.webp")])
        if not path:
            return
        style, idem = self.style.get(), uuid4().hex
        def work(base, headers, device):
            with httpx.Client(timeout=30, follow_redirects=False, trust_env=False) as client:
                capabilities = client.get(base + "/api/v1/image-capabilities", headers=headers)
                capabilities.raise_for_status()
                if not capabilities.json()["generation_enabled"]:
                    return ("generation_disabled",)
                with open(path, "rb") as stream:
                    raw = stream.read(5 * 1024 * 1024 + 1)
                if len(raw) > 5 * 1024 * 1024:
                    raise ValueError("Photo exceeds 5 MiB")
                response = client.post(base + "/api/v1/pet-assets/jobs", headers=headers,
                    files={"file": ("photo", raw)}, data={"device_id": device, "style": style, "idempotency_key": idem})
                response.raise_for_status()
                job = response.json()
                self.events.put(("job", job["job_id"]))
                deadline = time.monotonic() + 180
                while job["status"] in {"queued", "processing"}:
                    if time.monotonic() >= deadline:
                        raise TimeoutError()
                    time.sleep(1)
                    response = client.get(base + "/api/v1/pet-assets/jobs/" + job["job_id"], headers=headers, params={"device_id": device})
                    response.raise_for_status()
                    job = response.json()
                if job["status"] != "succeeded":
                    return ("failed_image", job)
                asset = next(item for item in job["artifacts"] if item["kind"] == "home")
                route = asset["download_url"]
                if not route.startswith("/api/v1/pet-assets/") or route.startswith("//"):
                    raise ValueError("Untrusted asset URL")
                response = client.get(base + route, headers=headers, params={"device_id": device})
                response.raise_for_status()
                raw = response.content
                if len(raw) != asset["byte_size"] or hashlib.sha256(raw).hexdigest() != asset["sha256"]:
                    raise ValueError("Asset integrity mismatch")
                return ("image", raw, job)
        self.start(work)

    def poll(self):
        while not self.events.empty():
            kind, value = self.events.get()
            if kind == "job":
                self.status.set("任务 " + value + "：等待结果；超时后请查询此任务，勿重复付费生成")
                continue
            self.busy = False
            if kind == "error":
                self.status.set(value)
                continue
            if value[0] == "chat":
                _, message, result, scope = value
                if scope != self.chat_scope():
                    self.cid = None
                    self.status.set("配置已更改，旧请求结果已忽略；下次发送会开启新会话")
                    continue
                self.cid = result["conversation_id"]
                self.log.configure(state="normal")
                self.log.insert("end", f"你：{message}\n表宠：{result['reply']}\n来源：{result['source']}\n\n")
                self.log.see("end")
                self.log.configure(state="disabled")
                self.status.set("完成 · " + result["source"])
            elif value[0] == "clear":
                self.cid = None
                self.log.configure(state="normal")
                self.log.delete("1.0", "end")
                self.log.configure(state="disabled")
                self.status.set("会话已清除")
            elif value[0] == "image":
                with Image.open(io.BytesIO(value[1])) as image:
                    self.tk_image = ImageTk.PhotoImage(image.copy())
                self.preview.configure(image=self.tk_image, text="")
                self.status.set(value[2]["notice"])
            elif value[0] == "appearance":
                self.pet.set(value[1])
                self.preview_default()
                self.status.set("默认形象已保存 · " + PETS[value[1]]["name"])
            elif value[0] == "generation_disabled":
                self.status.set("真实生图暂未启用：请先使用默认形象，未提交生成请求")
            else:
                self.status.set("图片任务失败 · " + str(value[1]["error_code"]))
        self.root.after(100, self.poll)


if __name__ == "__main__":
    window = tk.Tk()
    Demo(window)
    window.mainloop()
