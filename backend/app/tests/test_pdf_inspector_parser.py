from types import SimpleNamespace

from app.services.pdf_parser.pdf_inspector_parser import PdfInspectorParser
from app.services.section_segmenter import segment_act_text


class NativePdfInspectorClient:
    def process_pdf(self, file_path: str):
        return SimpleNamespace(
            page_count=2,
            pages_needing_ocr=[],
            has_encoding_issues=False,
        )

    def extract_pages_markdown(self, file_path: str):
        return SimpleNamespace(
            pages=[
                SimpleNamespace(page=0, markdown="**1.** Short title.\nLegal text."),
                SimpleNamespace(page=1, markdown="**2.** Duties.\nMore legal text."),
            ]
        )


class ScannedPdfInspectorClient:
    def process_pdf(self, file_path: str):
        return SimpleNamespace(
            page_count=2,
            pages_needing_ocr=[1, 2],
            has_encoding_issues=False,
        )

    def process_pdf_with_ocr(self, file_path: str, **options):
        return SimpleNamespace(
            page_count=2,
            pages_routed_to_ocr=[1, 2],
            pages_recommending_hosted=[],
            pages=[
                SimpleNamespace(page_number=1, markdown="**1.** Short title.\nLegal text."),
                SimpleNamespace(page_number=2, markdown="**2.** Duties.\nMore legal text."),
            ],
        )


def test_native_pdf_inspector_output_is_page_preserving_legal_plain_text(tmp_path):
    pdf = tmp_path / "act.pdf"
    pdf.write_bytes(b"%PDF-test")

    parsed = PdfInspectorParser(client=NativePdfInspectorClient()).extract(str(pdf))

    assert parsed.parser_name == "PDF_INSPECTOR"
    assert parsed.page_texts == [
        "1. Short title.\nLegal text.",
        "2. Duties.\nMore legal text.",
    ]
    assert segment_act_text(parsed.full_text).summary["sections_detected"] == 2


def test_scanned_pdf_uses_preinstalled_offline_ocr_and_returns_legal_text(tmp_path):
    pdf = tmp_path / "scan.pdf"
    pdf.write_bytes(b"%PDF-test")

    parsed = PdfInspectorParser(
        client=ScannedPdfInspectorClient(),
        ocr_enabled=True,
        ocr_model_directory="/opt/pdf-inspector/models",
    ).extract(str(pdf))

    assert parsed.parser_name == "PDF_INSPECTOR"
    assert segment_act_text(parsed.full_text).summary["sections_detected"] == 2
    assert any("2 page(s) were processed with offline OCR" in item for item in parsed.warnings)
