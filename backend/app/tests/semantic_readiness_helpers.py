from uuid import uuid4

from app.core.roles import EmbeddingStatus, ProcessingStatus
from app.db.session import SessionLocal
from app.models.act_section import ActSection
from app.models.legal_act import LegalAct
from app.services.text_cleaner import normalize_for_search


def enable_semantic_search(monkeypatch) -> None:
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "semantic_search_enabled", True)


def postgres_schema(monkeypatch, *, vector_extension=True, column_dimension=384) -> None:
    monkeypatch.setattr(
        "app.services.semantic_readiness.inspect_database_semantic_schema",
        lambda db: ("postgresql", vector_extension, column_dimension),
    )


def fail_embedding_model_load(monkeypatch) -> None:
    from app.core.config import get_settings
    from app.services.embedding_providers import reset_shared_model

    reset_shared_model()
    monkeypatch.setattr(get_settings(), "embedding_provider", "sentence-transformers")

    def fail_load(*_args, **_kwargs):
        raise OSError("model missing")

    monkeypatch.setattr(
        "app.services.embedding_providers.load_sentence_transformer",
        fail_load,
    )


def add_section(
    *,
    status: EmbeddingStatus,
    embedding_provider: str | None = None,
    embedding_model: str | None = None,
    embedding_dimension: int | None = None,
) -> None:
    title = f"Readiness {status.value} Act {uuid4().hex[:8]}"
    with SessionLocal() as db:
        act = LegalAct(
            title=title,
            normalized_title=normalize_for_search(title),
            source_file_name=f"{uuid4().hex}.pdf",
            stored_file_path=f"{uuid4().hex}.pdf",
            file_sha256=uuid4().hex.ljust(64, "0")[:64],
            processing_status=ProcessingStatus.VERIFIED,
            raw_text="Readiness probe body",
        )
        db.add(act)
        db.flush()
        db.add(
            ActSection(
                act_id=act.id,
                section_number="1",
                section_path="1",
                heading="Readiness",
                text="Readiness probe body",
                normalized_text=normalize_for_search("Readiness probe body"),
                sort_order=1,
                embedding=[0.1] * 384 if embedding_provider else None,
                embedding_status=status,
                embedding_provider=embedding_provider,
                embedding_model=embedding_model,
                embedding_dimension=embedding_dimension,
            )
        )
        db.commit()
