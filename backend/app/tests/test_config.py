import pytest

from app.core.config import DEFAULT_DEV_SECRET_KEY, Settings


def test_production_with_default_secret_key_refuses_to_start():
    with pytest.raises(RuntimeError, match="default SECRET_KEY"):
        Settings(environment="production", secret_key=DEFAULT_DEV_SECRET_KEY)


def test_production_with_custom_secret_key_starts_normally():
    settings = Settings(environment="production", secret_key="a-unique-production-secret")
    assert settings.secret_key == "a-unique-production-secret"


def test_development_with_default_secret_key_is_allowed():
    settings = Settings(environment="development", secret_key=DEFAULT_DEV_SECRET_KEY)
    assert settings.secret_key == DEFAULT_DEV_SECRET_KEY


def test_environment_check_is_case_insensitive():
    with pytest.raises(RuntimeError, match="default SECRET_KEY"):
        Settings(environment="PRODUCTION", secret_key=DEFAULT_DEV_SECRET_KEY)
