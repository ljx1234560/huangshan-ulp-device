from dataclasses import dataclass

import httpx

from ..config import Settings


@dataclass
class AiContext:
    user_id: str
    pet_name: str
    level: int
    current_exp: int
    next_level_exp: int
    today_steps: int
    goal: int
    active_minutes: int
    streak_days: int
    average_steps: int


class AiProvider:
    def coaching(self, context: AiContext) -> tuple[str, str]:
        raise NotImplementedError


class MockAiProvider(AiProvider):
    def coaching(self, context: AiContext) -> tuple[str, str]:
        remaining = max(0, context.goal - context.today_steps)
        if remaining:
            return f"今天还差 {remaining:,} 步，可以拆成两次轻松散步完成。", "mock"
        return "今天的目标已经完成，接下来保持轻松活动并注意恢复。", "mock"


class ExistingVelaPetAiProvider(AiProvider):
    def __init__(self, settings: Settings):
        self.settings = settings

    def coaching(self, context: AiContext) -> tuple[str, str]:
        body = {
            "device_id": "web-coach",
            "prompt_type": "task",
            "locale": "zh-CN",
            "max_chars": 80,
            "message": "根据活动快照给出一条简短、非医疗的运动建议",
            "context": {
                "pet_name": context.pet_name,
                "level": context.level,
                "current_exp": context.current_exp,
                "next_level_exp": context.next_level_exp,
                "total_steps": context.today_steps,
                "consecutive_days": context.streak_days,
                "daily_progress": context.today_steps / context.goal if context.goal else 0,
            },
        }
        headers = {"X-VelaPet-Token": self.settings.ai_device_token}
        with httpx.Client(timeout=8.0) as client:
            response = client.post(self.settings.ai_service_url.rstrip("/") + "/api/v1/chat", json=body, headers=headers)
            response.raise_for_status()
            result = response.json()
        return result["reply"], result.get("source", "local_fallback")


def get_ai_provider(settings: Settings) -> AiProvider:
    if settings.ai_provider == "existing_velapet" and settings.ai_device_token:
        return ExistingVelaPetAiProvider(settings)
    return MockAiProvider()
