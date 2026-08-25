from app.services.pdf_parser.base import ParsedPdf
from app.services.pdf_parser.native_first_parser import NativeFirstPdfParser
from app.services.pdf_parser.quality_gated_parser import QualityGatedPdfParser


class StubParser:
    def __init__(self, parsed: ParsedPdf) -> None:
        self.parsed = parsed
        self.parser_name = parsed.parser_name
        self.calls = 0

    def extract(self, file_path: str) -> ParsedPdf:
        self.calls += 1
        return self.parsed


def _parsed(parser_name: str, text: str, *, pages: int = 1) -> ParsedPdf:
    return ParsedPdf(
        full_text=text,
        page_count=pages,
        page_texts=[text],
        parser_name=parser_name,
        warnings=[],
    )


def test_native_first_parser_does_not_run_inspector_for_healthy_native_text():
    pymupdf = StubParser(
        _parsed(
            "PYMUPDF",
            "1. Short title.\nSubstantial native legal text on this page.",
        )
    )
    inspector = StubParser(_parsed("PDF_INSPECTOR", "1. OCR output.\nText."))

    result = NativeFirstPdfParser(pymupdf, inspector, None).extract("act.pdf")

    assert result.parser_name == "PYMUPDF"
    assert pymupdf.calls == 1
    assert inspector.calls == 0


def test_native_first_parser_runs_inspector_for_image_only_pdf():
    pymupdf = StubParser(_parsed("PYMUPDF", ""))
    inspector = StubParser(
        _parsed(
            "PDF_INSPECTOR",
            "1. Short title.\nSubstantial OCR legal text.\n\n"
            "2. Duties.\nMore substantial OCR legal text.",
        )
    )

    result = NativeFirstPdfParser(pymupdf, inspector, None).extract("act.pdf")

    assert result.parser_name == "PDF_INSPECTOR"
    assert inspector.calls == 1


def test_native_first_parser_runs_inspector_for_mixed_native_and_scanned_pages():
    native_text = "1. Short title.\nSubstantial native legal text on page one."
    pymupdf = StubParser(
        ParsedPdf(
            full_text=native_text,
            page_count=2,
            page_texts=[native_text, ""],
            parser_name="PYMUPDF",
            warnings=["Page 2 did not produce text."],
        )
    )
    inspector = StubParser(
        ParsedPdf(
            full_text=(
                f"{native_text}\n\n"
                "2. Scanned duties.\nSubstantial OCR legal text from page two."
            ),
            page_count=2,
            page_texts=[
                native_text,
                "2. Scanned duties.\nSubstantial OCR legal text from page two.",
            ],
            parser_name="PDF_INSPECTOR",
            warnings=[],
        )
    )

    result = NativeFirstPdfParser(pymupdf, inspector, None).extract("act.pdf")

    assert result.parser_name == "PDF_INSPECTOR"
    assert inspector.calls == 1


def test_good_primary_segmentation_and_citations_are_returned_over_baseline():
    primary = StubParser(
        _parsed(
            "PDF_INSPECTOR",
            "1. Short title.\nSubstantial legal text.\n\n"
            "2. Duties.\nSection 9 of the principal enactment is hereby amended.",
        )
    )
    docling = StubParser(_parsed("DOCLING", "1. Docling section.\nSubstantial legal text."))
    pymupdf = StubParser(
        _parsed(
            "PYMUPDF",
            "1. Short title.\nSubstantial legal text.\n\n"
            "2. Duties.\nSection 9 of the principal enactment is hereby amended.",
        )
    )

    result = QualityGatedPdfParser(primary, docling, pymupdf).extract("act.pdf")

    assert result.parser_name == "PDF_INSPECTOR"
    assert docling.calls == 0
    assert pymupdf.calls == 1


def test_bad_primary_segmentation_uses_optional_docling_fallback():
    primary = StubParser(_parsed("PDF_INSPECTOR", "Long unstructured extraction " * 100))
    docling = StubParser(
        _parsed("DOCLING", "1. Short title.\nSubstantial text.\n\n2. Duties.\nMore legal text.")
    )
    pymupdf = StubParser(_parsed("PYMUPDF", "1. PyMuPDF section.\nText."))

    result = QualityGatedPdfParser(primary, docling, pymupdf).extract("act.pdf")

    assert result.parser_name == "DOCLING"
    assert docling.calls == 1
    assert pymupdf.calls == 1
    assert any("PDF_INSPECTOR quality gate failed" in warning for warning in result.warnings)


def test_primary_with_good_sections_but_lost_citation_text_uses_pymupdf():
    primary = StubParser(
        _parsed(
            "PDF_INSPECTOR",
            "1. Short title.\nSubstantial legal text.\n\n2. Amendment.\nWords are changed.",
        )
    )
    pymupdf = StubParser(
        _parsed(
            "PYMUPDF",
            "1. Short title.\nSubstantial legal text.\n\n"
            "2. Amendment.\nSection 9 of the principal enactment is hereby amended.",
        )
    )

    result = QualityGatedPdfParser(primary, None, pymupdf).extract("act.pdf")

    assert result.parser_name == "PYMUPDF"
    assert any("citation-bearing text" in warning for warning in result.warnings)


def test_bad_primary_uses_pymupdf_as_final_fallback_when_docling_is_disabled():
    primary = StubParser(_parsed("PDF_INSPECTOR", "Long unstructured extraction " * 100))
    pymupdf = StubParser(_parsed("PYMUPDF", "1. Short title.\nText."))

    result = QualityGatedPdfParser(primary, None, pymupdf).extract("act.pdf")

    assert result.parser_name == "PYMUPDF"
    assert pymupdf.calls == 1
    assert any("PDF_INSPECTOR quality gate failed" in warning for warning in result.warnings)
