"""Benchmark native pgvector HNSW queries with synthetic normalized vectors."""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import statistics
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from sqlalchemy import create_engine, text

DIMENSION = 384


@dataclass(frozen=True)
class ScenarioResult:
    section_count: int
    filtered: bool
    cold_ms: float
    median_ms: float
    p95_ms: float
    index_build_ms: float
    plan: str


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--sizes", nargs="+", type=int, default=[1_000, 10_000])
    parser.add_argument("--runs", type=int, default=20)
    return parser.parse_args()


def _normalized_vector(seed: int) -> list[float]:
    generator = random.Random(seed)
    values = [generator.uniform(-1, 1) for _ in range(DIMENSION)]
    norm = math.sqrt(sum(value * value for value in values)) or 1.0
    return [value / norm for value in values]


def _vector_literal(values: list[float]) -> str:
    return "[" + ",".join(f"{value:.8f}" for value in values) + "]"


def run_scenario(connection, section_count: int, *, filtered: bool, runs: int) -> ScenarioResult:
    connection.execute(text("DROP TABLE IF EXISTS semantic_benchmark"))
    connection.execute(
        text(
            "CREATE TABLE semantic_benchmark ("
            "id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, "
            "category integer NOT NULL, embedding vector(384) NOT NULL)"
        )
    )
    for start in range(0, section_count, 500):
        rows = [
            {
                "category": index % 10,
                "embedding": _vector_literal(_normalized_vector(index)),
            }
            for index in range(start, min(start + 500, section_count))
        ]
        connection.execute(
            text(
                "INSERT INTO semantic_benchmark (category, embedding) "
                "VALUES (:category, CAST(:embedding AS vector))"
            ),
            rows,
        )
    started = time.perf_counter()
    connection.execute(
        text(
            "CREATE INDEX semantic_benchmark_hnsw ON semantic_benchmark "
            "USING hnsw (embedding vector_cosine_ops)"
        )
    )
    index_build_ms = (time.perf_counter() - started) * 1000
    connection.execute(text("ANALYZE semantic_benchmark"))

    where = "WHERE category = 3" if filtered else ""
    query = (
        "SELECT id FROM semantic_benchmark "
        f"{where} ORDER BY embedding <=> CAST(:query AS vector) LIMIT 10"
    )
    query_vector = _vector_literal(_normalized_vector(99_999))
    timings: list[float] = []
    for _ in range(runs + 1):
        started = time.perf_counter()
        connection.execute(text(query), {"query": query_vector}).all()
        timings.append((time.perf_counter() - started) * 1000)
    plan_rows = connection.execute(
        text("EXPLAIN (ANALYZE, BUFFERS) " + query), {"query": query_vector}
    ).all()
    warm = sorted(timings[1:])
    return ScenarioResult(
        section_count=section_count,
        filtered=filtered,
        cold_ms=timings[0],
        median_ms=statistics.median(warm),
        p95_ms=warm[math.ceil(0.95 * len(warm)) - 1],
        index_build_ms=index_build_ms,
        plan="\n".join(str(row[0]) for row in plan_rows),
    )


def main() -> None:
    args = _arguments()
    if args.runs < 1 or any(size < 1 for size in args.sizes):
        raise SystemExit("--runs and every --sizes value must be positive")
    database_url = os.environ.get("PGVECTOR_BENCHMARK_DATABASE_URL")
    if not database_url:
        raise SystemExit("Set PGVECTOR_BENCHMARK_DATABASE_URL to an isolated test database")
    engine = create_engine(database_url, future=True)
    with engine.begin() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        results = [
            run_scenario(connection, size, filtered=filtered, runs=args.runs)
            for size in args.sizes
            for filtered in (False, True)
        ]
        database_size = connection.execute(
            text("SELECT pg_database_size(current_database())")
        ).scalar_one()
        connection.execute(text("DROP TABLE IF EXISTS semantic_benchmark"))
    engine.dispose()

    args.output.mkdir(parents=True, exist_ok=False)
    payload = {
        "database_size_bytes": database_size,
        "dimension": DIMENSION,
        "runs": args.runs,
        "results": [asdict(result) for result in results],
    }
    (args.output / "benchmark.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )
    markdown = [
        "# Semantic search benchmark",
        "",
        "| Sections | Filtered | Cold ms | Median ms | p95 ms | Index build ms | HNSW used |",
        "|---:|:---:|---:|---:|---:|---:|:---:|",
    ]
    for result in results:
        markdown.append(
            f"| {result.section_count} | {result.filtered} | {result.cold_ms:.2f} | "
            f"{result.median_ms:.2f} | {result.p95_ms:.2f} | "
            f"{result.index_build_ms:.2f} | {'hnsw' in result.plan.lower()} |"
        )
        markdown.extend(["", "```text", result.plan, "```"])
    (args.output / "benchmark.md").write_text("\n".join(markdown) + "\n", encoding="utf-8")
    print(f"Wrote benchmark evidence to {args.output}")


if __name__ == "__main__":
    main()
