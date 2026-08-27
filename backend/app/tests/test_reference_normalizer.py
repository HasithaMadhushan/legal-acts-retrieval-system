from app.core.roles import RelationshipType
from app.services.reference_normalizer import (
    extract_cited_act_title,
    normalize_act_number,
    normalize_act_title,
    normalize_chapter_reference,
    normalize_relationship_type,
    normalize_schedule_reference,
    normalize_section_reference,
    normalize_target_path,
    normalize_year,
    parse_act_citation,
)


def test_normalizers():
    assert normalize_act_title("Example Act, No. 12 of 2020") == "example act"
    assert normalize_section_reference("sec. 5(1)") == "5(1)"
    assert normalize_year("No. 12 of 2020") == 2020


def test_normalizes_act_number_patterns():
    assert parse_act_citation("Example Act, No. 10 of 2026").number == "10"
    assert parse_act_citation("Example Act No. 10 of 2026").year == 2026
    assert normalize_act_number("Act, No. 10 of 2026") == "10"


def test_normalizes_chapter_references():
    assert normalize_chapter_reference("(Chapter 218)") == "Chapter 218"
    assert normalize_act_title("Poisons Ordinance (Chapter 218)") == "poisons ordinance"


def test_normalizes_section_subsection_paragraph_and_item_references():
    assert normalize_section_reference("Section 54AA") == "54AA"
    assert normalize_section_reference("subsection (1)") == "(1)"
    assert normalize_target_path("subsection (1) paragraph (d)") == "subsection (1) paragraph (d)"
    assert normalize_target_path("item 7") == "item 7"


def test_normalizes_schedule_references():
    assert normalize_schedule_reference("the First Schedule") == "First Schedule"
    assert normalize_target_path("Second Schedule") == "Second Schedule"


def test_normalizes_relationship_aliases():
    assert normalize_relationship_type("amends") == RelationshipType.AMENDS
    assert normalize_relationship_type("cross references") == RelationshipType.CROSS_REFERENCE
    assert normalize_relationship_type("addition") == RelationshipType.ADDS


def test_extracts_cited_act_title_from_definition_sentence():
    assert (
        extract_cited_act_title("means a director as defined in the Inland Revenue Act")
        == "Inland Revenue Act"
    )


def test_extracts_longest_cited_act_or_ordinance_name():
    assert (
        extract_cited_act_title(
            "as defined in the Value Added Tax Act and the Poisons Ordinance"
        )
        == "Value Added Tax Act"
    )


def test_extract_cited_act_title_skips_weak_and_internal_labels():
    assert extract_cited_act_title("paid into the Fund Act") is None
    assert extract_cited_act_title("section 22 of this Act") is None
    assert extract_cited_act_title(None) is None
