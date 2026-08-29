from __future__ import annotations

import math
from pathlib import Path

import pytest

from app.core.roles import ProcessingStatus, VerificationStatus
from app.db.session import SessionLocal
from app.models.act_section import ActSection
from app.models.legal_act import LegalAct
from app.services.retrieval_evaluation import (
    GoldQuery,
    QueryRun,
    aggregate_runs,
    load_gold_dataset,
    resolve_gold_queries,
    score_ranking,
)


def test_score_ranking_uses_graded_gold_and_fixed_precision_denominator():
    metrics = score_ranking(
        ["act.pdf#1", "irrelevant", "act.pdf#2"],
        {"act.pdf#1": 2, "act.pdf#2": 1},
    )

    assert metrics.precision_at_5 == pytest.approx(2 / 5)
    assert metrics.recall_at_5 == 1.0
    assert metrics.recall_at_10 == 1.0
    assert metrics.mrr == 1.0
    expected_dcg = 3 / math.log2(2) + 1 / math.log2(4)
    expected_idcg = 3 / math.log2(2) + 1 / math.log2(3)
    assert metrics.ndcg_at_10 == pytest.approx(expected_dcg / expected_idcg)
    assert metrics.zero_result is False


def test_score_ranking_handles_empty_results_and_no_relevant_result_query():
    empty = score_ranking([], {"act.pdf#1": 2})
    negative = score_ranking([], {})

    assert empty.precision_at_5 == 0.0
    assert empty.recall_at_5 == 0.0
    assert empty.mrr == 0.0
    assert empty.ndcg_at_10 == 0.0
    assert empty.zero_result is True
    assert negative.recall_at_10 == 1.0
    assert negative.ndcg_at_10 == 1.0


def test_aggregate_runs_reports_rates_and_nearest_rank_latency_percentile():
    runs = [
        QueryRun(
            query_id="LAR-001",
            mode="keyword",
            latency_ms=10.0,
            retrieved_ids=["a"],
            retrieved_scores=[1.0],
            relevant_grades={"a": 2},
            verified_results=1,
        ),
        QueryRun(
            query_id="LAR-002",
            mode="keyword",
            latency_ms=20.0,
            retrieved_ids=["x", "b"],
            retrieved_scores=[0.8, 0.7],
            relevant_grades={"b": 2},
            verified_results=1,
        ),
        QueryRun(
            query_id="LAR-003",
            mode="keyword",
            latency_ms=100.0,
            retrieved_ids=[],
            retrieved_scores=[],
            relevant_grades={},
            verified_results=0,
        ),
    ]

    aggregate = aggregate_runs(runs)

    assert aggregate.query_count == 3
    assert aggregate.zero_result_rate == pytest.approx(1 / 3)
    assert aggregate.verified_content_rate == pytest.approx(2 / 3)
    assert aggregate.median_latency_ms == 20.0
    assert aggregate.p95_latency_ms == 100.0


def test_load_gold_dataset_groups_multiple_graded_sections(tmp_path: Path):
    dataset = tmp_path / "queries.csv"
    dataset.write_text(
        "query_id,query,query_type,document_identifier,expected_section_path,"
        "relevance_grade,annotator,adjudication_status,notes\n"
        "LAR-001,deadline,exact_legal_terminology,act.pdf,3,2,a,agreed,direct\n"
        "LAR-001,deadline,exact_legal_terminology,act.pdf,5,1,a,agreed,related\n",
        encoding="utf-8",
    )

    queries = load_gold_dataset(dataset)

    assert len(queries) == 1
    assert queries[0].query_id == "LAR-001"
    assert queries[0].relevant_grades == {"act.pdf#3": 2, "act.pdf#5": 1}


def test_resolve_gold_queries_replaces_stable_paths_with_current_section_ids():
    with SessionLocal() as db:
        act = LegalAct(
            title="Test Act",
            normalized_title="test act",
            act_number="1",
            year=2020,
            source_file_name="act.pdf",
            stored_file_path="act.pdf",
            file_sha256="a" * 64,
            processing_status=ProcessingStatus.VERIFIED,
        )
        db.add(act)
        db.flush()
        section = ActSection(
            act_id=act.id,
            section_number="3",
            section_path="3",
            text="Relevant text",
            normalized_text="relevant text",
            sort_order=1,
            verification_status=VerificationStatus.VERIFIED,
        )
        db.add(section)
        db.commit()
        db.refresh(section)

        resolved = resolve_gold_queries(
            db,
            [
                GoldQuery(
                    query_id="LAR-001",
                    query="section three",
                    query_type="exact_section_path",
                    relevant_grades={"act.pdf#3": 2},
                )
            ],
        )

    assert resolved[0].relevant_grades == {section.id: 2}
