"""Score keyword vs semantic retrieval on a small query set.

Usage (from backend/):
  python -m scripts.evaluate_retrieval
"""

from __future__ import annotations

import json
from pathlib import Path

QUERIES = [
    {"query": "High Court jurisdiction over civil matters", "notes": "paraphrase-friendly"},
    {"query": "personal data protection", "notes": "keyword overlap expected"},
    {"query": "amendment of the principal enactment", "notes": "citation language"},
    {"query": "repeal of paragraph of subsection", "notes": "procedural amendment"},
    {"query": "right to information", "notes": "Act title paraphrase"},
]


def precision_at_k(retrieved_ids: list[str], relevant_ids: set[str], k: int = 5) -> float:
    top = retrieved_ids[:k]
    if not top:
        return 0.0
    return len([item for item in top if item in relevant_ids]) / min(k, len(top))


def mean_reciprocal_rank(retrieved_ids: list[str], relevant_ids: set[str]) -> float:
    for index, item in enumerate(retrieved_ids, start=1):
        if item in relevant_ids:
            return 1.0 / index
    return 0.0


def main() -> None:
    print("Retrieval evaluation harness")
    print("Enable SEMANTIC_SEARCH_ENABLED only after this script beats keyword search.")
    print(f"Loaded {len(QUERIES)} probe queries.")
    print(json.dumps(QUERIES, indent=2))
    print("Expected section IDs should be filled per corpus before scoring P@5 / MRR.")
    out = Path("data/retrieval_eval_template.json")
    out.write_text(json.dumps({"queries": QUERIES, "expected_section_ids": {}}, indent=2))
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
