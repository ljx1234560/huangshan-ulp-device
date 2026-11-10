# ui_ai_bridge 对接答疑

> 收件人：组员四、项目负责人。逐条回复《VelaPet 前端对接说明》P0-2 / P0-3 的问题。
> 全部以 `feat/frontend-ui` 分支的 `src/ui/ui_ai_bridge.h` / `ui_ai_bridge.c` / `ui_chat.c` 现有实现为准。接口冻结前如有异议，改此文档批注即可。

## P0-2 信箱语义

| 问题 | 答复 |
| --- | --- |
| 结构体与字段容量 | `ui_ai_request_t`：`request_id(u32)`、`kind(枚举)`、`max_chars(u32)`、`text[721]`（240 字符 × 3B UTF-8 + NUL）。`ui_ai_result_t`：`request_id`、`source(枚举)`、`error_code(i32)`、`intent[16]`、`emotion[16]`、`conversation_id[48]`、`persona_id[48]`、`reply[384]` |
| 返回值 | `ui_ai_bridge_take_request()`：1=取到请求 / 0=无请求。`ui_ai_bridge_push_result()`：1=已入箱 / 0=丢弃（request_id 不匹配或无在途请求时丢弃，调用方无需处理） |
| 调用线程 | `take_request` / `push_result` **仅限 AI 服务线程**；`submit` / `poll_result` / `cancel_pending` **仅限 LVGL 主线程**。跨线程使用为未定义行为 |
| 满槽行为 | **单在途模型，无多槽**。已有在途请求时 `ui_ai_submit()` 返回 `UI_AI_SUBMIT_BUSY`，页面 toast 提示"上一条还在处理"，不产生第二条等待 |
| 关联请求 | `request_id` 由信箱分配，你原样带回。重试 = 新 UI id。迟到/重复回包因 id 不匹配在 `push_result` 处被丢弃，**不会清除新请求的忙碌状态**（你要求的语义已实现） |
| 线程同步 | 信箱内部用 RT-Thread 临界区保护，临界区内只做短状态更新与按值复制；网络等待全部在你线程 |
| 缓冲与中文 | 输入 240 字符（ASCII 即 240 字节，符合你的约定），建议 `max_chars=50`。回复缓冲 384B ≥ 你要求的 201B。截断与缺字替换均按**完整 UTF-8 字符**处理：渲染前逐字 `lv_font_get_glyph_dsc` 校验，缺字形替换为 `?` |

## P0-3 聊天页 UI 行为

| 状态 | 页面行为 |
| --- | --- |
| 等待 | 提交成功后显示等待气泡（"思考中…"） |
| 离线 | 正式模式未接服务时 `submit` 返回 `OFFLINE`，气泡显示"AI 服务未接入" |
| 超时/失败 | 你侧超时后投递 `source=ERROR`、`error_code≠0`，页面显示失败样式 + **重试按钮** |
| 重试 | 按原 kind/text 重新 `submit`，使用新 request_id |
| 忙碌 | `BUSY` 时仅 toast 提示，不追加等待气泡 |
| 取消/退出 | 切页或退出调 `ui_ai_cancel_pending()`：在途 id 作废，你迟到的回包被丢弃；**退出后旧回复不渲染到新页面** |
| 降级 | `source=LOCAL_FALLBACK` 且有 reply → 气泡正常显示并标注"来自本地降级"；`ERROR` → 失败样式 |

## P0-1 快照

- `feat/frontend-ui` 分支即新版前端快照：`src/ui/ui_ai_bridge.h/.c`、`src/ui/ui_chat.c`（提交与轮询调用点）、`src/ui/velapet_ui.c/.h`（入口 `velapet_ui_init()`）、`src/app/velapet_service.h/.c`（`velapet_service_snapshot()` 声明与实现）、`src/main.c`（初始化入口）。
- 构建命令 `scripts/build.ps1`；板型 T113S3，SDK 版本号由负责人补充（本机无 SDK，未能记录）。
- 测试基线：`scripts/test-unit.ps1` 通过 core 5 例 + service 6 例。

## 联调顺序（同意你的安排）

1. 编译期定义 `VELAPET_UI_AI_MOCK` 用模拟应答验收四个快捷键、ASCII 输入、中文回复与缺字替换。
2. 边界验收：连点拒绝、超时重试、退出重进、迟到回包。
3. 接 BLE 桥接真实链路，用真实业务快照发快捷消息，分别记录 `LOCAL_FALLBACK` 与 `CLOUD` 来源及显示结果。

## 附：主机 API 现状

聊天（DeepSeek `deepseek-flash`）与生图（方舟 `doubao-seedream-5-0-pro-260628`）均已实测 HTTP 200。密钥在 `host/ai-backend/.env`（不入库）。生图接口实现仍为你的 P1 工作项，`.env` 的 `ARK_*` 段可直接读取。
