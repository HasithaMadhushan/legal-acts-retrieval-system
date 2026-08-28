from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.roles import EmbeddingStatus, ProcessingStatus
from app.db.backfill_embeddings import main as backfill_main
from app.db.session import SessionLocal
from app.models.act_section import ActSection
from app.models.legal_act import LegalAct
from app.services.embedding_backfill import (
    BackfillOptions,
    lock_query_for_dialect,
    run_backfill,
)
from app.services.embedding_providers import DeterministicTestProvider
from app.services.embedding_service import EmbeddingService
from app.services.text_cleaner import normalize_for_search

DIMENSION = 8


class _SelectiveFailProvider:
    provider_name = "hash-test"
    model_name = "hash-test"
    dimension = DIMENSION

    def __init__(self, fail_substring: str) -> None:
        self._fail_substring = fail_substring
        self._inner = DeterministicTestProvider(dimension=DIMENSION)

    def truncate_text(self, text: str) -> str:
        return self._inner.truncate_text(text)

    def embed_query(self, text: str) -> list[float]:
        return self._inner.embed_query(text)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if any(self._fail_substring in text for text in texts):
            raise RuntimeError("upstream inference failed")
        return self._inner.embed_documents(texts)


class _InterruptAfterFirstProvider:
    provider_name = "hash-test"
    model_name = "hash-test"
    dimension = DIMENSION

    def __init__(self) -> None:
        self._inner = DeterministicTestProvider(dimension=DIMENSION)
        self.calls = 0

    def truncate_text(self, text: str) -> str:
        return self._inner.truncate_text(text)

    def embed_query(self, text: str) -> list[float]:
        return self._inner.embed_query(text)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.calls += 1
        if self.calls > 1:
            raise KeyboardInterrupt()
        return self._inner.embed_documents(texts)


class _FlakyThenOkProvider:
    provider_name = "hash-test"
    model_name = "hash-test"
    dimension = DIMENSION

    def __init__(self) -> None:
        self._inner = DeterministicTestProvider(dimension=DIMENSION)
        self.calls = 0

    def truncate_text(self, text: str) -> str:
        return self._inner.truncate_text(text)

    def embed_query(self, text: str) -> list[float]:
        return self._inner.embed_query(text)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("transient inference failure")
        return self._inner.embed_documents(texts)


class _CountingProvider(DeterministicTestProvider):
    def __init__(self) -> None:
        super().__init__(dimension=DIMENSION)
        self.document_calls = 0

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.document_calls += 1
        vectors = super().embed_documents(texts)
        for vector in vectors:
            vector[0] += self.document_calls / 100
        return vectors


def _service(provider=None) -> EmbeddingService:
    return EmbeddingService(provider=provider or DeterministicTestProvider(dimension=DIMENSION))


def _seed_act(db, *, title: str = "Backfill Act") -> LegalAct:
    act = LegalAct(
        title=title,
        normalized_title=normalize_for_search(title),
        source_file_name="backfill.pdf",
        stored_file_path="backfill.pdf",
        file_sha256=uuid4().hex + uuid4().hex,
        processing_status=ProcessingStatus.PROCESSED,
        raw_text="Backfill probe.",
    )
    db.add(act)
    db.flush()
    return act


def _add_section(
    db,
    act: LegalAct,
    *,
    section_id: str,
    text: str,
    status: EmbeddingStatus = EmbeddingStatus.PENDING,
    embedding: list[float] | None = None,
    embedding_provider: str | None = None,
    embedding_model: str | None = None,
    embedding_dimension: int | None = None,
    embedding_source_hash: str | None = None,
    heading: str | None = "Probe",
    embedding_error: str | None = None,
) -> ActSection:
    section = ActSection(
        id=section_id,
        act_id=act.id,
        section_number=section_id[-1],
        section_path=section_id[-1],
        heading=heading,
        text=text,
        normalized_text=normalize_for_search(text),
        sort_order=len(section_id),
        embedding=embedding,
        embedding_provider=embedding_provider,
        embedding_model=embedding_model,
        embedding_dimension=embedding_dimension,
        embedding_source_hash=embedding_source_hash,
        embedding_status=status,
        embedding_error=embedding_error,
    )
    db.add(section)
    return section


def _current_ready_fields(service: EmbeddingService, section: ActSection) -> dict[str, object]:
    truncated = service.truncate_text(service.build_section_text(section.act, section))
    return {
        "embedding": [0.25] * DIMENSION,
        "embedding_provider": "hash-test",
        "embedding_model": "hash-test",
        "embedding_dimension": DIMENSION,
        "embedding_source_hash": service.source_hash(truncated),
        "status": EmbeddingStatus.READY,
    }


def _reload(section_id: str) -> SimpleNamespace:
    with SessionLocal() as db:
        loaded = db.get(ActSection, section_id)
        assert loaded is not None
        return SimpleNamespace(
            id=loaded.id,
            text=loaded.text,
            embedding=list(loaded.embedding) if loaded.embedding is not None else None,
            embedding_provider=loaded.embedding_provider,
            embedding_model=loaded.embedding_model,
            embedding_dimension=loaded.embedding_dimension,
            embedding_source_hash=loaded.embedding_source_hash,
            embedding_status=loaded.embedding_status,
            embedding_error=loaded.embedding_error,
            embedded_at=loaded.embedded_at,
        )


def test_backfill_embeds_pending_and_skips_current_ready():
    service = _service()
    with SessionLocal() as db:
        act = _seed_act(db)
        pending = _add_section(
            db, act, section_id="section-pending", text="Pending jurisdiction text."
        )
        ready = _add_section(db, act, section_id="section-ready", text="Pending jurisdiction text.")
        db.flush()
        expected_pending_hash = _current_ready_fields(service, pending)["embedding_source_hash"]
        ready_fields = _current_ready_fields(service, ready)
        ready.embedding = ready_fields["embedding"]
        ready.embedding_provider = ready_fields["embedding_provider"]
        ready.embedding_model = ready_fields["embedding_model"]
        ready.embedding_dimension = ready_fields["embedding_dimension"]
        ready.embedding_source_hash = ready_fields["embedding_source_hash"]
        ready.embedding_status = EmbeddingStatus.READY
        db.commit()

        result = run_backfill(
            db,
            options=BackfillOptions(batch_size=8),
            embedding_service=service,
        )

    assert result.processed == 1
    assert result.skipped == 1
    assert result.failed == 0
    assert result.remaining == 0
    pending_loaded = _reload("section-pending")
    ready_loaded = _reload("section-ready")
    assert pending_loaded.embedding_status == EmbeddingStatus.READY
    assert pending_loaded.embedding_provider == "hash-test"
    assert pending_loaded.embedding_model == "hash-test"
    assert pending_loaded.embedding_dimension == DIMENSION
    assert pending_loaded.embedding_source_hash == expected_pending_hash
    assert pending_loaded.embedding is not None
    assert ready_loaded.embedding == [0.25] * DIMENSION
    assert ready_loaded.embedding_status == EmbeddingStatus.READY


def test_backfill_replaces_stale_embeddings():
    service = _service()
    with SessionLocal() as db:
        act = _seed_act(db)
        stale = _add_section(
            db,
            act,
            section_id="section-stale",
            text="Stale jurisdiction clause.",
            embedding=[0.1] * DIMENSION,
            embedding_provider="hash-test",
            embedding_model="old-model",
            embedding_dimension=DIMENSION,
            embedding_source_hash="0" * 64,
            status=EmbeddingStatus.STALE,
        )
        db.commit()

        result = run_backfill(
            db,
            options=BackfillOptions(batch_size=8),
            embedding_service=service,
        )
        stale_id = stale.id

    loaded = _reload(stale_id)
    assert result.processed == 1
    assert loaded.embedding_status == EmbeddingStatus.READY
    assert loaded.embedding_model == "hash-test"
    assert loaded.embedding != [0.1] * DIMENSION
    assert loaded.embedding_source_hash != "0" * 64


def test_backfill_retries_failed_only_when_requested():
    service = _service()
    with SessionLocal() as db:
        act = _seed_act(db)
        _add_section(
            db,
            act,
            section_id="section-failed",
            text="Previously failed jurisdiction clause.",
            status=EmbeddingStatus.FAILED,
            embedding_error="Embedding provider failed",
        )
        db.commit()

        skipped = run_backfill(
            db,
            options=BackfillOptions(batch_size=8, retry_failed=False),
            embedding_service=service,
        )
        retried = run_backfill(
            db,
            options=BackfillOptions(batch_size=8, retry_failed=True),
            embedding_service=service,
        )

    loaded = _reload("section-failed")
    assert skipped.processed == 0
    assert skipped.remaining >= 1
    assert retried.processed == 1
    assert loaded.embedding_status == EmbeddingStatus.READY
    assert loaded.embedding_error is None


def test_backfill_reembeds_ready_when_source_hash_changes():
    service = _service()
    with SessionLocal() as db:
        act = _seed_act(db)
        section = _add_section(
            db,
            act,
            section_id="section-hash",
            text="Original jurisdiction clause.",
            embedding=[0.1] * DIMENSION,
            embedding_provider="hash-test",
            embedding_model="hash-test",
            embedding_dimension=DIMENSION,
            embedding_source_hash="0" * 64,
            status=EmbeddingStatus.READY,
        )
        db.commit()

        result = run_backfill(
            db,
            options=BackfillOptions(batch_size=8),
            embedding_service=service,
        )
        expected_hash = service.source_hash(
            service.truncate_text(service.build_section_text(section.act, section))
        )

    loaded = _reload("section-hash")
    assert result.processed == 1
    assert loaded.embedding_status == EmbeddingStatus.READY
    assert loaded.embedding_source_hash == expected_hash
    assert loaded.embedding != [0.1] * DIMENSION


def test_backfill_reembeds_ready_when_stored_model_is_outdated():
    service = _service()
    with SessionLocal() as db:
        act = _seed_act(db)
        _add_section(
            db,
            act,
            section_id="section-model",
            text="Model mismatch jurisdiction clause.",
            embedding=[0.1] * DIMENSION,
            embedding_provider="hash-test",
            embedding_model="sentence-transformers/all-MiniLM-L6-v2",
            embedding_dimension=DIMENSION,
            embedding_source_hash="a" * 64,
            status=EmbeddingStatus.READY,
        )
        db.commit()

        result = run_backfill(
            db,
            options=BackfillOptions(batch_size=8),
            embedding_service=service,
        )

    loaded = _reload("section-model")
    assert result.processed == 1
    assert loaded.embedding_model == "hash-test"
    assert loaded.embedding_status == EmbeddingStatus.READY


def test_backfill_commits_each_batch_and_resumes_after_interrupt():
    provider = _InterruptAfterFirstProvider()
    service = _service(provider)
    with SessionLocal() as db:
        act = _seed_act(db)
        _add_section(db, act, section_id="section-a", text="First jurisdiction clause.")
        _add_section(db, act, section_id="section-b", text="Second jurisdiction clause.")
        _add_section(db, act, section_id="section-c", text="Third jurisdiction clause.")
        db.commit()

        with pytest.raises(KeyboardInterrupt):
            run_backfill(
                db,
                options=BackfillOptions(batch_size=1),
                embedding_service=service,
            )

    assert _reload("section-a").embedding_status == EmbeddingStatus.READY
    assert _reload("section-b").embedding_status == EmbeddingStatus.PENDING
    assert _reload("section-c").embedding_status == EmbeddingStatus.PENDING

    with SessionLocal() as db:
        result = run_backfill(
            db,
            options=BackfillOptions(batch_size=1, resume=True),
            embedding_service=_service(),
        )

    assert result.processed == 2
    assert result.skipped == 1
    assert _reload("section-b").embedding_status == EmbeddingStatus.READY
    assert _reload("section-c").embedding_status == EmbeddingStatus.READY


def test_failed_batch_does_not_block_later_batches():
    service = _service(_SelectiveFailProvider("boom-token"))
    with SessionLocal() as db:
        act = _seed_act(db)
        _add_section(db, act, section_id="section-1", text="Safe first clause.")
        _add_section(db, act, section_id="section-2", text="Contains boom-token for failure.")
        _add_section(db, act, section_id="section-3", text="Safe third clause.")
        db.commit()

        result = run_backfill(
            db,
            options=BackfillOptions(batch_size=1, max_retries=1),
            embedding_service=service,
        )

    assert result.processed == 2
    assert result.failed == 1
    assert _reload("section-1").embedding_status == EmbeddingStatus.READY
    assert _reload("section-2").embedding_status == EmbeddingStatus.FAILED
    assert _reload("section-3").embedding_status == EmbeddingStatus.READY
    assert "boom-token" not in (_reload("section-2").embedding_error or "")


def test_partial_inner_batch_failure_counts_only_observed_outcomes():
    settings = get_settings().model_copy(update={"embedding_batch_size": 1})
    service = EmbeddingService(
        provider=_SelectiveFailProvider("boom-token"),
        settings=settings,
    )
    with SessionLocal() as db:
        act = _seed_act(db)
        _add_section(db, act, section_id="section-partial-1", text="Safe first clause.")
        _add_section(
            db,
            act,
            section_id="section-partial-2",
            text="Contains boom-token for failure.",
        )
        _add_section(db, act, section_id="section-partial-3", text="Unattempted clause.")
        db.commit()

        result = run_backfill(
            db,
            options=BackfillOptions(batch_size=3, max_retries=1),
            embedding_service=service,
        )

    assert result.processed == 1
    assert result.failed == 1
    assert _reload("section-partial-1").embedding_status == EmbeddingStatus.READY
    assert _reload("section-partial-2").embedding_status == EmbeddingStatus.FAILED
    assert _reload("section-partial-3").embedding_status == EmbeddingStatus.PENDING


def test_transient_batch_failure_is_retried():
    provider = _FlakyThenOkProvider()
    with SessionLocal() as db:
        act = _seed_act(db)
        _add_section(db, act, section_id="section-flaky", text="Transient failure clause.")
        db.commit()

        result = run_backfill(
            db,
            options=BackfillOptions(batch_size=1, max_retries=2),
            embedding_service=_service(provider),
        )

    assert provider.calls == 2
    assert result.processed == 1
    assert result.failed == 0
    assert _reload("section-flaky").embedding_status == EmbeddingStatus.READY


def test_second_run_is_idempotent_for_current_ready_rows():
    service = _service()
    with SessionLocal() as db:
        act = _seed_act(db)
        _add_section(db, act, section_id="section-once", text="Embed me once.")
        db.commit()
        first = run_backfill(db, options=BackfillOptions(batch_size=8), embedding_service=service)

    first_loaded = _reload("section-once")
    with SessionLocal() as db:
        second = run_backfill(
            db,
            options=BackfillOptions(batch_size=8),
            embedding_service=_service(),
        )

    second_loaded = _reload("section-once")
    assert first.processed == 1
    assert second.processed == 0
    assert second.skipped == 1
    assert second_loaded.embedding == first_loaded.embedding
    assert second_loaded.embedding_source_hash == first_loaded.embedding_source_hash


def test_dry_run_counts_work_without_writing():
    service = _service()
    with SessionLocal() as db:
        act = _seed_act(db)
        _add_section(db, act, section_id="section-dry", text="Dry run clause.")
        db.commit()

        result = run_backfill(
            db,
            options=BackfillOptions(batch_size=8, dry_run=True),
            embedding_service=service,
        )

    loaded = _reload("section-dry")
    assert result.processed == 1
    assert result.dry_run is True
    assert loaded.embedding_status == EmbeddingStatus.PENDING
    assert loaded.embedding is None


def test_limit_stops_after_requested_number_of_embeddings():
    service = _service()
    with SessionLocal() as db:
        act = _seed_act(db)
        _add_section(db, act, section_id="section-l1", text="Limit one.")
        _add_section(db, act, section_id="section-l2", text="Limit two.")
        _add_section(db, act, section_id="section-l3", text="Limit three.")
        db.commit()

        result = run_backfill(
            db,
            options=BackfillOptions(batch_size=8, limit=1),
            embedding_service=service,
        )

    statuses = [
        _reload("section-l1").embedding_status,
        _reload("section-l2").embedding_status,
        _reload("section-l3").embedding_status,
    ]
    assert result.processed == 1
    assert result.remaining == 2
    assert statuses.count(EmbeddingStatus.READY) == 1
    assert statuses.count(EmbeddingStatus.PENDING) == 2


def test_limit_mid_batch_does_not_skip_trailing_rows():
    service = _service()
    section_ids = [f"section-mid-{index}" for index in range(1, 6)]
    with SessionLocal() as db:
        act = _seed_act(db)
        for index, section_id in enumerate(section_ids, start=1):
            _add_section(
                db,
                act,
                section_id=section_id,
                text=f"Mid-batch limit clause {index}.",
            )
        db.commit()

        first = run_backfill(
            db,
            options=BackfillOptions(batch_size=3, limit=2),
            embedding_service=service,
        )
        second = run_backfill(
            db,
            options=BackfillOptions(batch_size=3),
            embedding_service=service,
        )

    statuses = [_reload(section_id).embedding_status for section_id in section_ids]
    assert first.processed == 2
    assert first.remaining == 3
    assert second.processed == 3
    assert second.remaining == 0
    assert statuses == [EmbeddingStatus.READY] * len(section_ids)


def test_force_reembeds_current_ready_rows():
    provider = _CountingProvider()
    service = _service(provider)
    with SessionLocal() as db:
        act = _seed_act(db)
        pending = _add_section(db, act, section_id="section-force", text="Force refresh clause.")
        service.embed_sections([pending])
        db.commit()
        current = (
            db.query(ActSection)
            .options(selectinload(ActSection.act))
            .filter(ActSection.id == pending.id)
            .one()
        )
        current.embedding_source_hash = service.source_hash(
            service.truncate_text(service.build_section_text(current.act, current))
        )
        db.commit()
        assert service.needs_embedding(current) is False
        original_embedding = list(current.embedding)

        result = run_backfill(
            db,
            options=BackfillOptions(batch_size=8, force=True),
            embedding_service=service,
        )

    loaded = _reload("section-force")
    assert result.processed == 1
    assert provider.document_calls == 2
    assert loaded.embedding_status == EmbeddingStatus.READY
    assert loaded.embedding != original_embedding


def test_postgres_row_lock_uses_skip_locked():
    with SessionLocal() as db:
        query = db.query(ActSection).order_by(ActSection.id)
        locked = lock_query_for_dialect(query, "postgresql")
        sql = str(locked.statement.compile(dialect=postgresql.dialect())).upper()

    assert "FOR UPDATE" in sql
    assert "SKIP LOCKED" in sql


def test_sqlite_row_lock_is_a_no_op():
    with SessionLocal() as db:
        query = db.query(ActSection).order_by(ActSection.id)
        locked = lock_query_for_dialect(query, "sqlite")

    assert locked is query


def test_cli_dry_run_exits_zero_without_writing():
    with SessionLocal() as db:
        act = _seed_act(db, title="CLI Dry Run Act")
        _add_section(db, act, section_id="section-cli-dry", text="CLI dry run clause.")
        db.commit()

    exit_code = backfill_main(["--dry-run", "--batch-size", "8"])

    loaded = _reload("section-cli-dry")
    assert exit_code == 0
    assert loaded.embedding_status == EmbeddingStatus.PENDING


def test_cli_exits_nonzero_when_failures_remain():
    with SessionLocal() as db:
        act = _seed_act(db, title="CLI Failure Act")
        _add_section(
            db,
            act,
            section_id="section-cli-fail",
            text="CLI failure clause.",
            status=EmbeddingStatus.FAILED,
        )
        db.commit()

    leftover = backfill_main(["--batch-size", "8"])
    tolerated = backfill_main(["--tolerate-failures", "--batch-size", "8"])

    assert _reload("section-cli-fail").embedding_status == EmbeddingStatus.FAILED
    assert leftover == 1
    assert tolerated == 0
