import sys
import types

import fitz

import app.services.pdf_parser.docling_parser as docling_parser_module
from app.services.pdf_parser.docling_parser import DoclingParser
from app.services.pdf_parser.quality_gated_parser import STRUCTURAL_REVIEW_WARNING


def _pdf_file(path, text: str) -> None:
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), text, fontsize=11)
    path.write_bytes(document.tobytes())
    document.close()


def _install_fake_docling(monkeypatch, converter_class) -> None:
    docling_module = types.ModuleType("docling")
    converter_module = types.ModuleType("docling.document_converter")
    converter_module.DocumentConverter = converter_class
    monkeypatch.setitem(sys.modules, "docling", docling_module)
    monkeypatch.setitem(sys.modules, "docling.document_converter", converter_module)


def test_docling_parser_uses_document_converter(monkeypatch, tmp_path):
    pdf_path = tmp_path / "act.pdf"
    _pdf_file(pdf_path, "TEST LEGAL ACT")

    class FakeDocument:
        pages = {1: object(), 2: object()}

        def export_to_markdown(self):
            return "# Test Legal Act\n\n**1.** Short title."

    class FakeResult:
        document = FakeDocument()

    class FakeConverter:
        def convert(self, path):
            assert path == pdf_path
            return FakeResult()

    _install_fake_docling(monkeypatch, FakeConverter)

    parsed = DoclingParser(timeout_seconds=None).extract(str(pdf_path))

    assert parsed.parser_name == "DOCLING"
    assert parsed.page_count == 2
    assert parsed.full_text == "Test Legal Act\n\n1. Short title."
    assert parsed.structured_document is not None
    assert parsed.structured_document.pages is None
    assert parsed.structured_document.markdown == "# Test Legal Act\n\n**1.** Short title."
    assert parsed.warnings == []


def test_docling_parser_falls_back_to_pymupdf_when_conversion_fails(monkeypatch, tmp_path):
    pdf_path = tmp_path / "act.pdf"
    _pdf_file(pdf_path, "Fallback text")

    class FailingConverter:
        def convert(self, path):
            raise RuntimeError("layout model failed")

    _install_fake_docling(monkeypatch, FailingConverter)

    parsed = DoclingParser(timeout_seconds=None).extract(str(pdf_path))

    assert parsed.parser_name == "PYMUPDF"
    assert "Fallback text" in parsed.full_text
    assert any("Docling extraction failed" in warning for warning in parsed.warnings)
    assert STRUCTURAL_REVIEW_WARNING in parsed.warnings


def test_docling_parser_falls_back_to_pymupdf_when_conversion_times_out(monkeypatch, tmp_path):
    pdf_path = tmp_path / "act.pdf"
    _pdf_file(pdf_path, "Timeout fallback text")

    def timeout(*args, **kwargs):
        raise TimeoutError("Docling extraction exceeded 1 seconds.")

    monkeypatch.setattr(docling_parser_module, "_convert_with_timeout", timeout)

    parsed = DoclingParser(timeout_seconds=1).extract(str(pdf_path))

    assert parsed.parser_name == "PYMUPDF"
    assert "Timeout fallback text" in parsed.full_text
    assert any("Docling extraction exceeded" in warning for warning in parsed.warnings)
    assert STRUCTURAL_REVIEW_WARNING in parsed.warnings
