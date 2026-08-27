from dataclasses import dataclass
from typing import Literal, Protocol

PAGE_SEPARATOR = "\n\n"
STRUCTURED_SCHEMA_VERSION = "1"
ExtractionMethod = Literal["native", "ocr", "unknown"]


@dataclass
class StructuredPage:
    page_number: int
    text: str
    extraction_method: ExtractionMethod


@dataclass
class StructuredDocument:
    schema_version: str
    pages: list[StructuredPage] | None
    markdown: str | None = None


@dataclass
class ParsedPdf:
    full_text: str
    page_count: int
    page_texts: list[str]
    parser_name: str
    warnings: list[str]
    structured_document: StructuredDocument | None = None

    def __post_init__(self) -> None:
        structured = self.structured_document
        if structured is None or structured.pages is None:
            _validate_unpaged_texts(self)
            return
        _validate_physical_pages(self, structured.pages)


def structured_pages_from_texts(
    page_texts: list[str],
    *,
    extraction_method: ExtractionMethod,
    markdown: str | None = None,
) -> StructuredDocument:
    pages = [
        StructuredPage(page_number=index, text=text, extraction_method=extraction_method)
        for index, text in enumerate(page_texts, start=1)
    ]
    return StructuredDocument(
        schema_version=STRUCTURED_SCHEMA_VERSION,
        pages=pages,
        markdown=markdown,
    )


def _validate_unpaged_texts(parsed: ParsedPdf) -> None:
    if len(parsed.page_texts) > 1:
        raise ValueError("without physical pages, page_texts must be empty or a single blob")


def _validate_physical_pages(parsed: ParsedPdf, pages: list[StructuredPage]) -> None:
    if len(parsed.page_texts) != parsed.page_count or len(pages) != parsed.page_count:
        raise ValueError("structured pages must match page_count and page_texts")
    expected_numbers = list(range(1, parsed.page_count + 1))
    actual_numbers = [page.page_number for page in pages]
    if actual_numbers != expected_numbers:
        raise ValueError("structured page numbers must be consecutive starting at 1")
    if any(page.text != parsed.page_texts[index] for index, page in enumerate(pages)):
        raise ValueError("structured page text must match page_texts")
    if parsed.full_text != PAGE_SEPARATOR.join(parsed.page_texts):
        raise ValueError("full_text must be PAGE_SEPARATOR.join(page_texts)")


class PdfExtractionError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        parser_name: str = "UNKNOWN",
        page_count: int | None = None,
        extracted_character_count: int | None = None,
        warnings: list[str] | None = None,
    ) -> None:
        super().__init__(message)
        self.parser_name = parser_name
        self.page_count = page_count
        self.extracted_character_count = extracted_character_count
        self.warnings = warnings or []


class PdfParser(Protocol):
    def extract(self, file_path: str) -> ParsedPdf:
        ...
