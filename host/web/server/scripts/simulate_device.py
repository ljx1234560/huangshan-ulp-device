import argparse
from datetime import datetime, timedelta, timezone

import httpx


def main():
    parser = argparse.ArgumentParser(description="Upload a simulated VelaPet activity batch")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--serial", default="VP-52U-2400168")
    parser.add_argument("--token", default="demo-device-token")
    parser.add_argument("--steps", type=int, default=11240)
    args = parser.parse_args()
    occurred_at = datetime.now(timezone.utc)
    local_date = (occurred_at + timedelta(minutes=480)).date()
    stamp = occurred_at.strftime("%Y%m%d%H%M%S%f")
    payload = {
        "uploadId": "manual-demo-" + stamp,
        "uploadOffset": 0,
        "final": True,
        "records": [{
            "recordId": "manual-record-" + stamp,
            "occurredAt": occurred_at.isoformat(),
            "localDate": local_date.isoformat(),
            "timezoneOffsetMinutes": 480,
            "steps": args.steps,
            "activeMinutes": round(args.steps / 185),
            "goal": 10000,
        }],
    }
    response = httpx.post(
        f"{args.base_url}/api/v1/device-uploads/{args.serial}/activity-batches",
        json=payload,
        headers={"X-VelaPet-Device-Token": args.token},
        timeout=15,
    )
    response.raise_for_status()
    print(response.json())


if __name__ == "__main__":
    main()
