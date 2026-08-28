from __future__ import annotations

import hashlib
import math

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.core.roles import EmbeddingStatus
from app.models.mixins import utc_now
from app.services.embedding_providers import (
    EmbeddingProvider,
    get_embedding_provider,
)

logger = get_logger(__name__)
_PROVIDER_FAILED = "Embedding provider failed"


class EmbeddingError(Exception):
    """Raised when embedding generation or validation fails."""


def _optional_text(value: object | None) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _act_citation(act: object | None) -> str:
    if act is None:
        return ""
    act_number = _optional_text(getattr(act, "act_number", None))
    year = getattr(act, "year", None)
    if act_number and year is not None:
        return f"Act {act_number} of {year}"
    if act_number:
        return f"Act {act_number}"
    if year is not None:
        return f"Year {year}"
    return ""


def _category_line(act: object | None) -> str:
    if act is None:
        return ""
    category = _optional_text(getattr(act, "category", None))
    if not category:
        return ""
    return f"Category: {category}"


def _section_citation(section: object) -> str:
    number = _optional_text(getattr(section, "section_number", None))
    path = _optional_text(getattr(section, "section_path", None))
    if number and path and path != number:
        return f"Section {number} / {path}"
    if number:
        return f"Section {number}"
    if path:
        return f"Section {path}"
    return ""


def _as_float_list(vector: object) -> list[float]:
    values = vector.tolist() if hasattr(vector, "tolist") else vector
    return [float(component) for component in values]


def _validated_vector(vector: object, dimension: int) -> list[float]:
    values = _as_float_list(vector)
    if len(values) != dimension:
        raise EmbeddingError(f"Embedding dimension mismatch: expected {dimension}")
    if any(not math.isfinite(component) for component in values):
        raise EmbeddingError("Embedding contains non-finite values")
    return values


def _resolve_provider(
    provider: EmbeddingProvider | None,
    settings: Settings,
) -> EmbeddingProvider:
    if provider is not None:
        return provider
    return get_embedding_provider(settings)


class EmbeddingService:
    def __init__(
        self,
        provider: EmbeddingProvider | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._provider = _resolve_provider(provider, self._settings)

    def truncate_text(self, text: str) -> str:
        return self._provider.truncate_text(text)

    def build_section_text(self, act: object, section: object) -> str:
        parts = [
            _optional_text(getattr(act, "title", None) if act is not None else None),
            _act_citation(act),
            _category_line(act),
            _section_citation(section),
            _optional_text(getattr(section, "heading", None)),
            _optional_text(getattr(section, "text", None)),
        ]
        return "\n".join(part for part in parts if part)

    def source_hash(self, text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def embed_query(self, text: str) -> list[float]:
        try:
            vector = self._provider.embed_query(self.truncate_text(text))
            return _validated_vector(vector, self._provider.dimension)
        except EmbeddingError:
            raise
        except Exception as exc:
            raise EmbeddingError(_PROVIDER_FAILED) from exc

    def needs_embedding(self, section: object) -> bool:
        status = getattr(section, "embedding_status", EmbeddingStatus.PENDING)
        if status != EmbeddingStatus.READY:
            return True
        try:
            return not self._metadata_is_current(section)
        except Exception:
            # Truncation/model load failures are handled when embedding runs.
            return True

    def embed_sections(self, sections: list[object], *, force: bool = False) -> None:
        pending = list(sections) if force else [
            section for section in sections if self.needs_embedding(section)
        ]
        if not pending:
            self._log_completion(embedded=0, skipped=len(sections))
            return
        batch_size = self._settings.embedding_batch_size
        embedded = 0
        for start in range(0, len(pending), batch_size):
            batch = pending[start : start + batch_size]
            embedded += self._embed_batch(batch)
        self._log_completion(embedded=embedded, skipped=len(sections) - len(pending))

    def _metadata_is_current(self, section: object) -> bool:
        return (
            getattr(section, "embedding", None) is not None
            and getattr(section, "embedding_provider", None) == self._provider.provider_name
            and getattr(section, "embedding_model", None) == self._provider.model_name
            and getattr(section, "embedding_dimension", None) == self._provider.dimension
            and getattr(section, "embedding_source_hash", None)
            == self.source_hash(self._truncated_section_text(section))
        )

    def _log_completion(self, *, embedded: int, skipped: int) -> None:
        logger.info(
            "sections_embedded",
            embedded=embedded,
            skipped=skipped,
            provider=self._provider.provider_name,
            model=self._provider.model_name,
        )

    def _truncated_section_text(self, section: object) -> str:
        return self.truncate_text(
            self.build_section_text(getattr(section, "act", None), section)
        )

    def _embed_batch(self, batch: list[object]) -> int:
        try:
            texts = [self._truncated_section_text(section) for section in batch]
            vectors = self._provider.embed_documents(texts)
            validated = [
                _validated_vector(vector, self._provider.dimension) for vector in vectors
            ]
        except EmbeddingError as exc:
            self._mark_failed(batch, exc)
            raise
        except Exception as exc:
            self._mark_failed(batch, exc)
            raise EmbeddingError(_PROVIDER_FAILED) from exc
        if len(validated) != len(batch):
            mismatch = EmbeddingError(_PROVIDER_FAILED)
            self._mark_failed(batch, mismatch)
            raise mismatch
        for section, truncated, vector in zip(batch, texts, validated, strict=True):
            self._apply_ready(section, truncated, vector)
        return len(batch)

    def _apply_ready(self, section: object, truncated: str, vector: list[float]) -> None:
        section.embedding = vector
        section.embedding_provider = self._provider.provider_name
        section.embedding_model = self._provider.model_name
        section.embedding_dimension = self._provider.dimension
        section.embedding_source_hash = self.source_hash(truncated)
        section.embedding_status = EmbeddingStatus.READY
        section.embedded_at = utc_now()
        section.embedding_error = None

    def _mark_failed(self, sections: list[object], exc: BaseException) -> None:
        error_type = type(exc).__name__
        for section in sections:
            section.embedding_status = EmbeddingStatus.FAILED
            section.embedding_error = _PROVIDER_FAILED
            logger.warning(
                "section_embedding_failed",
                section_id=getattr(section, "id", None),
                error_type=error_type,
            )


def embed_text(text: str) -> list[float]:
    return EmbeddingService().embed_query(text)


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    return sum(a * b for a, b in zip(left, right, strict=True))
