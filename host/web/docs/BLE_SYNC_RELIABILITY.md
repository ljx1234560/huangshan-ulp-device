# BLE 同步可靠性修复记录（阶段 3.5）

## 数据流

```text
完整 BLE 批次
  -> CRC/分片重组
  -> HTTP uploadOffset + deviceCursor
  -> 数据库事务提交
  -> ackCursor
  -> BLE ACK
  -> 设备发送下一批
```

桥接使用异步生成器逐批处理，任何时刻业务层只持有当前批次。重组层最多缓存 4 条未完成消息和 64 KiB 数据；单批默认最多 64 条运动记录。

硬件记录只有在协议 `flags.bit0`（时间已校准）置位时才会转换成 `rtcTrusted=true` 并上传；桥接和 FastAPI 都会拒绝 RTC 未可信的 `hardware` 记录。该标志同时写入数据库并参与幂等内容比较。

## 游标不变量

1. 设备游标是绝对值，可以从 100、10000 等任意合法值开始。
2. 新 `uploadId` 的 HTTP 偏移必须从 0 开始。
3. 同一上传任务续传时，`deviceCursor == taskStartDeviceCursor + uploadOffset`。
4. 后端拒绝领先于持久化游标的缺口；允许已持久化区间的字节等价重放。
5. 相同 recordId 但内容不同返回 409，不能静默当作重复。
6. 后端在 `devices.activity_cursor` 保存持久化绝对游标，进程重启不会归零。
7. 只有响应中的 `ackCursor` 可以发送给设备。

## 故障行为

- HTTP 超时：使用相同 uploadId、偏移和记录重试；若首次已提交，后端验证重放内容后返回 duplicate。
- BLE ACK 丢失：设备重发相同绝对游标；即使 BLE session/uploadId 变化，recordId 幂等仍阻止重复累计。
- 单批失败：不 ACK，重连后从设备未确认游标恢复。
- 缺片：watchdog 返回所有缺失 fragment index 的 NACK；三轮等待无数据后重连。
- BLE 断开：桥接上报 connected=false；最近同步结果单独保留。
- 桥接退出：上报 running=false；不能把最近同步成功显示成当前在线。
- 重新绑定：旧用户 uploadId 不能由新绑定用户继续。

## 尚待真机验证

Fake Transport 和伪 Bleak Client 只能验证协议状态机。LE Secure Connections、设备身份挑战、实际 MTU、通知节奏、射频丢包、真实计步与 Flash 掉电恢复仍必须在 SF32LB52 真机执行。
