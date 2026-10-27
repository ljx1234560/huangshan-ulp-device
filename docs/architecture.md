# Architecture

## Platform decision

The product firmware targets SiFli-SDK 2.4.x with RT-Thread on `sf32lb52-lchspi-ulp`. The earlier openVela/NuttX competition target is retired. Historical code may supply product rules, UI concepts, and network protocols, but its operating-system integration is not authoritative.

The vendor SDK remains an external pinned dependency. Product code belongs in this repository and is divided into application rules, services, drivers, UI, platform adaptation, and diagnostics.

## Runtime structure

```text
Windows development and test tools
        |
        | CH340 UART at 1,000,000 baud
        v
SF32LB52 HCPU running RT-Thread
        |
        +-- VelaPet application rules and persistence
        +-- LVGL display and touch UI
        +-- IMU, magnetometer, ambient-light and step inputs
        +-- audio, keys, RGB LED and vibration feedback
        +-- local flash and optional TF-card storage
        +-- network transport service
                    |
                    +-- primary: UART -> external ESP-01S -> 2.4 GHz Wi-Fi
                    |
                    +-- alternative: Bluetooth/LCPU -> phone or host PAN
                    v
             VelaPet backend and AI services
```

The Huangshan board does not provide native Wi-Fi. The project has purchased an external Ai-Thinker ESP-01S module, but it is not installed or electrically validated yet. Once its power and UART wiring are documented, it is the planned primary network adapter; Bluetooth PAN remains an alternative transport. Network users must depend on a transport-neutral service rather than calling ESP AT commands or Bluetooth APIs directly. The firmware must remain useful offline: movement tracking, pet growth, tasks, rewards, cached assets, and the UI cannot depend on a live backend.

The ESP-01S requires a dedicated installation and bring-up gate described in `docs/wifi-esp01s.md`. Do not reuse the UART1 debug console for product networking unless the loss of flashing and shell access is explicitly designed and a recovery path exists.

The existing custom BLE GATT characteristic is a diagnostic four-byte read/write path, not a network connection. The concrete backend contract and RT-Thread AI migration order are documented in `docs/ai-integration.md`.

The first offline domain slice now lives in `src/app/velapet_core.*`. It owns the
canonical in-memory pet profile, daily tasks, experience thresholds, streaks,
and skin unlocks. It deliberately accepts a caller-supplied local calendar day
instead of calling a platform clock, and it performs no allocation or I/O. An
RT-Thread application service will own this state and connect it to the clock,
storage adapter, sensor input, and LVGL UI in later slices.

## Legacy source intake

The historical `member_code` directory contains three useful categories:

- Platform-independent VelaPet rules: pet state, tasks, rewards, and JSON schemas.
- LVGL/BandX UI ideas and assets that require integration with the SiFli display stack.
- Backend and device protocol code that requires a board-specific RT-Thread transport, initially targeting the external ESP-01S while keeping Bluetooth PAN replaceable.

During migration, remove openVela/NuttX build definitions and replace POSIX-only lifecycle assumptions where RT-Thread primitives are clearer. Replace `/data/agent/...` with a product storage layout selected after the board filesystem is validated. Keep a single canonical set of public data structures.

## Validation architecture

Hardware diagnostics expose bounded serial commands with stable output. Host scripts invoke those commands, apply timeouts, collect evidence, and leave the board in a known state. Manual observations remain explicit for display quality, touch, buttons, audio, and power measurements.

