# SF32LB52 固件集成与真机验证

## 当前证据

本机 `E:\作业\velapet` 下没有硬件仓库。分析使用的是 GitHub 公开代码的只读临时副本，没有覆盖原项目。公开代码中：

- `velapet_motion.h/.c` 有平台无关运动模型与主机测试，但尚无真实产品传感器适配层。
- 工厂镜像曾读取 LSM6 加速度/陀螺仪/计步寄存器；静止时读到 0，未证明步行计步语义。
- `ble_service.c` 是四字节诊断特征，必须保留，不能承载历史同步。
- 文件系统可用性尚未证明，因此不能声称历史记录断电持久化。
- 宠物核心与服务存在；等级、EXP、任务和奖励继续由设备端决定。

`firmware/sf32lb52-sync/` 是平台无关候选实现，只完成主机 GCC 测试。它不是已经集成的 SF32 固件。

## 正确工作目录与环境确认

真实修改前先取得项目维护者确认的仓库（公开仓库说明指向 `E:\projects\huangshan-ulp-device`），检查 `git status`，确认板卡 `sf32lb52-lchspi-ulp`、SiFli SDK 2.4.6 与锁定提交，再从硬件仓库自己的 `scripts/build.ps1` 构建。不要把本目录候选文件直接覆盖到未知工作树。

## 集成顺序

1. 把 `velapet_sync_protocol.*`、`velapet_history.*` 移入硬件仓库 `src/services/`，并纳入其构建系统。
2. 保留原诊断 GATT；另建 `BLE_SYNC_PROTOCOL.md` 中的 128 位 Sync Service 与五个 Characteristic。
3. GATT 回调只校验/入队。分片发送、超时、重传和 ACK 释放记录在 BLE worker 中完成，禁止阻塞 LVGL 或 BLE 回调。
4. 建立传感器适配器：读取真实累计计步计数，处理回绕/复位后把增量输入现有 motion 模型。只有真实驱动路径使用 `VP_RECORD_SOURCE_HARDWARE`。
5. RTC 未校准时记录必须带 TIME_NOT_TRUSTED，不得伪造 UTC 时间上传为真实数据。
6. 每个汇总窗口生成唯一 `record_id`，写入 128 条有界 RAM 队列。队列满时报告 HISTORY_FULL，绝不覆盖未 ACK 数据。
7. `SYNC_START.cursor` 是设备绝对历史游标；每发送一个 `HISTORY_RECORDS` 批次就进入 `WAIT_ACK`，不得提前发送下一批。
8. 后端提交成功的 `ackCursor` 到达设备后才调用 `vp_history_ack()`；HTTP 的 `nextUploadOffset` 绝不能传给设备。BLE 普通断开不能清空队列。
9. 缺片 NACK 按 sequence + fragment index 重发原片；三轮失败后保留队列并结束会话。
10. 只有经过原始 Flash/文件系统擦写、sync、双元数据页和掉电注入测试后，才启用持久化并更新能力位。

## 真机操作步骤

1. 在确认的硬件工作树构建并烧录；保存构建日志、commit、SDK 版本与镜像哈希。
2. 用 nRF Connect/LightBlue 确认诊断服务仍存在，新 Sync Service 五个 UUID 可发现，默认 MTU 23 与协商 MTU 都能工作。
3. 读取 Protocol、Device Info、Motion Status；确认序列号与 Web 已绑定设备一致。
4. 静止 5 分钟验证无明显虚假步数，再步行已知步数，记录原始计步寄存器、motion 输出和历史记录。
5. Windows 执行 `velapet-bridge scan` 与 `sync`，观察 scanning/discovered/connecting/connected/syncing/success。
6. 检查 PostgreSQL `activity_records.source='hardware'`、`sync_logs.transport='ble_bridge'`，刷新用户端与管理端。
7. 在 HTTP 提交后、BLE ACK 前主动断开，再连接同步；应得到 duplicates 且总步数不增加。
8. 缺片、CRC 错误、ACK 丢失、桥接崩溃和队列满分别做故障注入。
9. 断电恢复测试必须在持久化适配器完成后单独进行；当前 RAM 候选在断电后会丢数据。

## Flash 寿命建议

128 × 28 字节记录约 3.5 KiB，连同游标约 4 KiB RAM。若后续使用 Flash，按 16–32 条批量追加、双元数据页轮换，避免每一步或每分钟擦写；目标擦写寿命必须依据实际 Flash 分区和器件数据手册重新计算。
