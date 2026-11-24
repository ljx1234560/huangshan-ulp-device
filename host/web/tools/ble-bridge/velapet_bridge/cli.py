from __future__ import annotations

import argparse
import asyncio
import getpass
import logging
import os
from pathlib import Path
import sys

from .api import ApiClient
from .bridge import BridgeRunner
from .transport import BleakTransport


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="VelaPet Windows BLE bridge")
    root.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    commands = root.add_subparsers(dest="command", required=True)
    scan = commands.add_parser("scan", help="scan for VelaPet devices")
    scan.add_argument("--seconds", type=float, default=8.0)
    sync = commands.add_parser("sync", help="connect, read history, upload, then ACK")
    sync.add_argument("--address", required=True, help="BLE address returned by scan")
    sync.add_argument("--api-url", default="http://localhost:8000")
    sync.add_argument("--email", required=True, help="bound VelaPet user email")
    sync.add_argument("--serial", required=True, help="expected serial; checked again after BLE connect")
    sync.add_argument("--client-id", default="windows-ble-bridge")
    sync.add_argument("--attempts", type=int, default=3)
    chat = commands.add_parser("chat", help="relay watch AI requests to the local AI backend")
    chat.add_argument("--address", required=True)
    chat.add_argument("--serial", required=True)
    chat.add_argument("--api-url", default="http://127.0.0.1:8000")
    return root


async def run(args: argparse.Namespace) -> int:
    if args.command == "scan":
        print("扫描中…")
        devices = await BleakTransport.scan(args.seconds)
        for item in devices:
            print(f"已发现设备 name={item.name} address={item.address} rssi={item.rssi}")
        return 0 if devices else 2

    if args.command == "chat":
        # The shared backend schema is authoritative. Reuse it from this checkout.
        sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "ai-backend"))
        from velapet_backend.chat_relay import ChatRelayClient
        from .chat import ChatBridgeRunner
        token = os.getenv("VELAPET_RELAY_TOKEN") or getpass.getpass("AI backend device token: ")
        relay = ChatRelayClient(args.api_url, token)
        await ChatBridgeRunner(BleakTransport(args.address), relay, args.serial).serve()
        return 0

    password = getpass.getpass("VelaPet 密码（仅用于本次授权，不保存）: ")
    api = await ApiClient.authorize(args.api_url, args.email, password, args.serial, args.client_id)
    try:
        runner = BridgeRunner(BleakTransport(args.address), api, args.client_id, expected_serial=args.serial)
        result = await runner.sync_with_reconnect(args.attempts)
        print(f"同步成功 accepted={result.accepted} duplicates={result.duplicates} cursor={result.acknowledged_cursor}")
        return 0
    finally:
        await api.close()


def main() -> None:
    args = parser().parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(message)s",
    )
    try:
        raise SystemExit(asyncio.run(run(args)))
    except KeyboardInterrupt:
        print("设备断开（用户取消）", file=sys.stderr)
        raise SystemExit(130)


if __name__ == "__main__":
    main()
