# VelaPet BLE Sync Protocol v1

状态：协议与主机/Fake Transport 已实现；SF32LB52 正式 GATT 服务尚未在真机编译、烧录或验证。现有四字节诊断服务必须保留，不能用它承载本协议。

## 1. GATT 定义

所有 UUID 使用同一 128 位基：

| 用途 | UUID | 属性 |
| --- | --- | --- |
| VelaPet Sync Service | `7a820001-64d7-4c8d-a4c8-7a2f6f656c61` | Primary Service |
| Control | `7a820002-64d7-4c8d-a4c8-7a2f6f656c61` | Write / Write Without Response / Indicate |
| Data | `7a820003-64d7-4c8d-a4c8-7a2f6f656c61` | Notify |
| Device Info | `7a820004-64d7-4c8d-a4c8-7a2f6f656c61` | Read |
| Transfer Status | `7a820005-64d7-4c8d-a4c8-7a2f6f656c61` | Read / Notify |

诊断服务 UUID `...0001/...0002` 保持原样。正式同步 Service 是新增服务。

Control 接收桥接命令与 ACK/NACK。Data 传输历史记录和宠物快照。Info 可在订阅前读取最小设备信息；Status 提供 idle/streaming/waiting_ack/error 与最近确认游标。

## 2. MTU 与分包

协议不假设 MTU 协商成功。每个 ATT value 都是一个完整 Frame：

```text
最大 Frame = negotiated ATT_MTU - 3
fragment payload capacity = max Frame - 16-byte header - 2-byte CRC
```

默认 ATT MTU=23 时，Frame 最大 20 字节，单片 payload 仅 2 字节但仍可工作；推荐协商 MTU 185，单片 payload 为 164 字节。消息最多 255 片。超过上限必须拆为多个 message/sequence，不能越界写入。

## 3. Frame 格式

全部多字节整数为 little-endian。

| 偏移 | 长度 | 字段 | 说明 |
| ---: | ---: | --- | --- |
| 0 | 2 | magic | `0x5056`，线上字节 `56 50`（VP） |
| 2 | 1 | version | 当前 `1` |
| 3 | 1 | message_type | 见消息表 |
| 4 | 2 | session_id | 一次 BLE 同步会话标识，允许回绕 |
| 6 | 2 | sequence | 一条逻辑消息标识，允许回绕 |
| 8 | 1 | fragment_index | 从 0 开始 |
| 9 | 1 | fragment_count | 1–255 |
| 10 | 2 | payload_length | 当前片 payload 字节数 |
| 12 | 4 | cursor | 设备持久/内存历史队列的下一记录游标 |
| 16 | N | payload | 当前片数据 |
| 16+N | 2 | CRC16 | CRC-16/CCITT-FALSE，poly `0x1021`，init `0xffff`，覆盖 header+payload |

接收方必须依次校验 magic、version、长度、片号和 CRC。CRC 不通过时发送 NACK，不得把部分数据交给 HTTP 层。

## 4. 消息类型

### 桥接到设备

| 值 | 名称 | payload |
| ---: | --- | --- |
| `0x01` | GET_PROTOCOL | 空 |
| `0x02` | GET_DEVICE_INFO | 空 |
| `0x03` | GET_MOTION_STATUS | 空 |
| `0x10` | SYNC_START | `cursor:u32, max_records:u16, flags:u8` |
| `0x11` | ACK | `next_cursor:u32, status:u8` |
| `0x12` | NACK | `sequence:u16, fragment:u8, error:u8` |
| `0x20` | GET_PET_SNAPSHOT | 空 |
| `0x7e` | PING | 可选 echo payload |
| `0x7f` | CANCEL | 空 |

### 设备到桥接

| 值 | 名称 | payload |
| ---: | --- | --- |
| `0x81` | PROTOCOL_INFO | UTF-8 JSON |
| `0x82` | DEVICE_INFO | UTF-8 JSON |
| `0x83` | MOTION_STATUS | UTF-8 JSON |
| `0x90` | HISTORY_RECORDS | `count:u16` + 固定 28 字节记录 |
| `0x91` | SYNC_COMPLETE | UTF-8 JSON 或空 |
| `0xa0` | PET_SNAPSHOT | UTF-8 JSON，允许多片 |
| `0xe0` | ERROR | UTF-8 JSON：code/message/retryable |

## 5. 运动记录

`HISTORY_RECORDS` 的每条记录固定 28 字节：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| record_id | u64 | 设备生成的单调/唯一记录 ID；与设备序列号共同唯一 |
| occurred_at_epoch_s | u32 | UTC Unix 秒；RTC 未可信时禁止上传为真实记录 |
| local_date | u32 | `YYYYMMDD` |
| timezone_offset_minutes | i16 | 例如中国标准时间 480 |
| steps | u32 | 本条记录的步数增量，不是重复累计快照 |
| active_minutes | u16 | 本条增量对应的活动分钟 |
| goal | u16 | 当日目标 |
| source | u8 | 1=hardware，2=test_injected |
| flags | u8 | bit0=时间已校准；其余保留 |

桥接层转换成现有 FastAPI JSON，并生成 `recordId=<serial>-<record_id hex>`。`test_injected` 必须原样传给后端，不能显示为真实硬件。

## 6. 设备信息与宠物快照

Device Info 最少包含：

```json
{
  "serialNumber": "VP-52U-2400168",
  "model": "SF32LB52-ULP",
  "firmwareVersion": "0.4.0",
  "protocolVersion": 1,
  "syncCursor": 42,
  "pendingRecords": 8
}
```

Pet Snapshot 使用已有后端字段：snapshotId、version、petInstanceId、name、level、currentExp、nextLevelExp、title、skins、tasks、totalSteps、streakDays、capturedAt。设备拥有等级、EXP、任务和奖励真值；桥接和 AI 不得改写。

## 7. 同步状态机

```text
DISCONNECTED
  -> CONNECTED / subscribe Data+Status
  -> GET_PROTOCOL
  -> GET_DEVICE_INFO
  -> SYNC_START(cursor=设备已确认游标)
  -> STREAMING (校验、去重、重组)
  -> HTTP_UPLOAD
  -> BACKEND_COMMITTED
  -> ACK(next_cursor)
  -> WAIT_NEXT_BATCH 或 COMPLETE
```

关键规则：

1. 只有 FastAPI 返回成功且给出 `nextCursor` 后，桥接才能 ACK。
2. BLE 断开、桥接崩溃、HTTP 失败或超时都不能删除设备未 ACK 记录。
3. ACK 丢失时设备重发；后端以 device_id + record_id 幂等，返回 duplicates 后桥接可再次 ACK。
4. 相同 session/sequence/fragment 的相同字节视为重复片并忽略；不同字节视为协议冲突并 NACK。
5. 缺片超过 8 秒，桥接 watchdog 主动枚举并 NACK 每个缺片编号；三轮等待仍未恢复则取消会话并重连。
6. 错序片可缓存重组；fragment_count/cursor 在同一消息中变化则丢弃整条消息。
7. 设备每次只允许一个 active sync session，避免两个桥接同时推进游标。

桥接使用异步流逐批消费：完整 `HISTORY_RECORDS` → 后端提交 → ACK → 继续读取。不会先把整段历史装入列表。单批最多 64 条记录，重组器同时最多缓存 4 条逻辑消息和 64 KiB 分片数据。

### 游标定义

- `device cursor`：设备历史队列的绝对游标，出现在 BLE Header、SYNC_START 和 ACK 中，可从任意非零值开始。
- `upload offset`：单个 HTTP `uploadId` 内的相对偏移，首次必须为 0。
- `ACK cursor`：本批数据库提交成功后，设备可释放到的绝对下一游标。
- `persisted device cursor`：后端已持久化的设备绝对下一游标，保存在 `devices.activity_cursor`，服务重启后仍存在。

Windows 桥接为每个 BLE 批次生成稳定的 `uploadId`，HTTP `uploadOffset=0`，同时传递该批的绝对 `deviceCursor`。HTTP 响应的 `ackCursor` 才能用于 BLE ACK；`nextUploadOffset` 不能写进设备游标。

## 8. 错误码

| 值 | 名称 | 是否可重试 |
| ---: | --- | --- |
| 1 | UNSUPPORTED_VERSION | 否，需升级桥接/固件 |
| 2 | INVALID_FRAME | 是 |
| 3 | CRC_FAILED | 是 |
| 4 | FRAGMENT_MISSING | 是 |
| 5 | CURSOR_OUT_OF_RANGE | 是，重新读 Status |
| 6 | SESSION_BUSY | 是，退避 |
| 7 | HISTORY_FULL | 否，先完成同步 |
| 8 | TIME_NOT_TRUSTED | 否，校准 RTC |
| 9 | STORAGE_UNAVAILABLE | 视情况；当前板上仍未验证 |
| 10 | INTERNAL_ERROR | 是，限次 |

## 9. 版本兼容

- 主版本位于 Frame version。未知主版本直接拒绝并返回 UNSUPPORTED_VERSION。
- JSON payload 可以新增字段，接收方必须忽略未知字段。
- 固定二进制记录只有在新主版本中才能改变长度或字段顺序。
- PROTOCOL_INFO 返回 version、minimumBridgeVersion、maxFrameSize 和 capabilities。

## 10. 安全与绑定

- BLE 名称、广播地址和 MAC 不能证明设备所有权。
- 第一次绑定继续使用现有 claim code；生产版应由设备屏幕显示一次性验证码或要求物理按键确认。当前公开固件尚未实现这个物理确认流程。
- Windows 桥接使用用户登录换取 15 分钟、单设备 Bridge Token。Token 只在内存中使用，不写固件。
- 固件不保存管理员 Token、数据库凭据或 AI Key。
- 生产环境建议在 BLE 层启用 LE Secure Connections/bonding，并在应用层对首次配对挑战签名；v1 文档只定义接口，真机安全配对尚未验证。

## 11. MCU 缓存与掉电边界

候选实现使用 128 条、约 4 KiB 的有界 RAM 环形缓存。缓存满时返回 HISTORY_FULL，绝不覆盖未 ACK 记录。普通 BLE 断开不会清空缓存。

Flash 持久化建议把记录按 16–32 条批量写入 append-only page，并使用双元数据页（generation、head、tail、CRC）轮换提交，避免逐步写 Flash。只有在板上文件系统或原始 Flash 区域经过擦写边界、同步、原子切换和掉电注入测试后才能启用。当前硬件证据仍显示文件系统不可用，因此本阶段不宣称断电恢复已经完成。
