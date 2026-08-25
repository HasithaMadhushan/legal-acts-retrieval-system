from collections.abc import Iterable

from app.services.section_segmenter import segment_act_text
from app.services.text_cleaner import normalize_for_search


def compare_parser_text(
    pdf_inspector_text: str,
    pymupdf_text: str,
    gold_citation_spans: Iterable[str],
) -> dict[str, dict[str, float | int]]:
    gold = {
        normalized
        for span in gold_citation_spans
        if (normalized := normalize_for_search(span))
    }
    return {
        "pdf_inspector": _text_metrics(pdf_inspector_text, gold),
        "pymupdf": _text_metrics(pymupdf_text, gold),
    }


def _text_metrics(text: str, gold: set[str]) -> dict[str, float | int]:
    normalized_text = normalize_for_search(text)
    found = sum(span in normalized_text for span in gold)
    return {
        "section_count": int(segment_act_text(text).summary["sections_detected"]),
        "gold_citation_text_total": len(gold),
        "gold_citation_text_found": found,
        "gold_citation_text_recall": found / len(gold) if gold else 0.0,
        "character_count": len(text),
    }
