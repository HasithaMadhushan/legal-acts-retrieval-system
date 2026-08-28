from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.roles import EmbeddingStatus
from app.models.act_section import ActSection
from app.services.embedding_providers import get_embedding_provider

_VECTOR_DIMENSION = re.compile(r"vector\((\d+)\)", re.IGNORECASE)


@dataclass(frozen=True)
class SemanticReadiness:
    enabled: bool
    ready: bool
    dialect: str
    postgresql: bool
    vector_extension: bool
    column_dimension: int | None
    configured_dimension: int
    provider_ready: bool
    pending_count: int
    failed_count: int
    stale_count: int
    reasons: tuple[str, ...]

    def as_health_check(self) -> dict[str, object]:
        return {
            "ok": self.ready or not self.enabled,
            "enabled": self.enabled,
            "ready": self.ready,
            "dialect": self.dialect,
            "postgresql": self.postgresql,
            "vector_extension": self.vector_extension,
            "column_dimension": self.column_dimension,
            "configured_dimension": self.configured_dimension,
            "provider_ready": self.provider_ready,
            "pending_count": self.pending_count,
            "failed_count": self.failed_count,
            "stale_count": self.stale_count,
            "reasons": list(self.reasons),
        }


def inspect_database_semantic_schema(db: Session) -> tuple[str, bool, int | None]:
    dialect = db.get_bind().dialect.name
    if dialect != "postgresql":
        return dialect, False, None
    return dialect, _vector_extension_installed(db), _embedding_column_dimension(db)


def check_provider_readiness(settings: Settings) -> tuple[bool, str | None]:
    try:
        provider = get_embedding_provider(settings)
        if provider.dimension != settings.embedding_dimension:
            return False, "Embedding provider dimension does not match configuration"
        provider.truncate_text("readiness")
        return True, None
    except Exception as exc:
        return False, f"Embedding provider is not ready ({type(exc).__name__})"


def probe_semantic_readiness(
    db: Session, settings: Settings | None = None
) -> SemanticReadiness:
    resolved = settings or get_settings()
    try:
        return _probe(db, resolved)
    except Exception as exc:
        return _failed_probe(resolved, exc)


def _probe(db: Session, settings: Settings) -> SemanticReadiness:
    dialect, vector_extension, column_dimension = inspect_database_semantic_schema(db)
    pending_count, failed_count, stale_count = _status_counts(db)
    provider_ready, provider_reason = check_provider_readiness(settings)
    reasons = _readiness_reasons(
        dialect=dialect,
        vector_extension=vector_extension,
        column_dimension=column_dimension,
        configured_dimension=settings.embedding_dimension,
        provider_ready=provider_ready,
        provider_reason=provider_reason,
        pending_count=pending_count,
        failed_count=failed_count,
        stale_count=stale_count,
    )
    return SemanticReadiness(
        enabled=settings.semantic_search_enabled,
        ready=not reasons,
        dialect=dialect,
        postgresql=dialect == "postgresql",
        vector_extension=vector_extension,
        column_dimension=column_dimension,
        configured_dimension=settings.embedding_dimension,
        provider_ready=provider_ready,
        pending_count=pending_count,
        failed_count=failed_count,
        stale_count=stale_count,
        reasons=tuple(reasons),
    )


def _failed_probe(settings: Settings, exc: BaseException) -> SemanticReadiness:
    return SemanticReadiness(
        enabled=settings.semantic_search_enabled,
        ready=False,
        dialect="unknown",
        postgresql=False,
        vector_extension=False,
        column_dimension=None,
        configured_dimension=settings.embedding_dimension,
        provider_ready=False,
        pending_count=0,
        failed_count=0,
        stale_count=0,
        reasons=(f"Semantic readiness probe failed ({type(exc).__name__})",),
    )


def _vector_extension_installed(db: Session) -> bool:
    result = db.execute(
        text("SELECT 1 FROM pg_extension WHERE extname = :name"),
        {"name": "vector"},
    )
    return result.scalar() is not None


def _embedding_column_dimension(db: Session) -> int | None:
    result = db.execute(
        text(
            """
            SELECT format_type(a.atttypid, a.atttypmod)
            FROM pg_attribute a
            JOIN pg_class c ON a.attrelid = c.oid
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE c.relname = 'act_sections'
              AND a.attname = 'embedding'
              AND n.nspname = 'public'
              AND NOT a.attisdropped
            """
        )
    )
    return _parse_vector_dimension(result.scalar())


def _parse_vector_dimension(type_name: object) -> int | None:
    if not isinstance(type_name, str):
        return None
    match = _VECTOR_DIMENSION.search(type_name)
    if match is None:
        return None
    return int(match.group(1))


def _status_counts(db: Session) -> tuple[int, int, int]:
    rows = dict(
        db.query(ActSection.embedding_status, func.count())
        .group_by(ActSection.embedding_status)
        .all()
    )
    return (
        int(rows.get(EmbeddingStatus.PENDING, 0)),
        int(rows.get(EmbeddingStatus.FAILED, 0)),
        int(rows.get(EmbeddingStatus.STALE, 0)),
    )


def _readiness_reasons(
    *,
    dialect: str,
    vector_extension: bool,
    column_dimension: int | None,
    configured_dimension: int,
    provider_ready: bool,
    provider_reason: str | None,
    pending_count: int,
    failed_count: int,
    stale_count: int,
) -> list[str]:
    reasons: list[str] = []
    if dialect != "postgresql":
        reasons.append("Semantic search requires PostgreSQL")
    elif not vector_extension:
        reasons.append("PostgreSQL vector extension is not installed")
    if column_dimension is None:
        reasons.append("Embedding column dimension is unavailable")
    elif column_dimension != configured_dimension:
        reasons.append(
            "Embedding column dimension does not match the configured model dimension"
        )
    if not provider_ready:
        reasons.append(provider_reason or "Embedding provider is not ready")
    incomplete = pending_count + failed_count + stale_count
    if incomplete:
        reasons.append(
            "Incomplete embedding backfill: "
            f"{pending_count} pending, {failed_count} failed, {stale_count} stale"
        )
    return reasons
