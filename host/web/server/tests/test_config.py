from pathlib import Path

from app.config import Settings
from app.services.ai_provider import DeepSeekTextProvider, MockTextProvider, get_text_provider
from app.services.image_provider import DoubaoImageProvider, MockImageProvider, OpenAIImageProvider, get_image_provider


SERVER_ROOT = Path(__file__).resolve().parents[1]
WEB_ROOT = SERVER_ROOT.parent


def env_names(path: Path) -> set[str]:
    names: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        names.add(stripped.split("=", 1)[0].strip())
    return names


def env_value(path: Path, name: str) -> str:
    prefix = name + "="
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith(prefix):
            return line[len(prefix):]
    raise AssertionError(f"missing environment template variable: {name}")


def test_server_env_example_matches_all_settings_fields_and_has_no_keys():
    expected = {"VELAPET_" + name.upper() for name in Settings.model_fields} | {
        "VELAPET_RUN_ONLINE_AI_SMOKE",
        "VELAPET_RUN_ONLINE_IMAGE_SMOKE",
        "VELAPET_RUN_ONLINE_DOUBAO_IMAGE_SMOKE",
    }
    declared = env_names(SERVER_ROOT / ".env.example")
    assert declared == expected
    assert env_value(SERVER_ROOT / ".env.example", "VELAPET_TEXT_AI_API_KEY") == ""
    assert env_value(SERVER_ROOT / ".env.example", "VELAPET_IMAGE_AI_API_KEY") == ""
    assert env_value(SERVER_ROOT / ".env.example", "VELAPET_TEXT_AI_DEVICE_TOKEN") == ""
    assert env_value(SERVER_ROOT / ".env.example", "VELAPET_RUN_ONLINE_AI_SMOKE") == "0"
    assert env_value(SERVER_ROOT / ".env.example", "VELAPET_RUN_ONLINE_IMAGE_SMOKE") == "0"
    assert env_value(SERVER_ROOT / ".env.example", "VELAPET_RUN_ONLINE_DOUBAO_IMAGE_SMOKE") == "0"


def test_frontend_env_example_contains_only_supported_vite_variables():
    assert env_names(WEB_ROOT / ".env.example") == {"VITE_API_MODE", "VITE_API_BASE_URL"}


def test_mock_providers_initialize_without_credentials():
    settings = Settings(_env_file=None, text_ai_provider="mock", image_ai_provider="mock")
    assert isinstance(get_text_provider(settings), MockTextProvider)
    assert isinstance(get_image_provider(settings), MockImageProvider)


def test_deepseek_and_doubao_read_explicit_settings_without_network_calls():
    settings = Settings(
        _env_file=None,
        text_ai_provider="deepseek",
        text_ai_api_key="configured-for-test",
        text_ai_base_url="https://api.deepseek.com",
        text_ai_model="account-enabled-text-model",
        image_ai_provider="doubao",
        image_ai_api_key="configured-for-test",
        image_ai_base_url="https://ark.cn-beijing.volces.com/api/v3",
        image_ai_model="doubao-seedream-5-0-flash-260128",
        image_ai_size="2K",
        image_ai_output_format="png",
        image_ai_background="opaque",
        image_ai_response_format="b64_json",
    )
    text_provider = get_text_provider(settings)
    image_provider = get_image_provider(settings)
    assert isinstance(text_provider, DeepSeekTextProvider)
    assert isinstance(image_provider, DoubaoImageProvider)
    assert text_provider.settings.text_ai_api_key == "configured-for-test"
    assert text_provider.settings.text_ai_model == "account-enabled-text-model"
    image_provider.validate_configuration()


def test_openai_provider_reads_compatible_shared_image_settings():
    settings = Settings(
        _env_file=None,
        image_ai_provider="openai",
        image_ai_api_key="configured-for-test",
        image_ai_base_url="https://api.openai.com/v1",
        image_ai_model="account-enabled-image-model",
        image_ai_size="1024x1024",
        image_ai_quality="medium",
        image_ai_output_format="png",
        image_ai_background="auto",
        image_ai_response_format="b64_json",
    )
    provider = get_image_provider(settings)
    assert isinstance(provider, OpenAIImageProvider)
    provider.validate_configuration()
