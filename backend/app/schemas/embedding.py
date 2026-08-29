from datetime import datetime

from pydantic import BaseModel


class EmbeddingCounts(BaseModel):
    total: int
    ready: int
    pending: int
    stale: int
    failed: int


class EmbeddingFailureSample(BaseModel):
    section_id: str
    act_id: str
    act_title: str
    section_path: str | None
    error: str


class EmbeddingIndexStatus(BaseModel):
    dialect: str
    vector_extension: bool
    column_dimension: int | None
    hnsw_index_present: bool | None


class EmbeddingStatusResponse(BaseModel):
    provider: str
    model: str
    model_revision: str
    dimension: int
    semantic_enabled: bool
    semantic_ready: bool
    readiness_reasons: list[str]
    counts: EmbeddingCounts
    index: EmbeddingIndexStatus
    latest_embedding_at: datetime | None
    latest_backfill_run: None = None
    failure_samples: list[EmbeddingFailureSample]
    remediation_command: str
