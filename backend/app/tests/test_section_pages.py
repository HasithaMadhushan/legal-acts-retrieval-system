from app.core.roles import SectionType
from app.services.metadata_extractor import extract_metadata
from app.services.pdf_parser.base import PAGE_SEPARATOR, ParsedPdf, structured_pages_from_texts
from app.services.pdf_parser.preparation import prepare_act_pages
from app.services.section_segmenter import SectionDraft, attach_section_pages, segment_act_text
from app.services.text_cleaner import clean_text


def _parsed_with_pages(page_texts: list[str], *, page_count: int | None = None) -> ParsedPdf:
    return ParsedPdf(
        full_text=PAGE_SEPARATOR.join(page_texts),
        page_count=page_count if page_count is not None else len(page_texts),
        page_texts=page_texts,
        parser_name="PYMUPDF",
        warnings=[],
        structured_document=structured_pages_from_texts(page_texts, extraction_method="native"),
    )


def test_dehyphenation_page_mapping_uses_prepared_offsets():
    parsed = _parsed_with_pages(
        ["1. Short ti-\ntle.\nThis Act may be cited as the Example Act."]
    )
    prepared = prepare_act_pages(parsed)
    result = segment_act_text(prepared.text)
    attach_section_pages(result.sections, prepared.page_spans)

    assert "title" in prepared.text
    section = next(item for item in result.sections if item.section_number == "1")
    assert section.page_start == 1
    assert section.page_end == 1


def test_prepare_keeps_one_span_per_physical_page_including_empty_first_and_last():
    parsed = _parsed_with_pages(["", "1. Short title.\nBody text on page two.", ""])

    prepared = prepare_act_pages(parsed)

    assert prepared.page_spans is not None
    assert len(prepared.page_spans) == 3
    assert prepared.page_spans[0].start == prepared.page_spans[0].end == 0
    assert prepared.page_spans[2].start == prepared.page_spans[2].end
    assert prepared.text == prepared.text.strip()
    assert "1. Short title." in prepared.text


def test_preamble_part_and_schedule_receive_pages_when_spans_exist():
    parsed = _parsed_with_pages(
        [
            "AN EXAMPLE ACT\nNo. 1 of 2024\n\nPART I\nPreliminary\n\n"
            "1. Short title.\nThis Act may be cited as the Example Act.",
            "FIRST SCHEDULE\nForms",
        ]
    )
    prepared = prepare_act_pages(parsed)
    result = segment_act_text(prepared.text)
    attach_section_pages(result.sections, prepared.page_spans)

    parts = [section for section in result.sections if section.section_type == SectionType.PART]
    schedules = [
        section for section in result.sections if section.section_type == SectionType.SCHEDULE
    ]
    assert parts
    assert parts[0].page_start == 1
    assert schedules
    assert schedules[0].page_start == 2


def test_prepare_without_physical_pages_has_no_spans():
    parsed = ParsedPdf(
        full_text="1. Short title.\nBody.",
        page_count=65,
        page_texts=["1. Short title.\nBody."],
        parser_name="DOCLING",
        warnings=[],
    )

    prepared = prepare_act_pages(parsed)

    assert prepared.page_spans is None
    assert prepared.text == clean_text(parsed.full_text)


def test_metadata_and_segmentation_use_the_same_prepared_text():
    parsed = _parsed_with_pages(
        [
            "EXAMPLE ACT\nNo. 1 of 2024",
            "1. Short title.\nThis Act may be cited as the Example Act.",
        ]
    )
    prepared = prepare_act_pages(parsed)

    metadata = extract_metadata(prepared.text, "example.pdf")
    result = segment_act_text(prepared.text)

    assert any(section.section_number == "1" for section in result.sections)
    assert metadata.act_number == "1" or "Example" in (metadata.title or "")


def test_section_after_empty_page_maps_to_the_occupied_page():
    parsed = _parsed_with_pages(["", "1. Short title.\nThis Act may be cited as the Example Act."])
    prepared = prepare_act_pages(parsed)
    result = segment_act_text(prepared.text)
    attach_section_pages(result.sections, prepared.page_spans)

    section = next(item for item in result.sections if item.section_number == "1")
    assert section.page_start == 2
    assert section.page_end == 2


def test_section_ending_at_page_boundary_does_not_include_next_page():
    page_one = "1. Short title.\nThis Act may be cited as the Example Act."
    page_two = "2. Duties.\nThe Minister may make regulations."
    parsed = _parsed_with_pages([page_one, page_two])
    prepared = prepare_act_pages(parsed)
    result = segment_act_text(prepared.text)
    attach_section_pages(result.sections, prepared.page_spans)
    first = next(item for item in result.sections if item.section_number == "1")

    assert first.page_start == 1
    assert first.page_end == 1


def test_source_end_inside_page_separator_maps_to_previous_page():
    page_one = "1. Short title.\nThis Act may be cited as the Example Act."
    page_two = "2. Duties.\nThe Minister may make regulations."
    parsed = _parsed_with_pages([page_one, page_two])
    prepared = prepare_act_pages(parsed)
    assert prepared.page_spans is not None

    draft = SectionDraft(
        section_number="1",
        section_path="1",
        heading="Short title",
        section_type=SectionType.SECTION,
        text=page_one,
        normalized_text="short title",
        sort_order=0,
        source_start=prepared.page_spans[0].start,
        source_end=prepared.page_spans[0].end + 1,
    )
    attach_section_pages([draft], prepared.page_spans)

    assert draft.page_start == 1
    assert draft.page_end == 1


def test_multi_page_section_span_covers_first_and_last_overlapping_pages():
    parsed = _parsed_with_pages(
        [
            "1. Short title.\nThis Act may be cited as the Example Act. Continuation ",
            "continues on page two until the next heading.\n2. Duties.\nMore text.",
        ]
    )
    prepared = prepare_act_pages(parsed)
    result = segment_act_text(prepared.text)
    attach_section_pages(result.sections, prepared.page_spans)

    first = next(item for item in result.sections if item.section_number == "1")
    assert first.page_start == 1
    assert first.page_end == 2


def test_docling_without_physical_pages_leaves_section_pages_unset():
    parsed = ParsedPdf(
        full_text="1. Short title.\nBody.\n\n2. Duties.\nMore.",
        page_count=65,
        page_texts=["1. Short title.\nBody.\n\n2. Duties.\nMore."],
        parser_name="DOCLING",
        warnings=[],
    )
    prepared = prepare_act_pages(parsed)
    result = segment_act_text(prepared.text)
    attach_section_pages(result.sections, prepared.page_spans)

    assert prepared.page_spans is None
    assert all(
        section.page_start is None and section.page_end is None for section in result.sections
    )


def test_section_offsets_come_from_boundaries_not_stripped_text_search():
    text = "1. Short title.\nBody of section one.\n\n\n2. Duties.\nMore."
    first = next(
        item for item in segment_act_text(text).sections if item.section_number == "1"
    )

    assert first.source_start == 0
    assert first.source_end is not None
    assert "2. Duties" not in text[first.source_start:first.source_end]
    assert not first.text.endswith("\n")


def test_page_mapping_follows_segmented_offsets_not_first_string_match():
    toc_and_body = [
        "CONTENTS\n1. Short title.\n2. Duties.",
        "1. Short title.\nThis Act may be cited as the Example Act.\n\n"
        "2. Duties.\nThe Minister may make regulations.",
    ]
    parsed = _parsed_with_pages(toc_and_body)
    prepared = prepare_act_pages(parsed)
    result = segment_act_text(prepared.text)
    attach_section_pages(result.sections, prepared.page_spans)

    numbered = [item for item in result.sections if item.section_number in {"1", "2"}]
    assert numbered[0].source_start is not None
    assert numbered[0].source_end is not None
    assert prepared.text[numbered[0].source_start:numbered[0].source_end].lstrip().startswith("1.")
