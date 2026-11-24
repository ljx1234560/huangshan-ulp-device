import json

import httpx
import pytest

from app.config import Settings
from app.services.ai_provider import (
    ActivityInsight,
    DeepSeekTextProvider,
    MockTextProvider,
    TextAiBalanceError,
    TextAiConfigurationError,
    TextAiEmptyResponseError,
    TextAiError,
    TextAiJsonSyntaxError,
    TextAiRateLimitError,
    TextAiResponseError,
    TextAiSchemaError,
    TextAiTimeoutError,
    TextAiTruncatedResponseError,
)


def insight(sufficient: bool = True) -> ActivityInsight:
    return ActivityInsight(
        window_days=30,
        days_with_data=7 if sufficient else 1,
        today_steps=8362,
        today_active_minutes=45,
        current_goal=10000,
        average_steps=9128,
        average_active_minutes=47,
        completed_days=4,
        trend_percent=6,
        safe_goal_min=8000,
        safe_goal_max=10500,
        sufficient_data=sufficient,
    )


def settings(**overrides) -> Settings:
    values = {
        "text_ai_provider": "deepseek",
        "text_ai_api_key": "unit-test-secret",
        "text_ai_base_url": "https://api.deepseek.com",
        "text_ai_model": "account-enabled-model",
        "text_ai_timeout_seconds": 1,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def valid_response() -> dict:
    content = {
        "today_summary": "今天已记录 8,362 步。",
        "today_advice": "分两次完成剩余步数。",
        "reason": "近期运动趋势平稳。",
        "weekly_plan": "本周保持规律活动。",
        "pet_encouragement": "露米会陪你继续前进！",
    }
    return {
        "model": "account-enabled-model",
        "choices": [{
            "finish_reason": "stop",
            "message": {"content": json.dumps(content, ensure_ascii=False)},
        }],
        "usage": {"prompt_tokens": 120, "completion_tokens": 80, "total_tokens": 200},
    }


def model_response(content: str, finish_reason: str = "stop") -> dict:
    result = valid_response()
    result["choices"][0]["finish_reason"] = finish_reason
    result["choices"][0]["message"]["content"] = content
    return result


def test_mock_provider_is_honest_when_data_is_insufficient():
    generated = MockTextProvider().generate(insight(False), "露米")
    assert generated.provider == "mock"
    assert "不足" in generated.advice.today_summary
    assert "推测" in generated.advice.reason


def test_deepseek_request_contract_and_normal_response():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://api.deepseek.com/chat/completions"
        assert request.headers["Authorization"] == "Bearer unit-test-secret"
        body = json.loads(request.content)
        assert body["model"] == "account-enabled-model"
        assert body["response_format"] == {"type": "json_object"}
        assert body["stream"] is False
        assert body["max_tokens"] == 1600
        system_prompt = body["messages"][0]["content"]
        assert "json" in system_prompt
        for field in ("today_summary", "today_advice", "reason", "weekly_plan", "pet_encouragement"):
            assert field in system_prompt
        return httpx.Response(200, json=valid_response())

    client = httpx.Client(transport=httpx.MockTransport(handler))
    generated = DeepSeekTextProvider(settings(), client).generate(insight(), "露米")
    assert generated.provider == "deepseek"
    assert generated.model == "account-enabled-model"
    assert generated.total_tokens == 200
    assert generated.advice.today_advice == "分两次完成剩余步数。"


@pytest.mark.parametrize("field", ["text_ai_api_key", "text_ai_model"])
def test_deepseek_requires_explicit_credentials_and_model(field):
    with pytest.raises(TextAiConfigurationError):
        DeepSeekTextProvider(settings(**{field: ""})).generate(insight(), "露米")


def test_deepseek_timeout_is_mapped():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(TextAiTimeoutError):
        DeepSeekTextProvider(settings(), client).generate(insight(), "露米")


def test_deepseek_insufficient_balance_is_mapped():
    client = httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(402, json={"error": {}})))
    with pytest.raises(TextAiBalanceError):
        DeepSeekTextProvider(settings(), client).generate(insight(), "露米")


def test_deepseek_rate_limit_is_mapped():
    client = httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(429, json={"error": {}})))
    with pytest.raises(TextAiRateLimitError):
        DeepSeekTextProvider(settings(), client).generate(insight(), "露米")


def test_deepseek_network_error_is_mapped_without_exposing_key():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline", request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(TextAiError) as error:
        DeepSeekTextProvider(settings(), client).generate(insight(), "露米")
    assert "unit-test-secret" not in str(error.value)


def test_deepseek_reports_missing_fields_after_one_bounded_retry():
    payload = model_response(json.dumps({"today_summary": "only one field"}))
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json=payload)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(TextAiSchemaError, match="缺少字段 today_advice") as error:
        DeepSeekTextProvider(settings(), client).generate(insight(), "露米")
    assert "已重试一次仍失败" in str(error.value)
    assert calls == 2


def test_deepseek_rejects_wrong_field_type():
    payload = valid_response()
    content = json.loads(payload["choices"][0]["message"]["content"])
    content["today_advice"] = 123
    payload["choices"][0]["message"]["content"] = json.dumps(content)
    client = httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload)))
    with pytest.raises(TextAiSchemaError, match="字段 today_advice 类型错误"):
        DeepSeekTextProvider(settings(), client).generate(insight(), "露米")


def test_deepseek_rejects_truncated_json_before_parsing():
    payload = model_response('{"today_summary":"incomplete"', finish_reason="length")
    client = httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload)))
    with pytest.raises(TextAiTruncatedResponseError, match="截断"):
        DeepSeekTextProvider(settings(), client).generate(insight(), "露米")


def test_deepseek_retries_blank_content_then_reports_empty_response():
    payload = model_response("   \n  ")
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json=payload)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(TextAiEmptyResponseError, match="空白内容"):
        DeepSeekTextProvider(settings(), client).generate(insight(), "露米")
    assert calls == 2


def test_deepseek_rejects_extra_fields():
    payload = valid_response()
    content = json.loads(payload["choices"][0]["message"]["content"])
    content["diagnosis"] = "not allowed"
    payload["choices"][0]["message"]["content"] = json.dumps(content)
    client = httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload)))
    with pytest.raises(TextAiSchemaError, match="存在未允许字段 diagnosis"):
        DeepSeekTextProvider(settings(), client).generate(insight(), "露米")


def test_deepseek_rejects_malformed_json():
    payload = model_response("{not valid json}")
    client = httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload)))
    with pytest.raises(TextAiJsonSyntaxError, match="JSON 语法错误"):
        DeepSeekTextProvider(settings(), client).generate(insight(), "露米")


def test_deepseek_retries_once_and_succeeds_with_cumulative_usage():
    payloads = [model_response("   "), valid_response()]
    requests: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        return httpx.Response(200, json=payloads.pop(0))

    client = httpx.Client(transport=httpx.MockTransport(handler))
    generated = DeepSeekTextProvider(settings(), client).generate(insight(), "露米")
    assert len(requests) == 2
    assert len(requests[1]["messages"]) == 3
    assert "上一次响应未通过结构校验" in requests[1]["messages"][-1]["content"]
    assert generated.total_tokens == 400
    assert generated.advice.today_summary == "今天已记录 8,362 步。"


def test_deepseek_retries_only_once_when_both_responses_are_invalid():
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json=model_response("not-json"))

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(TextAiJsonSyntaxError, match="已重试一次仍失败"):
        DeepSeekTextProvider(settings(), client).generate(insight(), "露米")
    assert calls == 2


def test_deepseek_rejects_missing_choices_with_diagnostic_error():
    client = httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, json={})))
    with pytest.raises(TextAiSchemaError, match=r"choices\[0\]"):
        DeepSeekTextProvider(settings(), client).generate(insight(), "露米")
