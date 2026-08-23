from datetime import datetime

from pydantic import BaseModel, ConfigDict


class GoldReferenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    act_id: str | None
    source_section_id: str | None
    expected_raw_text: str
    expected_relationship_type: str
    expected_target_act_title: str | None
    expected_target_section_number: str | None
    notes: str | None
    created_at: datetime


class GoldReferenceCreate(BaseModel):
    act_id: str | None = None
    source_section_id: str | None = None
    expected_raw_text: str
    expected_relationship_type: str
    expected_target_act_title: str | None = None
    expected_target_section_number: str | None = None
    notes: str | None = None


class EvaluationRunCreate(BaseModel):
    run_name: str
    act_id: str | None = None
    section_segmentation_accuracy: float | None = None
    extraction_mode: str | None = None


class EvaluationRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    run_name: str
    act_id: str | None
    precision: float
    recall: float
    f1_score: float
    section_segmentation_accuracy: float | None
    total_gold_references: int
    true_positives: int
    false_positives: int
    false_negatives: int
    run_summary_json: dict | None
    created_at: datetime


class EvaluationMetricsSummary(BaseModel):
    document_counts: dict[str, int]
    section_counts: dict[str, int]
    reference_counts: dict[str, int]
    processing_job_counts: dict[str, int]
    latest_processing_messages: list[dict]
    latest_evaluation_runs: list[dict]
