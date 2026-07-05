from uuid import uuid4

from app.core.roles import (
    ProcessingJobStatus,
    ProcessingStatus,
    RelationshipType,
    VerificationStatus,
)
from app.db.session import SessionLocal
from app.models.act_section import ActSection
from app.models.evaluation import EvaluationGoldReference
from app.models.legal_act import LegalAct
from app.models.legal_reference import LegalReference
from app.models.processing_job import ProcessingJob
from app.services.evaluation_service import (
    calculate_metrics,
    calculate_section_segmentation_accuracy,
)
from app.services.text_cleaner import normalize_for_search


def test_evaluation_metrics():
    metrics = calculate_metrics(
        gold_keys={("section 5", "AMENDS"), ("section 7", "REPEALS")},
        predicted_keys={("section 5", "AMENDS"), ("section 9", "REFERS_TO")},
    )
    assert metrics["true_positives"] == 1
    assert metrics["false_positives"] == 1
    assert metrics["false_negatives"] == 1
    assert metrics["precision"] == 0.5
    assert metrics["recall"] == 0.5
    assert metrics["f1_score"] == 0.5


def test_empty_gold_dataset_metrics_are_zero():
    metrics = calculate_metrics(gold_keys=set(), predicted_keys={("section 9", "AMENDS")})

    assert metrics["true_positives"] == 0
    assert metrics["false_positives"] == 1
    assert metrics["false_negatives"] == 0
    assert metrics["precision"] == 0.0
    assert metrics["recall"] == 0.0
    assert metrics["f1_score"] == 0.0


def test_section_segmentation_accuracy_helper():
    accuracy = calculate_section_segmentation_accuracy(
        expected_sections={"1", "2", "3"},
        detected_sections={"1", "3", "4"},
    )

    assert accuracy == 0.6667
    assert (
        calculate_section_segmentation_accuracy(expected_sections=set(), detected_sections={"1"})
        is None
    )


def test_run_evaluation_records_mismatches(client, admin_token):
    fixture = _create_evaluation_fixture()

    response = client.post(
        "/api/v1/evaluation/run",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"run_name": "Mismatch evaluation", "act_id": fixture["act_id"]},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["true_positives"] == 1
    assert data["false_positives"] == 1
    assert data["false_negatives"] == 1
    assert data["precision"] == 0.5
    assert data["recall"] == 0.5
    assert data["f1_score"] == 0.5
    summary = data["run_summary_json"]
    assert summary["mismatch_counts"] == {
        "matched": 1,
        "false_positives": 1,
        "false_negatives": 1,
    }
    assert summary["false_positives"][0]["raw_text"] == "unexpected reference"
    assert summary["false_negatives"][0]["raw_text"] == "missing reference"


def test_metrics_summary_counts(client, admin_token):
    fixture = _create_evaluation_fixture()
    with SessionLocal() as db:
        db.add(
            ProcessingJob(
                act_id=fixture["act_id"],
                status=ProcessingJobStatus.COMPLETED,
                current_step="Completed",
                progress_percent=100,
                summary_json={
                    "warnings": ["Top level warning"],
                    "segmentation": {"warnings": ["Segmentation warning"]},
                    "errors": [],
                },
            )
        )
        db.commit()

    response = client.get(
        "/api/v1/evaluation/metrics-summary",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["document_counts"]["processed"] >= 1
    assert data["document_counts"]["failed"] >= 1
    assert data["section_counts"]["verified"] >= 1
    assert data["section_counts"]["pending"] >= 1
    assert data["reference_counts"]["mapped"] >= 1
    assert data["reference_counts"]["unresolved"] >= 1
    assert data["processing_job_counts"]["COMPLETED"] >= 1
    messages = data["latest_processing_messages"][0]
    assert "Top level warning" in messages["warnings"]
    assert "Segmentation warning" in messages["warnings"]


def test_evaluation_endpoints_are_admin_only(client, user_token):
    for path in (
        "/api/v1/evaluation/gold-references",
        "/api/v1/evaluation/runs",
        "/api/v1/evaluation/metrics-summary",
    ):
        response = client.get(path, headers={"Authorization": f"Bearer {user_token}"})
        assert response.status_code == 403


def _create_evaluation_fixture() -> dict[str, str]:
    with SessionLocal() as db:
        act = LegalAct(
            title="Evaluation Act",
            normalized_title=normalize_for_search("Evaluation Act"),
            act_number="1",
            year=2026,
            source_file_name="evaluation.pdf",
            stored_file_path="evaluation.pdf",
            file_sha256=_sha(),
            processing_status=ProcessingStatus.PROCESSED,
        )
        failed_act = LegalAct(
            title="Failed Evaluation Act",
            normalized_title=normalize_for_search("Failed Evaluation Act"),
            source_file_name="failed.pdf",
            stored_file_path="failed.pdf",
            file_sha256=_sha(),
            processing_status=ProcessingStatus.FAILED,
        )
        target_act = LegalAct(
            title="Target Evaluation Act",
            normalized_title=normalize_for_search("Target Evaluation Act"),
            source_file_name="target.pdf",
            stored_file_path="target.pdf",
            file_sha256=_sha(),
            processing_status=ProcessingStatus.VERIFIED,
        )
        db.add_all([act, failed_act, target_act])
        db.flush()
        section = ActSection(
            act_id=act.id,
            section_number="5",
            section_path="5",
            heading="Verified section",
            text="Section text.",
            normalized_text=normalize_for_search("Section text."),
            sort_order=1,
            verification_status=VerificationStatus.VERIFIED,
        )
        pending_section = ActSection(
            act_id=act.id,
            section_number="6",
            section_path="6",
            heading="Pending section",
            text="Pending section.",
            normalized_text=normalize_for_search("Pending section."),
            sort_order=2,
            verification_status=VerificationStatus.PENDING,
        )
        db.add_all([section, pending_section])
        db.flush()
        matched_reference = LegalReference(
            source_act_id=act.id,
            source_section_id=section.id,
            raw_reference_text="Matched reference",
            context_snippet="Matched reference context.",
            relationship_type=RelationshipType.AMENDS,
            target_act_title_raw="Target Evaluation Act",
            target_section_number="9",
            target_act_id=target_act.id,
            confidence_score=0.9,
            verification_status=VerificationStatus.VERIFIED,
        )
        unexpected_reference = LegalReference(
            source_act_id=act.id,
            source_section_id=section.id,
            raw_reference_text="Unexpected reference",
            context_snippet="Unexpected reference context.",
            relationship_type=RelationshipType.REPEALS,
            confidence_score=0.3,
            verification_status=VerificationStatus.PENDING,
        )
        db.add_all([matched_reference, unexpected_reference])
        db.add_all(
            [
                EvaluationGoldReference(
                    act_id=act.id,
                    source_section_id=section.id,
                    expected_raw_text="Matched reference",
                    expected_relationship_type="AMENDS",
                    expected_target_act_title="Target Evaluation Act",
                    expected_target_section_number="9",
                ),
                EvaluationGoldReference(
                    act_id=act.id,
                    source_section_id=section.id,
                    expected_raw_text="Missing reference",
                    expected_relationship_type="INSERTS",
                ),
            ]
        )
        db.commit()
        return {"act_id": act.id}


def _sha() -> str:
    return uuid4().hex.ljust(64, "0")[:64]
