from uuid import uuid4

from app.core.roles import EmbeddingStatus, ProcessingStatus, UserRole, VerificationStatus
from app.db.session import SessionLocal
from app.models.act_section import ActSection
from app.models.legal_act import LegalAct
from app.services.embedding_providers import get_embedding_provider
from app.services.search_service import search
from app.services.text_cleaner import normalize_for_search

DIMENSION = 384


def _basis(index: int) -> list[float]:
    vector = [0.0] * DIMENSION
    vector[index] = 1.0
    return vector


QUERY_VECTOR = _basis(0)
NEAR_VECTOR = _basis(0)
MID_VECTOR = [0.8] + [0.6] + [0.0] * (DIMENSION - 2)
FAR_VECTOR = _basis(1)


def _sha() -> str:
    return uuid4().hex.ljust(64, "0")[:64]


def _use_query_vector(monkeypatch, vector: list[float]) -> None:
    monkeypatch.setattr(
        "app.services.embedding_service.EmbeddingService.embed_query",
        lambda self, text: vector,
    )
    monkeypatch.setattr("app.services.embedding_service.embed_text", lambda text: vector)


def _ready_fields() -> dict[str, object]:
    provider = get_embedding_provider()
    return {
        "embedding_status": EmbeddingStatus.READY,
        "embedding_provider": provider.provider_name,
        "embedding_model": provider.model_name,
        "embedding_dimension": provider.dimension,
    }


def _add_act(db, *, title: str, **overrides) -> LegalAct:
    fields = {
        "title": title,
        "normalized_title": normalize_for_search(title),
        "source_file_name": f"{title}.pdf",
        "stored_file_path": f"{title}.pdf",
        "file_sha256": _sha(),
        "processing_status": ProcessingStatus.VERIFIED,
        "raw_text": title,
        "year": 2020,
        "act_number": "1",
        "category": "Courts",
        **overrides,
    }
    act = LegalAct(**fields)
    db.add(act)
    db.flush()
    return act


def _add_section(
    db,
    act: LegalAct,
    *,
    section_id: str,
    heading: str,
    embedding: list[float] | None,
    verification_status: VerificationStatus = VerificationStatus.VERIFIED,
    **overrides,
) -> ActSection:
    fields = {
        "id": section_id,
        "act_id": act.id,
        "section_number": section_id.split("-")[-1],
        "section_path": section_id,
        "heading": heading,
        "text": heading,
        "normalized_text": normalize_for_search(heading),
        "sort_order": len(heading),
        "verification_status": verification_status,
        "embedding": embedding,
        **_ready_fields(),
        **overrides,
    }
    section = ActSection(**fields)
    db.add(section)
    return section


def test_semantic_search_orders_ready_neighbours_and_excludes_pending(monkeypatch):
    _use_query_vector(monkeypatch, QUERY_VECTOR)
    with SessionLocal() as db:
        act = _add_act(db, title="Nearest Neighbour Act")
        _add_section(db, act, section_id="section-far", heading="Far clause", embedding=FAR_VECTOR)
        _add_section(
            db, act, section_id="section-near", heading="Near clause", embedding=NEAR_VECTOR
        )
        _add_section(db, act, section_id="section-mid", heading="Mid clause", embedding=MID_VECTOR)
        _add_section(
            db,
            act,
            section_id="section-pending",
            heading="Pending closer clause",
            embedding=NEAR_VECTOR,
            embedding_status=EmbeddingStatus.PENDING,
        )
        db.commit()

        response = search(
            db,
            query="jurisdiction",
            role=UserRole.LAWYER,
            search_mode="semantic",
        )

    assert [item.section_id for item in response.results] == [
        "section-near",
        "section-mid",
        "section-far",
    ]
    assert response.total_results == 3
    assert response.section_results == 3
    assert response.act_results == 0
    assert response.reference_results == 0
    assert response.results[0].score == 100.0


def test_semantic_search_prioritizes_exact_section_bound_to_its_act(monkeypatch):
    _use_query_vector(monkeypatch, QUERY_VECTOR)
    with SessionLocal() as db:
        exact_act = _add_act(
            db,
            title="Anti-Corruption Act",
            act_number="9",
            year=2023,
        )
        wrong_act = _add_act(
            db,
            title="Integrity Commission Act",
            act_number="12",
            year=2022,
        )
        _add_section(
            db,
            exact_act,
            section_id="exact-section",
            heading="Exact but distant",
            embedding=FAR_VECTOR,
            section_number="34",
            section_path="34",
        )
        _add_section(
            db,
            wrong_act,
            section_id="wrong-act-neighbour",
            heading="Close but wrong Act",
            embedding=NEAR_VECTOR,
            section_number="34",
            section_path="34",
        )
        db.commit()

        response = search(
            db,
            query="section 34 of Act No. 9 of 2023",
            role=UserRole.LAWYER,
            search_mode="semantic",
        )

    assert response.results[0].id == "exact-section"
    assert response.results[0].score > 100.0
    assert next(item for item in response.results if item.id == "wrong-act-neighbour").score <= 100


def test_semantic_search_prioritizes_sections_from_exact_act(monkeypatch):
    _use_query_vector(monkeypatch, QUERY_VECTOR)
    with SessionLocal() as db:
        exact_act = _add_act(
            db,
            title="Anti-Corruption Act",
            act_number="9",
            year=2023,
        )
        wrong_act = _add_act(
            db,
            title="Integrity Commission Act",
            act_number="12",
            year=2022,
        )
        _add_section(
            db,
            exact_act,
            section_id="exact-act-section",
            heading="Exact Act but distant",
            embedding=FAR_VECTOR,
        )
        _add_section(
            db,
            wrong_act,
            section_id="semantic-neighbour",
            heading="Close neighbour",
            embedding=NEAR_VECTOR,
        )
        db.commit()

        response = search(
            db,
            query="Act No. 9 of 2023",
            role=UserRole.LAWYER,
            search_mode="semantic",
        )

    assert response.results[0].id == "exact-act-section"
    assert response.results[0].score > 100.0


def test_semantic_search_excludes_failed_stale_and_mismatched_identity(monkeypatch):
    _use_query_vector(monkeypatch, QUERY_VECTOR)
    with SessionLocal() as db:
        act = _add_act(db, title="Identity Filter Act")
        _add_section(
            db, act, section_id="section-ok", heading="Matching ready", embedding=NEAR_VECTOR
        )
        _add_section(
            db,
            act,
            section_id="section-failed",
            heading="Failed ready-looking",
            embedding=NEAR_VECTOR,
            embedding_status=EmbeddingStatus.FAILED,
        )
        _add_section(
            db,
            act,
            section_id="section-stale",
            heading="Stale ready-looking",
            embedding=NEAR_VECTOR,
            embedding_status=EmbeddingStatus.STALE,
        )
        _add_section(
            db,
            act,
            section_id="section-other-model",
            heading="Wrong model",
            embedding=NEAR_VECTOR,
            embedding_model="other-model",
        )
        _add_section(
            db,
            act,
            section_id="section-other-provider",
            heading="Wrong provider",
            embedding=NEAR_VECTOR,
            embedding_provider="sentence-transformers",
        )
        _add_section(
            db,
            act,
            section_id="section-other-dim",
            heading="Wrong dimension",
            embedding=NEAR_VECTOR,
            embedding_dimension=768,
        )
        db.commit()

        response = search(db, query="jurisdiction", role=UserRole.ADMIN, search_mode="semantic")

    assert [item.section_id for item in response.results] == ["section-ok"]
    assert response.total_results == 1


def test_semantic_search_hides_unverified_sections_from_general_users(monkeypatch):
    _use_query_vector(monkeypatch, QUERY_VECTOR)
    with SessionLocal() as db:
        act = _add_act(db, title="Visibility Act")
        verified = _add_section(
            db, act, section_id="section-verified", heading="Verified", embedding=NEAR_VECTOR
        )
        pending = _add_section(
            db,
            act,
            section_id="section-unverified",
            heading="Unverified",
            embedding=MID_VECTOR,
            verification_status=VerificationStatus.PENDING,
        )
        db.commit()

        public = search(
            db, query="jurisdiction", role=UserRole.GENERAL_USER, search_mode="semantic"
        )
        lawyer = search(db, query="jurisdiction", role=UserRole.LAWYER, search_mode="semantic")
        admin = search(db, query="jurisdiction", role=UserRole.ADMIN, search_mode="semantic")

    assert {item.section_id for item in public.results} == {verified.id}
    assert {item.section_id for item in lawyer.results} == {verified.id, pending.id}
    assert {item.section_id for item in admin.results} == {verified.id, pending.id}


def test_semantic_search_admin_sees_uploaded_acts_lawyer_does_not(monkeypatch):
    _use_query_vector(monkeypatch, QUERY_VECTOR)
    with SessionLocal() as db:
        uploaded = _add_act(
            db, title="Uploaded Draft Act", processing_status=ProcessingStatus.UPLOADED
        )
        processed = _add_act(
            db, title="Processed Act", processing_status=ProcessingStatus.PROCESSED
        )
        _add_section(
            db, uploaded, section_id="section-uploaded", heading="Draft", embedding=NEAR_VECTOR
        )
        _add_section(
            db, processed, section_id="section-processed", heading="Live", embedding=FAR_VECTOR
        )
        db.commit()

        lawyer = search(db, query="jurisdiction", role=UserRole.LAWYER, search_mode="semantic")
        admin = search(db, query="jurisdiction", role=UserRole.ADMIN, search_mode="semantic")

    assert [item.section_id for item in lawyer.results] == ["section-processed"]
    assert {item.section_id for item in admin.results} == {
        "section-uploaded",
        "section-processed",
    }


def test_semantic_search_applies_act_and_verification_filters_before_ranking(monkeypatch):
    _use_query_vector(monkeypatch, QUERY_VECTOR)
    with SessionLocal() as db:
        courts = _add_act(
            db,
            title="Courts Act",
            year=1978,
            act_number="2",
            category="Courts",
            processing_status=ProcessingStatus.VERIFIED,
        )
        tax = _add_act(
            db,
            title="Tax Act",
            year=2022,
            act_number="25",
            category="Tax",
            processing_status=ProcessingStatus.PROCESSED,
        )
        _add_section(
            db, courts, section_id="section-courts", heading="Courts", embedding=NEAR_VECTOR
        )
        _add_section(
            db,
            tax,
            section_id="section-tax-verified",
            heading="Tax verified",
            embedding=NEAR_VECTOR,
        )
        _add_section(
            db,
            tax,
            section_id="section-tax-pending",
            heading="Tax pending",
            embedding=NEAR_VECTOR,
            verification_status=VerificationStatus.PENDING,
        )
        db.commit()

        by_year = search(
            db, query="jurisdiction", role=UserRole.LAWYER, search_mode="semantic", year=2022
        )
        by_number = search(
            db,
            query="jurisdiction",
            role=UserRole.LAWYER,
            search_mode="semantic",
            act_number="2",
        )
        by_category = search(
            db,
            query="jurisdiction",
            role=UserRole.LAWYER,
            search_mode="semantic",
            category="Tax",
        )
        by_status = search(
            db,
            query="jurisdiction",
            role=UserRole.ADMIN,
            search_mode="semantic",
            processing_status=ProcessingStatus.PROCESSED,
        )
        by_verification = search(
            db,
            query="jurisdiction",
            role=UserRole.LAWYER,
            search_mode="semantic",
            verification_status=VerificationStatus.PENDING,
        )

    assert {item.section_id for item in by_year.results} == {
        "section-tax-verified",
        "section-tax-pending",
    }
    assert [item.section_id for item in by_number.results] == ["section-courts"]
    assert {item.section_id for item in by_category.results} == {
        "section-tax-verified",
        "section-tax-pending",
    }
    assert {item.section_id for item in by_status.results} == {
        "section-tax-verified",
        "section-tax-pending",
    }
    assert [item.section_id for item in by_verification.results] == ["section-tax-pending"]


def test_semantic_search_paginates_with_exact_filtered_count(monkeypatch):
    _use_query_vector(monkeypatch, QUERY_VECTOR)
    with SessionLocal() as db:
        act = _add_act(db, title="Pagination Act")
        _add_section(db, act, section_id="section-a", heading="A", embedding=NEAR_VECTOR)
        _add_section(db, act, section_id="section-b", heading="B", embedding=MID_VECTOR)
        _add_section(db, act, section_id="section-c", heading="C", embedding=FAR_VECTOR)
        db.commit()

        first = search(
            db,
            query="jurisdiction",
            role=UserRole.LAWYER,
            search_mode="semantic",
            limit=1,
            offset=0,
        )
        second = search(
            db,
            query="jurisdiction",
            role=UserRole.LAWYER,
            search_mode="semantic",
            limit=1,
            offset=1,
        )

    assert first.total_results == 3
    assert first.section_results == 3
    assert [item.section_id for item in first.results] == ["section-a"]
    assert [item.section_id for item in second.results] == ["section-b"]
    assert first.results[0].id != second.results[0].id


def test_semantic_search_clamps_orthogonal_neighbour_score_to_zero(monkeypatch):
    _use_query_vector(monkeypatch, QUERY_VECTOR)
    with SessionLocal() as db:
        act = _add_act(db, title="Score Act")
        _add_section(db, act, section_id="section-far", heading="Orthogonal", embedding=FAR_VECTOR)
        db.commit()
        response = search(db, query="jurisdiction", role=UserRole.LAWYER, search_mode="semantic")

    assert response.results[0].score == 0.0


def test_semantic_search_generates_the_query_vector_once(monkeypatch):
    calls = {"count": 0}

    def _embed(self, text):
        calls["count"] += 1
        return QUERY_VECTOR

    monkeypatch.setattr("app.services.embedding_service.EmbeddingService.embed_query", _embed)
    with SessionLocal() as db:
        act = _add_act(db, title="Once Act")
        _add_section(db, act, section_id="section-1", heading="One", embedding=NEAR_VECTOR)
        _add_section(db, act, section_id="section-2", heading="Two", embedding=FAR_VECTOR)
        db.commit()
        search(db, query="jurisdiction", role=UserRole.LAWYER, search_mode="semantic")

    assert calls["count"] == 1
