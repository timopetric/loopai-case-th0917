"""Settings: env-var mapping and the ADR-0003 dev-fakes fail-closed rule."""

import pytest

from app.config import Settings


def test_settings_reads_every_env_var_from_env_example(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "prod")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("APP_API_KEY", "super-secret")
    monkeypatch.setenv("UPSTREAM_BASE_URL", "https://upstream.example.test")
    monkeypatch.setenv("UPSTREAM_TOKEN", "tok-123")
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-456")
    monkeypatch.setenv("LLM_MODEL", "some/model")
    monkeypatch.setenv("LLM_TEMPERATURE", "0.7")
    monkeypatch.setenv("AGENT_MAX_ITERATIONS", "5")

    settings = Settings(_env_file=None)

    assert settings.environment == "prod"
    assert settings.log_level == "DEBUG"
    assert settings.app_api_key == "super-secret"
    assert settings.upstream_base_url == "https://upstream.example.test"
    assert settings.upstream_token == "tok-123"
    assert settings.openrouter_api_key == "or-456"
    assert settings.llm_model == "some/model"
    assert settings.llm_temperature == 0.7
    assert settings.agent_max_iterations == 5


@pytest.mark.parametrize("environment", ["local", "dev"])
def test_dev_fakes_allowed_in_development(environment: str) -> None:
    settings = Settings(_env_file=None, environment=environment, dev_fake_upstream=True)

    assert settings.dev_fake_upstream is True


@pytest.mark.parametrize("environment", ["test", "prod"])
def test_dev_fakes_refused_outside_development(environment: str) -> None:
    """ADR-0003: the app refuses to start, fail-closed, if a fake flag is set
    anywhere but a development environment."""
    with pytest.raises(ValueError, match="development-only"):
        Settings(_env_file=None, environment=environment, dev_fake_upstream=True)

    with pytest.raises(ValueError, match="development-only"):
        Settings(_env_file=None, environment=environment, dev_fake_llm=True)
