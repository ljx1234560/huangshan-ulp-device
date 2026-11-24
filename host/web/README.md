# VelaPet Web + API + Windows BLE Bridge

VelaPet 第三阶段可运行版本：Vue 3 用户端、Vue 3 管理端、FastAPI/SQLAlchemy 后端、正式 BLE 同步协议和 Windows Bleak 桥接程序。开发环境可使用 SQLite；正式数据库目标为 PostgreSQL，并通过 Alembic 管理结构。

> 当前已完成协议、桥接、Fake BLE、后端和网页的数据链路；尚未在 SF32LB52 真机上编译/烧录正式 GATT，也没有真实步行采集证据，因此不宣称真机 BLE 联调完成。

## 组成

```text
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
Set-Location 'E:\projects\huangshan-ulp-device\host\web'
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
Set-Location 'E:\projects\huangshan-ulp-device\host\web'
docker compose exec server python scripts/simulate_device.py --base-url http://127.0.0.1:8000 --steps 12345
```

本机后端模式也可运行 `server\.venv\Scripts\python.exe server\scripts\simulate_device.py --steps 12345`。上传完成后刷新用户端运动页；管理端会从数据库重新计算 Device DAU、Product DAU、同步成功率等指标。

## 本机 SQLite 开发

```powershell
Set-Location 'E:\projects\huangshan-ulp-device\host\web'
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
Set-Location 'E:\projects\huangshan-ulp-device\host\web\server'
$env:VELAPET_DATABASE_URL = 'postgresql+psycopg://velapet:velapet_dev@localhost:5432/velapet'
.\.venv\Scripts\python.exe -m alembic upgrade head
```

`20261118_0001` 创建第二阶段基础表；`20261118_0002` 增加 BLE 会话与数据来源；`20261119_0003` 增加设备持久化游标、桥接运行/连接/最近同步分离状态和同步日志绝对游标。

## Windows BLE 桥接

设备必须先由当前用户通过 claim code 绑定。桥接登录用户账号后只取得 15 分钟、限定设备的短期 Token；密码只用于当次授权的隐藏输入，不保存到固件或配置文件。

```powershell
Set-Location 'E:\projects\huangshan-ulp-device\host\web'
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

默认 `VELAPET_AI_PROVIDER=mock`。设置为 `existing` 时，后端会把运动摘要适配到已有 `host/ai-backend` 的 `POST /api/v1/chat`，并仅由服务端发送 `X-VelaPet-Token`。图片生成目前仍使用持久化 Mock Provider；不会暴露 API Key，也不会修改设备端 EXP 或奖励。

## 验证命令

```powershell
Set-Location 'E:\projects\huangshan-ulp-device\host\web'
pnpm typecheck
pnpm test
pnpm build
server\.venv\Scripts\python.exe -m pytest server\tests -q
$env:PYTHONPATH = 'tools/ble-bridge'
server\.venv\Scripts\python.exe -m pytest tools\ble-bridge\tests -q
```

详细 API、幂等/断点续传规则、指标口径和硬件边界见 [docs/API_INTEGRATION.md](docs/API_INTEGRATION.md)。
