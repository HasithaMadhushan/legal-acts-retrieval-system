import hashlib
import math
from types import SimpleNamespace

import pytest

from app.core.config import Settings
from app.core.roles import EmbeddingStatus
from app.services.embedding_providers import (
    DeterministicTestProvider,
    SentenceTransformerProvider,
    get_embedding_provider,
    reset_shared_model,
)
from app.services.embedding_service import (
    EmbeddingError,
    EmbeddingService,
    cosine_similarity,
    embed_text,
)

HELLO_SHA256 = "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"


class _RecordingModel:
    def __init__(self, dimension: int = 384, max_seq_length: int = 4) -> None:
        self.dimension = dimension
        self.max_seq_length = max_seq_length
        self.tokenizer = _WhitespaceTokenizer()
        self.encode_calls: list[dict[str, object]] = []

    def encode(self, texts, **kwargs):
        self.encode_calls.append({"texts": list(texts), **kwargs})
        return [[0.5] * self.dimension for _ in texts]


class _WhitespaceTokenizer:
    """Whitespace tokenizer that reserves CLS/SEP when add_special_tokens=True."""

    def __call__(self, text, truncation=True, max_length=None, add_special_tokens=False):
        tokens = text.split()
        special = 2 if add_special_tokens else 0
        if truncation and max_length is not None:
            tokens = tokens[: max(0, max_length - special)]
        ids = (["[CLS]"] + tokens + ["[SEP]"]) if add_special_tokens else list(tokens)
        return {"input_ids": ids}

    def decode(self, ids, skip_special_tokens=True):
        if skip_special_tokens:
            ids = [token for token in ids if token not in {"[CLS]", "[SEP]"}]
        return " ".join(ids)


class _NonIdempotentTruncateProvider:
    """Prepends a marker on every truncate so a second pass changes the string."""

    provider_name = "hash-test"
    model_name = "hash-test"

    def __init__(self, dimension: int = 8, max_seq_length: int = 4) -> None:
        self.dimension = dimension
        self.max_seq_length = max_seq_length
        self.encode_calls: list[list[str]] = []

    def truncate_text(self, text: str) -> str:
        tokens = text.split()
        kept = tokens[: max(0, self.max_seq_length - 1)]
        return " ".join(["<t>", *kept])

    def embed_query(self, text: str) -> list[float]:
        self.encode_calls.append([text])
        return DeterministicTestProvider(dimension=self.dimension).embed_query(text)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.encode_calls.append(list(texts))
        provider = DeterministicTestProvider(dimension=self.dimension)
        return [provider.embed_query(text) for text in texts]


class _BadVectorProvider:
    def __init__(self, vector: list[float], dimension: int = 384) -> None:
        self.provider_name = "hash-test"
        self.model_name = "hash-test"
        self.dimension = dimension
        self._vector = vector

    def truncate_text(self, text: str) -> str:
        return text

    def embed_query(self, text: str) -> list[float]:
        return list(self._vector)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_query(text) for text in texts]


class _ExplodingProvider:
    provider_name = "hash-test"
    model_name = "hash-test"
    dimension = 384

    def truncate_text(self, text: str) -> str:
        return text

    def embed_query(self, text: str) -> list[float]:
        raise RuntimeError("upstream inference failed")

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        raise RuntimeError("upstream inference failed")


class _ExplodingTruncateProvider:
    provider_name = "hash-test"
    model_name = "hash-test"
    dimension = 384

    def truncate_text(self, text: str) -> str:
        raise RuntimeError("tokenizer unavailable")

    def embed_query(self, text: str) -> list[float]:
        raise AssertionError("embed_query should not run after truncate failure")

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        raise AssertionError("embed_documents should not run after truncate failure")

def _act(**overrides) -> SimpleNamespace:
    values = {
        "title": "Civil Procedure Act",
        "act_number": "7",
        "year": 2023,
        "category": "Civil Procedure",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _section(**overrides) -> SimpleNamespace:
    values = {
        "id": "section-1",
        "act": _act(),
        "section_number": "2",
        "section_path": "2(1)",
        "heading": "Jurisdiction",
        "text": "The High Court shall have jurisdiction over civil matters.",
        "embedding": None,
        "embedding_provider": None,
        "embedding_model": None,
        "embedding_dimension": None,
        "embedding_source_hash": None,
        "embedding_status": EmbeddingStatus.PENDING,
        "embedded_at": None,
        "embedding_error": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _service(dimension: int = 8, max_seq_length: int = 256) -> EmbeddingService:
    return EmbeddingService(
        provider=DeterministicTestProvider(
            dimension=dimension,
            max_seq_length=max_seq_length,
        )
    )


@pytest.fixture(autouse=True)
def _reset_sentence_transformer_singleton():
    reset_shared_model()
    yield
    reset_shared_model()


def test_hash_test_settings_select_deterministic_provider():
    settings = Settings(environment="test", embedding_provider="hash-test")

    provider = get_embedding_provider(settings)

    assert isinstance(provider, DeterministicTestProvider)
    assert provider.provider_name == "hash-test"
    assert provider.dimension == 384


def test_sentence_transformers_settings_select_real_provider_without_loading_model(monkeypatch):
    loads: list[tuple[str, str, str]] = []

    def fake_load(model_name: str, revision: str, device: str):
        loads.append((model_name, revision, device))
        return _RecordingModel()

    monkeypatch.setattr(
        "app.services.embedding_providers.load_sentence_transformer",
        fake_load,
    )
    settings = Settings(embedding_provider="sentence-transformers")

    provider = get_embedding_provider(settings)

    assert isinstance(provider, SentenceTransformerProvider)
    assert provider.provider_name == "sentence-transformers"
    assert provider.model_name == "sentence-transformers/all-MiniLM-L6-v2"
    assert provider.dimension == 384
    assert loads == []


def test_deterministic_provider_returns_configured_dimension_and_unit_norm():
    provider = DeterministicTestProvider(dimension=8)

    vector = provider.embed_query("High Court jurisdiction")

    assert len(vector) == 8
    assert all(math.isfinite(component) for component in vector)
    assert math.sqrt(sum(component * component for component in vector)) == pytest.approx(1.0)


def test_deterministic_provider_is_stable_for_the_same_text():
    provider = DeterministicTestProvider(dimension=8)

    first = provider.embed_query("jurisdiction")
    second = provider.embed_query("jurisdiction")

    assert first == second


def test_empty_query_returns_zero_vector_of_provider_dimension():
    provider = DeterministicTestProvider(dimension=8)

    assert provider.embed_query("") == [0.0] * 8
    assert provider.embed_query("   ") == [0.0] * 8
    assert provider.embed_documents([]) == []


def test_embed_documents_returns_one_normalized_vector_per_input_in_order():
    provider = DeterministicTestProvider(dimension=8)
    texts = ["civil procedure", "criminal procedure", "evidence"]

    vectors = provider.embed_documents(texts)

    assert len(vectors) == 3
    assert vectors[0] == provider.embed_query("civil procedure")
    assert vectors[1] == provider.embed_query("criminal procedure")
    assert vectors[2] == provider.embed_query("evidence")
    assert vectors[0] != vectors[1]


def test_sentence_transformer_provider_encodes_with_normalization_and_batch_size(monkeypatch):
    model = _RecordingModel(dimension=384)

    def fake_load(model_name: str, revision: str, device: str):
        return model

    monkeypatch.setattr(
        "app.services.embedding_providers.load_sentence_transformer",
        fake_load,
    )
    settings = Settings(embedding_batch_size=16)
    provider = SentenceTransformerProvider.from_settings(settings)

    vectors = provider.embed_documents(["one", "two"])

    assert len(vectors) == 2
    assert all(len(vector) == 384 for vector in vectors)
    assert model.encode_calls == [
        {
            "texts": ["one", "two"],
            "normalize_embeddings": True,
            "batch_size": 16,
        }
    ]


def test_sentence_transformer_model_loads_once_across_provider_instances(monkeypatch):
    loads: list[int] = []

    def fake_load(model_name: str, revision: str, device: str):
        loads.append(1)
        return _RecordingModel()

    monkeypatch.setattr(
        "app.services.embedding_providers.load_sentence_transformer",
        fake_load,
    )
    settings = Settings()
    first = SentenceTransformerProvider.from_settings(settings)
    second = SentenceTransformerProvider.from_settings(settings)

    first.embed_query("one")
    second.embed_query("two")

    assert loads == [1]


def test_service_wraps_provider_failures_without_echoing_legal_text():
    legal_text = "The High Court shall have exclusive original jurisdiction."
    service = EmbeddingService(provider=_ExplodingProvider())

    with pytest.raises(EmbeddingError, match="provider") as caught:
        service.embed_query(legal_text)

    assert legal_text not in str(caught.value)
    assert caught.value.__cause__ is not None


def test_service_rejects_wrong_embedding_dimension():
    service = EmbeddingService(provider=_BadVectorProvider([0.1, 0.2], dimension=384))

    with pytest.raises(EmbeddingError, match="dimension"):
        service.embed_query("jurisdiction")


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_service_rejects_non_finite_embedding_values(value):
    service = EmbeddingService(provider=_BadVectorProvider([value] * 8, dimension=8))

    with pytest.raises(EmbeddingError, match="finite"):
        service.embed_query("jurisdiction")


def test_build_section_text_includes_act_and_section_identity():
    service = _service()
    composed = service.build_section_text(_act(), _section())

    assert composed == (
        "Civil Procedure Act\n"
        "Act 7 of 2023\n"
        "Category: Civil Procedure\n"
        "Section 2 / 2(1)\n"
        "Jurisdiction\n"
        "The High Court shall have jurisdiction over civil matters."
    )


def test_source_hash_is_sha256_hex_of_exact_text():
    service = _service()

    assert service.source_hash("hello") == HELLO_SHA256
    assert len(service.source_hash("hello")) == 64


def test_embed_query_delegates_to_injected_provider_and_validates():
    service = _service(dimension=8)

    vector = service.embed_query("jurisdiction")

    assert len(vector) == 8
    assert math.sqrt(sum(component * component for component in vector)) == pytest.approx(1.0)


def test_needs_embedding_is_true_until_ready_current_model_hash_matches():
    service = _service(dimension=8)
    pending = _section()
    ready = _section(
        embedding=[0.1] * 8,
        embedding_provider="hash-test",
        embedding_model="hash-test",
        embedding_dimension=8,
        embedding_source_hash=service.source_hash(
            service.truncate_text(service.build_section_text(pending.act, pending))
        ),
        embedding_status=EmbeddingStatus.READY,
    )

    assert service.needs_embedding(pending) is True
    assert service.needs_embedding(ready) is False
    ready.embedding_source_hash = "0" * 64
    assert service.needs_embedding(ready) is True


def test_needs_embedding_when_status_is_failed_or_stale_or_model_changed():
    service = _service(dimension=8)
    composed_hash = service.source_hash(
        service.truncate_text(service.build_section_text(_act(), _section()))
    )
    failed = _section(
        embedding=[0.1] * 8,
        embedding_provider="hash-test",
        embedding_model="hash-test",
        embedding_dimension=8,
        embedding_source_hash=composed_hash,
        embedding_status=EmbeddingStatus.FAILED,
    )
    stale = _section(
        embedding=[0.1] * 8,
        embedding_provider="hash-test",
        embedding_model="hash-test",
        embedding_dimension=8,
        embedding_source_hash=composed_hash,
        embedding_status=EmbeddingStatus.STALE,
    )
    other_model = _section(
        embedding=[0.1] * 8,
        embedding_provider="hash-test",
        embedding_model="other-model",
        embedding_dimension=8,
        embedding_source_hash=composed_hash,
        embedding_status=EmbeddingStatus.READY,
    )

    assert service.needs_embedding(failed) is True
    assert service.needs_embedding(stale) is True
    assert service.needs_embedding(other_model) is True


def test_embed_sections_writes_ready_metadata_and_skips_current_embeddings():
    service = _service(dimension=8)
    pending = _section(id="pending")
    current_text = service.truncate_text(service.build_section_text(pending.act, pending))
    already_ready = _section(
        id="ready",
        embedding=[0.25] * 8,
        embedding_provider="hash-test",
        embedding_model="hash-test",
        embedding_dimension=8,
        embedding_source_hash=service.source_hash(current_text),
        embedding_status=EmbeddingStatus.READY,
        embedded_at=None,
    )

    service.embed_sections([pending, already_ready])

    assert pending.embedding_status == EmbeddingStatus.READY
    assert pending.embedding_provider == "hash-test"
    assert pending.embedding_model == "hash-test"
    assert pending.embedding_dimension == 8
    assert pending.embedding_source_hash == service.source_hash(current_text)
    assert pending.embedding_error is None
    assert pending.embedded_at is not None
    assert len(pending.embedding) == 8
    assert already_ready.embedding == [0.25] * 8


def test_embed_sections_marks_failed_without_storing_legal_text_on_provider_error(
    monkeypatch,
):
    legal_text = "Secret exclusive original jurisdiction clause."
    section = _section(text=legal_text)
    service = EmbeddingService(provider=_ExplodingProvider())
    warnings: list[dict[str, object]] = []

    def capture_warning(event: str, **kwargs: object) -> None:
        warnings.append({"event": event, **kwargs})

    monkeypatch.setattr(
        "app.services.embedding_service.logger.warning",
        capture_warning,
    )

    with pytest.raises(EmbeddingError):
        service.embed_sections([section])

    assert section.embedding_status == EmbeddingStatus.FAILED
    assert section.embedding_error is not None
    assert legal_text not in section.embedding_error
    assert section.text == legal_text
    assert warnings == [
        {
            "event": "section_embedding_failed",
            "section_id": "section-1",
            "error_type": "RuntimeError",
        }
    ]


def test_tokenizer_truncation_uses_tokens_not_character_count():
    service = _service(dimension=8, max_seq_length=4)
    long_tokens = " ".join(f"token{index}" for index in range(20))
    truncated = service.truncate_text(long_tokens)

    assert truncated == "token0 token1 token2 token3"
    assert len(truncated.split()) == 4
    assert len(truncated) != 4


def test_truncated_section_text_is_what_gets_hashed_and_embedded():
    service = _service(dimension=8, max_seq_length=4)
    act = _act(title="Act", act_number=None, year=None, category=None)
    short_tail = _section(
        act=act,
        section_number="1",
        section_path="1",
        heading=None,
        text="alpha beta gamma delta",
    )
    long_tail = _section(
        act=act,
        section_number="1",
        section_path="1",
        heading=None,
        text="alpha beta gamma delta epsilon zeta",
    )

    service.embed_sections([short_tail, long_tail])

    assert short_tail.embedding == long_tail.embedding
    assert short_tail.embedding_source_hash == long_tail.embedding_source_hash
    assert service.truncate_text(service.build_section_text(act, short_tail)) == (
        "Act Section 1 alpha"
    )


def test_embed_sections_marks_failed_when_truncate_text_raises(monkeypatch):
    legal_text = "The High Court shall have exclusive original jurisdiction."
    section = _section(text=legal_text)
    service = EmbeddingService(provider=_ExplodingTruncateProvider())
    warnings: list[dict[str, object]] = []

    def capture_warning(event: str, **kwargs: object) -> None:
        warnings.append({"event": event, **kwargs})

    monkeypatch.setattr(
        "app.services.embedding_service.logger.warning",
        capture_warning,
    )

    with pytest.raises(EmbeddingError, match="provider") as caught:
        service.embed_sections([section])

    assert isinstance(caught.value.__cause__, RuntimeError)
    assert section.embedding_status == EmbeddingStatus.FAILED
    assert section.embedding_error == "Embedding provider failed"
    assert legal_text not in section.embedding_error
    assert section.embedding is None
    assert warnings == [
        {
            "event": "section_embedding_failed",
            "section_id": "section-1",
            "error_type": "RuntimeError",
        }
    ]


def test_needs_embedding_survives_truncate_failure_then_batch_marks_failed(monkeypatch):
    service = EmbeddingService(provider=_ExplodingTruncateProvider())
    ready = _section(
        embedding=[0.1] * 384,
        embedding_provider="hash-test",
        embedding_model="hash-test",
        embedding_dimension=384,
        embedding_source_hash="0" * 64,
        embedding_status=EmbeddingStatus.READY,
    )
    warnings: list[dict[str, object]] = []
    monkeypatch.setattr(
        "app.services.embedding_service.logger.warning",
        lambda event, **kwargs: warnings.append({"event": event, **kwargs}),
    )

    assert service.needs_embedding(ready) is True
    with pytest.raises(EmbeddingError):
        service.embed_sections([ready])
    assert ready.embedding_status == EmbeddingStatus.FAILED
    assert warnings[0]["error_type"] == "RuntimeError"


def _sentence_transformer_provider(
    monkeypatch,
    *,
    tokenizer: object,
    max_seq_length: int = 4,
) -> tuple[SentenceTransformerProvider, _RecordingModel]:
    model = _RecordingModel(dimension=8, max_seq_length=max_seq_length)
    model.tokenizer = tokenizer

    def fake_load(model_name: str, revision: str, device: str):
        return model

    monkeypatch.setattr(
        "app.services.embedding_providers.load_sentence_transformer",
        fake_load,
    )
    provider = SentenceTransformerProvider(
        model_name="test-model",
        dimension=8,
        revision="main",
        device="cpu",
        batch_size=8,
    )
    return provider, model


def test_source_hash_matches_the_truncated_string_that_is_embedded():
    provider = _NonIdempotentTruncateProvider(dimension=8, max_seq_length=4)
    service = EmbeddingService(provider=provider)
    act = _act(title="Act", act_number=None, year=None, category=None)
    section = _section(
        act=act,
        section_number="1",
        section_path="1",
        heading=None,
        text="alpha beta gamma delta epsilon zeta",
    )
    truncated_once = provider.truncate_text(service.build_section_text(act, section))

    service.embed_sections([section])

    assert truncated_once == "<t> Act Section 1"
    assert section.embedding_source_hash == hashlib.sha256(
        truncated_once.encode("utf-8")
    ).hexdigest()
    assert provider.encode_calls[0] == [truncated_once]


def test_embed_does_not_apply_a_second_truncation_before_encode():
    provider = _NonIdempotentTruncateProvider(dimension=8, max_seq_length=4)
    service = EmbeddingService(provider=provider)
    query = "alpha beta gamma delta epsilon zeta"
    truncated_once = provider.truncate_text(query)
    truncated_twice = provider.truncate_text(truncated_once)

    service.embed_query(query)

    assert truncated_once == "<t> alpha beta gamma"
    assert truncated_twice == "<t> <t> alpha beta"
    assert truncated_once != truncated_twice
    assert provider.encode_calls[0] == [truncated_once]


def test_sentence_transformer_truncation_reserves_special_token_budget(monkeypatch):
    provider, _model = _sentence_transformer_provider(
        monkeypatch,
        tokenizer=_WhitespaceTokenizer(),
        max_seq_length=4,
    )
    # max_length=4 with CLS+SEP leaves two content tokens.
    truncated = provider.truncate_text("alpha beta gamma delta epsilon")

    assert truncated == "alpha beta"
    assert len(truncated.split()) == 2


def test_special_token_budget_matches_encode_content_window(monkeypatch):
    """Hash must describe content that fits after CLS/SEP consume the max length."""

    class _EncodeAwareModel(_RecordingModel):
        def encode(self, texts, **kwargs):
            self.encode_calls.append({"texts": list(texts), **kwargs})
            # Simulate encode() re-tokenizing with special tokens and dropping overflow.
            kept = []
            for text in texts:
                tokens = text.split()
                kept.append(" ".join(tokens[: max(0, self.max_seq_length - 2)]))
            self.encode_calls[-1]["effective"] = kept
            return [[0.5] * self.dimension for _ in texts]

    model = _EncodeAwareModel(dimension=8, max_seq_length=4)
    model.tokenizer = _WhitespaceTokenizer()

    def fake_load(model_name: str, revision: str, device: str):
        return model

    monkeypatch.setattr(
        "app.services.embedding_providers.load_sentence_transformer",
        fake_load,
    )
    provider = SentenceTransformerProvider(
        model_name="test-model",
        dimension=8,
        revision="main",
        device="cpu",
        batch_size=8,
    )
    service = EmbeddingService(provider=provider)
    query = "alpha beta gamma delta epsilon"
    truncated = provider.truncate_text(query)

    service.embed_query(query)

    assert truncated == "alpha beta"
    assert model.encode_calls[0]["texts"] == [truncated]
    assert model.encode_calls[0]["effective"] == [truncated]


def test_deterministic_provider_encodes_caller_text_without_truncating():
    provider = DeterministicTestProvider(dimension=8, max_seq_length=2)
    long_text = "alpha beta gamma delta"
    truncated = provider.truncate_text(long_text)

    assert truncated == "alpha beta"
    assert provider.embed_query(long_text) != provider.embed_query(truncated)
    assert provider.embed_documents([long_text])[0] == provider.embed_query(long_text)


def test_embed_text_uses_configured_hash_test_provider(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("EMBEDDING_PROVIDER", "hash-test")
    from app.core.config import get_settings

    get_settings.cache_clear()
    try:
        vector = embed_text("High Court jurisdiction over civil matters.")
        assert len(vector) == 384
        assert math.sqrt(sum(component * component for component in vector)) == pytest.approx(
            1.0
        )
        assert embed_text("High Court jurisdiction over civil matters.") == vector
        assert get_settings().embedding_provider == "hash-test"
    finally:
        get_settings.cache_clear()


def test_embedding_service_respects_sentence_transformers_settings_without_pytest_override(
    monkeypatch,
):
    loads: list[int] = []

    def fake_load(model_name: str, revision: str, device: str):
        loads.append(1)
        return _RecordingModel(dimension=384)

    monkeypatch.setattr(
        "app.services.embedding_providers.load_sentence_transformer",
        fake_load,
    )
    settings = Settings(
        environment="test",
        embedding_provider="sentence-transformers",
        embedding_dimension=384,
    )
    service = EmbeddingService(settings=settings)

    vector = service.embed_query("jurisdiction")

    assert loads == [1]
    assert len(vector) == 384


def test_cosine_similarity_of_identical_and_orthogonal_unit_vectors():
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)
    assert cosine_similarity([], [1.0]) == 0.0
