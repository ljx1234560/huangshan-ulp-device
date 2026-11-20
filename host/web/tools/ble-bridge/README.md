# VelaPet Windows BLE Bridge

该程序把正式 VelaPet BLE 同步协议转换为现有 FastAPI 设备上传 API。它不会把设备名称或 MAC 当作所有权依据；用户必须先在 Web 完成设备绑定，桥接程序再用用户邮箱/密码换取短期、限定设备的 Bridge Token。

```powershell
Set-Location 'E:\projects\huangshan-ulp-device\host\web'
py -3.12 -m venv tools\ble-bridge\.venv
tools\ble-bridge\.venv\Scripts\python.exe -m pip install -e 'tools\ble-bridge[dev]'

tools\ble-bridge\.venv\Scripts\velapet-bridge.exe scan --seconds 10
tools\ble-bridge\.venv\Scripts\velapet-bridge.exe sync `
  --address '<扫描结果中的地址>' `
  --serial 'VP-52U-2400168' `
  --email 'demo@velapet.cn' `
  --api-url 'http://localhost:8000'
```

密码通过隐藏输入读取，不写配置文件。桥接逐批执行“BLE 重组 → FastAPI 提交 → ACK”，不会一次缓存全部历史；只有数据库确认 `ackCursor` 后才发送设备 ACK。分片缓存限制为 4 条逻辑消息/64 KiB，超时 watchdog 会按缺片编号发送 NACK。日志状态包括扫描、发现、连接、同步、成功、失败与断开。

设备绝对游标、HTTP 上传偏移、ACK 游标和数据库持久化游标是四个独立概念。桥接不会再把非零设备游标直接当成新 HTTP 任务偏移。

完整协议见 `docs/BLE_SYNC_PROTOCOL.md`。没有手表时使用测试中的 `FakeBleTransport`，但 Fake 测试不是真机 BLE 证据。
