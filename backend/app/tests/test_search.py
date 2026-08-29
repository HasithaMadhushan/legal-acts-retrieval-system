from uuid import uuid4

import pytest

from app.core.config import get_settings
from app.core.roles import (
    EmbeddingStatus,
    ProcessingStatus,
    RelationshipType,
    UserRole,
    VerificationStatus,
)
from app.db.session import SessionLocal
from app.models.act_section import ActSection
from app.models.legal_act import LegalAct
from app.models.legal_reference import LegalReference
from app.services.embedding_providers import get_embedding_provider
from app.services.search_service import _fulltext_condition, _is_postgres, search
from app.services.text_cleaner import normalize_for_search


def _sha() -> str:
    return uuid4().hex.ljust(64, "0")[:64]


def _create_search_fixture() -> dict[str, str]:
    with SessionLocal() as db:
        judicature = LegalAct(
            title="Judicature Act",
            normalized_title=normalize_for_search("Judicature Act"),
            act_number="2",
            year=1978,
            category="Courts",
            source_name="Parliament",
            source_file_name="judicature.pdf",
            stored_file_path="judicature.pdf",
            file_sha256=_sha(),
            raw_text="Judicature Act body text and court jurisdiction.",
            processing_status=ProcessingStatus.PROCESSED,
        )
        levy = LegalAct(
            title="Social Security Contribution Levy Act",
            normalized_title=normalize_for_search("Social Security Contribution Levy Act"),
            act_number="25",
            year=2022,
            category="Tax",
            source_name="Parliament",
            source_file_name="levy.pdf",
            stored_file_path="levy.pdf",
            file_sha256=_sha(),
            raw_text="Contribution levy body text.",
            processing_status=ProcessingStatus.VERIFIED,
        )
        draft = LegalAct(
            title="Draft Pending Act",
            normalized_title=normalize_for_search("Draft Pending Act"),
            act_number="99",
            year=2026,
            category="Draft",
            source_file_name="draft.pdf",
            stored_file_path="draft.pdf",
            file_sha256=_sha(),
            raw_text="Pending administrative text.",
            processing_status=ProcessingStatus.UPLOADED,
        )
        db.add_all([judicature, levy, draft])
        db.flush()

        section_9 = ActSection(
            act_id=judicature.id,
            section_number="9",
            section_path="9",
            heading="High Court jurisdiction",
            text="Section 9 describes High Court jurisdiction.",
            normalized_text=normalize_for_search("Section 9 describes High Court jurisdiction."),
            sort_order=1,
            verification_status=VerificationStatus.VERIFIED,
        )
        pending_section = ActSection(
            act_id=judicature.id,
            section_number="10",
            section_path="10",
            heading="Pending procedure",
            text="Pending procedure text.",
            normalized_text=normalize_for_search("Pending procedure text."),
            sort_order=2,
            verification_status=VerificationStatus.PENDING,
        )
        levy_section = ActSection(
            act_id=levy.id,
            section_number="4",
            section_path="4",
            heading="Tax liability",
            text="Section 4 covers taxable turnover.",
            normalized_text=normalize_for_search("Section 4 covers taxable turnover."),
            sort_order=1,
            verification_status=VerificationStatus.VERIFIED,
        )
        db.add_all([section_9, pending_section, levy_section])
        db.flush()

        mapped_reference = LegalReference(
            source_act_id=levy.id,
            source_section_id=levy_section.id,
            raw_reference_text="Section 9 of the Judicature Act is hereby amended",
            context_snippet="Section 9 of the Judicature Act is hereby amended.",
            relationship_type=RelationshipType.AMENDS,
            target_act_title_raw="Judicature Act",
            target_act_id=judicature.id,
            target_section_number="9",
            target_section_id=section_9.id,
            confidence_score=0.95,
            verification_status=VerificationStatus.VERIFIED,
        )
        unresolved_reference = LegalReference(
            source_act_id=levy.id,
            source_section_id=levy_section.id,
            raw_reference_text="The First Schedule is amended",
            context_snippet="The First Schedule is amended by addition.",
            relationship_type=RelationshipType.ADDS,
            target_section_path="First Schedule",
            confidence_score=0.5,
            verification_status=VerificationStatus.NEEDS_REVIEW,
        )
        pending_reference = LegalReference(
            source_act_id=judicature.id,
            source_section_id=pending_section.id,
            raw_reference_text="Pending reference",
            context_snippet="Pending reference context.",
            relationship_type=RelationshipType.REPEALS,
            confidence_score=0.4,
            verification_status=VerificationStatus.PENDING,
        )
        db.add_all([mapped_reference, unresolved_reference, pending_reference])
        db.commit()
        return {
            "judicature_id": judicature.id,
            "levy_id": levy.id,
            "draft_id": draft.id,
            "section_9_id": section_9.id,
            "mapped_reference_id": mapped_reference.id,
            "unresolved_reference_id": unresolved_reference.id,
            "pending_reference_id": pending_reference.id,
        }


def test_search_by_act_title_ranks_exact_title_first():
    ids = _create_search_fixture()
    with SessionLocal() as db:
        response = search(db, query="Judicature Act", role=UserRole.LAWYER)

    assert response.results[0].result_type == "ACT"
    assert response.results[0].act_id == ids["judicature_id"]
    assert response.total_results >= 1
    assert response.act_results >= 1


def test_search_by_act_number_and_year_filter():
    _create_search_fixture()
    with SessionLocal() as db:
        response = search(
            db,
            query="",
            role=UserRole.LAWYER,
            act_number="25",
            year=2022,
        )

    assert response.total_results > 0
    assert {result.act_number for result in response.results} == {"25"}
    assert {result.year for result in response.results} == {2022}


def test_search_by_section_number_and_heading():
    _create_search_fixture()
    with SessionLocal() as db:
        number_response = search(db, query="9", role=UserRole.LAWYER)
        heading_response = search(db, query="High Court jurisdiction", role=UserRole.LAWYER)

    assert number_response.results[0].result_type == "SECTION"
    assert number_response.results[0].section_number == "9"
    assert heading_response.results[0].section_heading == "High Court jurisdiction"


def test_search_by_section_text():
    _create_search_fixture()
    with SessionLocal() as db:
        response = search(db, query="taxable turnover", role=UserRole.GENERAL_USER)

    assert any(
        result.result_type == "SECTION" and result.section_number == "4"
        for result in response.results
    )


def test_relationship_type_and_mapped_filters():
    ids = _create_search_fixture()
    with SessionLocal() as db:
        mapped = search(
            db,
            query="",
            role=UserRole.ADMIN,
            relationship_type=RelationshipType.AMENDS,
            mapped_status="mapped",
        )
        unresolved = search(db, query="", role=UserRole.ADMIN, mapped_status="unresolved")

    assert [result.reference_id for result in mapped.results] == [ids["mapped_reference_id"]]
    assert ids["unresolved_reference_id"] in {result.reference_id for result in unresolved.results}
    assert all(result.mapped is False for result in unresolved.results)


def test_filter_by_category_and_processing_status():
    ids = _create_search_fixture()
    with SessionLocal() as db:
        response = search(
            db,
            query="",
            role=UserRole.ADMIN,
            category="Draft",
            processing_status=ProcessingStatus.UPLOADED,
        )

    assert response.total_results == 1
    assert response.results[0].act_id == ids["draft_id"]
    assert response.results[0].processing_status == ProcessingStatus.UPLOADED


def test_admin_sees_pending_data_and_general_user_does_not():
    ids = _create_search_fixture()
    with SessionLocal() as db:
        admin = search(db, query="pending", role=UserRole.ADMIN)
        general = search(db, query="pending", role=UserRole.GENERAL_USER)

    assert ids["pending_reference_id"] in {result.reference_id for result in admin.results}
    assert all(
        result.verification_status == VerificationStatus.VERIFIED
        for result in general.results
        if result.verification_status
    )


def test_lawyer_can_view_advanced_read_only_status_filters():
    ids = _create_search_fixture()
    with SessionLocal() as db:
        response = search(
            db,
            query="pending",
            role=UserRole.LAWYER,
            verification_status=VerificationStatus.PENDING,
        )

    assert ids["pending_reference_id"] in {result.reference_id for result in response.results}


def test_search_pagination():
    _create_search_fixture()
    with SessionLocal() as db:
        first = search(db, query="", role=UserRole.ADMIN, limit=2, offset=0)
        second = search(db, query="", role=UserRole.ADMIN, limit=2, offset=2)

    assert first.limit == 2
    assert first.offset == 0
    assert len(first.results) == 2
    assert second.offset == 2
    first_ids = {result.id for result in first.results}
    second_ids = {result.id for result in second.results}
    assert first_ids.isdisjoint(second_ids)


def test_empty_query_with_filters_and_long_query_validation():
    _create_search_fixture()
    with SessionLocal() as db:
        filtered = search(db, query="   ", role=UserRole.ADMIN, category="Tax")
        assert filtered.total_results > 0
        with pytest.raises(ValueError):
            search(db, query="x" * 201, role=UserRole.ADMIN)


def test_search_endpoint_validation(client, admin_token):
    response = client.get(
        "/api/v1/search",
        headers={"Authorization": f"Bearer {admin_token}"},
        params={"q": "x" * 201},
    )

    assert response.status_code == 422


def test_is_postgres_is_false_for_the_sqlite_test_database():
    """F-013: search() must fall back to ILIKE (not the Postgres-only
    `search_vector` full-text column) on SQLite, which is what tests and
    local dev without Docker use."""
    with SessionLocal() as db:
        assert _is_postgres(db) is False


def test_fulltext_condition_targets_the_search_vector_column_with_bound_query():
    """F-013 regression: verifies the exact full-text SQL fragment used
    against Postgres's `search_vector` (see the `20260706_01` migration)
    without requiring a real Postgres connection in the test suite."""
    condition = _fulltext_condition("legal_acts", "gaming levy")

    compiled = condition.compile()
    assert "legal_acts.search_vector" in str(compiled)
    assert "plainto_tsquery" in str(compiled)
    assert compiled.params == {"fts_query": "gaming levy"}


def test_semantic_mode_returns_only_ready_sections_not_keyword_acts():
    _create_search_fixture()
    with SessionLocal() as db:
        semantic = search(db, query="Judicature Act", role=UserRole.LAWYER, search_mode="semantic")
        keyword = search(db, query="Judicature Act", role=UserRole.LAWYER)

    assert semantic.act_results == 0
    assert semantic.reference_results == 0
    assert semantic.total_results == 0
    assert keyword.act_results >= 1


def test_search_uses_fulltext_condition_when_postgres_is_simulated(monkeypatch):
    """Forces the Postgres branch (via monkeypatch, since the test DB is
    SQLite) and confirms `search()` still runs end-to-end without raising --
    i.e. the extra `or_()` branch is wired up correctly, not just present in
    isolation."""
    _create_search_fixture()
    monkeypatch.setattr("app.services.search_service._is_postgres", lambda db: True)
    with SessionLocal() as db:
        # The simulated Postgres branch appends a `search_vector @@ ...`
        # clause that SQLite can't execute, so this should error at query
        # time -- proving the branch really is reached -- rather than
        # silently falling back to the ILIKE path.
        with pytest.raises(Exception, match="search_vector|no such column|OperationalError"):
            search(db, query="jurisdiction", role=UserRole.GENERAL_USER)


_HYBRID_DIMENSION = 384
_QUERY_VECTOR = [1.0] + [0.0] * (_HYBRID_DIMENSION - 1)
_NEAR_VECTOR = [1.0] + [0.0] * (_HYBRID_DIMENSION - 1)
_FAR_VECTOR = [0.0, 1.0] + [0.0] * (_HYBRID_DIMENSION - 2)


def _enable_hybrid(monkeypatch) -> None:
    from app.core.config import get_settings
    from app.services.semantic_readiness import SemanticReadiness

    monkeypatch.setattr(get_settings(), "semantic_search_enabled", True)
    monkeypatch.setattr(
        "app.services.semantic_readiness.probe_semantic_readiness",
        lambda db, settings=None: SemanticReadiness(
            enabled=True,
            ready=True,
            dialect="postgresql",
            postgresql=True,
            vector_extension=True,
            column_dimension=384,
            configured_dimension=384,
            provider_ready=True,
            pending_count=0,
            failed_count=0,
            stale_count=0,
            reasons=(),
        ),
    )


def _use_query_vector(monkeypatch, vector: list[float]) -> None:
    monkeypatch.setattr(
        "app.services.embedding_service.EmbeddingService.embed_query",
        lambda self, text: vector,
    )


def _ready_fields() -> dict[str, object]:
    provider = get_embedding_provider()
    return {
        "embedding_status": EmbeddingStatus.READY,
        "embedding_provider": provider.provider_name,
        "embedding_model": provider.model_name,
        "embedding_dimension": provider.dimension,
    }


def _hybrid_act(db, *, title: str, **overrides) -> LegalAct:
    act = LegalAct(
        title=title,
        normalized_title=normalize_for_search(title),
        act_number=overrides.pop("act_number", "1"),
        year=overrides.pop("year", 2020),
        category=overrides.pop("category", "Courts"),
        source_file_name=f"{title}.pdf",
        stored_file_path=f"{title}.pdf",
        file_sha256=uuid4().hex.ljust(64, "0")[:64],
        raw_text=overrides.pop("raw_text", title),
        processing_status=overrides.pop("processing_status", ProcessingStatus.VERIFIED),
        **overrides,
    )
    db.add(act)
    db.flush()
    return act


def _hybrid_section(
    db,
    act: LegalAct,
    *,
    section_id: str,
    heading: str,
    embedding: list[float] | None,
    text: str | None = None,
    **overrides,
) -> ActSection:
    body = text or heading
    section = ActSection(
        id=section_id,
        act_id=act.id,
        section_number=overrides.pop("section_number", section_id.split("-")[-1]),
        section_path=overrides.pop("section_path", section_id),
        heading=heading,
        text=body,
        normalized_text=normalize_for_search(body),
        sort_order=len(heading),
        verification_status=overrides.pop("verification_status", VerificationStatus.VERIFIED),
        embedding=embedding,
        **{**_ready_fields(), **overrides},
    )
    db.add(section)
    return section


def test_all_mode_fuses_semantic_sections_with_keyword_acts_when_ready(monkeypatch):
    _enable_hybrid(monkeypatch)
    _use_query_vector(monkeypatch, _QUERY_VECTOR)
    with SessionLocal() as db:
        keyword_act = _hybrid_act(db, title="Jurisdiction Act", raw_text="jurisdiction over courts")
        other = _hybrid_act(db, title="Unrelated Levy Act", raw_text="levy rates")
        _hybrid_section(
            db,
            other,
            section_id="section-semantic-only",
            heading="Tribunal competence",
            text="Tribunal competence without the keyword.",
            embedding=_NEAR_VECTOR,
        )
        _hybrid_section(
            db,
            keyword_act,
            section_id="section-keyword",
            heading="Jurisdiction clause",
            text="This clause repeats jurisdiction.",
            embedding=_FAR_VECTOR,
        )
        db.commit()
        keyword_act_id = keyword_act.id

        hybrid = search(db, query="jurisdiction", role=UserRole.LAWYER, search_mode="all")
        keyword = search(db, query="jurisdiction", role=UserRole.LAWYER, search_mode="keyword")
        semantic = search(db, query="jurisdiction", role=UserRole.LAWYER, search_mode="semantic")

    hybrid_ids = {(item.result_type, item.id) for item in hybrid.results}
    assert ("ACT", keyword_act_id) in hybrid_ids
    assert ("SECTION", "section-semantic-only") in hybrid_ids
    assert ("SECTION", "section-keyword") in hybrid_ids
    assert all(item.result_type != "ACT" for item in semantic.results)
    assert all(item.id != "section-semantic-only" for item in keyword.results)
    assert hybrid.total_results == len(hybrid.results)


def test_keyword_and_semantic_modes_stay_unmixed_when_hybrid_is_ready(monkeypatch):
    _enable_hybrid(monkeypatch)
    _use_query_vector(monkeypatch, _QUERY_VECTOR)
    with SessionLocal() as db:
        keyword_act = _hybrid_act(db, title="Jurisdiction Act", raw_text="jurisdiction")
        other = _hybrid_act(db, title="Unrelated Levy Act", raw_text="levy rates")
        _hybrid_section(
            db,
            other,
            section_id="section-near",
            heading="Tribunal competence",
            embedding=_NEAR_VECTOR,
        )
        db.commit()
        act_id = keyword_act.id

        keyword = search(db, query="jurisdiction", role=UserRole.LAWYER, search_mode="keyword")
        semantic = search(db, query="jurisdiction", role=UserRole.LAWYER, search_mode="semantic")

    assert any(item.id == act_id for item in keyword.results)
    assert all(item.id != "section-near" for item in keyword.results)
    assert all(item.result_type == "SECTION" for item in semantic.results)
    assert semantic.act_results == 0


def test_all_mode_stays_keyword_only_when_semantic_is_disabled(monkeypatch):
    _use_query_vector(monkeypatch, _QUERY_VECTOR)
    with SessionLocal() as db:
        _hybrid_act(db, title="Jurisdiction Act", raw_text="jurisdiction")
        other = _hybrid_act(db, title="Unrelated Levy Act", raw_text="levy rates")
        _hybrid_section(
            db,
            other,
            section_id="section-near",
            heading="Tribunal competence",
            embedding=_NEAR_VECTOR,
        )
        db.commit()

        response = search(db, query="jurisdiction", role=UserRole.LAWYER, search_mode="all")

    assert all(item.id != "section-near" for item in response.results)
    assert any(item.result_type == "ACT" for item in response.results)


def test_all_mode_stays_keyword_only_when_semantic_is_enabled_but_not_ready(monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "semantic_search_enabled", True)
    _use_query_vector(monkeypatch, _QUERY_VECTOR)
    with SessionLocal() as db:
        _hybrid_act(db, title="Jurisdiction Act", raw_text="jurisdiction")
        other = _hybrid_act(db, title="Unrelated Levy Act", raw_text="levy rates")
        _hybrid_section(
            db,
            other,
            section_id="section-near",
            heading="Tribunal competence",
            embedding=_NEAR_VECTOR,
        )
        db.commit()

        response = search(db, query="jurisdiction", role=UserRole.LAWYER, search_mode="all")

    assert all(item.id != "section-near" for item in response.results)
    assert any(item.result_type == "ACT" for item in response.results)


def test_hybrid_exact_identifier_precedes_semantic_neighbour(monkeypatch):
    _enable_hybrid(monkeypatch)
    _use_query_vector(monkeypatch, _QUERY_VECTOR)
    with SessionLocal() as db:
        exact = _hybrid_act(
            db,
            title="Anti-Corruption Act",
            act_number="9",
            year=2023,
            raw_text="Short certified text.",
        )
        neighbour_host = _hybrid_act(
            db,
            title="Integrity Commission Act",
            act_number="12",
            year=2022,
            raw_text="Unrelated body.",
        )
        _hybrid_section(
            db,
            neighbour_host,
            section_id="section-near",
            heading="Integrity investigations",
            embedding=_NEAR_VECTOR,
        )
        db.commit()
        exact_id = exact.id

        response = search(db, query="Act No. 9 of 2023", role=UserRole.LAWYER, search_mode="all")

    assert response.results[0].result_type == "ACT"
    assert response.results[0].id == exact_id
    assert response.results[0].score > 100.0
    assert any(item.id == "section-near" for item in response.results)


def test_hybrid_exact_section_path_precedes_semantic_neighbour(monkeypatch):
    _enable_hybrid(monkeypatch)
    _use_query_vector(monkeypatch, _QUERY_VECTOR)
    with SessionLocal() as db:
        host = _hybrid_act(db, title="Penalties Act", act_number="4", year=2020, raw_text="body")
        _hybrid_section(
            db,
            host,
            section_id="zzz-exact",
            heading="Fine amounts",
            text="The fine is one hundred thousand rupees.",
            embedding=None,
            embedding_status=EmbeddingStatus.PENDING,
            section_number="34",
            section_path="34(2)(a)",
        )
        neighbour_host = _hybrid_act(
            db, title="Integrity Commission Act", act_number="12", year=2022, raw_text="Unrelated."
        )
        _hybrid_section(
            db,
            neighbour_host,
            section_id="aaa-near",
            heading="Integrity investigations",
            embedding=_NEAR_VECTOR,
        )
        db.commit()

        response = search(db, query="section 34(2)(a)", role=UserRole.LAWYER, search_mode="all")

    assert response.results[0].id == "zzz-exact"
    assert response.results[0].score > 100.0
    assert any(item.id == "aaa-near" for item in response.results)


def test_hybrid_paginates_after_fusion_without_duplicate_identities(monkeypatch):
    _enable_hybrid(monkeypatch)
    _use_query_vector(monkeypatch, _QUERY_VECTOR)
    with SessionLocal() as db:
        act = _hybrid_act(db, title="Jurisdiction Act", raw_text="jurisdiction")
        _hybrid_section(
            db,
            act,
            section_id="section-overlap",
            heading="Jurisdiction clause",
            text="This clause repeats jurisdiction.",
            embedding=_NEAR_VECTOR,
        )
        _hybrid_section(
            db,
            act,
            section_id="section-semantic-only",
            heading="Tribunal competence",
            embedding=_FAR_VECTOR,
        )
        db.commit()

        first = search(
            db, query="jurisdiction", role=UserRole.LAWYER, search_mode="all", limit=1, offset=0
        )
        second = search(
            db, query="jurisdiction", role=UserRole.LAWYER, search_mode="all", limit=1, offset=1
        )
        full = search(db, query="jurisdiction", role=UserRole.LAWYER, search_mode="all")

    identities = [(item.result_type, item.id) for item in full.results]
    assert len(identities) == len(set(identities))
    assert first.total_results == full.total_results == len(full.results)
    assert first.results[0].id != second.results[0].id
    assert {item.id for item in first.results}.isdisjoint({item.id for item in second.results})


def test_hybrid_candidate_total_is_stable_across_page_depth(monkeypatch):
    _enable_hybrid(monkeypatch)
    _use_query_vector(monkeypatch, _QUERY_VECTOR)
    monkeypatch.setattr(get_settings(), "semantic_candidate_limit", 2)
    with SessionLocal() as db:
        act = _hybrid_act(db, title="Jurisdiction Act", raw_text="jurisdiction")
        for index in range(3):
            _hybrid_section(
                db,
                act,
                section_id=f"stable-total-{index}",
                heading=f"Semantic clause {index}",
                embedding=_NEAR_VECTOR,
            )
        db.commit()

        first = search(
            db, query="jurisdiction", role=UserRole.LAWYER, search_mode="all", limit=1, offset=0
        )
        deeper = search(
            db, query="jurisdiction", role=UserRole.LAWYER, search_mode="all", limit=1, offset=3
        )

    assert first.total_results == deeper.total_results


def test_hybrid_exposes_score_components_to_admin_not_general_users(monkeypatch):
    _enable_hybrid(monkeypatch)
    _use_query_vector(monkeypatch, _QUERY_VECTOR)
    with SessionLocal() as db:
        act = _hybrid_act(db, title="Jurisdiction Act", raw_text="jurisdiction")
        _hybrid_section(
            db,
            act,
            section_id="section-near",
            heading="Tribunal competence",
            embedding=_NEAR_VECTOR,
        )
        db.commit()

        admin = search(db, query="jurisdiction", role=UserRole.ADMIN, search_mode="all")
        public = search(db, query="jurisdiction", role=UserRole.GENERAL_USER, search_mode="all")

    assert admin.results
    assert all(item.score_components is not None for item in admin.results)
    assert "keyword_rank" in admin.results[0].score_components
    assert "semantic_rank" in admin.results[0].score_components
    assert all(item.score_components is None for item in public.results)


def test_search_response_schema_includes_requested_and_effective_mode():
    from app.core.config import LEGAL_DISCLAIMER
    from app.schemas.search import SearchResponse

    payload = SearchResponse(
        query="jurisdiction",
        results=[],
        total_results=0,
        act_results=0,
        section_results=0,
        reference_results=0,
        limit=25,
        offset=0,
        disclaimer=LEGAL_DISCLAIMER,
        requested_mode="all",
        effective_mode="hybrid",
        embedding_model="sentence-transformers/all-MiniLM-L6-v2",
        semantic_ready=True,
    )
    dumped = payload.model_dump()

    assert dumped["query"] == "jurisdiction"
    assert dumped["requested_mode"] == "all"
    assert dumped["effective_mode"] == "hybrid"
    assert dumped["embedding_model"] == "sentence-transformers/all-MiniLM-L6-v2"
    assert dumped["semantic_ready"] is True


def test_search_response_keeps_legacy_fields_when_mode_metadata_is_omitted():
    from app.core.config import LEGAL_DISCLAIMER
    from app.schemas.search import SearchResponse

    dumped = SearchResponse(
        query="levy",
        results=[],
        total_results=0,
        act_results=0,
        section_results=0,
        reference_results=0,
        limit=10,
        offset=0,
        disclaimer=LEGAL_DISCLAIMER,
    ).model_dump()

    assert dumped["query"] == "levy"
    assert dumped["results"] == []
    assert dumped["total_results"] == 0
    assert dumped["disclaimer"] == LEGAL_DISCLAIMER
    assert dumped["requested_mode"] == "all"
    assert dumped["effective_mode"] == "keyword"
    assert dumped["semantic_ready"] is False


def test_all_mode_reports_keyword_not_hybrid_when_semantic_is_disabled():
    with SessionLocal() as db:
        response = search(db, query="Judicature Act", role=UserRole.LAWYER, search_mode="all")

    assert response.requested_mode == "all"
    assert response.effective_mode == "keyword"
    assert response.semantic_ready is False
    assert response.embedding_model == get_settings().embedding_model


def test_all_mode_reports_hybrid_when_semantic_is_ready(monkeypatch):
    _enable_hybrid(monkeypatch)
    _use_query_vector(monkeypatch, _QUERY_VECTOR)
    with SessionLocal() as db:
        act = _hybrid_act(db, title="Jurisdiction Act", raw_text="jurisdiction")
        _hybrid_section(
            db,
            act,
            section_id="mode-semantic-candidate",
            heading="Tribunal competence",
            embedding=_NEAR_VECTOR,
        )
        db.commit()
        response = search(db, query="jurisdiction", role=UserRole.LAWYER, search_mode="all")

    assert response.requested_mode == "all"
    assert response.effective_mode == "hybrid"
    assert response.semantic_ready is True
    assert response.embedding_model == get_settings().embedding_model


def test_all_mode_reports_keyword_when_filters_skip_semantic_branch(monkeypatch):
    _enable_hybrid(monkeypatch)
    _use_query_vector(monkeypatch, _QUERY_VECTOR)
    with SessionLocal() as db:
        response = search(
            db,
            query="amend",
            role=UserRole.LAWYER,
            search_mode="all",
            relationship_type=RelationshipType.AMENDS,
        )

    assert response.semantic_ready is True
    assert response.effective_mode == "keyword"


def test_all_mode_reports_keyword_when_semantic_candidate_pool_is_empty(monkeypatch):
    _enable_hybrid(monkeypatch)
    _use_query_vector(monkeypatch, _QUERY_VECTOR)
    with SessionLocal() as db:
        _hybrid_act(db, title="Jurisdiction Act", raw_text="jurisdiction")
        db.commit()
        response = search(db, query="jurisdiction", role=UserRole.LAWYER, search_mode="all")

    assert response.semantic_ready is True
    assert response.effective_mode == "keyword"


def test_keyword_mode_never_claims_hybrid_when_semantic_is_ready(monkeypatch):
    _enable_hybrid(monkeypatch)
    _use_query_vector(monkeypatch, _QUERY_VECTOR)
    with SessionLocal() as db:
        _hybrid_act(db, title="Jurisdiction Act", raw_text="jurisdiction")
        db.commit()
        response = search(db, query="jurisdiction", role=UserRole.LAWYER, search_mode="keyword")

    assert response.requested_mode == "keyword"
    assert response.effective_mode == "keyword"
    assert response.semantic_ready is True


def test_semantic_mode_reports_semantic_effective_mode_when_ready(monkeypatch):
    _enable_hybrid(monkeypatch)
    _use_query_vector(monkeypatch, _QUERY_VECTOR)
    with SessionLocal() as db:
        act = _hybrid_act(db, title="Jurisdiction Act", raw_text="jurisdiction")
        _hybrid_section(
            db,
            act,
            section_id="section-near",
            heading="Tribunal competence",
            embedding=_NEAR_VECTOR,
        )
        db.commit()
        response = search(db, query="jurisdiction", role=UserRole.LAWYER, search_mode="semantic")

    assert response.requested_mode == "semantic"
    assert response.effective_mode == "semantic"
    assert response.semantic_ready is True


def test_all_mode_reports_keyword_when_semantic_is_enabled_but_not_ready(monkeypatch):
    monkeypatch.setattr(get_settings(), "semantic_search_enabled", True)
    with SessionLocal() as db:
        response = search(db, query="jurisdiction", role=UserRole.LAWYER, search_mode="all")

    assert response.requested_mode == "all"
    assert response.effective_mode == "keyword"
    assert response.semantic_ready is False
    assert response.embedding_model == get_settings().embedding_model


def test_search_endpoint_includes_mode_metadata_without_dropping_legacy_fields(client, user_token):
    response = client.get(
        "/api/v1/search",
        params={"q": "jurisdiction", "search_mode": "all"},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    body = response.json()

    assert response.status_code == 200
    assert body["query"] == "jurisdiction"
    assert "results" in body
    assert "total_results" in body
    assert "disclaimer" in body
    assert body["requested_mode"] == "all"
    assert body["effective_mode"] == "keyword"
    assert body["semantic_ready"] is False
    assert body["embedding_model"] == get_settings().embedding_model


def test_semantic_only_request_is_rejected_when_disabled(client, user_token):
    from app.schemas.search import SEMANTIC_SEARCH_DISABLED

    response = client.get(
        "/api/v1/search",
        params={"q": "jurisdiction", "search_mode": "semantic"},
        headers={"Authorization": f"Bearer {user_token}"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == SEMANTIC_SEARCH_DISABLED


def test_semantic_only_request_is_rejected_when_not_ready(client, user_token, monkeypatch):
    from app.schemas.search import SEMANTIC_SEARCH_NOT_READY

    monkeypatch.setattr(get_settings(), "semantic_search_enabled", True)
    response = client.get(
        "/api/v1/search",
        params={"q": "jurisdiction", "search_mode": "semantic"},
        headers={"Authorization": f"Bearer {user_token}"},
    )

    assert response.status_code == 503
    assert response.json()["detail"] == SEMANTIC_SEARCH_NOT_READY
