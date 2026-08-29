import inspect
import os
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import sessionmaker

from app.core.config import LEGAL_DISCLAIMER
from app.core.roles import EmbeddingStatus, ProcessingStatus, UserRole, VerificationStatus
from app.db.base import Base
from app.db.session import SessionLocal
from app.db.types import SECTION_EMBEDDING_DIMENSION
from app.models.act_section import ActSection
from app.models.legal_act import LegalAct
from app.schemas.search import SearchResponse
from app.services.embedding_providers import get_embedding_provider
from app.services.search_service import search
from app.services.semantic_search import (
    _filter_ready_current_identity,
    _sqlite_fallback_results,
    cosine_distance_expression,
    postgres_nearest_neighbour_query,
    score_from_cosine_distance,
)
from app.services.text_cleaner import normalize_for_search

QUERY_VECTOR = [0.0] * SECTION_EMBEDDING_DIMENSION
QUERY_VECTOR[0] = 1.0
BACKEND_DIR = Path(__file__).resolve().parents[2]
SEARCH_SERVICE = BACKEND_DIR / "app" / "services" / "search_service.py"
PGVECTOR_TEST_URL = os.environ.get("PGVECTOR_TEST_DATABASE_URL")


def _compile(query) -> str:
    return str(query.statement.compile(dialect=postgresql.dialect()))


def test_score_from_cosine_distance_is_the_documented_transform():
    assert score_from_cosine_distance(0.0) == 100.0
    assert score_from_cosine_distance(0.2) == 80.0
    assert score_from_cosine_distance(1.0) == 0.0
    assert score_from_cosine_distance(1.5) == 0.0


def test_postgres_nearest_neighbour_sql_uses_cosine_distance_and_sql_pagination():
    with SessionLocal() as db:
        query = postgres_nearest_neighbour_query(
            db.query(ActSection), QUERY_VECTOR, limit=25, offset=10
        )
        sql = _compile(query).upper()

    assert "<=>" in sql
    assert "LIMIT" in sql
    assert "OFFSET" in sql
    assert "ORDER BY" in sql
    assert "ACT_SECTIONS.ID ASC" not in sql


def test_postgres_cosine_distance_expression_has_no_cast_that_would_hide_hnsw():
    sql = str(
        cosine_distance_expression(QUERY_VECTOR).compile(dialect=postgresql.dialect())
    ).upper()
    assert "<=>" in sql
    assert "CAST" not in sql


def test_ready_identity_sql_filters_status_provider_model_and_dimension():
    with SessionLocal() as db:
        compiled = _filter_ready_current_identity(db.query(ActSection)).statement.compile(
            dialect=postgresql.dialect()
        )
        sql = str(compiled).lower()
        bound = {str(value).lower() for value in compiled.params.values()}

    assert "embedding_status" in sql
    assert "embedding_provider" in sql
    assert "embedding_model" in sql
    assert "embedding_dimension" in sql
    assert "is not null" in sql
    assert any("ready" in item for item in bound)
    assert "hash-test" in bound
    assert "384" in bound


def test_search_service_does_not_score_the_semantic_corpus_in_python():
    source = SEARCH_SERVICE.read_text()
    assert "cosine_similarity" not in source
    assert "def _semantic_results" not in source
    assert "search_semantic_sections" in source


def test_postgres_dialect_does_not_use_sqlite_python_corpus_fallback(monkeypatch):
    monkeypatch.setattr("app.services.semantic_search._is_postgres", lambda db: True)

    def fake_postgres(*_args, **_kwargs):
        return SearchResponse(
            query="jurisdiction",
            results=[],
            total_results=0,
            act_results=0,
            section_results=0,
            reference_results=0,
            limit=25,
            offset=0,
            disclaimer=LEGAL_DISCLAIMER,
        )

    def fail_sqlite(*_args, **_kwargs):
        raise AssertionError("SQLite fallback must not run on PostgreSQL")

    monkeypatch.setattr("app.services.semantic_search._postgres_results", fake_postgres)
    monkeypatch.setattr("app.services.semantic_search._sqlite_fallback_results", fail_sqlite)
    with SessionLocal() as db:
        search(db, query="jurisdiction", role=UserRole.LAWYER, search_mode="semantic")


def test_sqlite_fallback_is_marked_non_production():
    source = inspect.getsource(_sqlite_fallback_results)
    assert "non-production" in source.lower()
    module_doc = inspect.getdoc(__import__("app.services.semantic_search", fromlist=["*"]))
    assert module_doc is not None
    assert "non-production" in module_doc.lower()
    assert "postgresql" in module_doc.lower()


@pytest.mark.skipif(
    not PGVECTOR_TEST_URL,
    reason="Set PGVECTOR_TEST_DATABASE_URL to run native HNSW EXPLAIN verification",
)
def test_postgres_explain_selects_hnsw_index_for_nearest_neighbour():
    assert PGVECTOR_TEST_URL is not None
    engine = create_engine(PGVECTOR_TEST_URL, future=True)
    with engine.begin() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS ix_act_sections_embedding_hnsw
                ON act_sections
                USING hnsw (embedding vector_cosine_ops)
                WHERE embedding IS NOT NULL
                """
            )
        )

    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    provider = get_embedding_provider()
    with Session() as db:
        act = LegalAct(
            title="HNSW Probe Act",
            normalized_title=normalize_for_search("HNSW Probe Act"),
            source_file_name="hnsw.pdf",
            stored_file_path="hnsw.pdf",
            file_sha256="a" * 64,
            processing_status=ProcessingStatus.VERIFIED,
            raw_text="HNSW probe",
        )
        db.add(act)
        db.flush()
        for index in range(2_000):
            vector = [0.0] * SECTION_EMBEDDING_DIMENSION
            vector[0 if index == 0 else (index % 7) + 1] = 1.0
            db.add(
                ActSection(
                    act_id=act.id,
                    section_number=str(index),
                    section_path=str(index),
                    heading=f"Clause {index}",
                    text=f"Clause {index}",
                    normalized_text=normalize_for_search(f"Clause {index}"),
                    sort_order=index,
                    verification_status=VerificationStatus.VERIFIED,
                    embedding=vector,
                    embedding_status=EmbeddingStatus.READY,
                    embedding_provider=provider.provider_name,
                    embedding_model=provider.model_name,
                    embedding_dimension=provider.dimension,
                )
            )
        db.commit()

        nearest = (
            db.query(ActSection.section_number)
            .order_by(cosine_distance_expression(QUERY_VECTOR).asc(), ActSection.id.asc())
            .limit(1)
            .scalar()
        )
        assert nearest == "0"

        db.execute(text("ANALYZE act_sections"))

        plan_rows = db.execute(
            text(
                """
                EXPLAIN (ANALYZE, BUFFERS)
                SELECT id
                FROM act_sections
                WHERE embedding IS NOT NULL
                  AND embedding_status = :status
                ORDER BY embedding <=> CAST(:query AS vector)
                LIMIT 10
                """
            ),
            {
                "status": EmbeddingStatus.READY.value,
                "query": "[" + ",".join(str(value) for value in QUERY_VECTOR) + "]",
            },
        ).all()
        plan = "\n".join(str(row[0]) for row in plan_rows)

    engine.dispose()
    assert "hnsw" in plan.lower()
    assert "ix_act_sections_embedding_hnsw" in plan.lower()
