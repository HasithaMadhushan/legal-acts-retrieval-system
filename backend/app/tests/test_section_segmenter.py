from app.core.roles import SectionType
from app.services.section_segmenter import segment_act_text, segment_sections


def _main_sections(text: str):
    return [
        section
        for section in segment_act_text(text).sections
        if section.section_type == SectionType.SECTION
    ]


def test_segment_main_sections_with_headings_without_losing_text():
    text = """AN EXAMPLE ACT
No. 12 of 2020

1. Short title.
This Act may be cited as the Example Act.

2. Amendment of section 5.
Section 5 of the principal enactment is amended by adding words.

3. Repeal.
The former rule is hereby repealed.
"""
    sections = segment_sections(text)
    numbers = [section.section_number for section in sections]
    assert numbers == ["1", "2", "3"]
    assert sections[0].heading == "Short title"
    assert "principal enactment" in sections[1].text
    assert all(section.text for section in sections)


def test_previous_line_marginal_heading_is_attached_to_section():
    text = """Short title
1. This Act may be cited as the Example Act.

Amendment of section 3 of the principal enactment
2. Section 3 of the principal enactment is amended as follows.
Continuation text remains in section 2.
"""
    sections = _main_sections(text)

    assert sections[0].heading == "Short title"
    assert sections[1].heading == "Amendment of section 3 of the principal enactment"
    assert "Continuation text remains in section 2." in sections[1].text


def test_part_heading_is_captured_in_order():
    text = """PART I
Preliminary

1. Short title.
Text.

PART II
Administration

2. Powers.
More text.
"""
    sections = segment_act_text(text).sections

    assert [section.section_type for section in sections] == [
        SectionType.PART,
        SectionType.SECTION,
        SectionType.PART,
        SectionType.SECTION,
    ]
    assert [section.sort_order for section in sections] == [0, 1, 2, 3]


def test_schedule_is_captured_without_duplication_in_previous_section():
    text = """1. Interpretation.
Definitions apply.

FIRST SCHEDULE
Forms
1. Schedule item should not become a main section.
"""
    result = segment_act_text(text)
    schedules = [
        section for section in result.sections if section.section_type == SectionType.SCHEDULE
    ]
    main_sections = [
        section for section in result.sections if section.section_type == SectionType.SECTION
    ]

    assert len(main_sections) == 1
    assert len(schedules) == 1
    assert "FIRST SCHEDULE" not in main_sections[0].text
    assert "Schedule item" in schedules[0].text
    assert result.summary["schedules_detected"] == 1


def test_schedule_references_in_body_do_not_become_schedule_identifiers():
    text = """1. Processing duties.
Schedule I or under item (a) of Schedule II hereto, processing may be based on consent.

2. Further duties.
The controller shall comply with this section.

FIRST SCHEDULE
Required particulars.
"""

    result = segment_act_text(text)
    main_sections = [
        section for section in result.sections if section.section_type == SectionType.SECTION
    ]
    schedules = [
        section for section in result.sections if section.section_type == SectionType.SCHEDULE
    ]

    assert [section.section_number for section in main_sections] == ["1", "2"]
    assert [section.section_number for section in schedules] == ["FIRST SCHEDULE"]
    assert "Schedule I or under item" in main_sections[0].text
    assert all(len(section.section_number) <= 50 for section in result.sections)


def test_cover_and_publication_text_is_not_treated_as_section_body():
    text = """PARLIAMENT OF THE DEMOCRATIC SOCIALIST REPUBLIC OF SRI LANKA
POISONS, OPIUM AND DANGEROUS DRUGS (AMENDMENT) ACT
No. 7 of 2026
Published as a Supplement to Part II of the Gazette
Price : Rs. 12.00

1. Short title.
This Act may be cited as the Poisons Amendment Act.
"""
    result = segment_act_text(text)

    assert [section.section_number for section in result.sections] == ["1"]
    assert "Price" not in result.sections[0].text
    assert result.summary["possible_cover_text_removed"] is True


def test_no_section_fallback_is_marked_clearly():
    result = segment_act_text("Only unstructured extracted document text.")

    assert len(result.sections) == 1
    assert result.sections[0].section_type == SectionType.OTHER
    assert result.summary["fallback_used"] is True
    assert result.summary["sections_detected"] == 0
    assert result.summary["warnings"]


def test_no_important_text_loss_across_segmentation():
    text = """1. First section.
Alpha text.
Continuation alpha.

2. Second section.
Beta text.

SECOND SCHEDULE
Gamma schedule text.
"""
    joined = "\n".join(section.text for section in segment_act_text(text).sections)

    for phrase in ("Alpha text", "Continuation alpha", "Beta text", "Gamma schedule text"):
        assert phrase in joined


def test_poisons_2026_representative_text_has_about_ten_main_sections():
    text = "\n\n".join(
        [
            "PARLIAMENT OF THE DEMOCRATIC SOCIALIST REPUBLIC OF SRI LANKA",
            "POISONS, OPIUM AND DANGEROUS DRUGS (AMENDMENT) ACT\nNo. 7 of 2026",
            *[
                f"{index}. Section {index} heading.\n"
                f"Representative amendment text for section {index}."
                for index in range(1, 11)
            ],
        ]
    )

    assert len(_main_sections(text)) == 10


def test_judicature_2026_representative_text_has_about_three_main_sections():
    text = """JUDICATURE (AMENDMENT) ACT
No. 8 of 2026

1. Short title.
This Act may be cited as the Judicature Amendment Act.

2. Amendment of section 45.
The principal enactment is amended.

3. Sinhala text to prevail in case of inconsistency.
In the event of any inconsistency the Sinhala text shall prevail.
"""

    assert len(_main_sections(text)) == 3


def test_social_security_levy_2026_representative_text_has_about_five_main_sections():
    text = """SOCIAL SECURITY CONTRIBUTION LEVY (AMENDMENT) ACT
No. 10 of 2026

1. Short title.
Text.

2. Amendment of section 2.
Text.

3. Insertion of new section.
Text.

4. Amendment of the Schedule.
Text.

5. Sinhala text to prevail in case of inconsistency.
Text.
"""

    assert len(_main_sections(text)) == 5
