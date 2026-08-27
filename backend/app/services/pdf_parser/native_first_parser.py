from app.services.pdf_parser.base import ParsedPdf, PdfParser
from app.services.pdf_parser.preparation import prepare_act_pages
from app.services.pdf_parser.quality_gated_parser import (
    STRUCTURAL_REVIEW_WARNING,
    segmentation_quality_errors,
)

_SPARSE_FALLBACK_ATTEMPTED = (
    "PyMuPDF found image-only or mixed sparse pages; fallback extraction was attempted."
)
_SPARSE_NO_FALLBACK = "PyMuPDF found image-only or mixed sparse pages."


class NativeFirstPdfParser:
    """Prefer native PDF text and reserve OCR-capable parsers for sparse pages."""

    parser_name = "NATIVE_FIRST"

    def __init__(
        self,
        native: PdfParser,
        inspector: PdfParser | None,
        docling_fallback: PdfParser | None,
    ) -> None:
        self.native = native
        self.inspector = inspector
        self.docling_fallback = docling_fallback

    def extract(self, file_path: str) -> ParsedPdf:
        native = self.native.extract(file_path)
        native_text = prepare_act_pages(native).text
        native_errors = segmentation_quality_errors(native, processing_text=native_text)
        sparse_pages = [text for text in native.page_texts if len(text.strip()) < 20]
        dense_and_valid = bool(native.full_text.strip()) and not sparse_pages and not native_errors
        if dense_and_valid:
            return native

        fallbacks = [parser for parser in (self.inspector, self.docling_fallback) if parser]
        warnings = _sparse_page_warnings(sparse_pages, has_fallback=bool(fallbacks))
        for parser in fallbacks:
            accepted, warning_lines = _try_fallback(parser, file_path, native_text)
            warnings.extend(warning_lines)
            if accepted is not None:
                accepted.warnings = [*warnings, *accepted.warnings]
                return accepted

        if native_errors:
            warnings.append(STRUCTURAL_REVIEW_WARNING)
        native.warnings = [*warnings, *native.warnings]
        return native


def _sparse_page_warnings(sparse_pages: list[str], *, has_fallback: bool) -> list[str]:
    if not sparse_pages:
        return []
    if has_fallback:
        return [_SPARSE_FALLBACK_ATTEMPTED]
    return [_SPARSE_NO_FALLBACK]


def _try_fallback(
    parser: PdfParser, file_path: str, baseline_text: str
) -> tuple[ParsedPdf | None, list[str]]:
    try:
        parsed = parser.extract(file_path)
    except Exception as exc:
        return None, [f"{parser.parser_name} extraction failed: {exc}"]
    quality_errors = segmentation_quality_errors(
        parsed,
        processing_text=prepare_act_pages(parsed).text,
        baseline_text=baseline_text,
    )
    if not quality_errors:
        return parsed, []
    return None, [
        f"{parsed.parser_name} quality gate failed: {'; '.join(quality_errors)}",
        *parsed.warnings,
    ]
