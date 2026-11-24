"""Database-backed image generation worker."""

import argparse
import time

from app.config import get_settings
from app.services.image_jobs import process_next_image_job, recover_stale_image_jobs


def main() -> int:
    parser = argparse.ArgumentParser(description="VelaPet persisted image generation worker")
    parser.add_argument("--once", action="store_true", help="Process at most one queued job and exit")
    parser.add_argument("--poll-seconds", type=float, default=2.0)
    args = parser.parse_args()
    settings = get_settings()
    recovered = recover_stale_image_jobs(settings)
    print(f"image-worker provider={settings.image_ai_provider} recovered={recovered}")
    while True:
        job_id = process_next_image_job(settings)
        if job_id:
            print(f"image-worker processed job={job_id}")
        if args.once:
            return 0
        if not job_id:
            time.sleep(max(0.2, args.poll_seconds))


if __name__ == "__main__":
    raise SystemExit(main())
