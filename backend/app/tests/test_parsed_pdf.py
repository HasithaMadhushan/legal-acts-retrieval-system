import pytest

from app.services.pdf_parser.base import (
    PAGE_SEPARATOR,
    ParsedPdf,
    StructuredDocument,
    structured_pages_from_texts,
)


def test_parsed_pdf_rejects_unpaged_structure_with_multiple_page_texts():
    with pytest.raises(ValueError, match="single blob"):
        ParsedPdf(
            full_text="a\n\nb",
            page_count=2,
            page_texts=["a", "b"],
            parser_name="PDF_INSPECTOR",
            warnings=[],
            structured_document=StructuredDocument(schema_version="1", pages=None),
        )


def test_parsed_pdf_rejects_missing_structure_with_multiple_page_texts():
    with pytest.raises(ValueError, match="single blob"):
        ParsedPdf(
            full_text="a\n\nb",
            page_count=2,
            page_texts=["a", "b"],
            parser_name="PYMUPDF",
            warnings=[],
        )


def test_parsed_pdf_without_structure_allows_page_count_mismatch():
    parsed = ParsedPdf(
        full_text="whole document",
        page_count=65,
        page_texts=["whole document"],
        parser_name="DOCLING",
        warnings=[],
        structured_document=StructuredDocument(schema_version="1", pages=None),
    )

    assert parsed.page_count == 65
    assert parsed.structured_document is not None
    assert parsed.structured_document.pages is None


def test_parsed_pdf_rejects_structured_pages_that_drift_from_page_texts():
    with pytest.raises(ValueError, match="structured page text"):
        ParsedPdf(
            full_text="a" + PAGE_SEPARATOR + "b",
            page_count=2,
            page_texts=["a", "b"],
            parser_name="PYMUPDF",
            warnings=[],
            structured_document=structured_pages_from_texts(
                ["a", "other"], extraction_method="native"
            ),
        )


def test_parsed_pdf_accepts_matching_physical_pages():
    parsed = ParsedPdf(
        full_text="one" + PAGE_SEPARATOR + "two",
        page_count=2,
        page_texts=["one", "two"],
        parser_name="PYMUPDF",
        warnings=[],
        structured_document=structured_pages_from_texts(
            ["one", "two"], extraction_method="native"
        ),
    )

    assert parsed.structured_document is not None
    assert parsed.structured_document.pages is not None
    assert [page.page_number for page in parsed.structured_document.pages] == [1, 2]
