from uuid import uuid4

from app.core.roles import RelationshipType, SectionType, VerificationStatus
from app.db.session import SessionLocal
from app.models.act_section import ActSection
from app.models.legal_act import LegalAct
from app.models.legal_reference import LegalReference
from app.services.reference_mapper import (
    build_mapping_context,
    map_reference_with_result,
    summarize_mapping,
)
from app.services.text_cleaner import normalize_for_search


def _sha() -> str:
    return uuid4().hex.ljust(64, "0")[:64]


def _act(
    db,
    title: str,
    *,
    number: str | None = None,
    year: int | None = None,
    source_name: str | None = None,
) -> LegalAct:
    act = LegalAct(
        title=title,
        normalized_title=normalize_for_search(title),
        act_number=number,
        year=year,
        source_name=source_name,
        source_file_name=f"{uuid4()}.pdf",
        stored_file_path="test.pdf",
        file_sha256=_sha(),
    )
    db.add(act)
    db.flush()
    return act


def _section(
    db,
    act: LegalAct,
    number: str,
    *,
    path: str | None = None,
    heading: str | None = None,
    section_type: SectionType = SectionType.SECTION,
) -> ActSection:
    section = ActSection(
        act_id=act.id,
        section_number=number,
        section_path=path or number,
        heading=heading,
        section_type=section_type,
        text=heading or f"Section {number}",
        normalized_text=normalize_for_search(heading or f"Section {number}"),
        sort_order=1,
    )
    db.add(section)
    db.flush()
    return section


def _reference(source_act: LegalAct, **values) -> LegalReference:
    return LegalReference(
        source_act_id=source_act.id,
        raw_reference_text=values.pop("raw_reference_text", "Section 9"),
        context_snippet=values.pop("context_snippet", "Section 9 is amended."),
        relationship_type=values.pop("relationship_type", RelationshipType.AMENDS),
        confidence_score=values.pop("confidence_score", 0.7),
        verification_status=values.pop("verification_status", VerificationStatus.PENDING),
        **values,
    )


def test_maps_reference_to_existing_act_by_act_number_and_year():
    with SessionLocal() as db:
        source = _act(db, "Amendment Act", number="10", year=2026)
        target = _act(db, "Judicature Act", number="2", year=1978)
        reference = _reference(source, target_act_number="2", target_act_year=1978)

        result = map_reference_with_result(db, reference)

        assert result.mapped_act is True
        assert result.confidence_band == "exact"
        assert reference.target_act_id == target.id
        assert reference.confidence_score == 0.92


def test_maps_reference_to_existing_act_by_normalized_title():
    with SessionLocal() as db:
        source = _act(db, "Amendment Act")
        target = _act(db, "Social Security Contribution Levy Act")
        reference = _reference(source, target_act_title_raw="Social Security Contribution Levy Act")

        result = map_reference_with_result(db, reference)

        assert result.mapped_act is True
        assert result.confidence_band == "exact"
        assert reference.target_act_id == target.id


def test_maps_reference_to_existing_target_section():
    with SessionLocal() as db:
        source = _act(db, "Amendment Act")
        target = _act(db, "Judicature Act", number="2", year=1978)
        section = _section(db, target, "9", heading="Jurisdiction")
        reference = _reference(
            source,
            target_act_number="2",
            target_act_year=1978,
            target_section_number="Section 9",
        )

        result = map_reference_with_result(db, reference)

        assert result.mapped_section is True
        assert reference.target_section_id == section.id
        assert reference.confidence_score == 0.98


def test_maps_chapter_reference_to_existing_act_title():
    with SessionLocal() as db:
        source = _act(db, "Amendment Act")
        target = _act(db, "Poisons, Opium and Dangerous Drugs Ordinance Chapter 218")
        reference = _reference(
            source,
            target_act_title_raw="Chapter 218",
            target_section_path="Chapter 218",
        )

        result = map_reference_with_result(db, reference)

        assert result.mapped_act is True
        assert result.confidence_band == "partial"
        assert reference.target_act_id == target.id


def test_maps_schedule_reference_by_schedule_path():
    with SessionLocal() as db:
        source = _act(db, "Amendment Act")
        target = _act(db, "Principal Act", number="25", year=2022)
        schedule = _section(
            db,
            target,
            "SCHEDULE-1",
            path="First Schedule",
            heading="First Schedule",
            section_type=SectionType.SCHEDULE,
        )
        reference = _reference(
            source,
            target_act_number="25",
            target_act_year=2022,
            target_section_path="the First Schedule",
        )

        result = map_reference_with_result(db, reference)

        assert result.mapped_section is True
        assert reference.target_section_id == schedule.id


def test_uses_principal_enactment_context_for_later_references():
    with SessionLocal() as db:
        source = _act(db, "Social Security Contribution Levy Amendment Act", number="10", year=2026)
        principal = _act(db, "Social Security Contribution Levy Act", number="25", year=2022)
        section = _section(db, principal, "5", heading="Chargeability")
        intro = _reference(
            source,
            raw_reference_text="Social Security Contribution Levy Act, No. 25 of 2022",
            target_act_title_raw="Social Security Contribution Levy Act",
            target_act_number="25",
            target_act_year=2022,
        )
        later = _reference(
            source,
            raw_reference_text="Section 5 of the principal enactment",
            target_section_number="section 5",
        )
        context = build_mapping_context(db, source, [intro, later])

        result = map_reference_with_result(db, later, context)

        assert result.used_principal_context is True
        assert result.confidence_band == "inferred"
        assert later.target_act_id == principal.id
        assert later.target_section_id == section.id


def test_unresolved_reference_remains_unmapped_without_fake_target():
    with SessionLocal() as db:
        source = _act(db, "Amendment Act")
        reference = _reference(source, target_section_number="section 9")

        result = map_reference_with_result(db, reference)

        assert result.mapped_act is False
        assert reference.target_act_id is None
        assert reference.target_section_id is None
        assert reference.verification_status == VerificationStatus.NEEDS_REVIEW
        assert reference.confidence_score == 0.55


def test_mapping_summary_counts_and_confidence_bands():
    with SessionLocal() as db:
        source = _act(db, "Amendment Act")
        target = _act(db, "Judicature Act", number="2", year=1978)
        exact = _reference(source, target_act_number="2", target_act_year=1978)
        partial = _reference(source, target_act_title_raw="Judicature")
        unresolved = _reference(source, target_act_title_raw="Missing Act")

        results = [
            map_reference_with_result(db, exact),
            map_reference_with_result(db, partial),
            map_reference_with_result(db, unresolved),
        ]
        summary = summarize_mapping(results)

        assert exact.target_act_id == target.id
        assert partial.target_act_id == target.id
        assert unresolved.target_act_id is None
        assert summary["total_references"] == 3
        assert summary["mapped_act_count"] == 2
        assert summary["unresolved_count"] == 1
        assert summary["confidence_bands"]["exact"] == 1
        assert summary["confidence_bands"]["partial"] == 1
        assert summary["confidence_bands"]["unresolved"] == 1
