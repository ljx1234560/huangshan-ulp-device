# 第三阶段实现与验收记录

记录日期：2026-11-19（Asia/Shanghai）。

## 已完成并执行验证

- BLE Sync v1：128 位 GATT UUID、16 字节帧头、CRC16、MTU 分片、错序/重复重组、ACK/NACK、绝对设备游标和版本策略。
- Windows 桥接：Bleak 扫描/连接/订阅、协议与设备信息查询、逐批重组与持久化、HTTP 重试、断线重连、提交后 ACK、短期用户授权。
- Fake/真实 Transport 协议层：多批连续同步、上传失败不 ACK、重连、ACK 丢失后安全重复、跨天记录、非零游标和游标恢复测试。
- FastAPI：Bridge Token、用户/设备绑定校验、内容冲突拒绝、硬件/测试来源、BLE 传输日志、固件/协议版本、桥接状态和管理聚合。
- Web：设备中心轮询后端桥接心跳，活动页显示数据来源，管理端显示活跃设备、同步失败与固件分布。
- 固件候选：CRC 帧编解码、128 条 RAM 有界队列与 `WAIT_ACK` 会话状态机通过主机 GCC 测试；未 ACK 记录不会因普通 BLE 断开被释放。
- Alembic：全新 SQLite 数据库实际从空库升级到 `20261119_0003 (head)`。
- 视觉：用户端 390px 视口和管理端默认视口完成浏览器检查，整页无横向溢出。

执行结果：

```text
BLE bridge pytest       21 passed
FastAPI pytest          14 passed
TypeScript/Vue tests     6 passed
TypeScript typecheck     passed (4 workspaces)
Vue production build     passed (user + admin)
C host protocol test     PASS (3 cases)
Alembic fresh upgrade    20261119_0003 (head)
```

生产构建仍有既有的 Vite `chunk > 500 kB` 性能警告，不影响构建成功，后续可按路由拆分 Element Plus/ECharts。

## 阶段 3.5 可靠性回归

- 连续两轮同步：第一轮设备绝对游标 `100 -> 101`，第二轮以新的 `uploadId`、HTTP 偏移 `0` 从设备游标 `101` 继续；两轮均持久化并返回精确 ACK 游标。
- 断线续传：未收到 ACK 的批次保留在设备侧，重连后使用同一绝对游标重放，不释放历史记录。
- ACK 丢失：后端已持久化但设备未收到 ACK 时，新的上传任务可重放相同 `recordId` 和相同内容；返回幂等重复，累计步数不增加。
- 冲突保护：相同 `deviceId + recordId` 但内容不同返回 `409`，不会静默忽略；同步任务也不能跨用户绑定继续。
- 时间可信：`hardware` 记录必须带 `TIME_TRUSTED`/`rtcTrusted=true`；桥接与后端双重拒绝 RTC 未校准记录。
- 分片恢复：超时会报告精确缺片编号并逐片 NACK；重试受限，已接收分片保留供重传补齐，重连后旧会话重组状态被清空。
- 状态语义：当前桥接运行、当前 BLE 连接、最近一次同步结果分别存储和展示；断开后不会继续显示“在线”。

## 硬件代码审查结论

本机 `E:\作业\velapet` 没有硬件工作树。只读分析的公开仓库显示：运动模型有主机测试；诊断 BLE 只有四字节读写；真实产品传感器适配、正式 Sync GATT、离线 Flash 持久化和物理配对确认均未完成真机证明。公开历史记录提到工厂镜像可读 LSM6 数据，但静止计步为 0 不能证明真实步行计步正确。

因此当前状态分类为：

- 已实现且自动测试：二进制协议、Python 桥接、Fake Transport、后端幂等/绑定、前端展示、C 候选队列。
- 已实现但仅主机测试：候选 C 协议与 RAM 历史缓存。
- 尚未集成：SF32 正式 GATT、真实计步驱动适配、物理配对确认、Flash 掉电恢复。
- 因硬件缺失无法验证：烧录、真实步行、Windows 真机 BLE、断电注入、ACK 丢失真机恢复。

## PostgreSQL 验证状态

当前机器没有可用的 `docker` 或 `psql` 命令，故本阶段没有完成 PostgreSQL 运行验收。SQLite 测试和迁移成功不作为 PostgreSQL 运行替代证据。

具备 Docker Desktop 后执行：

```powershell
Set-Location 'E:\作业\velapet\web'
docker compose up --build -d
docker compose ps
docker compose exec server python -m alembic current
docker compose exec postgres psql -U velapet -d velapet -c "select version();"
docker compose exec postgres psql -U velapet -d velapet -c "select source, count(*) from activity_records group by source;"
docker compose exec postgres psql -U velapet -d velapet -c "select transport, status, count(*) from sync_logs group by transport, status;"
```

随后运行桥接或模拟上传，刷新用户端与管理端并再次查询上述表。

## 真机验收入口

完整步骤见 `docs/FIRMWARE_INTEGRATION.md`。必须保留构建日志、固件哈希、真实步行记录和数据库查询结果，才能把“待真机”改为“真机通过”。
