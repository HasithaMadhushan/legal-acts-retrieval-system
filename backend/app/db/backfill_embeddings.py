"""Resumable batched embedding backfill for Act sections."""

from __future__ import annotations

import argparse
import sys

from app.db.session import SessionLocal
from app.services.embedding_backfill import BackfillOptions, BackfillResult, run_backfill


def parse_args(argv: list[str] | None = None) -> BackfillOptions:
    parser = argparse.ArgumentParser(description="Resumable embedding backfill for Act sections")
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument(
        "--resume",
        action="store_true",
        help=(
            "Accepted for CLI compatibility; backfill is already idempotent. "
            "Re-running without this flag also continues from remaining eligible "
            "sections after committed batches."
        ),
    )
    parser.add_argument("--model", type=str, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--retry-failed", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--tolerate-failures", action="store_true")
    args = parser.parse_args(argv)
    if args.batch_size <= 0:
        parser.error("--batch-size must be greater than zero")
    if args.limit is not None and args.limit <= 0:
        parser.error("--limit must be greater than zero")
    return BackfillOptions(
        batch_size=args.batch_size,
        resume=args.resume,
        model=args.model,
        dry_run=args.dry_run,
        retry_failed=args.retry_failed,
        force=args.force,
        limit=args.limit,
        tolerate_failures=args.tolerate_failures,
    )


def backfill_embeddings(options: BackfillOptions | None = None) -> BackfillResult:
    with SessionLocal() as db:
        return run_backfill(db, options=options or BackfillOptions())


def main(argv: list[str] | None = None) -> int:
    options = parse_args(argv)
    result = backfill_embeddings(options)
    print(
        f"processed={result.processed} skipped={result.skipped} "
        f"failed={result.failed} remaining={result.remaining}"
    )
    return result.exit_code(options.tolerate_failures)


if __name__ == "__main__":
    sys.exit(main())
