# 前端缺失 velapet_ai_bridge.h 的补交说明

## 本次定位

旧版多页面前端的 `ui_chat.c` 和 `ui_pet_image.c` 在非 Mock 模式引用 `<velapet_ai_bridge.h>`，分别调用 `velapet_ai_request_reply()` 和 `velapet_ai_request_pet_image()`。

该头文件存在于历史 AI 交付的 `backend-ai/device/include/`，并非单文件：它还引用同目录 `velapet_ai_client.h`。前端单独收到 UI 文件夹但缺少 AI device 模块或 include 路径时，会出现当前报错。

## 补交包内容和使用范围

曾单独生成本地补交包 `releases/velapet-legacy-ai-bridge-supplement.zip`，用于修复历史交付遗漏；它不属于源码提交内容，也不能在干净检出中假定存在。**不是当前 SiFli/RT-Thread AI 服务的最终实现**，不加入当前产品的 `src/SConscript`。按最新协作规范，新产品必须通过 `vp_net_*` 和 `velapet_service_*` 对接。

```text
include/ai/velapet_ai_bridge.h
include/ai/velapet_ai_client.h
include/core/vela_pet_api.h
include/core/pet.h
include/core/task.h
include/ui/velapet_ui.h
src/velapet_ai_bridge.c
src/velapet_ai_client.c
tests/bridge_test.c
tests/c_stubs/cJSON.h
README.md
```

`include/core` 是旧业务 ABI 快照，仅匹配旧实现，不取代当前产品 `src/app/velapet_core.h`。两套结构体不得混编或互相强制转换。

## 旧前端 CMake 接入

关闭 Mock 时，现有 UI CMake 需要指定：

```text
VELAPET_UI_BUILD_MOCK=OFF
VELAPET_APP_INCLUDE_DIR=<补交包>/include/core
VELAPET_AI_BRIDGE_INCLUDE_DIR=<补交包>/include/ai
```

以上仅解决头文件查找。最终应用还需把 `src/velapet_ai_bridge.c`、`src/velapet_ai_client.c` 加入编译，并提供：

- 与 `include/core` 匹配的旧业务库实现；
- 前端实际 UI 实现，头文件可使用包内 `include/ui/velapet_ui.h`；
- pthread、cJSON 和 HTTP/TLS transport 实现。

不要把 `tests/c_stubs/cJSON.h` 放进正式构建；它只用于主机语法检查。

bridge/client 源文件的 include 路径至少包含 `include/ai`、`include/core`、`include/ui` 和正式 cJSON 目录。原目录里只有一个源码清单的 `device/CMakeLists.txt` 不会自动完成链接。

主流程在业务/网络准备后初始化 bridge，在合法 LVGL 线程周期调用 `velapet_ai_bridge_poll_ui()`。所有 bridge 公共接口按旧约定从同一 UI 线程调用；退出时停 poll，再 deinit 等待线程，最后销毁业务和 UI。

## 与当前产品的差异

- 当前产品采用 RT-Thread、`velapet_state_t`，旧 bridge 使用 pthread 和 `vela_pet_get_ai_context()` 等旧接口。
- 旧图片客户端使用 `style` 自由字符串、`asset_kinds` 和固定 `/data/agent/...` 路径；当前后端要求预设 style、idempotency_key，资源由设备自行映射，状态/下载请求还需要 device_id。
- 旧 bridge 不携带当前会话/人设接口，回复缓存和输入字节限制也需重新评审。
- 所以即使补头文件后编译/链接成功，也不能声称已对接当前新后端。
- 当前真实 Seedream 生图依用户要求保持禁用。

## 前端需要回传

请明确报错来自哪一套工程，并提供分支/提交、UI CMake/SConscript 和完整缺失符号列表：

1. 旧 UI 独立构建：本补交包用于补齐历史依赖；只检查头文件不等于网络联调完成。
2. 当前黄山派产品：先统一 RT-Thread 服务契约，由端侧负责人实现新服务，前端迁移到新接口；不要用空函数伪装 AI 已接入。

## 验证范围

本次补交只做旧 bridge 的主机回归和客户端语法检查；回归中 HTTP、业务和 UI 都是假实现。不执行付费请求，不做整机/目标板构建。实际验证结果写入仓库 CHALLENGELOG。
