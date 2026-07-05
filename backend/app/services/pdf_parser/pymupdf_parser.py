from pathlib import Path

from app.services.pdf_parser.base import ParsedPdf, PdfExtractionError


class PyMuPdfParser:
    parser_name = "PYMUPDF"

    def extract(self, file_path: str) -> ParsedPdf:
        path = Path(file_path)
        if not path.is_file():
            raise PdfExtractionError(
                "The uploaded PDF file could not be found on disk.",
                parser_name=self.parser_name,
            )

        try:
            import fitz
        except ImportError as exc:
            raise PdfExtractionError(
                "PyMuPDF is not installed.", parser_name=self.parser_name
            ) from exc

        page_texts: list[str] = []
        warnings: list[str] = []
        try:
            with fitz.open(path) as document:
                for page in document:
                    page_text = page.get_text("text")
                    if not page_text.strip():
                        warnings.append(f"Page {page.number + 1} did not produce text.")
                    page_texts.append(page_text)
        except Exception as exc:
            raise PdfExtractionError(
                "The uploaded PDF is corrupted or could not be read by PyMuPDF.",
                parser_name=self.parser_name,
            ) from exc

        return ParsedPdf(
            full_text="\n\n".join(page_texts),
            page_count=len(page_texts),
            page_texts=page_texts,
            parser_name=self.parser_name,
            warnings=warnings,
        )
