# 聊天信箱与生图联调：组员四交付

共同仓库基线：main 的 5863e0a。已核对《ui_ai_bridge 对接答疑》与实现，认可冻结 src/ui/ui_ai_bridge.h，不改结构体、枚举和函数签名。

## 聊天联调

工作线程从 ui_ai_bridge_take_request() 取件，以提交时由 LVGL 主线程复制的业务快照调用 vp_net_chat 适配器，再通过 ui_ai_bridge_push_result() 投回使用原 UI request_id 的结果。LVGL 原有定时器继续负责渲染。服务不存在或链路未就绪时，提交即时返回 OFFLINE；掉线、超时或响应无效则推送 ERROR。页面退出清空已经完成但还未显示的结果，旧回包不会解除新请求的忙碌状态。UI mock 不启动网络线程。

服务协议在 src/services/vp_net_chat.h。硬件端把已跑过的 GATT 实现接到 vp_net_chat_platform()，ready() 提供缓存的链路状态，exchange() 在工作线程执行一次有界往返（预算 35 秒）。C 层返回 0 表示已取得可渲染回复（包括本地降级），负数 -1/-2/-3 分别是超时、离线、回复无效。HTTP 失败可原样传递非零状态码。手表请求 ID 单独回传，服务端生成的字符串 ID 不用于配对。

Windows GATT 桥接收到完整请求后可复用 host/ai-backend/velapet_backend/chat_relay.py 的 ChatRelayClient.exchange(ui_request_id, payload)。payload 使用 /api/v1/chat 的 schema，带 device_id、prompt_type、message、上下文和 max_chars；不要从 total_steps 推导今日步数。回包 source 为 cloud、local_fallback 或 error，按冻结头文件映射枚举；字符串字段按 UTF‑8 编码、NUL 终止。只有会话 ID 原样合法可容纳时才回传。传输权限、GATT UUID、分片和重连规则以组员一已验收的实现为准。

当前 main 的 BLE 文件只有 4 字节诊断特征，未包含硬件交接提及的 host/ble-ai-bridge/bridge.py 和对应固件源码。本交付刻意保留其诊断通道，请组员一或负责人提供跑通版本和分片约定后再绑定适配器。板型以 sdk.lock 为准：sf32lb52-lchspi-ulp，不使用答疑里写的 T113S3。工作线程栈 4096 字节是初始配置，需与实际 BLE 适配器一起测高水位。

## 生图联调

- 后端从忽略的 .env 读取 ARK_API_KEY、ARK_API_BASE_URL、ARK_IMAGE_MODEL。三项均配置时默认选择 Seedream；如果现有配置显式设了 VELAPET_IMAGE_PROVIDER=demo 或 VELAPET_IMAGE_GENERATION_ENABLED=false，仍以显式开关为准。旧 SEEDREAM_MODEL 保留兼容，优先使用 ARK_IMAGE_MODEL。
- GET /api/v1/image-capabilities 看配置；POST /api/v1/pet-assets/jobs 接收 multipart（file、device_id、style、idempotency_key）。GET /api/v1/pet-assets/jobs/{job_id}?device_id=... 查状态，到 succeeded 后根据 manifest 的 download_url 下载 avatar、home、skin（同一个 device_id 和设备 Token）。
- 方舟响应直接接收 Base64 图像字节。后端限制体积、解码校验，然后将三份 PNG 原子写入，并在下载前复核 byte_size 和 sha256。设备消费方下载后也要比对 manifest，再原子替换已验证的本地路径。损坏资源返回 ASSET_INTEGRITY_FAILED，页面保留原图。上游生成超时不自动重试，避免重复扣费。
- 手表图片落盘和 LVGL 解码仍待硬件提供通过验证的可写路径和缓存刷新联调。本次后端下载验证不代表真机落盘已通过。

## 验证命令

- PowerShell: .\scripts\test-ai-backend.ps1；之后用测试环境的 Python 运行 host/ai-backend/tools/smoke_http.py。
- PowerShell: .\scripts\test-ai-mailbox.ps1；主机 GCC + RT-Thread/LVGL 测试替身，验正式信箱和 mock 两种模式。
- 硬件组：配置 sdk.lock 锁定的 SDK 后运行 .\scripts\doctor.ps1、.\scripts\build.ps1，再用板子跑快捷消息、离线、掉线重连、本地降级及一条云回复。
