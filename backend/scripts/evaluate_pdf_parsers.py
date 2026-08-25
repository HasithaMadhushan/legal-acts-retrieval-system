"""Compare PDF Inspector with PyMuPDF on hand-checked citation text.

Run from the repository root after installing backend requirements:
    PYTHONPATH=backend python -m scripts.evaluate_pdf_parsers
"""

from __future__ import annotations

import argparse
import csv
import json
import time
from collections import defaultdict
from pathlib import Path

from app.services.pdf_parser.evaluation import compare_parser_text
from app.services.pdf_parser.pdf_inspector_parser import PdfInspectorParser
from app.services.pdf_parser.pymupdf_parser import PyMuPdfParser

ROOT = Path(__file__).resolve().parents[2]
EVALUATION_DIR = ROOT / "data" / "evaluation-acts"
GOLD_CSV = EVALUATION_DIR / "gold_references.csv"


def load_gold_spans() -> dict[str, list[str]]:
    spans: dict[str, list[str]] = defaultdict(list)
    with GOLD_CSV.open(newline="", encoding="utf-8-sig") as stream:
        for row in csv.DictReader(stream):
            source_file = row.get("document_identifier", "").strip()
            raw_text = row.get("expected_raw_text", "").strip()
            if source_file and raw_text:
                spans[source_file].append(raw_text)
    return dict(spans)


def evaluate(files: list[Path]) -> dict[str, object]:
    gold_by_file = load_gold_spans()
    inspector = PdfInspectorParser(ocr_enabled=False)
    pymupdf = PyMuPdfParser()
    rows: list[dict[str, object]] = []

    for pdf in files:
        started = time.perf_counter()
        inspector_result = inspector.extract(str(pdf))
        inspector_seconds = time.perf_counter() - started
        started = time.perf_counter()
        pymupdf_result = pymupdf.extract(str(pdf))
        pymupdf_seconds = time.perf_counter() - started
        metrics = compare_parser_text(
            inspector_result.full_text,
            pymupdf_result.full_text,
            gold_by_file.get(pdf.name, []),
        )
        metrics["pdf_inspector"]["seconds"] = round(inspector_seconds, 4)
        metrics["pymupdf"]["seconds"] = round(pymupdf_seconds, 4)
        rows.append(
            {
                "file": pdf.name,
                "metrics": metrics,
                "pdf_inspector_warnings": inspector_result.warnings,
                "pymupdf_warnings": pymupdf_result.warnings,
            }
        )

    return {"gold_source": str(GOLD_CSV.relative_to(ROOT)), "documents": rows}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("files", nargs="*", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    files = args.files or sorted(EVALUATION_DIR.glob("*.pdf"))
    result = evaluate([path.resolve() for path in files])
    rendered = json.dumps(result, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
