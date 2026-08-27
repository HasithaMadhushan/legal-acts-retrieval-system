from types import SimpleNamespace

from app.services.document_processor import _select_parser
from app.services.pdf_parser.base import PAGE_SEPARATOR, ParsedPdf, structured_pages_from_texts
from app.services.pdf_parser.native_first_parser import NativeFirstPdfParser
from app.services.pdf_parser.quality_gated_parser import (
    STRUCTURAL_REVIEW_WARNING,
    QualityGatedPdfParser,
    segmentation_quality_errors,
)


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
    assert any("fallback extraction was attempted" in warning for warning in result.warnings)
    assert all("OCR extraction was attempted" not in warning for warning in result.warnings)


def test_native_first_parser_runs_inspector_for_mixed_native_and_scanned_pages():
    native_text = "1. Short title.\nSubstantial native legal text on page one."
    scanned = "2. Scanned duties.\nSubstantial OCR legal text from page two."
    pymupdf = StubParser(
        ParsedPdf(
            full_text=PAGE_SEPARATOR.join([native_text, ""]),
            page_count=2,
            page_texts=[native_text, ""],
            parser_name="PYMUPDF",
            warnings=["Page 2 did not produce text."],
            structured_document=structured_pages_from_texts(
                [native_text, ""], extraction_method="native"
            ),
        )
    )
    inspector = StubParser(
        ParsedPdf(
            full_text=PAGE_SEPARATOR.join([native_text, scanned]),
            page_count=2,
            page_texts=[native_text, scanned],
            parser_name="PDF_INSPECTOR",
            warnings=[],
            structured_document=structured_pages_from_texts(
                [native_text, scanned], extraction_method="ocr"
            ),
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


UNSTRUCTURED = "Long unstructured extraction " * 100


def test_native_first_runs_inspector_for_dense_text_without_numbered_sections():
    pymupdf = StubParser(_parsed("PYMUPDF", UNSTRUCTURED))
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


def test_native_first_keeps_invalid_dense_native_when_inspector_is_disabled():
    pymupdf = StubParser(_parsed("PYMUPDF", UNSTRUCTURED))

    result = NativeFirstPdfParser(pymupdf, None, None).extract("act.pdf")

    assert result.parser_name == "PYMUPDF"
    assert STRUCTURAL_REVIEW_WARNING in result.warnings
    assert all("OCR extraction was attempted" not in warning for warning in result.warnings)


def test_native_first_sparse_with_docling_only_does_not_claim_ocr_was_attempted():
    pymupdf = StubParser(_parsed("PYMUPDF", ""))
    docling = StubParser(
        _parsed(
            "DOCLING",
            "1. Short title.\nSubstantial Docling legal text.\n\n"
            "2. Duties.\nMore substantial Docling legal text.",
        )
    )

    result = NativeFirstPdfParser(pymupdf, None, docling).extract("act.pdf")

    assert result.parser_name == "DOCLING"
    assert any("fallback extraction was attempted" in warning for warning in result.warnings)
    assert all("OCR extraction was attempted" not in warning for warning in result.warnings)


def test_native_first_sparse_without_fallback_does_not_claim_ocr_was_attempted():
    pymupdf = StubParser(
        ParsedPdf(
            full_text="",
            page_count=1,
            page_texts=[""],
            parser_name="PYMUPDF",
            warnings=["Page 1 did not produce text."],
        )
    )

    result = NativeFirstPdfParser(pymupdf, None, None).extract("act.pdf")

    assert any("image-only or mixed sparse pages" in warning for warning in result.warnings)
    assert all("OCR extraction was attempted" not in warning for warning in result.warnings)


def test_quality_gated_baseline_carries_manual_review_warning_when_structurally_invalid():
    primary = StubParser(_parsed("PDF_INSPECTOR", UNSTRUCTURED))
    pymupdf = StubParser(_parsed("PYMUPDF", UNSTRUCTURED))

    result = QualityGatedPdfParser(primary, None, pymupdf).extract("act.pdf")

    assert result.parser_name == "PYMUPDF"
    assert STRUCTURAL_REVIEW_WARNING in result.warnings


def test_quality_gate_uses_processing_text_not_raw_full_text():
    parsed = _parsed("PYMUPDF", UNSTRUCTURED)
    processing_text = (
        "1. Short title.\nSubstantial legal text.\n\n2. Duties.\nMore substantial legal text."
    )

    assert segmentation_quality_errors(parsed, processing_text=processing_text) == []


def _parser_settings(**overrides):
    values = {
        "doc_parser_primary": "pymupdf",
        "pdf_inspector_enabled": True,
        "docling_enabled": False,
        "ocr_enabled": False,
        "pdf_inspector_ocr_model_directory": "/tmp",
        "docling_timeout_seconds": 60,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_select_parser_wraps_native_first_when_inspector_is_disabled():
    parser, requested, _warnings = _select_parser(
        _parser_settings(pdf_inspector_enabled=False)
    )

    assert requested == "pymupdf"
    assert isinstance(parser, NativeFirstPdfParser)
    assert parser.inspector is None


def test_select_parser_wraps_native_first_for_disabled_inspector_primary():
    parser, _, warnings = _select_parser(
        _parser_settings(doc_parser_primary="pdf-inspector", pdf_inspector_enabled=False)
    )

    assert isinstance(parser, NativeFirstPdfParser)
    assert parser.inspector is None
    assert any("PDF_INSPECTOR_ENABLED=false" in item for item in warnings)
    assert any("native-first route" in item for item in warnings)
    assert all("PyMuPDF was used" not in item for item in warnings)


def test_select_parser_disabled_docling_primary_keeps_configured_inspector():
    parser, _, warnings = _select_parser(
        _parser_settings(doc_parser_primary="docling", pdf_inspector_enabled=True)
    )

    assert isinstance(parser, NativeFirstPdfParser)
    assert parser.inspector is not None
    assert parser.docling_fallback is None
    assert any("DOCLING_ENABLED=false" in item for item in warnings)


def test_select_parser_ocr_primary_does_not_claim_pymupdf_was_used():
    parser, _, warnings = _select_parser(_parser_settings(doc_parser_primary="ocr"))

    assert isinstance(parser, NativeFirstPdfParser)
    assert any("OCR was requested but is disabled" in item for item in warnings)
    assert all("OCR parsing is not enabled" not in item for item in warnings)
    assert all("PyMuPDF was used" not in item for item in warnings)


def test_select_parser_ocr_primary_with_inspector_uses_selective_ocr_wording():
    parser, _, warnings = _select_parser(
        _parser_settings(doc_parser_primary="ocr", ocr_enabled=True)
    )

    assert isinstance(parser, NativeFirstPdfParser)
    assert parser.inspector is not None
    assert any("selective OCR fallback" in item for item in warnings)
    assert all("OCR parsing is not enabled" not in item for item in warnings)
    assert all("OCR was requested but is disabled" not in item for item in warnings)


def test_select_parser_ocr_primary_with_inspector_disabled_does_not_claim_ocr_is_disabled():
    parser, _, warnings = _select_parser(
        _parser_settings(
            doc_parser_primary="ocr",
            pdf_inspector_enabled=False,
            ocr_enabled=True,
        )
    )

    assert isinstance(parser, NativeFirstPdfParser)
    assert parser.inspector is None
    assert any("PDF Inspector is disabled" in item for item in warnings)
    assert all("OCR was requested but is disabled" not in item for item in warnings)


def test_select_parser_unknown_primary_does_not_claim_pymupdf_was_used():
    parser, _, warnings = _select_parser(_parser_settings(doc_parser_primary="unknown"))

    assert isinstance(parser, NativeFirstPdfParser)
    assert any("native-first route" in item for item in warnings)
    assert all("PyMuPDF was used" not in item for item in warnings)
