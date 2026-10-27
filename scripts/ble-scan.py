#!/usr/bin/env python3
"""Run a bounded BLE advertisement scan and emit stable result lines."""

from __future__ import annotations

import argparse
import asyncio

try:
    from bleak import BleakScanner
except ImportError as error:
    raise SystemExit(
        "Bleak is required. Install it in an isolated environment with "
        "'python -m pip install bleak'."
    ) from error


async def scan(seconds: float, expected_name: str, expected_address: str) -> int:
    discovered = await BleakScanner.discover(timeout=seconds, return_adv=True)
    matches: list[tuple[str, str, int | None]] = []
    observed: list[tuple[str, str, int | None]] = []

    for device, advertisement in discovered.values():
        name = advertisement.local_name or device.name or ""
        item = (name, device.address.upper(), advertisement.rssi)
        observed.append(item)
        if expected_name and name != expected_name:
            continue
        if expected_address and item[1] != expected_address:
            continue
        matches.append(item)

    observed.sort(key=lambda item: (item[0], item[1]))
    matches.sort(key=lambda item: (item[0], item[1]))
    if not matches:
        print(
            f"BLE_SCAN result=NOT_FOUND name={expected_name or '*'} "
            f"address={expected_address or '*'} seconds={seconds:g} "
            f"observed={len(observed)}"
        )
        for name, address, rssi in observed:
            print(
                f"BLE_SCAN observed name={name or '<unnamed>'} "
                f"address={address} rssi={rssi}"
            )
        return 2

    for name, address, rssi in matches:
        print(
            f"BLE_SCAN result=FOUND name={name or '<unnamed>'} address={address} "
            f"rssi={rssi}"
        )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seconds", type=float, default=15.0)
    parser.add_argument("--name", default="")
    parser.add_argument("--address", default="")
    args = parser.parse_args()
    if not 1.0 <= args.seconds <= 300.0:
        parser.error("--seconds must be between 1 and 300")
    expected_address = args.address.strip().upper()
    return asyncio.run(scan(args.seconds, args.name, expected_address))


if __name__ == "__main__":
    raise SystemExit(main())
