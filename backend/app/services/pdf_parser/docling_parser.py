from multiprocessing import Queue, get_context
from pathlib import Path

from app.services.pdf_parser.base import ParsedPdf, PdfExtractionError
from app.services.pdf_parser.pymupdf_parser import PyMuPdfParser


class DoclingParser:
    parser_name = "DOCLING"

    def __init__(self, timeout_seconds: int | None = 60) -> None:
        self.timeout_seconds = timeout_seconds

    def extract(self, file_path: str) -> ParsedPdf:
        path = Path(file_path)
        if not path.is_file():
            raise PdfExtractionError(
                "The uploaded PDF file could not be found on disk.",
                parser_name=self.parser_name,
            )

        try:
            from docling.document_converter import DocumentConverter
        except ImportError:
            parsed = PyMuPdfParser().extract(file_path)
            parsed.warnings.insert(0, "Docling is not installed; PyMuPDF fallback was used.")
            return parsed

        try:
            if self.timeout_seconds is None:
                conversion = _convert_with_docling(path, DocumentConverter)
            else:
                conversion = _convert_with_timeout(path, self.timeout_seconds)
        except Exception as exc:
            parsed = PyMuPdfParser().extract(file_path)
            parsed.warnings.insert(
                0,
                f"Docling extraction failed; PyMuPDF fallback was used. Reason: {exc}",
            )
            return parsed

        text = str(conversion["text"])
        page_texts = _split_markdown_pages(text)
        return ParsedPdf(
            full_text=text,
            page_count=int(conversion["page_count"]) or len(page_texts),
            page_texts=page_texts,
            parser_name=self.parser_name,
            warnings=[] if text.strip() else ["Docling did not produce extractable text."],
        )


def _split_markdown_pages(text: str) -> list[str]:
    if not text:
        return [""]
    return [text]


def _convert_with_timeout(path: Path, timeout_seconds: int) -> dict[str, object]:
    if timeout_seconds <= 0:
        raise TimeoutError("Docling extraction timed out before it was started.")

    context = get_context("spawn")
    queue: Queue = context.Queue()
    process = context.Process(target=_docling_worker, args=(str(path), queue))
    process.start()
    process.join(timeout_seconds)

    if process.is_alive():
        process.terminate()
        process.join()
        raise TimeoutError(f"Docling extraction exceeded {timeout_seconds} seconds.")

    if queue.empty():
        raise RuntimeError("Docling extraction ended without returning a result.")

    result = queue.get()
    if result["status"] == "error":
        raise RuntimeError(str(result["message"]))
    return result


def _docling_worker(file_path: str, queue: Queue) -> None:
    try:
        from docling.document_converter import DocumentConverter

        queue.put({"status": "ok", **_convert_with_docling(Path(file_path), DocumentConverter)})
    except Exception as exc:
        queue.put({"status": "error", "message": str(exc)})


def _convert_with_docling(path: Path, converter_class) -> dict[str, object]:
    result = converter_class().convert(path)
    text = result.document.export_to_markdown()
    return {"text": text, "page_count": _docling_page_count(result) or 0}


def _docling_page_count(result: object) -> int | None:
    pages = getattr(getattr(result, "document", None), "pages", None)
    if isinstance(pages, dict):
        return len(pages)
    if isinstance(pages, list):
        return len(pages)
    return None
