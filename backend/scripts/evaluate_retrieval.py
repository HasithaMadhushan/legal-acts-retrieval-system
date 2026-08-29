"""Evaluate keyword, semantic, and hybrid retrieval against source judgments."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.services.retrieval_evaluation import (
    load_gold_dataset,
    resolve_gold_queries,
    run_evaluation,
    validate_evaluation_environment,
    write_evaluation_results,
)


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def _commit_sha() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def main() -> None:
    args = _arguments()
    settings = get_settings()
    queries = load_gold_dataset(args.dataset)
    with SessionLocal() as db:
        validate_evaluation_environment(db, settings, queries)
        resolved = resolve_gold_queries(db, queries)
        result = run_evaluation(
            db,
            resolved,
            settings=settings,
            commit_sha=_commit_sha(),
            dataset_path=args.dataset,
        )
    write_evaluation_results(result, args.output)
    print(f"Wrote retrieval evaluation to {args.output}")


if __name__ == "__main__":
    main()
