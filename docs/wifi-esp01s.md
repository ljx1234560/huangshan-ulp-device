# External ESP-01S Wi-Fi bring-up

## Status

- Module: Ai-Thinker ESP-01S, one unit identified from the user-provided purchase image.
- Board relationship: external accessory; it is not native or onboard Wi-Fi.
- Current state: not installed, not powered from the Huangshan board, and not functionally tested.
- Planned role: primary network adapter for backend and AI traffic. Bluetooth PAN remains an alternative transport.

## Verified module facts

The Ai-Thinker ESP-01S product specification identifies an 802.11 b/g/n 2.4 GHz module with UART/GPIO interface, 3.0-3.6 V supply range, required supply capability above 300 mA, and a default UART baud rate of 115200. The installed firmware and supported AT command version of the purchased unit are still unknown.

## Purchased cable assessment

The purchased cable is listed as `XY-GH1.25-28B-200-DD3-2A`: GH1.25 2-pin, UL1571 28 AWG, 200 mm, red/black, with one end stripped and tinned for 3 mm. This is only a two-conductor pigtail; its part number does not assign it to a power, battery, speaker, or data function.

- It cannot connect the ESP-01S. The module is DIP-8 and a usable UART installation requires at least 3.3 V, GND, TX, RX, and EN, plus access to reset and boot-strap signals for recovery.
- The Huangshan speaker socket is GH1.25 2-pin, and the purchased 30 mm 8-ohm/2-watt speaker is also advertised with a GH1.25 lead. If the physical speaker already has the matching plug, connect that plug directly to the board socket marked `SPK`; the extra red/black pigtail is not needed.
- The Huangshan battery socket is also GH1.25 2-pin, but it is a different circuit. Never identify it by fit alone. A battery connection must use a suitable protected single-cell lithium battery and must match the `+`/`-` polarity printed on the board. Do not insert this loose pigtail into the battery socket for experimentation.
- The 30-pin expansion connector is a 2x15, 1.27 mm-pitch header, so the GH1.25 pigtail does not mate with it. Pins 25 and 27 are the board's debug UART TX/RX and are already used for download/debug; they are not yet approved as the permanent ESP UART.

For ESP-01S bring-up, obtain a keyed ESP-01/ESP-01S DIP-8 socket or breakout, preferably an ESP-01 programmer/adapter with a proven regulated 3.3 V supply and local decoupling. A separate 3.3 V USB-UART adapter is recommended for the first independent AT test. Do not apply 5 V directly to the ESP-01S. The exact permanent Huangshan-side UART and connector remain pending pin-mux and power-budget validation.

## Installation gate

Do not connect or power the module until every item below is resolved and recorded:

1. Photograph and identify the module, any adapter/socket, and the intended Huangshan expansion connector from both sides.
2. Map ESP-01S VCC, GND, TX, RX, EN, RST, GPIO0, and GPIO2 to exact board nets and pins. Confirm orientation instead of relying on connector shape.
3. Confirm that the selected rail is 3.3 V under load and can supply the module's transmit-current transients. Add local decoupling or use a separate regulated 3.3 V supply with common ground if the board rail is not proven adequate.
4. Confirm 3.3 V logic levels, cross TX to RX, and select a UART that does not remove UART1 flashing/debug access.
5. Define safe enable, reset, and boot-strap levels for normal boot and firmware recovery. Never hot-plug the bare module.
6. Confirm antenna clearance and keep metal, the battery, display flex, and wiring away from the PCB antenna region.

## Bring-up sequence

1. With power off, continuity-check power and ground and check for shorts.
2. Power the module with a current-limited supply or a rail whose capability is already verified; observe voltage during startup.
3. Open the dedicated UART at 115200 baud and issue a bounded `AT` probe. If there is no response, capture boot output and identify the actual firmware/baud before changing configuration.
4. Query firmware identity and capabilities without writing persistent settings.
5. Scan for access points, then join a dedicated 2.4 GHz test network using credentials that are not committed or printed in logs.
6. Verify association, DHCP/IP, DNS, a bounded TCP request, and the selected HTTP/TLS path.
7. Test disconnect, retry limits, access-point loss, module reset, board reset, and offline operation.
8. Measure active and sleep current before enabling Wi-Fi by default in the wearable product.

## Software boundary

Product code should use a transport-neutral network service. The ESP-specific layer owns UART framing, AT parsing, reset/recovery, association state, and socket operations. Application, UI, and AI code must not send raw AT commands.

Credentials and tokens belong in ignored, provisioned storage. Diagnostic commands may report state and error codes but must redact SSIDs when requested and must never print passwords or backend secrets.

## References

- SiFli board documentation: <https://docs.sifli.com/projects/sdk/latest/en/sf32lb58x/supported_boards/boards/sf32lb52-lchspi-ulp/doc/index.html>
- Ai-Thinker ESP-01S product specification V1.2: <https://docs.ai-thinker.com/_media/esp8266/docs/esp-01s_product_specification_en.pdf>
