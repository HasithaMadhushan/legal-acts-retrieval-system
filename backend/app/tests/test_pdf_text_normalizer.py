from app.core.roles import SectionType
from app.services.pdf_text_normalizer import markdown_to_legal_text
from app.services.section_segmenter import segment_act_text


def test_markdown_section_marker_becomes_plain_line_start_marker():
    markdown = """### PART I

Short title and date of operation**1.** (1) This Act may be cited as the Example Act.

**2.** Section 5 of the principal enactment is hereby amended.
"""

    normalized = markdown_to_legal_text(markdown)

    assert "Short title and date of operation\n1. (1)" in normalized
    assert "\n2. Section 5" in normalized
    assert "**" not in normalized
    assert segment_act_text(normalized).summary["sections_detected"] == 2


def test_layout_table_sections_are_restored_but_toc_rows_stay_tables():
    markdown = """## TABLE OF SECTIONS
|Section|Heading|Page|
|---|---|---|
|1.|Short title|1|
|2.|Imposition of tax|1|

|1.||This Act may be cited as the Example Act.|Short title|
|2.|(1)|A tax shall be charged on every taxable supply.|Imposition of tax|
"""

    normalized = markdown_to_legal_text(markdown)
    segmentation = segment_act_text(normalized)

    assert "|1.|Short title|1|" in normalized
    assert "\n1. This Act may be cited" in normalized
    assert "\n2. (1) A tax shall be charged" in normalized
    assert [
        section.section_number
        for section in segmentation.sections
        if section.section_type == SectionType.SECTION
    ] == ["1", "2"]
