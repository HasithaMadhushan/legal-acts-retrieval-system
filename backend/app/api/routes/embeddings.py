from fastapi import APIRouter, Depends
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.core.config import get_settings
from app.core.roles import EmbeddingStatus
from app.db.session import get_db
from app.models.act_section import ActSection
from app.models.legal_act import LegalAct
from app.schemas.embedding import EmbeddingStatusResponse
from app.services.semantic_readiness import probe_semantic_readiness

router = APIRouter(
    prefix="/embeddings",
    tags=["embeddings"],
    dependencies=[Depends(require_admin)],
)


@router.get("/status", response_model=EmbeddingStatusResponse)
def get_embedding_status(db: Session = Depends(get_db)) -> dict[str, object]:
    settings = get_settings()
    readiness = probe_semantic_readiness(db, settings)
    status_rows = db.query(ActSection.embedding_status, func.count(ActSection.id)).group_by(
        ActSection.embedding_status
    )
    counts = {status: int(count) for status, count in status_rows}
    total = sum(counts.values())
    failures = (
        db.query(ActSection, LegalAct)
        .join(LegalAct, LegalAct.id == ActSection.act_id)
        .filter(ActSection.embedding_status == EmbeddingStatus.FAILED)
        .order_by(ActSection.updated_at.desc())
        .limit(10)
        .all()
    )
    return {
        "provider": settings.embedding_provider,
        "model": settings.embedding_model,
        "model_revision": settings.embedding_model_revision,
        "dimension": settings.embedding_dimension,
        "semantic_enabled": settings.semantic_search_enabled,
        "semantic_ready": readiness.ready,
        "readiness_reasons": list(readiness.reasons),
        "counts": {
            "total": total,
            "ready": counts.get(EmbeddingStatus.READY, 0),
            "pending": counts.get(EmbeddingStatus.PENDING, 0),
            "stale": counts.get(EmbeddingStatus.STALE, 0),
            "failed": counts.get(EmbeddingStatus.FAILED, 0),
        },
        "index": {
            "dialect": readiness.dialect,
            "vector_extension": readiness.vector_extension,
            "column_dimension": readiness.column_dimension,
            "hnsw_index_present": _hnsw_index_present(db),
        },
        "latest_embedding_at": db.query(func.max(ActSection.embedded_at)).scalar(),
        "latest_backfill_run": None,
        "failure_samples": [
            {
                "section_id": section.id,
                "act_id": act.id,
                "act_title": act.title,
                "section_path": section.section_path,
                "error": (section.embedding_error or "Unknown embedding failure")[:300],
            }
            for section, act in failures
        ],
        "remediation_command": "python -m app.db.backfill_embeddings --resume --retry-failed",
    }


def _hnsw_index_present(db: Session) -> bool | None:
    if db.get_bind().dialect.name != "postgresql":
        return None
    return bool(
        db.execute(
            text(
                "SELECT 1 FROM pg_indexes "
                "WHERE schemaname = 'public' AND tablename = 'act_sections' "
                "AND indexdef ILIKE '%USING hnsw%' LIMIT 1"
            )
        ).scalar()
    )
