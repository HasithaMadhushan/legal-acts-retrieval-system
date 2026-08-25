from app.services.pdf_parser.evaluation import compare_parser_text


def test_comparison_reports_section_count_and_gold_citation_text_coverage():
    gold = [
        "Section 22 of the Value Added Tax Act, No. 14 of 2002",
        "The First Schedule to the principal enactment is hereby amended",
    ]
    pdf_inspector_text = """1. Short title.
Section 22 of the Value Added Tax Act, No. 14 of 2002 is amended.

2. Amendment.
No schedule citation survived.
"""
    pymupdf_text = """1. Short title.
Section 22 of the Value Added Tax Act, No. 14 of 2002 is amended.

2. Amendment.
The First Schedule to the principal enactment is hereby amended.
"""

    result = compare_parser_text(pdf_inspector_text, pymupdf_text, gold)

    assert result["pdf_inspector"]["section_count"] == 2
    assert result["pdf_inspector"]["gold_citation_text_found"] == 1
    assert result["pdf_inspector"]["gold_citation_text_recall"] == 0.5
    assert result["pymupdf"]["gold_citation_text_found"] == 2
    assert result["pymupdf"]["gold_citation_text_recall"] == 1.0
