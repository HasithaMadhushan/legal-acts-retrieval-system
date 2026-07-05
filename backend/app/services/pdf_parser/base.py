from dataclasses import dataclass
from typing import Protocol


@dataclass
class ParsedPdf:
    full_text: str
    page_count: int
    page_texts: list[str]
    parser_name: str
    warnings: list[str]


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
