# VelaPet Web + API + Windows BLE Bridge

VelaPet 阶段 4B-2 可运行版本：Vue 3 用户端、Vue 3 管理端、FastAPI/SQLAlchemy 后端、DeepSeek 文本建议、OpenAI 与火山方舟豆包 Seedream 图片生成适配、数据库图片任务 Worker、正式 BLE 同步协议和 Windows Bleak 桥接程序。开发环境可使用 SQLite；正式数据库目标为 PostgreSQL，并通过 Alembic 管理结构。

> 当前已完成协议、桥接、Fake BLE、后端和网页的数据链路；尚未在 SF32LB52 真机上编译/烧录正式 GATT，也没有真实步行采集证据，因此不宣称真机 BLE 联调完成。

## 一键启动（Windows）

在仓库的 `host/web` 目录打开 PowerShell，或直接双击 `start-web.cmd`：

```powershell
Set-Location .\host\web

.\start-web.cmd                 # Mock：用户端 + 管理端，无需后端
.\start-web.cmd -Mode real      # Real：SQLite 后端 + 用户端 + 管理端
```

| 参数 | 作用 |
| --- | --- |
| `-Mode real` | 启动 FastAPI + SQLite，自动执行 Alembic 迁移 |
| `-NoAdmin` | 只启动用户端 |
| `-NoBrowser` | 不自动打开浏览器 |
| `-Reinstall` | 强制重装前端/后端依赖 |

启动后：

- 用户端：<http://localhost:5173>
- 管理端：<http://localhost:5174>
- 后端健康检查：<http://localhost:8000/health>（仅 Real 模式）

说明：

- 首次运行会安装 pnpm（缺失时）和前端依赖；Real 模式还会创建 `server/.venv`、安装后端依赖并迁移 `server/velapet.db`。
- 每次运行会生成 `host/web/.env.local`；已有文件会备份为 `.env.local.bak-时间戳`。
- 5173/5174/8000 已被占用时会跳过重复启动；关闭对应的启动窗口即可停止服务。
- 演示账号：
  - Mock：用户 `demo@velapet.cn / velapet-demo`，管理员 `admin@velapet.cn / velapet-admin-demo`
  - Real：用户 `demo@velapet.cn / VelaPetDemo123!`，管理员 `admin@velapet.cn / VelaPetAdmin123!`

## 组成

```text
start-web.cmd / .ps1       Windows 一键启动（Mock/Real）
apps/user/                 用户端，localhost:5173
apps/admin/                管理端，localhost:5174
packages/shared/           共享 TypeScript 模型
packages/api/              Mock/Real API 客户端
server/app/                FastAPI、SQLAlchemy 与业务服务
server/migrations/         Alembic 迁移
server/tests/              后端集成测试
server/scripts/            模拟设备上传客户端
tools/ble-bridge/          Windows Bleak 桥接、协议编解码和测试
firmware/sf32lb52-sync/    供真实硬件仓库集成的主机可测候选 C 模块
docs/BLE_SYNC_PROTOCOL.md  正式 BLE GATT/分包/ACK 协议
docker-compose.yml         PostgreSQL 17 + API
```

## 推荐：PostgreSQL 完整联调

要求：Node.js 20+、pnpm 10+、Python 3.11+、Docker Desktop。

在 Windows PowerShell 中执行：

```powershell
Set-Location 'E:\作业\velapet\web'
Copy-Item .env.example .env
(Get-Content .env) -replace 'VITE_API_MODE=mock', 'VITE_API_MODE=real' | Set-Content .env

pnpm install
docker compose up --build -d

# 终端 1
pnpm dev:user

# 终端 2
pnpm dev:admin
```

打开：

- 用户端：http://localhost:5173
- 管理端：http://localhost:5174
- API 文档：http://localhost:8000/docs
- 健康检查：http://localhost:8000/health

开发种子数据明确标记为 Demo，不应当作真实运营数据：

- 用户：`demo@velapet.cn` / `VelaPetDemo123!`
- 管理员：`admin@velapet.cn` / `VelaPetAdmin123!`
- 模拟设备 Token：`demo-device-token`

模拟手表上传一批运动数据：

```powershell
Set-Location 'E:\作业\velapet\web'
docker compose exec server python scripts/simulate_device.py --base-url http://127.0.0.1:8000 --steps 12345
```

本机后端模式也可运行 `server\.venv\Scripts\python.exe server\scripts\simulate_device.py --steps 12345`。上传完成后刷新用户端运动页；管理端会从数据库重新计算 Device DAU、Product DAU、同步成功率等指标。

## 本机 SQLite 开发

```powershell
Set-Location 'E:\作业\velapet\web'
py -3.12 -m venv server\.venv
server\.venv\Scripts\python.exe -m pip install -e 'server[dev]'

Set-Location server
$env:VELAPET_DATABASE_URL = 'sqlite:///./velapet.db'
$env:VELAPET_SEED_DEMO = 'true'
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

SQLite 仅用于本地开发与测试。PostgreSQL 是主要数据库目标。

## 数据库迁移

Docker 服务启动时会先执行 `alembic upgrade head`。手动迁移 PostgreSQL：

```powershell
Set-Location 'E:\作业\velapet\web\server'
$env:VELAPET_DATABASE_URL = 'postgresql+psycopg://velapet:velapet_dev@localhost:5432/velapet'
.\.venv\Scripts\python.exe -m alembic upgrade head
```

`20261118_0001` 创建第二阶段基础表；`20261118_0002` 增加 BLE 会话与数据来源；`20261119_0003` 增加同步可靠性字段；`20261124_0004` 增加按用户隔离的 AI 运动建议生成记录。

## Windows BLE 桥接

设备必须先由当前用户通过 claim code 绑定。桥接登录用户账号后只取得 15 分钟、限定设备的短期 Token；密码只用于当次授权的隐藏输入，不保存到固件或配置文件。

```powershell
Set-Location 'E:\作业\velapet\web'
py -3.11 -m venv tools\ble-bridge\.venv
tools\ble-bridge\.venv\Scripts\python.exe -m pip install -e 'tools\ble-bridge[dev]'

tools\ble-bridge\.venv\Scripts\velapet-bridge.exe scan --seconds 10
tools\ble-bridge\.venv\Scripts\velapet-bridge.exe sync `
  --address '<扫描结果中的地址>' `
  --serial 'VP-52U-2400168' `
  --email 'demo@velapet.cn' `
  --api-url 'http://localhost:8000'
```

桥接校验 BLE 设备序列号与授权设备一致，逐批重组分片、校验 CRC、上传幂等 API，且只在后端提交成功后向设备 ACK。详见 [桥接说明](tools/ble-bridge/README.md)、[BLE 协议](docs/BLE_SYNC_PROTOCOL.md)、[可靠性记录](docs/BLE_SYNC_RELIABILITY.md) 和 [固件集成说明](docs/FIRMWARE_INTEGRATION.md)。

## Mock / Real 模式

根目录 `.env`：

```dotenv
VITE_API_MODE=mock
VITE_API_BASE_URL=http://localhost:8000
```

- `mock`：纯前端演示；Mock 同步历史、生成任务、资源收藏和当前形象会保存在浏览器 localStorage。
- `real`：请求 FastAPI。用户身份由 HttpOnly Cookie 会话恢复，修改请求使用双提交 CSRF Token，管理员权限由服务端 RBAC 验证。

Real 模式不接受任意密码，也不将数据库连接、设备 Token 或 AI Key 写入前端。

## 认证与数据边界

- 密码使用随机盐的 scrypt 哈希，不保存明文。
- Access/Refresh 会话是数据库中的不透明 Token 哈希；刷新时轮换旧会话。
- Cookie 使用 HttpOnly、SameSite=Lax；生产 HTTPS 必须设置 `VELAPET_COOKIE_SECURE=true`。
- 所有活动、设备、宠物资源接口按当前用户隔离；管理员接口强制 `admin` 角色。
- 用户解绑后不再接收该设备的新上传；解绑前历史记录仍归原用户，不能自动转移给新绑定用户。
- Web 的“请求同步”和设备的“上传数据”是两个不同端点和日志来源。

## AI 适配

文本与图片 Provider 已拆分。默认 `VELAPET_TEXT_AI_PROVIDER=mock`；设置为 `deepseek` 后，后端会读取最近 30 天运动汇总，经安全目标边界计算后调用 DeepSeek Chat Completions。模型名称没有写死，必须按实际账户权限显式填写。API Key 只放在 `server/.env` 或进程环境变量中，不进入浏览器、日志或版本库。

```dotenv
VELAPET_TEXT_AI_PROVIDER=deepseek
VELAPET_TEXT_AI_API_KEY=
VELAPET_TEXT_AI_BASE_URL=https://api.deepseek.com
VELAPET_TEXT_AI_MODEL=
VELAPET_TEXT_AI_TIMEOUT_SECONDS=20
VELAPET_IMAGE_AI_PROVIDER=openai
VELAPET_IMAGE_AI_API_KEY=
VELAPET_IMAGE_AI_BASE_URL=https://api.openai.com/v1
VELAPET_IMAGE_AI_MODEL=
VELAPET_IMAGE_AI_TIMEOUT_SECONDS=120
VELAPET_IMAGE_AI_SIZE=1024x1024
VELAPET_IMAGE_AI_QUALITY=medium
VELAPET_IMAGE_AI_OUTPUT_FORMAT=png
VELAPET_IMAGE_AI_BACKGROUND=auto
VELAPET_IMAGE_AI_RESPONSE_FORMAT=b64_json
VELAPET_IMAGE_AI_WATERMARK=false
VELAPET_IMAGE_STORAGE_DIR=./data/pet-images
```

使用豆包 Seedream 时将 Provider 改为 `doubao`、Base URL 改为 `https://ark.cn-beijing.volces.com/api/v3`，并填写账户有权限的模型 ID。模型 ID 没有默认值；示例 `doubao-seedream-5-5-261028` 只能在账户实际可用时使用。Seedream 5.5 支持 `png/jpeg` 和透明背景；5.0 pro/flash、5.0 lite、4.x 的能力不同，后端会按模型族校验并省略不支持的参数。4.x 固定 JPEG，应配置 `VELAPET_IMAGE_AI_OUTPUT_FORMAT=jpeg`。

真实 Provider 的超时、网络、限流、余额不足、鉴权和非法响应会明确报错，不会悄悄返回 Mock。文本建议与图片任务的模型、耗时和 Token 用量会落库，历史记录按登录用户隔离。图片模型没有写死，必须按供应商账户实际权限填写；默认仍为 Mock。

图片任务使用数据库队列和独立 Worker。生成结果以 Base64 接收，经真实格式、尺寸和大小校验后写入私有数据目录；浏览器只能通过带登录会话且校验 owner 的资源端点读取。任务 ID、资源 ID 和宠物实例 ID 始终分离。每日默认 10 次、每用户同时 1 个任务；超时不自动重试，避免响应丢失时潜在重复计费，限流和 5xx 最多按配置重试一次。供应商没有提供可靠费用时管理端显示“暂无可靠数据”。

Windows PowerShell 启动真实文本 AI：

```powershell
Set-Location 'E:\作业\velapet\web'
Copy-Item server\.env.example server\.env
# 仅编辑被 Git 忽略的 server\.env，填写 API Key 与账户可用模型
Set-Location server
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
# OpenAI 或豆包图片 Provider 必须在另一个终端运行数据库 Worker
.\.venv\Scripts\python.exe scripts\image_worker.py
# 新终端回到仓库根目录启动用户端
Set-Location 'E:\作业\velapet\web'
pnpm dev:user
```

显式在线冒烟测试（会真实调用并可能产生费用）：

```powershell
$env:VELAPET_RUN_ONLINE_AI_SMOKE = '1'
server\.venv\Scripts\python.exe server\scripts\smoke_deepseek.py

# 图片冒烟测试会真实生成图片并产生费用，必须单独显式启用
$env:VELAPET_RUN_ONLINE_IMAGE_SMOKE = '1'
server\.venv\Scripts\python.exe server\scripts\smoke_openai_image.py

# 豆包图片冒烟测试同样会真实生成图片并产生费用，使用独立开关
$env:VELAPET_RUN_ONLINE_DOUBAO_IMAGE_SMOKE = '1'
server\.venv\Scripts\python.exe server\scripts\smoke_doubao_image.py
```

## 验证命令

```powershell
Set-Location 'E:\作业\velapet\web'
pnpm typecheck
pnpm test
pnpm build
server\.venv\Scripts\python.exe -m pytest server\tests -q
$env:PYTHONPATH = 'tools/ble-bridge'
server\.venv\Scripts\python.exe -m pytest tools\ble-bridge\tests -q
```

详细 API、幂等/断点续传规则、指标口径和硬件边界见 [docs/API_INTEGRATION.md](docs/API_INTEGRATION.md)。
