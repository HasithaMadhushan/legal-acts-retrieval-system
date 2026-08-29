from pathlib import Path

import pytest

from app.core.config import DEFAULT_DEV_SECRET_KEY, Settings

BACKEND_ROOT = Path(__file__).resolve().parents[2]

pytestmark = pytest.mark.no_hash_test_embeddings


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


def test_semantic_dependencies_are_pinned():
    requirements = (BACKEND_ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()

    assert "pgvector==0.5.0" in requirements
    assert "sentence-transformers==6.0.0" in requirements


def test_docker_image_bakes_configured_embedding_model_for_offline_use():
    dockerfile = (BACKEND_ROOT / "Dockerfile").read_text(encoding="utf-8")
    cache_script = (BACKEND_ROOT / "scripts" / "cache_embedding_model.py").read_text(
        encoding="utf-8"
    )

    assert "ARG EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2" in dockerfile
    assert "ARG EMBEDDING_MODEL_REVISION=1110a243fdf4706b3f48f1d95db1a4f5529b4d41" in dockerfile
    assert "ARG HF_HOME=/opt/huggingface" in dockerfile
    assert "ENV HF_HOME=${HF_HOME}" in dockerfile
    assert "ENV HF_HUB_OFFLINE=1" in dockerfile
    assert "python /tmp/cache_embedding_model.py" in dockerfile
    assert "revision=os.environ[\"EMBEDDING_MODEL_REVISION\"]" in cache_script


def test_semantic_configuration_defaults_to_real_provider_but_disabled_search():
    settings = Settings()

    assert settings.semantic_search_enabled is False
    assert settings.enable_pgvector is True
    assert settings.embedding_provider == "sentence-transformers"
    assert settings.embedding_model == "sentence-transformers/all-MiniLM-L6-v2"
    assert settings.embedding_model_revision == "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"
    assert settings.embedding_dimension == 384
    assert settings.embedding_batch_size == 32
    assert settings.embedding_device == "cpu"
    assert settings.embedding_normalize is True
    assert settings.semantic_candidate_limit == 100
    assert settings.hybrid_rrf_k == 60
    assert settings.hybrid_keyword_weight == 1.0
    assert settings.hybrid_semantic_weight == 1.0


@pytest.mark.parametrize("dimension", [0, -1, 383, 385])
def test_minilm_rejects_invalid_embedding_dimensions(dimension):
    with pytest.raises(ValueError, match="384 dimensions"):
        Settings(embedding_dimension=dimension)


@pytest.mark.parametrize("model", ["all-MiniLM-L6-v2", "sentence-transformers/all-MiniLM-L6-v2"])
def test_minilm_aliases_reject_invalid_embedding_dimensions(model):
    with pytest.raises(ValueError, match="384 dimensions"):
        Settings(embedding_model=model, embedding_dimension=383)


def test_semantic_configuration_rejects_unknown_provider():
    with pytest.raises(ValueError, match="embedding provider"):
        Settings(embedding_provider="unknown")


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("embedding_batch_size", 0),
        ("semantic_candidate_limit", 0),
        ("hybrid_rrf_k", 0),
        ("hybrid_keyword_weight", 0),
        ("hybrid_semantic_weight", -1),
    ],
)
def test_semantic_configuration_rejects_non_positive_tuning_values(field, value):
    with pytest.raises(ValueError, match="must be greater than zero"):
        Settings(**{field: value})


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_semantic_configuration_rejects_non_finite_weights(value):
    with pytest.raises(ValueError, match="must be finite"):
        Settings(hybrid_semantic_weight=value)


def test_hash_test_provider_is_available_in_tests():
    settings = Settings(environment="test", embedding_provider="hash-test")

    assert settings.embedding_provider == "hash-test"


def test_hash_test_provider_is_rejected_outside_tests():
    with pytest.raises(ValueError, match="only available when ENVIRONMENT=test"):
        Settings(environment="development", embedding_provider="hash-test")


def test_enabled_semantic_search_requires_pgvector():
    with pytest.raises(ValueError, match="ENABLE_PGVECTOR=true"):
        Settings(semantic_search_enabled=True, enable_pgvector=False)
