# Huangshan ULP Device

立创·黄山派 SF32LB52-ULP 的产品级软硬件开发仓库。仓库以 `sf32lb52-lchspi-ulp` 为唯一默认目标板，覆盖固件、硬件版本、机械结构、生产资料和硬件在环测试。

## 本机开发环境

- 产品仓库：`E:\projects\huangshan-ulp-device`
- SiFli-SDK：`E:\projects\OpenSiFli\SiFli-SDK`
- SDK 工具：`E:\SIFLI\tools`
- 默认板型：`sf32lb52-lchspi-ulp`
- 调试串口：1,000,000 baud

机器路径保存在被 Git 忽略的 `.env.local.ps1` 中。团队成员可复制 `.env.example.ps1` 并按自己的电脑修改。

## 快速开始

在 PowerShell 中运行：

```powershell
cd E:\projects\huangshan-ulp-device

# 检查 SDK、工具链和串口
.\scripts\doctor.ps1

# 编译黄山派固件
.\scripts\build.ps1

# 查看可用串口
.\scripts\ports.ps1

# 烧录；必须明确目标串口，脚本还会要求确认
.\scripts\flash.ps1 -Port COM12

# 查看运行日志
.\scripts\serial-monitor.ps1 -Port COM12
```

如果需要在当前终端手工使用 `scons`、`sdk.py` 等命令，请点调用环境脚本：

```powershell
. .\scripts\env.ps1
```

## 目录职责

- `project/`：SCons、Kconfig 和固件构建配置。
- `src/`：产品固件源代码。
- `boards/`：未来自研 PCB 所需的项目级 BSP；当前直接使用 SDK 自带黄山派 BSP。
- `hardware/`：参考设计、自研 PCB、BOM 与生产文件。
- `mechanical/`：外壳和装配设计。
- `scripts/`：环境、构建、烧录、串口和自动检查。
- `tests/`：单元测试与硬件在环测试。
- `docs/`：架构、上电、测试和权限说明。

当前固件已启动 LVGL 交互页和 `VelaPet-BLE` 自定义 GATT 诊断服务；它还没有通过 ESP-01S 或 Bluetooth PAN 接入互联网。`src/app/velapet_core.*` 已提供不依赖 RT-Thread、文件系统和网络的离线宠物/任务/奖励规则，并可通过 `.\scripts\test-unit.ps1` 在主机验证；该核心尚未绑定到当前演示 UI 或持久化层。产品自有的最小文本 AI 后端位于 `host/ai-backend/`，支持 DeepSeek、MiMo、设备 Token、限流和本地降级，可用 `.\scripts\test-ai-backend.ps1` 验证。主机端已用低成本 `deepseek-flash` 完成一次真实短文本回复；开发板仍需独立完成 IP 网络链路。硬件证据见 `docs/hardware-validation.md`，AI 后端接口与端侧迁移路线见 `docs/ai-integration.md`。历史 `member_code` 仅作为迁移参考，不是当前可直接烧录的 RT-Thread 应用。

