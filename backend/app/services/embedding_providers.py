from __future__ import annotations

import hashlib
import math
import re
from threading import Lock
from typing import Protocol

from app.core.config import Settings, get_settings

_WHITESPACE = re.compile(r"\s+")
_shared_model_lock = Lock()
_shared_model: object | None = None
_shared_model_key: tuple[str, str, str] | None = None


class EmbeddingProvider(Protocol):
    """Callers truncate once via ``truncate_text``, then ``embed_*`` encodes as-is."""

    provider_name: str
    model_name: str
    dimension: int

    def truncate_text(self, text: str) -> str: ...
    def embed_query(self, text: str) -> list[float]: ...
    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...


def load_sentence_transformer(model_name: str, revision: str, device: str) -> object:
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(model_name, revision=revision, device=device)


def reset_shared_model() -> None:
    global _shared_model, _shared_model_key
    with _shared_model_lock:
        _shared_model = None
        _shared_model_key = None


def _shared_sentence_transformer(model_name: str, revision: str, device: str) -> object:
    global _shared_model, _shared_model_key
    key = (model_name, revision, device)
    with _shared_model_lock:
        if _shared_model is None or _shared_model_key != key:
            _shared_model = load_sentence_transformer(model_name, revision, device)
            _shared_model_key = key
        return _shared_model


def _hash_vector(text: str, dimension: int) -> list[float]:
    normalized = _WHITESPACE.sub(" ", (text or "").lower()).strip()
    if not normalized:
        return [0.0] * dimension
    seed = hashlib.sha256(normalized.encode("utf-8")).digest()
    values: list[float] = []
    block = seed
    while len(values) < dimension:
        block = hashlib.sha256(block).digest()
        values.extend((byte / 255.0) * 2 - 1 for byte in block)
    vector = values[:dimension]
    norm = math.sqrt(sum(item * item for item in vector)) or 1.0
    return [item / norm for item in vector]


def _truncate_whitespace(text: str, max_seq_length: int) -> str:
    tokens = text.split()
    if len(tokens) <= max_seq_length:
        return text
    return " ".join(tokens[:max_seq_length])


def _as_float_matrix(encoded: object) -> list[list[float]]:
    values = encoded.tolist() if hasattr(encoded, "tolist") else encoded
    if not values:
        return []
    first = values[0]
    if isinstance(first, int | float):
        values = [values]
    return [[float(component) for component in vector] for vector in values]


class DeterministicTestProvider:
    """Network-free hash embeddings for tests. Not used in production."""

    provider_name = "hash-test"
    model_name = "hash-test"

    def __init__(self, dimension: int = 384, max_seq_length: int = 256) -> None:
        self.dimension = dimension
        self.max_seq_length = max_seq_length

    @classmethod
    def from_settings(cls, settings: Settings) -> DeterministicTestProvider:
        return cls(dimension=settings.embedding_dimension)

    def truncate_text(self, text: str) -> str:
        return _truncate_whitespace(text, self.max_seq_length)

    def embed_query(self, text: str) -> list[float]:
        return _hash_vector(text, self.dimension)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_query(text) for text in texts]


class SentenceTransformerProvider:
    provider_name = "sentence-transformers"

    def __init__(
        self,
        model_name: str,
        dimension: int,
        revision: str,
        device: str,
        batch_size: int,
    ) -> None:
        self.model_name = model_name
        self.dimension = dimension
        self._revision = revision
        self._device = device
        self._batch_size = batch_size

    @classmethod
    def from_settings(cls, settings: Settings) -> SentenceTransformerProvider:
        return cls(
            model_name=settings.embedding_model,
            dimension=settings.embedding_dimension,
            revision=settings.embedding_model_revision,
            device=settings.embedding_device,
            batch_size=settings.embedding_batch_size,
        )

    def _get_model(self) -> object:
        return _shared_sentence_transformer(self.model_name, self._revision, self._device)

    def truncate_text(self, text: str) -> str:
        if not text:
            return text
        model = self._get_model()
        tokenizer = model.tokenizer
        max_length = model.max_seq_length or 256
        encoded = tokenizer(
            text,
            truncation=True,
            max_length=max_length,
            add_special_tokens=False,
        )
        return tokenizer.decode(encoded["input_ids"], skip_special_tokens=True)

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        encoded = self._get_model().encode(
            texts,
            normalize_embeddings=True,
            batch_size=self._batch_size,
        )
        return _as_float_matrix(encoded)


def get_embedding_provider(settings: Settings | None = None) -> EmbeddingProvider:
    resolved = settings or get_settings()
    if resolved.embedding_provider == "hash-test":
        return DeterministicTestProvider.from_settings(resolved)
    return SentenceTransformerProvider.from_settings(resolved)
