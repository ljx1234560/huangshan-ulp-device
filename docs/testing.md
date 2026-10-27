# Test strategy

## Evidence levels

Use the narrowest accurate status:

- **Enumerated:** the host or RT-Thread can see a device.
- **Initialized:** the driver completed initialization and identity checks.
- **Functional:** a meaningful read/write or stimulus/response test succeeded.
- **Manually confirmed:** a person verified a visible, audible, tactile, or electrical result.

Do not promote enumeration or compilation to a functional hardware pass.

## Host-side checks

- SDK and toolchain activation.
- Serial-port enumeration and unambiguous board selection.
- Firmware image presence and address mapping before flashing.
- Serial command/response timeouts.
- Collection of the final firmware version and reset reason.
- Portable VelaPet domain rules via `.\scripts\test-unit.ps1`, compiled as C11
  with warnings treated as errors.

## Firmware diagnostics roadmap

The diagnostic firmware will expose bounded commands for:

- GPIO and key state
- I2C bus scan
- LSM6-series accelerometer, gyroscope, and step samples
- MMC56x3 magnetometer identity and samples
- LTR303 ambient-light samples
- LCD color bars and touch coordinates
- microphone level and bounded speaker playback
- RGB LED and vibration motor
- internal filesystem and TF-card round trips
- battery voltage, charger state, and low-power measurements
- external ESP-01S power/reset, UART/AT response, Wi-Fi scan, association, IP, DNS, and bounded HTTP/TLS requests
- Bluetooth advertising, connection, and PAN status

Expected output and cleanup behavior must be documented before a command is automated. Commands must restore temporary state and must not run indefinitely.

## Test layers

- Host unit tests cover platform-independent pet, task, reward, serialization, and protocol logic.
- Firmware integration tests cover RT-Thread threads, synchronization, storage adapters, and service lifecycles.
- Hardware-in-the-loop tests cover board drivers, the external ESP-01S, and real peripherals.
- Manual acceptance covers display quality, touch feel, buttons, sound, vibration, RF pairing, charging, and current consumption.

Current board evidence and remaining checks are maintained in `docs/hardware-validation.md`.

