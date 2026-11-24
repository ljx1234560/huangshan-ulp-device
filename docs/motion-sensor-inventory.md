# 黄山派运动模型：传感器与返回数据核查

核查日期：2026-11-17。目标板：`sf32lb52-lchspi-ulp`，SDK 固定版本见 `sdk.lock`。

## 结论与证据等级

板载的独立环境/运动传感器为 LSM6DS3TR-C 六轴 IMU、MMC5603NJ 三轴磁力计和 LTR-303ALS-01 环境光传感器。它们可形成五路现有 SDK 数据：三轴加速度、三轴角速度、芯片计步累计值、三轴磁场、一路光照原始通道。触摸控制器、麦克风、电源/充电状态可提供其他输入，但不属于已验证的运动传感器。板上没有列明心率、血氧、GPS 或气压传感器；SDK 的通用 Kconfig 选项不能当成板上已装器件。[立创板级清单](https://wiki.lckfb.com/zh-hans/hspi-sf32lb52/hardware/board.html)、[立创传感器示例](https://wiki.lckfb.com/zh-hans/hspi-sf32lb52/lckfb-hspi-sf32lb52/sensor.html)。

| 器件/数据流 | SDK 返回字段 | 已有实板证据 | 当前产品固件状态 | 运动模型用途 |
| --- | --- | --- | --- | --- |
| LSM6DS3TR-C 加速度 | `acce.x/y/z`，整数，SDK 计算值为 mg；附 `timestamp` | 原厂镜像静止状态五组 XYZ，合加速度接近 1 g | 未注册 | 主要原始输入：步态周期、活动强度、静止/运动区分 |
| LSM6DS3TR-C 角速度 | `gyro.x/y/z`，整数，库计算值为 mdps；`sensor_cmd` 显示时除以 1000 成 dps；附 `timestamp` | 原厂镜像静止状态五组 XYZ，接近 0 dps | 未注册 | 辅助识别手腕旋转和运动伪步 |
| LSM6DS3TR-C 计步器 | `step`，16 位寄存器累计值；附 `timestamp` | 原厂镜像静止状态五次均为 0，尚无已知步数行走验证 | 未注册 | 可作基线/交叉校验，不能直接当作已验证的真实步数 |
| MMC5603NJ 磁力计 | `mag.x/y/z`，整数；驱动标注 mGauss；附 `timestamp` | 原厂镜像识别 ID `0x10` 并返回五组三轴值；旋转响应和校准未验证 | 未注册 | 方向/姿态辅助，暂不参与步数或强度主判定 |
| LTR-303ALS-01 光照 | `light`，整数；附 `timestamp` | 原厂镜像识别和注册成功；未取得遮挡/照明变化样本 | 未注册 | 环境上下文和亮屏策略，不作为运动量 |

历史证据详见 [hardware-validation.md](hardware-validation.md)。2026-11-17 对连接在 COM8 的 CH340 串口做 RTS 重启，取得当前 VelaPet 固件启动日志；随后 `list_device` 显示 `i2c1`、`i2c2`、`i2c4` 和 UI/音频等设备，**没有** `i2c3` 或任何上述传感器。构建配置 `project/build_sf32lb52-lchspi-ulp_hcpu/.config` 中 `CONFIG_RT_USING_SENSOR` 与 `CONFIG_BSP_USING_I2C3` 均未启用。因此当前固件不能输出实时传感器数据，UI 的步数也不能视为实测值。重启后显示与 BLE 服务正常初始化；未改 Flash。

## 芯片可提供但当前数据通路未开放的信息

- LSM6DS3TR-C 芯片还支持温度、步事件、显著运动、倾斜/抬腕、唤醒、自由落体、方向、单击/双击以及 FIFO 等功能；现有 RT-Thread 封装仅注册加速度、角速度和累计步数三路。功能是否适合本板需要配置、功耗和实测验证。[ST 数据手册](https://www.st.com/resource/en/datasheet/lsm6ds3tr-c.pdf)。
- MMC5603NJ 芯片具有磁场三轴与片上温度输出；现有封装仅返回磁场三轴，未提供温度字段。[MEMSIC 数据手册](https://www.memsic.com/Public/Uploads/uploadfile/files/20220119/MMC5603NJDatasheetRev.B.pdf)。
- LTR-303ALS-01 芯片有两个光照 ADC 通道；现有封装 `LTR303_ReadVisible()` 只取 CH1 的 16 位原始值并写入 `light`，虽然元数据标为 `LUX`，**并未换算照度**。要输出 lux 须读取两路通道并按器件手册及增益/积分时间计算，随后做光照对照验证。[Lite-On 数据手册](https://optoelectronics.liteon.com/upload/download/DS86-2013-0004/LTR-303ALS-01_DS_V1.pdf)。

## 现有 SDK 封装的建模风险

以下是固定 SDK 源码的检查结果，尚未改动厂商 SDK：

1. `customer/peripherals/sensor/MMC56x3/mmc56x3.c` 的 `MMC56x3_ReadData()` 读取 8 字节，却在计算 Z 轴时访问 `buffer[8]`；Z 轴结果不可采信，且该访问越界。产品侧引入磁力计前需要安全适配并验证原始寄存器映射。
2. `customer/peripherals/sensor/LTR303/LTR303.c` 的 `LTR303_ReadVisible()` 返回 CH1 原始计数，封装却把单位标为 lux；不能直接用它做照度阈值。
3. `customer/peripherals/sensor/LSM6DSL/st_lsm6dsl_sensor_v1.c` 的轮询读取对部分底层调用未检查返回码，仍返回一条数据；采集层必须明确区分有效样本和 I2C 失败。该封装还把加速度/角速度的元数据单位写成与实际计算值不一致的枚举，应以原始读数和库换算核对。
   板上器件标称 LSM6DS3TR-C，而封装命名为 LSM6DSL；正式采集前还须核对器件 ID、寄存器兼容性和采样配置。
4. `rtos/rtthread/components/drivers/sensors/sensor.h` 在启用 RTC 时用 `time(NULL)` 作传感器 `timestamp`，分辨率为秒；运动模型应另记单调毫秒时间戳，不能用该字段估算步频或采样间隔。
5. 芯片计步值为 16 位累计计数；回绕、重启、掉电、日切换、佩戴方向与手臂摆动造成的误判都未实测。应记录原始计数和设备启动标识，再计算有界增量。

## 自研运动模型的第一版输入与验证

先实现数据采集与标注，再确定阈值/分类器。采集记录至少包含：单调时间戳、三轴加速度（mg）、三轴角速度（mdps）、芯片累计步数、采样是否成功、实际采样间隔、设备佩戴方向与测试动作标签。磁场和光照可同录但不进入第一版计步主路径。原始数据与推导结果分开保存，便于回放与复算。

第一版模型候选：用加速度模长去除重力/慢变化分量，检测有时间间隔约束的周期峰；用角速度和短窗口稳定性排除晃表、敲击及交通工具振动；以芯片计步值做对照，输出步数、步频、活动时长及置信度。运动强度和走/跑分类必须经多人的标注数据校准后再发布；距离、卡路里、心率区间目前缺少可靠输入或个体参数，不能由现有读数直接声称准确。

下一次实板测试需在产品固件中先启用 I2C3 与传感器框架，使用有界诊断命令输出五路原始样本和读错信息，并修正上述封装问题。按静置、缓慢转动、遮光/照明、已知步数步行、原地摆臂与上下楼等场景记录连续时间序列；每组保留固件版本、配置、采样率、原始日志与人工计数。完成构建、镜像大小及恢复路径审查后再烧录；当前轮次只做了只读核查与一次重启。
