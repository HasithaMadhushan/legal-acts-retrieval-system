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
    def __call__(self, text, truncation=True, max_length=None, add_special_tokens=False):
        tokens = text.split()
        if truncation and max_length is not None:
            tokens = tokens[:max_length]
        return {"input_ids": tokens}

    def decode(self, ids, skip_special_tokens=True):
        return " ".join(ids)


class _BadVectorProvider:
    def __init__(self, vector: list[float], dimension: int = 384) -> None:
        self.provider_name = "hash-test"
        self.model_name = "hash-test"
        self.dimension = dimension
        self._vector = vector

    def embed_query(self, text: str) -> list[float]:
        return list(self._vector)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_query(text) for text in texts]


class _ExplodingProvider:
    provider_name = "hash-test"
    model_name = "hash-test"
    dimension = 384

    def embed_query(self, text: str) -> list[float]:
        raise RuntimeError("upstream inference failed")

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        raise RuntimeError("upstream inference failed")


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


def test_embed_sections_marks_failed_without_storing_legal_text_on_provider_error():
    legal_text = "Secret exclusive original jurisdiction clause."
    section = _section(text=legal_text)
    service = EmbeddingService(provider=_ExplodingProvider())

    with pytest.raises(EmbeddingError):
        service.embed_sections([section])

    assert section.embedding_status == EmbeddingStatus.FAILED
    assert section.embedding_error is not None
    assert legal_text not in section.embedding_error
    assert section.text == legal_text


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


def test_embed_text_uses_configured_test_provider_path():
    vector = embed_text("High Court jurisdiction over civil matters.")

    assert len(vector) == 384
    assert math.sqrt(sum(component * component for component in vector)) == pytest.approx(1.0)
    assert embed_text("High Court jurisdiction over civil matters.") == vector


def test_cosine_similarity_of_identical_and_orthogonal_unit_vectors():
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)
    assert cosine_similarity([], [1.0]) == 0.0
