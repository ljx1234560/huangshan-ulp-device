# 电脑端聊天与照片联调

对应 `member-4/cloud-chat-assets` 分支。当前为电脑端原型；没有修改开发板 UI 或驱动，桌面中文显示不等同于板端字库已可用。

## 启动

在产品仓库根目录运行（Python 3.11+，桌面需要 Tk）：

可先执行 `.\scripts\configure-ai.ps1` 隐藏输入 API Key 和模型 ID，保存到本地 `.env`。脚本不调用 API，直接回车保留现有值。

```powershell
python -m venv test-results/ai-backend-venv-host
.\test-results\ai-backend-venv-host\Scripts\python.exe -m pip install -r host/ai-backend/requirements-dev.txt
# 终端一：默认 loopback，无 Key 时使用本地降级和图片 demo
.\test-results\ai-backend-venv-host\Scripts\python.exe host/ai-backend/run.py
# 终端二
.\test-results\ai-backend-venv-host\Scripts\python.exe host/ai-backend/tools/desktop_demo.py
```

真实调用前把 `host/ai-backend/.env.example` 复制成同目录 `.env`（已有则保留），本机填写：

更新：当前按用户要求暂缓真实生图，使用内置默认形象。详见 [默认形象与生图开关](default-pets-and-images.md)。即使已配置 Seedream Key，未开启 `VELAPET_IMAGE_GENERATION_ENABLED` 也不会请求模型。

```dotenv
VELAPET_CHAT_PROVIDER=deepseek
DEEPSEEK_API_KEY=<本机填写，不上传>
DEEPSEEK_CHAT_MODEL=<账号当前可用模型ID>
VELAPET_IMAGE_PROVIDER=seedream
ARK_API_KEY=<本机填写，不上传>
SEEDREAM_MODEL=<控制台已开通的图生图模型ID>
VELAPET_IMAGE_GENERATION_ENABLED=false
```

示例模型 ID 不代表账号已开通。首次实调前确认额度和预算。API Key 只放后端；窗口仅填写独立设备 Token。电脑端验证无需公网服务器和对象存储。

仅当后续明确允许真实生图测试时，才把 `VELAPET_IMAGE_GENERATION_ENABLED` 改为 true 并重启服务。聊天调用不受该开关影响。

## 功能和边界

- NOVA（温暖耐心）或 SPARK（活泼俏皮），可设置展示名。
- 快捷问候、鼓励、任务、成长进度，自由文本聊天。
- 返回 conversation_id，续用时保留最近六轮，可清除会话。
- 选择 PNG/JPEG/WebP 照片，提交任务、轮询、校验哈希、预览主页图。
- demo 仅缩放原照片，明确标注不是 AI 生成；seedream 才执行收费图生图。
- 无有效聊天 Key 时 source=local_fallback，不可称为 DeepSeek 实际回复。

请求在后台线程执行，队列结果交给 Tk 主线程。业务上下文是示例，不是开发板实时数据。调整设备/地址后建议清除旧会话；人设切换前等待任务完成。图片超时不自动重发收费任务。

## 临时图片规格

| kind | 尺寸 | 格式 |
| --- | --- | --- |
| avatar | 128×128 | RGB PNG |
| home | 240×240 | RGB PNG |
| skin | 160×160 | RGB PNG，仅预览 |

浅色背景、不承诺透明通道，三个资源由同一基准图派生。skin 不自动加入成长皮肤白名单。真机内存和前端布局确认后再锁定规格。

## 接口

原 `/api/v1/chat` 保持兼容，新增可选 `conversation_id` 和 `persona_id`（nova/spark）。返回同名字段及原有 reply/source/error_code。

```json
{"device_id":"watch-01","prompt_type":"custom","message":"今天走路有点累","persona_id":"nova","conversation_id":null,"context":{"pet_name":"NOVA"}}
```

| 方法/路径 | 内容 |
| --- | --- |
| GET `/api/v1/personas` | 内置人设 |
| DELETE `/api/v1/conversations/{id}?device_id=...` | 清除该凭证/设备的会话 |
| POST `/api/v1/pet-assets/jobs` | multipart：file、device_id、style（cartoon/pixel）、idempotency_key |
| GET `/api/v1/pet-assets/jobs/{id}?device_id=...` | queued/processing/succeeded/failed |
| GET `/api/v1/pet-assets/{id}/files/{filename}?device_id=...` | 鉴权后的资源下载 |

配置 Token 时业务接口携带 X-VelaPet-Token。会话/任务按凭证摘要和设备标识隔离，原始 Token 不落库。同一 Token 仍处于同一信任域，不等于多用户账号及设备所有权系统。

同一 idempotency_key 与相同照片/画风返回同一任务，内容不同返回 409。超时后查询原任务。成功清单含 kind/version/sha256/byte_size/width/height/mime_type/download_url，不指定设备绝对路径。

## 存储与限制

- SQLite：`runtime-data/velapet.sqlite3` 保存最近对话和任务元数据。对话是本机明文；清除接口删除逻辑记录，不承诺安全擦除。
- 资源：`runtime-data/image-jobs/<job_id>/`。不存原始照片，无原图下载路由。
- 写入后 flush/fsync、原子替换，元数据成功前不开放下载。
- 单进程 MVP，最多两个图片任务并发；重启将未完成任务标记 PROCESS_INTERRUPTED，不重发收费请求。
- 上传读取上限 5 MiB，解码上限 1600 万像素。公开部署另需入口层总请求大小限制、账号鉴权、资源清理和调用预算上限。
- Seedream 单图、1K、Base64 返回、保留水印；账号/模型差异待实调确认。

## 验证

```powershell
.\scripts\test-ai-backend.ps1
.\test-results\ai-backend-venv-host\Scripts\python.exe host/ai-backend/tools/smoke_http.py
.\test-results\ai-backend-venv-host\Scripts\python.exe host/ai-backend/tools/desktop_smoke.py
```

后两项启动临时本地服务、清空模型 Key、使用测试照片，结束后关闭。桌面测试隐藏窗口，验证中文文本和回填；不替代人工视觉及鼠标交互验收。

## 明日待提供

1. DeepSeek/方舟可用模型 ID、额度、首轮预算；Key 仅本地配置。
2. 用户已确认板子有联网功能；补链路类型、网络 API、TLS 所属层、访问后端的验证结果。本轮不重复假定设备仍未联网。
3. 存储挂载点/API、空间、原子替换能力，RAM/PSRAM/堆峰值。
4. 麦克风采样率、位深、声道、PCM API、录音时长；ASR 识别服务和预算。先录音转写后复用 custom 文本聊天接口。
5. 最新前端页面接口、UI线程消息接收方式、图片区域和字库。

## 板端中文方案

电脑窗口使用系统中文字体。板端先测试固定快捷文案子集，再针对自由回复评估完整字体或按需加载；固定字库不能保证任意中文回复可显示。取得 SDK 字体方案、存储和 RAM 数据后决定字号、字体缓存与缺字回退。没有 SDK/板端证据前不修改字体宏，不宣称中文上板完成。
