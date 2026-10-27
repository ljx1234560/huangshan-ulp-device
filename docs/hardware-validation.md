# Huangshan hardware validation status

Last updated: 2026-10-23

This file records evidence from the exact connected board. `PASS` means the listed evidence was obtained; it does not imply that every mode of the component has been tested. `PARTIAL` means initialization or a limited path worked. `PENDING` means no reliable end-to-end test has been completed. `BLOCKED` identifies a missing prerequisite rather than a hardware failure.

The current board runs the project LVGL UI + BLE firmware, built from SiFli-SDK 2.4.6 (`ce200146`). The original 16 MiB flash image was saved before the first write at `releases/factory-20261022-full.bin` (SHA-256 `9425D8C0FC25BB8190956D842DE0377B011FF1B5F38DD6239E242220DECAF2C5`).

| Component | Status | Evidence | Remaining work |
| --- | --- | --- | --- |
| USB power and CH340 UART | PASS | COM8 enumerated as CH340; RTS reset and bidirectional shell at 1,000,000 baud succeeded | Repeat after cable/host changes |
| HCPU, LCPU clock tree, heap | PASS | `sysinfo` reported HCPU 240 MHz, LCPU 48 MHz; heap query succeeded | Add long-run and low-power tests |
| Boot flash and image loading | PASS | Project bootloader and flash table were previously verified; the current 846,904-byte BLE/UI main image (SHA-256 `8B1E961206CBF8B673E38B75BE2104E08B768CD733E442F22DB5AB024C8E7E21`) was written to `0x12020000`, booted, and accepted shell commands | Exercise restoration from the captured factory image |
| RTC initialization | PARTIAL | RTC initialized from LXT during every observed boot | Verify time retention and alarm wakeup |
| AMOLED display and GPU path | PARTIAL | Product firmware initialized CO5300, framebuffer, GPU, and LVGL; the first frame completed, the LCD entered `ON`, and UI updates ran without a fault | Human confirmation that the VelaPet page is visible, correctly oriented, artifact-free, and readable; then test brightness and sleep/wake |
| Capacitive touch | PARTIAL | FT6146 opened successfully; injected clicks at button centers triggered TASK, FEED, and CHAT callbacks and changed the live UI state | Confirm physical finger input, coordinate edges, gestures, and sleep/wake |
| LSM6-series accelerometer | PASS | Five live XYZ samples were plausible for a stationary board, with magnitude near 1 g | Movement/orientation and calibration tests |
| LSM6-series gyroscope | PASS | Five live XYZ samples were near 0 dps while stationary | Controlled rotation and calibration tests |
| LSM6-series step counter | PARTIAL | Five reads succeeded and reported zero while stationary | Walk a known number of steps and verify increments/reset semantics |
| MMC56x3 magnetometer | PASS | ID 0x10 initialized; five live XYZ samples were returned | Rotation response and calibration test |
| LTR303 ambient light | PARTIAL | I2C discovery, configuration, registration, and model information succeeded | Capture changing raw/lux readings under covered and lit conditions |
| Internal writable filesystem | BLOCKED | `/dev` mount initialized, but `df` returned `dfs_statfs failed` | Select/enable a product filesystem and perform create/read/fsync/rename/remove test |
| TF card | PENDING | No card insertion or filesystem evidence collected | Insert a known card, detect, mount, read, write, sync, and unmount |
| KEY1 and KEY2 | PENDING | No KEY2 event appeared during one 60-second observation window; result is inconclusive | Capture press/release/debounce for both keys |
| RGB LED | PENDING | Pin exists in BSP, but no mapped bounded test was run | Verify colors, active level, and restore state |
| Vibration motor | PENDING | No safe diagnostic command in the current image | Confirm schematic driver/pin and run a bounded pulse |
| Microphone and speaker | PENDING | Audio devices registered; continuous 1 kHz command was intentionally not run | Use bounded record/playback with gain limit and human confirmation |
| Battery voltage and charger | PENDING | Charger appears on I2C2 in the BSP; no battery/ADC evidence collected | Check polarity, ADC scaling, charger state, USB/battery transitions |
| Bluetooth and LCPU radio | PASS | The product image advertises as `VelaPet-BLE`, accepted a phone connection, exposed its custom service, received a 4-byte write with value 1, and returned `01-00-00-00` on read. Disconnect reporting and manual advertising restart also passed. The SDK automatic-restart option is now enabled, built, flashed, and startup-tested | Phone disconnect, automatic rediscovery, and reconnect on the new image remain **unverified**; troubleshoot the Windows/Intel scan path separately; PAN/IP is not yet implemented |
| External Wi-Fi module | PENDING | User inventory identifies one Ai-Thinker ESP-01S; the module is not installed. Vendor data identifies a 3.0-3.6 V UART/GPIO device requiring a supply capable of more than 300 mA | Verify physical orientation, exact board pins, 3.3 V rail/current budget, UART ownership, enable/reset and boot straps before connection; then identify firmware and issue a bounded `AT` probe |
| Network path | PENDING | An external ESP-01S is available for the planned primary path; Bluetooth PAN remains an alternative | Bring up UART transport, Wi-Fi association, DHCP/IP, DNS and bounded HTTP/TLS; verify reconnect, credential handling and offline fallback |

## Evidence commands used

```text
version
sysinfo
free
df
list_device
list_thread
drv_lcd_test 1 1
ui_status
ble_test
ble_test start
ble_test stop
tp_ctrl click 70 346
tp_ctrl click 195 346
tp_ctrl click 320 346
sensor_cmd probe acce_lsm
sensor_cmd read 5
sensor_cmd probe gyro_lsm
sensor_cmd read 5
sensor_cmd probe mag_mmc5
sensor_cmd read 5
sensor_cmd probe step_lsm
sensor_cmd read 5
sensor_cmd probe li_ltr30
sensor_cmd info
```

The sensor evidence above was collected from the original factory image, which held sensor devices open. Its `sensor_cmd probe` therefore printed `open device failed`, while subsequent reads succeeded through the existing device instance. Each sensor test was isolated with a reboot so the shell's static probe handle could not leave the factory application in a changed state.

The current project image is a bounded UI bring-up image. `ui_status` returned `status=PASS taps=3 last=CHAT exp=40 steps=1305` after three injected clicks. This proves the LVGL event routing and screen-state update path, but injected input is not a substitute for a physical finger test.

The current image also includes a bounded BLE smoke test. A clean reboot of the new 846,904-byte image produced `stack=PASS`, `service=PASS`, and `advertising=PASS ... status=0`. The advertising window is 300 seconds and can be renewed or reopened with `ble_test start`. The SDK `is_auto_restart` option was enabled so a phone disconnect should restart the advertising activity and renew its timer via the STARTED event; this code path still needs an actual phone disconnect/reconnect test.

Host discovery was attempted with a local isolated Python environment using Bleak 3.0.2. The Windows Intel Bluetooth adapter discovered unrelated nearby BLE advertisements, but it did not discover `VelaPet-BLE`. A phone generic-BLE application successfully received `VelaPet-BLE`, independently proving over-the-air advertisement and narrowing that host problem to the Windows/Intel scan path. For connection control, the SDK's unmodified `example/ble/peripheral` image was temporarily flashed. The phone connected and displayed Generic Access, Generic Attribute, Device Information, and the example's custom primary service. The board then accepted `cmd_diss conn 24` and reported `Updated connection interval :19`, providing UART-side proof of an active bidirectional BLE connection. After the product image was restored, the phone also connected to `VelaPet-BLE`; UART reported `[ble-test] connection=PASS peer=5e:52:be:7b:d5:a2`, advertising stopped with reason 0, and connection intervals updated to 6 and then 40. The phone wrote `01-00-00-00`; UART reported `[ble-test] write=PASS length=4 value=1`, and the phone subsequently read back `01-00-00-00`. A phone-initiated disconnect produced reason 19, but the prior product image stayed `IDLE` instead of automatically restarting advertising. `ble_test start` restored advertising successfully; the new auto-restart image has not yet been retested with a phone.

The reusable host command is:

```powershell
python scripts/ble-scan.py --seconds 20 --name VelaPet-BLE
```

It requires the third-party `bleak` package. Use an isolated Python environment rather than modifying the system Python installation.

## Diagnostic firmware command plan

The product repository should provide bounded commands with consistent return lines:

```text
diag info
diag sensor all
diag light watch <seconds>
diag step watch <seconds>
diag lcd pattern <seconds>
diag touch watch <seconds>
diag keys watch <seconds>
diag rgb cycle <milliseconds>
diag vibration pulse <milliseconds>
diag storage roundtrip
diag tf roundtrip
diag battery
diag audio loopback <seconds>
diag wifi info
diag wifi at <seconds>
diag wifi scan <seconds>
diag wifi status
diag ble advertise <seconds>
diag ble pan status
```

The current first-stage BLE smoke test uses `ble_test`. On boot it requests a connectable advertisement named `VelaPet-BLE` for 300 seconds. `ble_test` prints the current stack, advertising, connection, address, and last advertising status; `ble_test start` renews an active window or reopens a stopped one, and `ble_test stop` ends it early. Advertising logs use the `[ble-test]` prefix. Host discovery or a successful connection is required before changing Bluetooth hardware status to `PASS`.

Every command must finish or time out, print one final `PASS`, `FAIL`, or `MANUAL_CONFIRM` record, and restore the component to its prior state.

