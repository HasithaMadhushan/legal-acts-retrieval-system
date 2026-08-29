from __future__ import annotations

import csv
import json
import math
import statistics
import time
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.roles import ProcessingStatus, UserRole, VerificationStatus
from app.models.act_section import ActSection
from app.models.legal_act import LegalAct
from app.services.semantic_readiness import probe_semantic_readiness


@dataclass(frozen=True)
class RankingMetrics:
    precision_at_5: float
    recall_at_5: float
    recall_at_10: float
    mrr: float
    ndcg_at_10: float
    zero_result: bool


@dataclass(frozen=True)
class QueryRun:
    query_id: str
    mode: str
    latency_ms: float
    retrieved_ids: list[str]
    retrieved_scores: list[float]
    relevant_grades: dict[str, int]
    verified_results: int


@dataclass(frozen=True)
class AggregateMetrics:
    query_count: int
    precision_at_5: float
    recall_at_5: float
    recall_at_10: float
    mrr: float
    ndcg_at_10: float
    zero_result_rate: float
    verified_content_rate: float
    median_latency_ms: float
    p95_latency_ms: float


@dataclass(frozen=True)
class GoldQuery:
    query_id: str
    query: str
    query_type: str
    relevant_grades: dict[str, int]


@dataclass(frozen=True)
class ResolvedGoldQuery:
    query_id: str
    query: str
    query_type: str
    relevant_grades: dict[str, int]


@dataclass(frozen=True)
class EvaluationRun:
    metadata: dict[str, Any]
    aggregates: dict[str, AggregateMetrics]
    query_runs: dict[str, list[QueryRun]]


_DATASET_FIELDS = {
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


def load_gold_dataset(path: Path) -> list[GoldQuery]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if set(reader.fieldnames or ()) != _DATASET_FIELDS:
            raise ValueError("Retrieval dataset columns do not match the versioned contract.")
        rows = list(reader)

    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row["query_id"].strip()].append(row)

    queries: list[GoldQuery] = []
    for query_id, records in grouped.items():
        texts = {row["query"].strip() for row in records}
        query_types = {row["query_type"].strip() for row in records}
        if not query_id or len(texts) != 1 or len(query_types) != 1:
            raise ValueError(f"Inconsistent dataset rows for {query_id or '<empty>'}.")
        grades: dict[str, int] = {}
        for row in records:
            try:
                grade = int(row["relevance_grade"])
            except ValueError as exc:
                raise ValueError(f"Invalid relevance grade for {query_id}.") from exc
            if grade not in {0, 1, 2}:
                raise ValueError(f"Invalid relevance grade for {query_id}.")
            path_value = row["expected_section_path"].strip()
            if grade == 0:
                if path_value:
                    raise ValueError(f"Grade-zero row has a section path for {query_id}.")
                continue
            if not path_value:
                raise ValueError(f"Relevant row is missing a section path for {query_id}.")
            identity = f"{row['document_identifier'].strip()}#{path_value}"
            if identity in grades:
                raise ValueError(f"Duplicate relevance judgment for {query_id}: {identity}.")
            grades[identity] = grade
        queries.append(
            GoldQuery(
                query_id=query_id,
                query=texts.pop(),
                query_type=query_types.pop(),
                relevant_grades=grades,
            )
        )
    return sorted(queries, key=lambda item: item.query_id)


def resolve_gold_queries(
    db: Session, queries: list[GoldQuery]
) -> list[ResolvedGoldQuery]:
    resolved: list[ResolvedGoldQuery] = []
    for query in queries:
        grades: dict[str, int] = {}
        for identity, grade in query.relevant_grades.items():
            document_identifier, separator, section_path = identity.rpartition("#")
            if not separator or not document_identifier or not section_path:
                raise ValueError(f"Invalid stable section identity: {identity}.")
            matches = (
                db.query(ActSection.id)
                .join(LegalAct, LegalAct.id == ActSection.act_id)
                .filter(
                    LegalAct.source_file_name == document_identifier,
                    ActSection.section_path == section_path,
                )
                .all()
            )
            if len(matches) != 1:
                raise ValueError(
                    f"Expected exactly one corpus section for {identity}; found {len(matches)}."
                )
            grades[str(matches[0][0])] = grade
        resolved.append(
            ResolvedGoldQuery(
                query_id=query.query_id,
                query=query.query,
                query_type=query.query_type,
                relevant_grades=grades,
            )
        )
    return resolved


def validate_evaluation_environment(
    db: Session,
    settings: Settings,
    queries: list[GoldQuery],
) -> None:
    readiness = probe_semantic_readiness(db, settings)
    if not settings.semantic_search_enabled:
        raise ValueError(
            "Set SEMANTIC_SEARCH_ENABLED=true only for the evaluator process; "
            "deployed serving may remain disabled."
        )
    if not readiness.ready:
        raise ValueError("Semantic retrieval is not ready: " + "; ".join(readiness.reasons))
    expected_documents = {
        identity.rpartition("#")[0]
        for query in queries
        for identity in query.relevant_grades
    }
    actual_documents = {name for (name,) in db.query(LegalAct.source_file_name).all()}
    if expected_documents != actual_documents:
        missing = sorted(expected_documents - actual_documents)
        unexpected = sorted(actual_documents - expected_documents)
        raise ValueError(
            "Corpus does not match the frozen dataset "
            f"(missing={missing}, unexpected={unexpected})."
        )


def run_evaluation(
    db: Session,
    queries: list[ResolvedGoldQuery],
    *,
    settings: Settings,
    commit_sha: str,
    dataset_path: Path,
) -> EvaluationRun:
    from app.services.search_service import search

    query_runs: dict[str, list[QueryRun]] = {}
    for mode in ("keyword", "semantic", "all"):
        mode_runs: list[QueryRun] = []
        for gold in queries:
            started = time.perf_counter()
            response = search(
                db,
                query=gold.query,
                role=UserRole.GENERAL_USER,
                search_mode=mode,
                limit=10,
            )
            latency_ms = (time.perf_counter() - started) * 1000
            retrieved_ids = [
                str(result.section_id or result.id)
                if result.result_type == "SECTION"
                else f"{result.result_type}:{result.id}"
                for result in response.results
            ]
            mode_runs.append(
                QueryRun(
                    query_id=gold.query_id,
                    mode=mode,
                    latency_ms=latency_ms,
                    retrieved_ids=retrieved_ids,
                    retrieved_scores=[result.score for result in response.results],
                    relevant_grades=gold.relevant_grades,
                    verified_results=sum(_is_verified(result) for result in response.results),
                )
            )
        query_runs[mode] = mode_runs

    return EvaluationRun(
        metadata={
            "created_at": datetime.now(UTC).isoformat(),
            "commit_sha": commit_sha,
            "dataset": str(dataset_path),
            "embedding_provider": settings.embedding_provider,
            "embedding_model": settings.embedding_model,
            "embedding_model_revision": settings.embedding_model_revision,
            "embedding_dimension": settings.embedding_dimension,
            "semantic_candidate_limit": settings.semantic_candidate_limit,
            "hybrid_rrf_k": settings.hybrid_rrf_k,
            "hybrid_keyword_weight": settings.hybrid_keyword_weight,
            "hybrid_semantic_weight": settings.hybrid_semantic_weight,
        },
        aggregates={mode: aggregate_runs(runs) for mode, runs in query_runs.items()},
        query_runs=query_runs,
    )


def write_evaluation_results(run: EvaluationRun, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=False)
    payload = {
        "metadata": run.metadata,
        "aggregates": {mode: asdict(metrics) for mode, metrics in run.aggregates.items()},
        "query_runs": {
            mode: [
                {
                    **asdict(item),
                    "metrics": asdict(
                        score_ranking(item.retrieved_ids, item.relevant_grades)
                    ),
                }
                for item in items
            ]
            for mode, items in run.query_runs.items()
        },
    }
    (output_dir / "results.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output_dir / "summary.md").write_text(_render_markdown(run), encoding="utf-8")


def score_ranking(
    retrieved_ids: list[str], relevant_grades: dict[str, int]
) -> RankingMetrics:
    relevant = {identifier for identifier, grade in relevant_grades.items() if grade > 0}
    top_five = retrieved_ids[:5]
    top_ten = retrieved_ids[:10]
    precision = sum(identifier in relevant for identifier in top_five) / 5

    if relevant:
        recall_five = sum(identifier in relevant for identifier in top_five) / len(relevant)
        recall_ten = sum(identifier in relevant for identifier in top_ten) / len(relevant)
        reciprocal_rank = next(
            (
                1 / rank
                for rank, identifier in enumerate(retrieved_ids, start=1)
                if identifier in relevant
            ),
            0.0,
        )
        ndcg = _ndcg_at_ten(top_ten, relevant_grades)
    else:
        recall_five = 1.0
        recall_ten = 1.0
        reciprocal_rank = 0.0
        ndcg = 1.0 if not retrieved_ids else 0.0

    return RankingMetrics(
        precision_at_5=precision,
        recall_at_5=recall_five,
        recall_at_10=recall_ten,
        mrr=reciprocal_rank,
        ndcg_at_10=ndcg,
        zero_result=not retrieved_ids,
    )


def aggregate_runs(runs: list[QueryRun]) -> AggregateMetrics:
    if not runs:
        raise ValueError("At least one query run is required.")
    scored = [score_ranking(run.retrieved_ids, run.relevant_grades) for run in runs]
    retrieved_count = sum(len(run.retrieved_ids) for run in runs)
    verified_count = sum(run.verified_results for run in runs)
    latencies = sorted(run.latency_ms for run in runs)

    return AggregateMetrics(
        query_count=len(runs),
        precision_at_5=statistics.fmean(item.precision_at_5 for item in scored),
        recall_at_5=statistics.fmean(item.recall_at_5 for item in scored),
        recall_at_10=statistics.fmean(item.recall_at_10 for item in scored),
        mrr=statistics.fmean(item.mrr for item in scored),
        ndcg_at_10=statistics.fmean(item.ndcg_at_10 for item in scored),
        zero_result_rate=sum(item.zero_result for item in scored) / len(scored),
        verified_content_rate=(verified_count / retrieved_count if retrieved_count else 0.0),
        median_latency_ms=statistics.median(latencies),
        p95_latency_ms=latencies[math.ceil(0.95 * len(latencies)) - 1],
    )


def _ndcg_at_ten(retrieved_ids: list[str], relevant_grades: dict[str, int]) -> float:
    gains = [relevant_grades.get(identifier, 0) for identifier in retrieved_ids[:10]]
    ideal = sorted((grade for grade in relevant_grades.values() if grade > 0), reverse=True)[:10]
    if not ideal:
        return 0.0
    return _discounted_gain(gains) / _discounted_gain(ideal)


def _discounted_gain(grades: list[int]) -> float:
    return sum((2**grade - 1) / math.log2(rank + 1) for rank, grade in enumerate(grades, 1))


def _is_verified(result: Any) -> bool:
    if result.result_type == "ACT":
        return result.processing_status == ProcessingStatus.VERIFIED
    return result.verification_status == VerificationStatus.VERIFIED


def _render_markdown(run: EvaluationRun) -> str:
    lines = [
        "# Retrieval evaluation",
        "",
        f"Commit: `{run.metadata['commit_sha']}`  ",
        f"Model: `{run.metadata['embedding_model']}`  ",
        f"Dataset: `{run.metadata['dataset']}`",
        "",
        "| Mode | P@5 | R@5 | R@10 | MRR | nDCG@10 | Zero rate | "
        "Verified rate | Median ms | p95 ms |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for mode, metrics in run.aggregates.items():
        lines.append(
            f"| {mode} | {metrics.precision_at_5:.4f} | {metrics.recall_at_5:.4f} | "
            f"{metrics.recall_at_10:.4f} | {metrics.mrr:.4f} | {metrics.ndcg_at_10:.4f} | "
            f"{metrics.zero_result_rate:.4f} | {metrics.verified_content_rate:.4f} | "
            f"{metrics.median_latency_ms:.2f} | {metrics.p95_latency_ms:.2f} |"
        )
    return "\n".join(lines) + "\n"
