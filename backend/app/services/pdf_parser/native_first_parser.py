from app.services.pdf_parser.base import ParsedPdf, PdfParser
from app.services.pdf_parser.quality_gated_parser import segmentation_quality_errors


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
        sparse_pages = [text for text in native.page_texts if len(text.strip()) < 20]
        if native.full_text.strip() and not sparse_pages:
            return native

        warnings = [
            "PyMuPDF found image-only or mixed sparse pages; OCR extraction was attempted."
        ]
        candidates = [parser for parser in (self.inspector, self.docling_fallback) if parser]
        for parser in candidates:
            try:
                parsed = parser.extract(file_path)
            except Exception as exc:
                warnings.append(f"{parser.parser_name} extraction failed: {exc}")
                continue
            quality_errors = segmentation_quality_errors(parsed, baseline=native)
            if not quality_errors:
                parsed.warnings = [*warnings, *parsed.warnings]
                return parsed
            warnings.append(
                f"{parsed.parser_name} quality gate failed: {'; '.join(quality_errors)}"
            )
            warnings.extend(parsed.warnings)

        native.warnings = [*warnings, *native.warnings]
        return native
