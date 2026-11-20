# VelaPet API 与前后端联调

## 1. 模式与响应契约

用户端和管理端通过 `packages/api` 使用同一套共享 TypeScript 模型：

```dotenv
VITE_API_MODE=mock|real
VITE_API_BASE_URL=http://localhost:8000
```

Real 模式发送 Cookie（`withCredentials`），遇到过期 Access 会话时调用 `/api/v1/auth/refresh` 并重试一次。写请求带 `X-CSRF-Token`。401 会统一清理客户端状态并回到登录页。

日期参数统一为 `YYYY-MM-DD`：

```text
range=day|week|month&start_date=2026-11-01&end_date=2026-11-18
```

## 2. 正式 API

### 用户认证

- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `GET /api/v1/auth/me`
- `POST /api/v1/auth/refresh`
- `POST /api/v1/auth/logout`

密码使用 scrypt。Access/Refresh Token 只以哈希形式存库，并通过 HttpOnly Cookie 传输；CSRF Cookie 可由前端读取并回传请求头。角色只取数据库中的 `user.role`，客户端不能自行声明管理员。

### 运动数据

- `GET /api/v1/activity/daily`
- `GET /api/v1/activity/trends`
- `GET /api/v1/activity/weekly-summary`

查询按当前用户过滤。`start_date/end_date` 会验证顺序和最大跨度。没有记录时返回零值或空数组，不生成伪数据。

### 设备与同步

- `GET /api/v1/devices`
- `POST /api/v1/devices/bind`
- `DELETE /api/v1/devices/{device_id}/binding`
- `POST /api/v1/devices/{device_id}/sync`：Web 只创建“请求同步”日志。
- `GET /api/v1/devices/sync-logs`
- `POST /api/v1/devices/serial/{serial}/bridge-sessions`：已登录且已绑定用户换取 15 分钟短期 Bridge Token。
- `GET /api/v1/devices/{device_id}/bridge-status`：网页轮询本机桥接最近心跳；不是全球在线状态。
- `POST /api/v1/device-uploads/{serial}/bridge-status`：桥接上报 connecting/syncing/success/failed/disconnected。
- `POST /api/v1/device-uploads/{serial}/activity-batches`：设备/桥接上传运动批次。
- `POST /api/v1/device-uploads/{serial}/pet-snapshots`：设备/桥接上传宠物快照。

直接设备上传使用 `X-VelaPet-Device-Token`。Windows 桥接使用 `Authorization: Bearer <短期 Bridge Token>`；短期 Token 与用户、设备及有效绑定同时校验。服务端验证字段范围、时间戳和本地日期，BLE 名称或 MAC 不参与所有权判断。

运动批次示例：

```json
{
  "uploadId": "ble-0007-0009-00000064",
  "uploadOffset": 0,
  "deviceCursor": 100,
  "final": true,
  "records": [
    {
      "recordId": "device-record-001",
      "occurredAt": "2026-11-18T02:00:00Z",
      "localDate": "2026-11-18",
      "timezoneOffsetMinutes": 480,
      "steps": 12345,
      "activeMinutes": 66,
      "goal": 10000,
      "source": "hardware",
      "rtcTrusted": true
    }
  ]
}
```

规则：

1. `recordId + device_id` 唯一，重复记录计入 `duplicates`，不重复累加。
2. `uploadId` 标识一次 HTTP 上传任务，`uploadOffset` 从 0 开始并匹配 `nextUploadOffset`。
3. `deviceCursor` 是本批第一条记录在设备历史队列中的绝对游标，不要求从 0 开始。
4. 响应 `ackCursor` 是可回给设备的绝对游标；`persistedDeviceCursor` 是数据库当前持久化游标。
5. `final=false` 可继续同一 HTTP 任务；`final=true` 将该同步日志标为成功。
6. `occurredAt + timezoneOffsetMinutes` 必须与 `localDate` 一致。
7. 活动原始记录写入 `activity_records`，每日汇总写入 `activity_daily`。
8. 上传时记录当前绑定用户 ID；旧 uploadId 不能跨解绑/重新绑定继续。
9. `source` 只能是 `hardware` 或 `test_injected`；每日多来源汇总为 `mixed`，前端原样展示。
10. `hardware` 记录必须同时传递 `rtcTrusted=true`；RTC 未校准的记录会被拒绝，不能伪装为有效真实运动。
10. `transport` 区分 `direct_api` 与 `ble_bridge`；Web 的“请求同步”仍是独立端点。

### 宠物

- `GET /api/v1/pets/current`
- `POST /api/v1/pets/generation-jobs`
- `GET /api/v1/pets/generation-jobs`
- `GET /api/v1/pets/generation-jobs/{job_id}`
- `POST /api/v1/pets/assets/{asset_id}/favorite`
- `POST /api/v1/pets/assets/{asset_id}/set-current`

三个 ID 语义严格分离：

- `job_id`：异步生成任务。
- `asset_id`：完成后的图片资源，带 owner_id。
- `pet_instance_id`：设备端宠物实例。

设备快照 `version` 必须单调递增；旧版本返回 409。level、EXP、任务、奖励和皮肤来自设备快照，Web/AI 不能修改这些字段。Mock 图片 Provider 也会真实写入数据库，因此刷新后仍可查询任务和资源。

### AI

- `GET /api/v1/ai/coaching`

默认 Provider 为 `mock`。`existing` Provider 兼容硬件仓库 `host/ai-backend` 已有的：

```text
POST /api/v1/chat
X-VelaPet-Token: <只存在服务端的 token>
```

后端只传递受限活动摘要和宠物上下文。AI 响应是建议，不是医疗判断，也不能直接写 EXP、任务奖励或设备状态。外部 Provider 不可用时返回可解释的本地降级建议。

### 管理端

- `GET /api/v1/admin/metrics/overview`
- `GET /api/v1/admin/users`
- `GET /api/v1/admin/devices`
- `GET /api/v1/admin/metrics/ai-services`
- `GET /api/v1/admin/metrics/retention`
- `GET /api/v1/admin/audit-logs`

所有端点执行服务端管理员 RBAC，并记录管理访问审计。

## 3. 活跃与留存口径

- Web DAU：当天 `web_active` 事件的去重 user_id。
- Device DAU：当天 `device_active` 事件的去重 user_id。
- Product DAU：两者 user_id 并集，不能相加。
- WAU/MAU：对应 7/30 日 Product Active 并集。
- 同步成功率：设备上传同步日志中 `success / (success + failed)`；Web 请求同步不混入分母。
- 新增用户：选定日期区间内创建且非管理员用户。
- 基础留存：注册 cohort 在第 1、7、30 日仍有 Product Active 事件的比例。
- 目标完成率：仅统计存在有效日汇总且 goal > 0 的用户日。

`user_events.dedupe_key` 按事件类型、用户和日期去重，避免同日多次刷新放大活跃数。返回的 `dataSource` 为 `demo`、`production`、`mixed` 或 `empty`；Demo 种子不会伪装成正式运营指标。

## 4. 数据库与迁移

主要表：

- `users`、`auth_sessions`
- `devices`、`device_bindings`、`bridge_sessions`
- `activity_records`、`activity_daily`
- `pet_snapshots`、`pet_assets`、`pet_generation_jobs`
- `sync_logs`、`user_events`、`admin_audit_logs`

迁移：`20261118_0001_initial.py`、`20261118_0002_ble_sync.py` 与 `20261119_0003_sync_reliability.py`。

```powershell
Set-Location 'E:\projects\huangshan-ulp-device\host\web\server'
$env:VELAPET_DATABASE_URL = 'postgresql+psycopg://velapet:velapet_dev@localhost:5432/velapet'
.\.venv\Scripts\python.exe -m alembic upgrade head
```

## 5. BLE 与硬件边界

已检查 `huangshan-ulp-device` 的 AI 集成文档。当前可兼容的是 `host/ai-backend` 文本聊天服务；图片生成尚未迁移。设备固件拥有宠物状态、EXP 和任务奖励的权威性。

公开硬件仓库当前自定义 GATT 仍只有四字节诊断通道。本仓库新增了正式协议、Windows 桥接、Fake Transport 和供固件仓库集成的 C 候选模块，但没有修改只读下载的硬件参考代码，也没有真机编译、烧录或步行验证。UUID、MTU、分包、CRC、ACK/NACK、游标和离线 RAM 队列见 `BLE_SYNC_PROTOCOL.md`。

## 6. 验收流程

1. `docker compose up --build -d` 启动 PostgreSQL 和 API。
2. 将根 `.env` 设为 `VITE_API_MODE=real`，启动两个 Vue 应用。
3. 使用 Demo 用户登录用户端，管理员登录管理端。
4. 运行 `server/scripts/simulate_device.py --steps 12345`。
5. 刷新用户端，确认日期筛选后的活动记录仍存在。
6. 刷新管理端，确认 Device DAU/Product DAU/同步指标来自数据库聚合。
7. 普通用户请求 `/api/v1/admin/metrics/overview` 应返回 403。
8. 再次提交同一 `recordId`，服务端返回 duplicate 且每日步数不重复增加。

Fake BLE 验收使用：

```powershell
$env:PYTHONPATH = 'tools/ble-bridge'
server\.venv\Scripts\python.exe -m pytest tools\ble-bridge\tests -q
```

这验证协议、分包重组、CRC、重试、重连、ACK 丢失与游标恢复，不代表真机 BLE 成功。
