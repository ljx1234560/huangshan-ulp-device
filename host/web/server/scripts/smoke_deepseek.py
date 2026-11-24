"""Explicit, billable DeepSeek smoke test. Never runs as part of pytest."""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import Settings  # noqa: E402
from app.services.ai_provider import ActivityInsight, get_text_provider  # noqa: E402


def main() -> int:
    if os.getenv("VELAPET_RUN_ONLINE_AI_SMOKE") != "1":
        print("已跳过：仅在显式设置 VELAPET_RUN_ONLINE_AI_SMOKE=1 时调用真实付费接口。")
        return 2
    settings = Settings(_env_file=Path(__file__).resolve().parents[1] / ".env")
    insight = ActivityInsight(
        window_days=30, days_with_data=7, today_steps=8362, today_active_minutes=45,
        current_goal=10000, average_steps=9128, average_active_minutes=47,
        completed_days=4, trend_percent=6, safe_goal_min=8000, safe_goal_max=10500,
        sufficient_data=True,
    )
    # This is deliberately the same provider factory, prompt, parser and strict
    # schema used by POST /api/v1/ai/coaching; there is no smoke-only shortcut.
    generated = get_text_provider(settings).generate(insight, "露米")
    print(
        f"成功：provider={generated.provider} model={generated.model} "
        f"duration_ms={generated.duration_ms} total_tokens={generated.total_tokens}"
    )
    print(generated.advice.today_advice)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
