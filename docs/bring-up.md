# Board bring-up checklist

1. Verify jumpers 5-6, 7-8, and 11-12 on the 30-pin header are shorted.
2. Check battery polarity before connecting a Li-ion cell.
3. Connect the PC to the USB-to-UART Type-C connector using a data cable.
4. Run `scripts\ports.ps1` and identify the CH340 port.
5. Run `scripts\doctor.ps1`.
6. Build with `scripts\build.ps1`.
7. Flash only after confirming the selected COM port.
8. Monitor at 1,000,000 baud and confirm the boot banner and heartbeat.

The three jumper pairs are physical power-path links and cannot be reliably verified in software.

