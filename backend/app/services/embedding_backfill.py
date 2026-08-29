from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Query, Session, selectinload

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.core.roles import EmbeddingStatus
from app.models.act_section import ActSection
from app.services.embedding_service import EmbeddingError, EmbeddingService

logger = get_logger(__name__)
_DEFAULT_BATCH_SIZE = 32
_DEFAULT_RETRIES = 3
_REMAINING_SCAN_SIZE = 100


@dataclass(frozen=True)
class BackfillOptions:
    batch_size: int = _DEFAULT_BATCH_SIZE
    limit: int | None = None
    dry_run: bool = False
    retry_failed: bool = False
    force: bool = False
    resume: bool = False
    model: str | None = None
    tolerate_failures: bool = False
    max_retries: int = _DEFAULT_RETRIES


@dataclass(frozen=True)
class BackfillResult:
    processed: int
    skipped: int
    failed: int
    remaining: int
    failed_remaining: int = 0
    dry_run: bool = False

    def exit_code(self, tolerate_failures: bool = False) -> int:
        if tolerate_failures or self.failed_remaining == 0:
            return 0
        return 1


@dataclass
class _Counters:
    processed: int = 0
    skipped: int = 0
    failed: int = 0
    remaining: int = 0
    failed_remaining: int = 0
    dry_run: bool = False
    budget: int | None = None

    def to_result(self) -> BackfillResult:
        return BackfillResult(
            processed=self.processed,
            skipped=self.skipped,
            failed=self.failed,
            remaining=self.remaining,
            failed_remaining=self.failed_remaining,
            dry_run=self.dry_run,
        )


def lock_query_for_dialect(query: Query, dialect_name: str) -> Query:
    if dialect_name == "postgresql":
        return query.with_for_update(of=ActSection, skip_locked=True)
    return query


def run_backfill(
    db: Session,
    *,
    options: BackfillOptions | None = None,
    embedding_service: EmbeddingService | None = None,
    settings: Settings | None = None,
) -> BackfillResult:
    resolved = options or BackfillOptions()
    service = embedding_service or _service_from_options(resolved, settings)
    counters = _Counters(dry_run=resolved.dry_run, budget=resolved.limit)
    try:
        _run_batches(db, service, resolved, counters)
    except KeyboardInterrupt:
        db.rollback()
        raise
    counters.remaining = _count_needing_embedding(db, service)
    counters.failed_remaining = _count_failed(db)
    logger.info(
        "embedding_backfill_complete",
        processed=counters.processed,
        skipped=counters.skipped,
        failed=counters.failed,
        remaining=counters.remaining,
        dry_run=resolved.dry_run,
        resume=resolved.resume,
        model=resolved.model,
    )
    return counters.to_result()


def _service_from_options(
    options: BackfillOptions,
    settings: Settings | None,
) -> EmbeddingService:
    resolved = settings or get_settings()
    if options.model:
        resolved = resolved.model_copy(update={"embedding_model": options.model})
    return EmbeddingService(settings=resolved)


def _run_batches(
    db: Session,
    service: EmbeddingService,
    options: BackfillOptions,
    counters: _Counters,
) -> None:
    last_id: str | None = None
    while not _budget_exhausted(counters.budget):
        batch = _fetch_batch(db, options, last_id)
        if not batch:
            break
        batch_fully_consumed, last_consumed_id = _process_batch(
            db, service, options, batch, counters
        )
        if last_consumed_id is not None:
            last_id = last_consumed_id
        if not batch_fully_consumed:
            break
        logger.info(
            "embedding_backfill_batch",
            processed=counters.processed,
            skipped=counters.skipped,
            failed=counters.failed,
            last_section_id=last_id,
        )


def _budget_exhausted(budget: int | None) -> bool:
    return budget is not None and budget <= 0


def _fetch_batch(
    db: Session,
    options: BackfillOptions,
    last_id: str | None,
) -> list[ActSection]:
    query = (
        db.query(ActSection)
        .options(selectinload(ActSection.act))
        .filter(_status_filter(options))
        .order_by(ActSection.id)
    )
    if last_id is not None:
        query = query.filter(ActSection.id > last_id)
    query = lock_query_for_dialect(query, db.get_bind().dialect.name)
    return query.limit(options.batch_size).all()


def _status_filter(options: BackfillOptions):
    statuses = [
        EmbeddingStatus.PENDING,
        EmbeddingStatus.STALE,
        EmbeddingStatus.READY,
    ]
    if options.retry_failed or options.force:
        statuses.append(EmbeddingStatus.FAILED)
    return ActSection.embedding_status.in_(statuses)


def _process_batch(
    db: Session,
    service: EmbeddingService,
    options: BackfillOptions,
    batch: list[ActSection],
    counters: _Counters,
) -> tuple[bool, str | None]:
    to_embed: list[ActSection] = []
    last_consumed_id: str | None = None
    for section in batch:
        if options.force or service.needs_embedding(section):
            if _budget_exhausted(counters.budget):
                break
            to_embed.append(section)
            if counters.budget is not None:
                counters.budget -= 1
            last_consumed_id = section.id
        else:
            counters.skipped += 1
            last_consumed_id = section.id
    if not to_embed:
        return last_consumed_id == batch[-1].id, last_consumed_id
    if options.dry_run:
        counters.processed += len(to_embed)
        return last_consumed_id == batch[-1].id, last_consumed_id
    _embed_and_commit(
        db,
        service,
        to_embed,
        options.max_retries,
        counters,
        force=options.force,
    )
    return last_consumed_id == batch[-1].id, last_consumed_id


def _embed_and_commit(
    db: Session,
    service: EmbeddingService,
    batch: list[ActSection],
    max_retries: int,
    counters: _Counters,
    *,
    force: bool,
) -> None:
    try:
        _embed_with_retries(service, batch, max_retries, force=force)
        counters.processed += len(batch)
        db.commit()
    except EmbeddingError:
        counters.processed += sum(
            1 for section in batch if not service.needs_embedding(section)
        )
        counters.failed += sum(
            1
            for section in batch
            if section.embedding_status == EmbeddingStatus.FAILED
        )
        db.commit()


def _embed_with_retries(
    service: EmbeddingService,
    batch: list[ActSection],
    max_retries: int,
    *,
    force: bool,
) -> None:
    attempts = max(1, max_retries)
    last_error: EmbeddingError | None = None
    for _ in range(attempts):
        try:
            service.embed_sections(batch, force=force)
            return
        except EmbeddingError as exc:
            last_error = exc
    if last_error is not None:
        raise last_error


def _count_needing_embedding(db: Session, service: EmbeddingService) -> int:
    remaining = 0
    last_id: str | None = None
    while True:
        query = db.query(ActSection).options(selectinload(ActSection.act)).order_by(ActSection.id)
        if last_id is not None:
            query = query.filter(ActSection.id > last_id)
        batch = query.limit(_REMAINING_SCAN_SIZE).all()
        if not batch:
            return remaining
        last_id = batch[-1].id
        remaining += sum(1 for section in batch if service.needs_embedding(section))


def _count_failed(db: Session) -> int:
    return (
        db.query(ActSection).filter(ActSection.embedding_status == EmbeddingStatus.FAILED).count()
    )
