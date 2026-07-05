from app.services.pdf_parser.base import ParsedPdf


class OcrParser:
    parser_name = "OCR"

    def extract(self, file_path: str) -> ParsedPdf:
        raise RuntimeError("OCR parsing is not enabled in the MVP runtime.")
