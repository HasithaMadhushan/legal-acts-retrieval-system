from uuid import uuid4

from app.core.roles import EmbeddingStatus, ProcessingStatus, UserRole, VerificationStatus
from app.db.session import SessionLocal
from app.models.act_section import ActSection
from app.models.legal_act import LegalAct
from app.services.embedding_service import embed_text
from app.services.search_service import search
from app.services.text_cleaner import normalize_for_search


def test_search_paginates_beyond_two_hundred_fifty_acts(client, admin_token):
    with SessionLocal() as db:
        for index in range(260):
            title = f"Pagination Probe Act {index}"
            db.add(
                LegalAct(
                    title=title,
                    normalized_title=normalize_for_search(title),
                    act_number=str(index),
                    year=2000,
                    category="Probe",
                    source_file_name=f"probe-{index}.pdf",
                    stored_file_path=f"probe-{index}.pdf",
                    file_sha256=uuid4().hex.ljust(64, "0")[:64],
                    raw_text="Pagination probe body",
                    processing_status=ProcessingStatus.VERIFIED,
                )
            )
        db.commit()

    first = client.get(
        "/api/v1/search",
        params={"q": "Pagination Probe", "limit": 25, "offset": 0},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    deep = client.get(
        "/api/v1/search",
        params={"q": "Pagination Probe", "limit": 25, "offset": 250},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert first.status_code == 200
    assert deep.status_code == 200
    assert first.json()["total_results"] >= 260
    assert len(deep.json()["results"]) >= 1
    first_ids = {item["id"] for item in first.json()["results"]}
    deep_ids = {item["id"] for item in deep.json()["results"]}
    assert first_ids.isdisjoint(deep_ids)


def test_semantic_search_disabled_returns_400(client, user_token):
    response = client.get(
        "/api/v1/search",
        params={"q": "jurisdiction", "search_mode": "semantic"},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert response.status_code == 400
    assert "not enabled" in response.json()["detail"].lower()


def test_semantic_search_enabled_but_not_ready_returns_503(client, user_token, monkeypatch):
    _enable_semantic_search(monkeypatch)

    response = client.get(
        "/api/v1/search",
        params={"q": "jurisdiction", "search_mode": "semantic"},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert response.status_code == 503
    assert "not ready" in response.json()["detail"].lower()


def test_keyword_search_stays_available_when_semantic_is_not_ready(
    client, user_token, monkeypatch
):
    _enable_semantic_search(monkeypatch)

    response = client.get(
        "/api/v1/search",
        params={"q": "jurisdiction", "search_mode": "keyword"},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert response.status_code == 200


def test_all_search_stays_available_when_semantic_is_not_ready(client, user_token, monkeypatch):
    _enable_semantic_search(monkeypatch)

    response = client.get(
        "/api/v1/search",
        params={"q": "jurisdiction", "search_mode": "all"},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert response.status_code == 200


def test_semantic_search_returns_503_when_vector_extension_is_missing(
    client, user_token, monkeypatch
):
    _enable_semantic_search(monkeypatch)
    _postgres_schema(monkeypatch, vector_extension=False, column_dimension=384)

    response = client.get(
        "/api/v1/search",
        params={"q": "jurisdiction", "search_mode": "semantic"},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert response.status_code == 503
    assert "not ready" in response.json()["detail"].lower()


def test_semantic_search_returns_503_when_column_dimension_is_wrong(
    client, user_token, monkeypatch
):
    _enable_semantic_search(monkeypatch)
    _postgres_schema(monkeypatch, vector_extension=True, column_dimension=768)

    response = client.get(
        "/api/v1/search",
        params={"q": "jurisdiction", "search_mode": "semantic"},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert response.status_code == 503
    assert "not ready" in response.json()["detail"].lower()


def test_semantic_search_does_not_fall_back_to_hash_when_model_is_unavailable(
    client, user_token, monkeypatch
):
    _enable_semantic_search(monkeypatch)
    _postgres_schema(monkeypatch)
    _fail_embedding_model_load(monkeypatch)

    response = client.get(
        "/api/v1/search",
        params={"q": "jurisdiction", "search_mode": "semantic"},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert response.status_code == 503
    assert "not ready" in response.json()["detail"].lower()


def test_semantic_search_returns_503_when_backfill_is_incomplete(
    client, user_token, monkeypatch
):
    _add_section(status=EmbeddingStatus.PENDING)
    _enable_semantic_search(monkeypatch)
    _postgres_schema(monkeypatch)

    response = client.get(
        "/api/v1/search",
        params={"q": "jurisdiction", "search_mode": "semantic"},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert response.status_code == 503
    assert "not ready" in response.json()["detail"].lower()


def test_semantic_search_hides_unverified_sections_from_general_users(monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "semantic_search_enabled", True)
    with SessionLocal() as db:
        act = LegalAct(
            title="Embedding Visibility Act",
            normalized_title=normalize_for_search("Embedding Visibility Act"),
            source_file_name="embed.pdf",
            stored_file_path="embed.pdf",
            file_sha256="c" * 64,
            processing_status=ProcessingStatus.VERIFIED,
            raw_text="High Court jurisdiction over civil matters.",
        )
        db.add(act)
        db.flush()
        verified = ActSection(
            act_id=act.id,
            section_number="1",
            section_path="1",
            heading="Verified jurisdiction",
            text="High Court jurisdiction over civil matters.",
            normalized_text=normalize_for_search("High Court jurisdiction over civil matters."),
            sort_order=1,
            verification_status=VerificationStatus.VERIFIED,
            embedding=embed_text("High Court jurisdiction over civil matters."),
        )
        pending = ActSection(
            act_id=act.id,
            section_number="2",
            section_path="2",
            heading="Pending jurisdiction",
            text="High Court jurisdiction draft notes.",
            normalized_text=normalize_for_search("High Court jurisdiction draft notes."),
            sort_order=2,
            verification_status=VerificationStatus.PENDING,
            embedding=embed_text("High Court jurisdiction draft notes."),
        )
        db.add_all([verified, pending])
        db.commit()

        public = search(
            db,
            query="High Court jurisdiction",
            role=UserRole.GENERAL_USER,
            search_mode="semantic",
        )
        lawyer = search(
            db,
            query="High Court jurisdiction",
            role=UserRole.LAWYER,
            search_mode="semantic",
        )
        public_section_ids = {item.section_id for item in public.results}
        lawyer_section_ids = {item.section_id for item in lawyer.results}
        assert verified.id in public_section_ids
        assert pending.id not in public_section_ids
        assert pending.id in lawyer_section_ids


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
