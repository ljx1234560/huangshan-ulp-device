# 2026-11-24 运动模型与同步模块决策纪要

- 决策人：项目负责人（组长）
- 记录：集成统筹
- 依据：`AGENTS.md` 第 4、6、9 节；`docs/motion-model.md`；`docs/motion-handoff.md`；`host/web/docs/BLE_SYNC_PROTOCOL.md`
- 状态：第 1、3 项已生效；第 2、4 项为有条件通过

## 1. AGENTS.md 第 4 节职责修正：批准并已落实

按 2026-11-24 定版：

- 手表端负责人：**组员二**
- Web 管理端负责人：**组员三**
- 后端线：组员四；硬件线：组员一 + 项目负责人

已修改：

- `AGENTS.md` 第 4 节分工表两行负责人及 Web 行协作对象。
- `AGENTS.md` 第 4 节“手表端由组员二统一负责……组员三负责独立的 Web 管理端”。
- `AGENTS.md` 第 5 节目录职责 `host/web/` → 组员三。
- `docs/motion-handoff.md` 中 Web 口径协作对象 → 组员三。

遗留一致性项：`docs/animation-design.md:3` 仍写“负责人：组员三（前端）”。动画/UI 属手表端，应改由组员二维护；改动前需组员二确认文档内容仍然有效。

## 2. INT-1：`vp_sensor_*` 第五跨线接口（有条件批准）

结论：原则同意新增，状态为**有条件批准**。

已确认的接口基线：

- 只负责采样、时间戳与错误码，不做活动语义判断。
- 非阻塞；单消费者；不跨线程回调。
- 设备打开失败必须返回可区分错误码，运动模型可整体降级。
- 硬件线实现，手表端定义语义与验收。

未完成：评审方提出的 **3 点修改原文尚未归档**，仓库、分支和文档中均未找到。收到并确认后：

1. 在 `AGENTS.md`“关键跨层契约”中正式加入 `vp_sensor_*`（五个接口）。
2. 更新 `docs/motion-model.md` 12.1 为“已批准”。
3. 冻结 `src/services/motion_sensor.h` 的权威签名。

在完成前，实现方可按现文档签名开发，但不得对外宣称接口已冻结。

## 3. FE-1/FE-2 归属：移交硬件线

背景：手表端收缩为 1 人（组员二），板级传感器工作不再由手表端承担。

决定：

| 任务 | 新归属 | 交付 | 手表端职责 |
| --- | --- | --- | --- |
| FE-1 采样适配器与诊断命令 | 硬件线（组员一 + 项目负责人） | `vp_sensor_*`、`src/services/motion_sensor.*`、有界诊断命令 | 评审语义、验收 |
| FE-2 计步语义验证与阈值标定 | 硬件线主责 | 计步语义证据、轨迹、阈值、回放用例 | 给出验收口径、消费结果 |
| FE-3~FE-7 | 手表端（组员二） | 业务接入、任务奖励、提醒 UI、持久化、增强项 | 全部 |

已同步：

- `AGENTS.md` 硬件线边界加入运动采样适配器；手表端边界加入 `src/app/velapet_motion.*`。
- `docs/motion-model.md` 第 18 节责任表。
- `docs/motion-handoff.md` 第 1、4、9、10 节。

## 4. sf32lb52-sync 候选模块：立项有条件通过

评审对象：`host/web/firmware/sf32lb52-sync/`（`velapet_sync_protocol.*`、`velapet_history.*`、`velapet_sync_session.*`）。

验证结果：自行编译并运行候选测试，`VELAPET_SYNC_PROTOCOL_TEST result=PASS cases=3`（WSL GCC）。协议帧、CRC、绝对游标、WAIT_ACK 精确确认、满队列不覆盖等设计成立。

**结论：候选阶段通过；进入 `src/` 前必须关闭以下门禁。**

1. **记录编解码缺失**：C 模块只有帧编解码，没有 `HISTORY_RECORDS` 的 28 字节记录编解码。必须显式小端序列化，与桥接 `<QIIhIHHBB`（`host/web/tools/ble-bridge/velapet_bridge/protocol.py:27`）逐字节对齐，并用 C↔Python 黄金向量互测。
2. **ABI 与 RAM 估算**：`vp_motion_record_t` 未 packed，按常见 ABI 为 32 字节而非 28；README 的 3.5 KiB 估算偏低。改为存 28 字节线上格式或 packed + `static_assert`，重算容量与 RAM。
3. **record_id 生命周期**：后端以 device + record_id 幂等（`BLE_SYNC_PROTOCOL.md` 第 5、7 节）。必须定义重启后的单调性（boot epoch 或持久化计数器），否则重启会 409/重复。
4. **线程与所有权**：history/session 无锁，必须由 BLE worker 单线程独占；GATT 回调只校验并入队。补 pending count/cursor 访问器，避免外部直接读结构体内部。
5. **MTU/分片/NACK**：模块未实现重组与重发。worker 必须限定 frame ≤ MTU-3、≤255 片，并实现超时、缺片 NACK、三轮失败策略及测试。
6. **授权闭环**：同步服务会把历史暴露给任意 central。claim code、物理确认或 BLE bonding 必须有结论后才能在生产固件启用。

补充要求：

- 补齐测试：CRC 已知向量（`"123456789"` → `0x29B1`）、超长/截断帧、未知消息、队列满、游标缺口、长流、跨语言回环。
- `HISTORY_FULL` 需映射为错误码 7，并提供 Device Info/Status 可见的 pending 信息。
- 归属：不再以 `host/web` 为产品归属；评审通过后迁入 `src/services/sync/`，加入 SConscript 与单测脚本，按“后端定协议、手表端定数据语义、硬件线做 GATT 传输”走一次正式跨线评审。

## 5. 待办与责任

| 编号 | 事项 | 负责 | 期限 |
| --- | --- | --- | --- |
| A-1 | 提交 `vp_sensor_*` 3 点修改原文 | 提出评审的组员 | 立即 |
| A-2 | 确认 `vp_sensor_*` 修改并写入正式契约 | 项目负责人 + 集成 | 收到后 |
| A-3 | FE-1/FE-2 计划与排期（驱动、诊断、标定） | 硬件线 | 本周 |
| A-4 | 关闭 sync 模块 6 个门禁并提交评审包 | 组员三（同步协议）+ 硬件线（GATT） | 进 `src/` 前 |
| A-5 | 更新 `docs/animation-design.md` 负责人 | 组员二确认后 | 本周 |

## 6. 本次仓库变更

- `AGENTS.md`：职责修正、边界补充。
- `docs/motion-model.md`：接口状态、责任表。
- `docs/motion-handoff.md`：归属、依赖、分支命名、INT-1 状态。
- 新增本纪要。
- 未改任何固件源码；未构建、未烧录、未接触开发板。
