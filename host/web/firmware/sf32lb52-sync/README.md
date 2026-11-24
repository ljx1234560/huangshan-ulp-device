# SF32LB52 同步固件候选模块

这里是依据公开硬件仓库当前接口编写的、平台无关且可做主机测试的候选模块。它没有直接写入临时下载的硬件仓库，因为本机不存在仓库规定的真实工作目录 `E:\projects\huangshan-ulp-device`，也没有确认本机 SiFli-SDK/板卡环境。

模块用途：

- `velapet_sync_protocol.*`：与 Windows 桥接完全相同的帧头、CRC16 和分包语义。
- `velapet_history.*`：128 条有界 RAM 历史记录；只有收到后端成功后的 ACK 才释放记录。
- `velapet_sync_session.*`：绝对游标与 `STREAMING/WAIT_ACK` 状态机；每批必须收到精确 ACK 后才允许读取下一批。
- `tests/sync_protocol_test.c`：协议与缓存主机测试。

集成到真实固件时应：

1. 保留现有 `ble_service.c` 的诊断 Service/Characteristic。
2. 在 `src/services/` 新增这些文件，并用 SiFli `BLE_GATT_SERVICE_DEFINE_128` 注册文档中的五个正式同步特征。
3. BLE 写回调只做帧校验和投递；历史读取、重传和 ACK 处理放到现有 BLE worker，不能阻塞回调或 LVGL 线程。
4. 真实 LSM6 计步适配器读取累计计步值后调用现有 `velapet_motion_feed_steps()`；再把 `velapet_motion_take_steps()` 和活动分钟增量写入 `vp_history_append()`，来源必须是 `VP_RECORD_SOURCE_HARDWARE`。
   只有 RTC 已由可信时间源校准后才能同时设置 `VP_RECORD_FLAG_TIME_TRUSTED`；否则桥接和后端会拒绝该硬件记录。
5. 自动化注入使用 `VP_RECORD_SOURCE_TEST_INJECTED`，不得在 UI/后端显示成真实硬件数据。
6. 当前缓存仅保证普通 BLE 断开不丢未 ACK 数据；掉电会丢失。只有板上可写文件系统完成 create/write/sync/atomic rename 验证后，才能实现并宣称断电持久化。

建议的 MCU 资源：128 × 28 字节记录约 3.5 KiB，加元数据约 4 KiB。满且全部未 ACK 时应停止覆盖并报告 `VP_HISTORY_FULL`，不能静默丢最旧数据。
