"""Settings loading and the Secrets Manager override."""

import pytest

from app.core import config
from app.core.config import Settings


class FakeSecretsManager:
    def __init__(self, secrets):
        self.secrets = secrets
        self.requested = []

    def get_secret_value(self, SecretId):
        self.requested.append(SecretId)
        if SecretId not in self.secrets:
            raise KeyError(SecretId)
        return {"SecretString": self.secrets[SecretId]}


@pytest.fixture
def fake_sm(monkeypatch):
    import boto3

    fake = FakeSecretsManager({"careerforge/cognito-app-client-secret": "from-sm"})
    monkeypatch.setattr(boto3, "client", lambda *args, **kwargs: fake)
    return fake


def test_secrets_manager_disabled_never_creates_a_client(monkeypatch):
    import boto3

    def explode(*args, **kwargs):
        raise AssertionError("boto3.client must not be called")

    monkeypatch.setattr(boto3, "client", explode)
    settings = Settings(USE_SECRETS_MANAGER=False)
    assert settings.COGNITO_APP_CLIENT_SECRET is None


def test_cognito_secret_has_no_hardcoded_default(monkeypatch):
    monkeypatch.delenv("COGNITO_APP_CLIENT_SECRET", raising=False)
    assert Settings.model_fields["COGNITO_APP_CLIENT_SECRET"].default is None


def test_missing_cognito_secret_is_loaded_from_secrets_manager(fake_sm, monkeypatch):
    monkeypatch.delenv("COGNITO_APP_CLIENT_SECRET", raising=False)
    settings = Settings(USE_SECRETS_MANAGER=True)
    assert settings.COGNITO_APP_CLIENT_SECRET == "from-sm"
    assert "careerforge/cognito-app-client-secret" in fake_sm.requested


def test_explicit_cognito_secret_wins_over_secrets_manager(fake_sm):
    settings = Settings(USE_SECRETS_MANAGER=True, COGNITO_APP_CLIENT_SECRET="from-env")
    assert settings.COGNITO_APP_CLIENT_SECRET == "from-env"
    assert "careerforge/cognito-app-client-secret" not in fake_sm.requested


def test_unreachable_secret_keeps_env_value(fake_sm):
    # The JWT secret is not in the fake store, so the sentinel default stays.
    settings = Settings(USE_SECRETS_MANAGER=True, JWT_SECRET_KEY="change-me-in-production")
    assert settings.JWT_SECRET_KEY == "change-me-in-production"


def test_gemini_keys_skip_empty_slots():
    settings = Settings(
        USE_SECRETS_MANAGER=False, GEMINI_API_KEY_1="a", GEMINI_API_KEY_3="c"
    )
    assert settings.gemini_api_keys == ["a", "c"]


def test_max_upload_size_bytes():
    settings = Settings(USE_SECRETS_MANAGER=False, MAX_UPLOAD_SIZE_MB=2)
    assert settings.max_upload_size_bytes == 2 * 1024 * 1024


def test_suite_runs_with_secrets_manager_off():
    assert config.settings.USE_SECRETS_MANAGER is False


def test_cognito_callback_refuses_without_client_secret(client, monkeypatch):
    monkeypatch.setattr(config.settings, "COGNITO_APP_CLIENT_SECRET", None)
    response = client.post("/api/auth/cognito/callback", json={"code": "abc"})
    assert response.status_code == 503
    assert response.json()["detail"] == "Cognito not configured"
