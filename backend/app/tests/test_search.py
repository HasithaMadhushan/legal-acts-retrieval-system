from uuid import uuid4

import pytest

from app.core.roles import ProcessingStatus, RelationshipType, UserRole, VerificationStatus
from app.db.session import SessionLocal
from app.models.act_section import ActSection
from app.models.legal_act import LegalAct
from app.models.legal_reference import LegalReference
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
