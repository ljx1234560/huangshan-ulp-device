# 默认形象与暂缓真实生图

## 当前决定

按 2026-11-03 用户要求，先完成图片接口和本地资源流程，暂不实测 Seedream。新增默认关闭的 `VELAPET_IMAGE_GENERATION_ENABLED=false`。即便已有方舟 Key 且 provider=seedream，提交仍返回 503 / IMAGE_GENERATION_DISABLED；只有明确决定实测时才改为 true。

电脑端先用三款原创矢量候选形象：星云猫（默认）、奶油犬、薄荷兔。预览、PNG 导出和形象选择均不调用模型。选择外观独立于等级、奖励皮肤和聊天人设。

## 新接口

配置鉴权时带 X-VelaPet-Token：

| 接口 | 内容 |
| --- | --- |
| GET `/api/v1/default-pets` | 三款默认形象、默认 ID、PNG 清单/大小/哈希 |
| GET `/api/v1/default-pets/{id}/{kind}.png` | avatar/home/skin 本地渲染的 PNG |
| GET `/api/v1/appearance?device_id=...` | 获取设备的默认形象选择，缺省 nova-cat |
| PUT `/api/v1/appearance` | JSON：device_id、pet_id；保存选择 |
| GET `/api/v1/image-capabilities` | provider、generation_enabled、paid_generation、styles、max_upload_bytes |

选择存储在已有 SQLite，按设备 ID 和凭证摘要隔离。固件尚未消费这些接口；设备上最终资源目录由硬件适配方确认。默认资源不依赖云端生成，可导出后随设备资源部署。

## 电脑端使用

按 `ai-desktop-guide.md` 启动后端和桌面程序。默认形象下拉框支持离线预览，保存/加载选择需要本地后端。暂不点击照片生成；即便误点，禁用开关也会阻止 Seedream 请求。

照片处理和任务代码已具备：上传限制、异步任务、重复提交保护、下载清单、大小和 SHA-256 校验、重启中断处理。只在测试替身/demo 模式验证过，不意味着真实模型参数、生成质量或账号额度已经验证。

## 已验证与未验证

- DeepSeek：本轮仅一次真实短文本请求，deepseek-flash 返回 source=deepseek、error_code=null，已证实本机聊天密钥和模型可以调用。
- Seedream：本轮实际调用次数 0，测试仅使用本地替身。
- 默认素材：本地预览已检查；PNG 解码、尺寸/哈希、选择持久化及凭证隔离纳入回归测试。
- 板端：尚未修改固件、配置字库或连接网络/存储驱动；没有烧录。SDK 配置、网络 API、文件系统和 RAM 情况仍待提供。

## 后续待确认

前端确认：选哪款为最终默认、主页形象区域、中文字体和结果事件接口。

硬件确认：联网类型和 HTTP/TLS API、挂载点/资源分区、空闲 RAM/PSRAM、PNG 解码器；语音另需 PCM 接口、采样率/位深/声道。

用户后续决定：何时允许真实 Seedream 测试及上限，提供授权参考照片；在此之前保持付费生图禁用。
