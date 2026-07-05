from app.core.roles import RelationshipType
from app.services.reference_normalizer import (
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
