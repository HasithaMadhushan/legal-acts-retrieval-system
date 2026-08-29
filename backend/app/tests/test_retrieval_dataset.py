from __future__ import annotations

import csv
from collections import Counter, defaultdict
from pathlib import Path

DATASET = Path(__file__).parents[3] / "data" / "retrieval-evaluation" / "queries.csv"
REQUIRED_FIELDS = {
    "query_id",
    "query",
    "query_type",
    "document_identifier",
    "expected_section_path",
    "relevance_grade",
    "annotator",
    "adjudication_status",
    "notes",
}
QUERY_TYPES = {
    "exact_act_identifier",
    "exact_section_path",
    "exact_legal_terminology",
    "paraphrased_legal_concept",
    "relationship_amendment_intent",
    "ambiguous_plain_language",
    "spelling_format_variation",
    "difficult_negative",
}


def _rows() -> list[dict[str, str]]:
    with DATASET.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        assert set(reader.fieldnames or ()) == REQUIRED_FIELDS
        return list(reader)


def test_retrieval_gold_v1_has_complete_schema_and_coverage():
    rows = _rows()
    queries: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        queries[row["query_id"]].append(row)

    assert len(queries) >= 30
    assert {row["query_type"] for row in rows} == QUERY_TYPES
    assert len({row["document_identifier"] for row in rows}) == 12
    assert {row["relevance_grade"] for row in rows} == {"0", "1", "2"}
    assert all(row["query"].strip() and row["annotator"].strip() for row in rows)
    assert all(row["adjudication_status"] in {"agreed", "adjudicated"} for row in rows)

    query_texts = {
        query_id: {row["query"] for row in records}
        for query_id, records in queries.items()
    }
    assert all(len(texts) == 1 for texts in query_texts.values())
    assert all(
        row["expected_section_path"].strip() or row["relevance_grade"] == "0"
        for row in rows
    )


def test_at_least_twenty_percent_of_queries_are_double_annotated_and_adjudicated():
    rows = _rows()
    annotations: dict[str, set[str]] = defaultdict(set)
    statuses: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        annotations[row["query_id"]].update(
            annotator.strip() for annotator in row["annotator"].split(";") if annotator.strip()
        )
        statuses[row["query_id"]].add(row["adjudication_status"])

    required = (len(annotations) + 4) // 5
    double_annotated = {
        query_id
        for query_id, annotators in annotations.items()
        if len(annotators) >= 2 and statuses[query_id] <= {"agreed", "adjudicated"}
    }
    assert len(double_annotated) >= required


def test_query_ids_are_stable_and_rows_are_not_duplicated():
    rows = _rows()
    counts = Counter(
        (
            row["query_id"],
            row["document_identifier"],
            row["expected_section_path"],
        )
        for row in rows
    )
    assert all(query_id.startswith("LAR-") for query_id, *_ in counts)
    assert not [key for key, count in counts.items() if count > 1]
