from uuid import uuid4

import pytest

from app.core.roles import ProcessingStatus, RelationshipType, UserRole, VerificationStatus
from app.db.session import SessionLocal
from app.models.act_section import ActSection
from app.models.legal_act import LegalAct
from app.services.search_intent import (
    EXACT_IDENTIFIER_BOOST,
    exact_identifier_boost,
    parse_search_intent,
)
from app.services.search_service import search
from app.services.text_cleaner import normalize_for_search


@pytest.mark.parametrize(
    ("query", "act_number", "act_year", "section_number", "section_path", "act_title"),
    [
        ("Act No. 9 of 2023", "9", 2023, None, None, None),
        ("No. 9 of 2023", "9", 2023, None, None, None),
        ("section 34", None, None, "34", "34", None),
        ("section 34(2)(a)", None, None, "34", "34(2)(a)", None),
        ("Judicature Act", None, None, None, None, "judicature act"),
        ("the Anti-Corruption Act, No. 9 of 2023", "9", 2023, None, None, "anti corruption act"),
    ],
)
def test_parse_search_intent_detects_legal_identifiers(
    query, act_number, act_year, section_number, section_path, act_title
):
    intent = parse_search_intent(query)

    assert intent.act_number == act_number
    assert intent.act_year == act_year
    assert intent.section_number == section_number
    assert intent.section_path == section_path
    assert intent.act_title == act_title
    assert intent.has_exact_identifier is True


@pytest.mark.parametrize(
    ("query", "relationship"),
    [
        ("amend", RelationshipType.AMENDS),
        ("repeal", RelationshipType.REPEALS),
        ("insert", RelationshipType.INSERTS),
        ("substitute", RelationshipType.SUBSTITUTES),
        ("amend section 34 of Act No. 9 of 2023", RelationshipType.AMENDS),
    ],
)
def test_parse_search_intent_detects_relationship_terms(query, relationship):
    intent = parse_search_intent(query)

    assert intent.relationship_type == relationship


@pytest.mark.parametrize(
    "query",
    [
        "Act No. of 2023",
        "No. of 2023",
        "section",
        "section (2)(a)",
        "taxable turnover",
        "",
        "   ",
    ],
)
def test_parse_search_intent_ignores_malformed_identifiers(query):
    intent = parse_search_intent(query)

    assert intent.act_number is None
    assert intent.act_year is None
    assert intent.section_number is None
    assert intent.section_path is None
    assert intent.act_title is None
    assert intent.has_exact_identifier is False


def test_parse_search_intent_treats_section_only_query_as_ambiguous():
    intent = parse_search_intent("section 34")

    assert intent.section_number == "34"
    assert intent.act_number is None
    assert intent.act_year is None
    assert intent.has_act_identifier is False
    assert intent.has_section_identifier is True


def test_parse_search_intent_does_not_treat_bare_number_as_act_identifier():
    intent = parse_search_intent("9")

    assert intent.act_number is None
    assert intent.act_year is None
    assert intent.section_number is None
    assert intent.has_exact_identifier is False


def test_combined_query_keeps_identifiers_without_inventing_a_title():
    intent = parse_search_intent("amend section 34 of Act No. 9 of 2023")

    assert intent.act_number == "9"
    assert intent.act_year == 2023
    assert intent.section_number == "34"
    assert intent.relationship_type == RelationshipType.AMENDS
    assert intent.act_title is None


def test_exact_act_identifier_boost_exceeds_semantic_score_scale():
    intent = parse_search_intent("Act No. 9 of 2023")
    boost = exact_identifier_boost(
        intent,
        result_type="ACT",
        act_number="9",
        year=2023,
        title="Anti-Corruption Act",
    )

    assert boost == EXACT_IDENTIFIER_BOOST
    assert boost > 100.0


def test_exact_act_identifier_boost_requires_matching_year():
    intent = parse_search_intent("Act No. 9 of 2023")

    assert (
        exact_identifier_boost(
            intent,
            result_type="ACT",
            act_number="9",
            year=2010,
            title="Anti-Corruption Act",
        )
        == 0.0
    )


def test_exact_section_path_boost_does_not_apply_to_parent_section():
    intent = parse_search_intent("section 34(2)(a)")

    assert (
        exact_identifier_boost(
            intent,
            result_type="SECTION",
            section_number="34",
            section_path="34(2)(a)",
        )
        == EXACT_IDENTIFIER_BOOST
    )
    assert (
        exact_identifier_boost(
            intent,
            result_type="SECTION",
            section_number="34",
            section_path="34",
        )
        == 0.0
    )


def test_exact_title_boost_matches_normalized_act_title():
    intent = parse_search_intent("Judicature Act")

    assert (
        exact_identifier_boost(
            intent,
            result_type="ACT",
            act_number="2",
            year=1978,
            title="Judicature Act",
        )
        == EXACT_IDENTIFIER_BOOST
    )


def _sha() -> str:
    return uuid4().hex.ljust(64, "0")[:64]


def _add_act(db, *, title: str, act_number: str, year: int, raw_text: str) -> LegalAct:
    act = LegalAct(
        title=title,
        normalized_title=normalize_for_search(title),
        act_number=act_number,
        year=year,
        category="Test",
        source_file_name=f"{title}.pdf",
        stored_file_path=f"{title}.pdf",
        file_sha256=_sha(),
        raw_text=raw_text,
        processing_status=ProcessingStatus.VERIFIED,
    )
    db.add(act)
    db.flush()
    return act


def _add_section(
    db,
    act: LegalAct,
    *,
    section_number: str,
    section_path: str,
    heading: str,
    text: str,
    sort_order: int,
) -> ActSection:
    section = ActSection(
        act_id=act.id,
        section_number=section_number,
        section_path=section_path,
        heading=heading,
        text=text,
        normalized_text=normalize_for_search(text),
        sort_order=sort_order,
        verification_status=VerificationStatus.VERIFIED,
    )
    db.add(section)
    db.flush()
    return section


def test_exact_act_number_and_year_precede_approximate_body_match():
    with SessionLocal() as db:
        exact = _add_act(
            db,
            title="Anti-Corruption Act",
            act_number="9",
            year=2023,
            raw_text="Short certified text.",
        )
        _add_act(
            db,
            title="Integrity Commission Act",
            act_number="12",
            year=2022,
            raw_text="This discussion of Act No. 9 of 2023 is only an approximate mention.",
        )
        db.commit()
        exact_id = exact.id

        response = search(db, query="Act No. 9 of 2023", role=UserRole.LAWYER)

    assert response.results, "exact Act identifier should produce a hit"
    assert response.results[0].result_type == "ACT"
    assert response.results[0].act_id == exact_id
    assert response.results[0].act_number == "9"
    assert response.results[0].year == 2023
    assert response.results[0].score > 100.0


def test_exact_section_path_precedes_approximate_section_text():
    with SessionLocal() as db:
        host = _add_act(
            db,
            title="Penalties Act",
            act_number="4",
            year=2020,
            raw_text="Penalties Act body.",
        )
        exact = _add_section(
            db,
            host,
            section_number="34(2)(a)",
            section_path="34(2)(a)",
            heading="Fine amounts",
            text="The fine is one hundred thousand rupees.",
            sort_order=1,
        )
        _add_section(
            db,
            host,
            section_number="1",
            section_path="1",
            heading="Purpose",
            text="This Act mentions section 34(2)(a) only as an approximate cross-reference.",
            sort_order=2,
        )
        db.commit()
        exact_id = exact.id

        response = search(db, query="section 34(2)(a)", role=UserRole.LAWYER)

    assert response.results, "exact section path should produce a hit"
    assert response.results[0].result_type == "SECTION"
    assert response.results[0].section_id == exact_id
    assert response.results[0].section_number == "34(2)(a)"
    assert response.results[0].score > 100.0


def test_ambiguous_section_query_ranks_matching_sections_from_each_act():
    with SessionLocal() as db:
        first = _add_act(
            db,
            title="First Host Act",
            act_number="1",
            year=2019,
            raw_text="First host.",
        )
        second = _add_act(
            db,
            title="Second Host Act",
            act_number="2",
            year=2021,
            raw_text="Second host.",
        )
        _add_section(
            db,
            first,
            section_number="34",
            section_path="34",
            heading="First thirty four",
            text="First Act section 34.",
            sort_order=1,
        )
        _add_section(
            db,
            second,
            section_number="34",
            section_path="34",
            heading="Second thirty four",
            text="Second Act section 34.",
            sort_order=1,
        )
        db.commit()
        first_id = first.id
        second_id = second.id

        response = search(db, query="section 34", role=UserRole.LAWYER)

    section_hits = [item for item in response.results if item.result_type == "SECTION"]
    assert {item.section_number for item in section_hits} == {"34"}
    assert {item.act_id for item in section_hits} == {first_id, second_id}
    assert section_hits[0].score >= section_hits[1].score
    assert response.results[0].result_type == "SECTION"


def test_keyword_title_query_still_ranks_exact_title_first():
    with SessionLocal() as db:
        judicature = _add_act(
            db,
            title="Judicature Act",
            act_number="2",
            year=1978,
            raw_text="Judicature Act body text and court jurisdiction.",
        )
        _add_act(
            db,
            title="High Court of the Provinces Act",
            act_number="19",
            year=1990,
            raw_text="Refers to the Judicature Act in passing.",
        )
        db.commit()
        judicature_id = judicature.id

        response = search(db, query="Judicature Act", role=UserRole.LAWYER)

    assert response.results[0].result_type == "ACT"
    assert response.results[0].act_id == judicature_id
