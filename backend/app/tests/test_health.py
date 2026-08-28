from uuid import uuid4

from app.core.roles import EmbeddingStatus, ProcessingStatus
from app.db.session import SessionLocal
from app.models.act_section import ActSection
from app.models.legal_act import LegalAct
from app.services.text_cleaner import normalize_for_search


def test_health_reports_ok_when_all_checks_pass(client):
    response = client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["checks"]["database"]["ok"] is True
    assert data["checks"]["upload_directory"]["ok"] is True
    assert data["checks"]["parser_configuration"]["ok"] is True
    assert data["checks"]["semantic_configuration"]["ok"] is True


def test_health_reports_semantic_readiness_without_degrading_when_disabled(client):
    response = client.get("/health")

    assert response.status_code == 200
    semantic = response.json()["checks"]["semantic_configuration"]
    assert semantic["ok"] is True
    assert semantic["enabled"] is False
    assert semantic["ready"] is False
    assert semantic["dialect"] == "sqlite"
    assert semantic["postgresql"] is False
    assert semantic["vector_extension"] is False
    assert semantic["column_dimension"] is None
    assert semantic["configured_dimension"] == 384
    assert semantic["provider_ready"] is True
    assert semantic["pending_count"] == 0
    assert semantic["failed_count"] == 0
    assert semantic["stale_count"] == 0
    assert any("postgresql" in reason.lower() for reason in semantic["reasons"])


def test_parser_configuration_defaults_to_pymupdf(monkeypatch):
    from app.core.config import Settings

    monkeypatch.delenv("DOC_PARSER_PRIMARY", raising=False)

    assert Settings(_env_file=None).doc_parser_primary == "pymupdf"


def test_response_includes_request_id_header(client):
    response = client.get("/health")

    assert response.status_code == 200
    request_id = response.headers.get("x-request-id")
    assert request_id
    # Should be a UUID4 string, e.g. 8-4-4-4-12 hex groups.
    assert len(request_id) == 36
    assert request_id.count("-") == 4


def test_health_accepts_pdf_inspector_parser_configuration(client, monkeypatch):
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "doc_parser_primary", "pdf_inspector")

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["checks"]["parser_configuration"] == {
        "ok": True,
        "parser_requested": "pdf_inspector",
    }


def test_health_flags_unknown_parser_configuration(client, monkeypatch):
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "doc_parser_primary", "not-a-real-parser")

    response = client.get("/health")

    assert response.status_code == 503
    data = response.json()
    assert data["status"] == "degraded"
    assert data["checks"]["parser_configuration"]["ok"] is False


def test_health_stays_ok_when_semantic_disabled_despite_pending_embeddings(client):
    _add_section(status=EmbeddingStatus.PENDING)

    response = client.get("/health")

    assert response.status_code == 200
    semantic = response.json()["checks"]["semantic_configuration"]
    assert semantic["ok"] is True
    assert semantic["enabled"] is False
    assert semantic["ready"] is False
    assert semantic["pending_count"] >= 1


def test_health_degrades_when_semantic_enabled_on_sqlite(client, monkeypatch):
    _enable_semantic_search(monkeypatch)

    response = client.get("/health")

    assert response.status_code == 503
    data = response.json()
    assert data["status"] == "degraded"
    semantic = data["checks"]["semantic_configuration"]
    assert semantic["ok"] is False
    assert semantic["enabled"] is True
    assert semantic["ready"] is False


def test_health_degrades_when_semantic_enabled_without_vector_extension(client, monkeypatch):
    _enable_semantic_search(monkeypatch)
    _postgres_schema(monkeypatch, vector_extension=False, column_dimension=384)

    response = client.get("/health")

    assert response.status_code == 503
    semantic = response.json()["checks"]["semantic_configuration"]
    assert semantic["ok"] is False
    assert semantic["vector_extension"] is False
    assert any("vector extension" in reason.lower() for reason in semantic["reasons"])


def test_health_degrades_when_semantic_enabled_with_wrong_column_dimension(client, monkeypatch):
    _enable_semantic_search(monkeypatch)
    _postgres_schema(monkeypatch, vector_extension=True, column_dimension=768)

    response = client.get("/health")

    assert response.status_code == 503
    semantic = response.json()["checks"]["semantic_configuration"]
    assert semantic["ok"] is False
    assert semantic["column_dimension"] == 768
    assert semantic["configured_dimension"] == 384
    assert any("dimension" in reason.lower() for reason in semantic["reasons"])


def test_health_degrades_when_semantic_model_is_unavailable(client, monkeypatch):
    _enable_semantic_search(monkeypatch)
    _postgres_schema(monkeypatch)
    _fail_embedding_model_load(monkeypatch)

    response = client.get("/health")

    assert response.status_code == 503
    semantic = response.json()["checks"]["semantic_configuration"]
    assert semantic["ok"] is False
    assert semantic["provider_ready"] is False
    assert any("provider" in reason.lower() for reason in semantic["reasons"])


def test_health_degrades_when_semantic_backfill_is_incomplete(client, monkeypatch):
    _add_section(status=EmbeddingStatus.PENDING)
    _add_section(status=EmbeddingStatus.FAILED)
    _add_section(status=EmbeddingStatus.STALE)
    _enable_semantic_search(monkeypatch)
    _postgres_schema(monkeypatch)

    response = client.get("/health")

    assert response.status_code == 503
    semantic = response.json()["checks"]["semantic_configuration"]
    assert semantic["ok"] is False
    assert semantic["pending_count"] >= 1
    assert semantic["failed_count"] >= 1
    assert semantic["stale_count"] >= 1
    assert any("backfill" in reason.lower() for reason in semantic["reasons"])


def _enable_semantic_search(monkeypatch) -> None:
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "semantic_search_enabled", True)


def _postgres_schema(monkeypatch, *, vector_extension=True, column_dimension=384) -> None:
    monkeypatch.setattr(
        "app.services.semantic_readiness.inspect_database_semantic_schema",
        lambda db: ("postgresql", vector_extension, column_dimension),
    )


def _fail_embedding_model_load(monkeypatch) -> None:
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


def _add_section(*, status: EmbeddingStatus) -> None:
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
                embedding_status=status,
            )
        )
        db.commit()

