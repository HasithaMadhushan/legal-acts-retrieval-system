from pathlib import Path
from typing import Any

from app.services.pdf_parser.base import (
    PAGE_SEPARATOR,
    STRUCTURED_SCHEMA_VERSION,
    ExtractionMethod,
    ParsedPdf,
    PdfExtractionError,
    StructuredDocument,
    StructuredPage,
)
from app.services.pdf_text_normalizer import markdown_to_legal_text


class PdfInspectorParser:
    parser_name = "PDF_INSPECTOR"

    def __init__(
        self,
        *,
        client: Any | None = None,
        ocr_enabled: bool = False,
        ocr_model_directory: str = "/opt/pdf-inspector/models",
    ) -> None:
        self.client = client
        self.ocr_enabled = ocr_enabled
        self.ocr_model_directory = ocr_model_directory

    def extract(self, file_path: str) -> ParsedPdf:
        path = Path(file_path)
        if not path.is_file():
            raise PdfExtractionError(
                "The uploaded PDF file could not be found on disk.",
                parser_name=self.parser_name,
            )

        client = self.client or _load_pdf_inspector()
        try:
            inspection = client.process_pdf(str(path))
            pages_needing_ocr = list(inspection.pages_needing_ocr)
            if pages_needing_ocr and self.ocr_enabled:
                return self._extract_with_ocr(client, path)
            return self._extract_native(client, path, inspection, pages_needing_ocr)
        except PdfExtractionError:
            raise
        except Exception as exc:
            raise PdfExtractionError(
                f"PDF Inspector extraction failed: {exc}",
                parser_name=self.parser_name,
            ) from exc

    def _extract_native(
        self, client: Any, path: Path, inspection: Any, pages_needing_ocr: list[int]
    ) -> ParsedPdf:
        extracted = client.extract_pages_markdown(str(path))
        page_markdowns = [page.markdown for page in extracted.pages]
        page_texts = [markdown_to_legal_text(markdown) for markdown in page_markdowns]
        warnings: list[str] = []
        if pages_needing_ocr:
            warnings.append(
                f"PDF Inspector recommended OCR for {len(pages_needing_ocr)} page(s), "
                "but OCR is disabled."
            )
        if getattr(inspection, "has_encoding_issues", False):
            warnings.append("PDF Inspector detected broken or suspicious font encoding.")
        return _parsed_inspector_result(
            page_texts,
            page_count=int(inspection.page_count),
            warnings=warnings,
            extraction_methods=["native"] * len(page_texts),
            markdown=PAGE_SEPARATOR.join(page_markdowns),
        )

    def _extract_with_ocr(self, client: Any, path: Path) -> ParsedPdf:
        result = client.process_pdf_with_ocr(
            str(path),
            mode="auto",
            model_directory=self.ocr_model_directory,
            offline=True,
        )
        ordered_pages = sorted(result.pages, key=lambda page: page.page_number)
        page_markdowns = [page.markdown for page in ordered_pages]
        page_texts = [markdown_to_legal_text(markdown) for markdown in page_markdowns]
        ocr_page_numbers = {int(number) for number in result.pages_routed_to_ocr}
        extraction_methods = [
            "ocr" if page.page_number in ocr_page_numbers else "native"
            for page in ordered_pages
        ]
        warnings = [
            f"{len(result.pages_routed_to_ocr)} page(s) were processed with offline OCR."
        ]
        if result.pages_recommending_hosted:
            warnings.append(
                f"{len(result.pages_recommending_hosted)} OCR page(s) remained low quality; "
                "manual review is required."
            )
        return _parsed_inspector_result(
            page_texts,
            page_count=int(result.page_count),
            warnings=warnings,
            extraction_methods=extraction_methods,
            markdown=PAGE_SEPARATOR.join(page_markdowns),
        )


def _parsed_inspector_result(
    page_texts: list[str],
    *,
    page_count: int,
    warnings: list[str],
    extraction_methods: list[ExtractionMethod],
    markdown: str,
) -> ParsedPdf:
    pages_match = page_count == len(page_texts)
    if not pages_match:
        blob = PAGE_SEPARATOR.join(page_texts)
        return ParsedPdf(
            full_text=blob,
            page_count=page_count,
            page_texts=[blob] if blob else [],
            parser_name="PDF_INSPECTOR",
            warnings=warnings,
            structured_document=StructuredDocument(
                schema_version=STRUCTURED_SCHEMA_VERSION,
                pages=None,
                markdown=markdown,
            ),
        )
    pages = [
        StructuredPage(page_number=index, text=text, extraction_method=method)
        for index, (text, method) in enumerate(
            zip(page_texts, extraction_methods, strict=True), start=1
        )
    ]
    return ParsedPdf(
        full_text=PAGE_SEPARATOR.join(page_texts),
        page_count=page_count,
        page_texts=page_texts,
        parser_name="PDF_INSPECTOR",
        warnings=warnings,
        structured_document=StructuredDocument(
            schema_version=STRUCTURED_SCHEMA_VERSION,
            pages=pages,
            markdown=markdown,
        ),
    )


def _load_pdf_inspector() -> Any:
    try:
        import pdf_inspector
    except ImportError as exc:
        raise PdfExtractionError(
            "pdf-inspector is not installed.", parser_name="PDF_INSPECTOR"
        ) from exc
    return pdf_inspector
