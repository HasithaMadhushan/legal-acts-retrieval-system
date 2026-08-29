import json
from pathlib import Path

import fitz

from app.core.roles import EmbeddingStatus, ProcessingJobStatus, ProcessingStatus
from app.db.session import SessionLocal
from app.models.act_section import ActSection
from app.models.legal_act import LegalAct
from app.models.legal_reference import LegalReference
from app.services import document_processor as processor_module
from app.services.embedding_service import EmbeddingService
from app.services.extraction_artifact import ArtifactPersistError
from app.services.storage import get_storage
from app.tests.helpers import process_and_wait

SAMPLE_ACT_TEXT = """TEST LEGAL ACT
Act, No. 1 of 2024

1. Short title.
This Act may be cited as the Test Legal Act.

2. Interpretation.
For the purposes of section 1, this section provides sample text.
"""


def _pdf_bytes_with_pages(page_texts: list[str]) -> bytes:
    document = fitz.open()
    for text in page_texts:
        page = document.new_page()
        page.insert_text((72, 72), text, fontsize=11)
    content = document.tobytes()
    document.close()
    return content


def _pdf_bytes_with_text(text: str) -> bytes:
    return _pdf_bytes_with_pages([text])


def _blank_pdf_bytes() -> bytes:
    document = fitz.open()
    document.new_page()
    content = document.tobytes()
    document.close()
    return content


def _upload_pdf(client, admin_token, content: bytes, filename: str = "act.pdf") -> dict:
    response = client.post(
        "/api/v1/acts/upload",
        headers={"Authorization": f"Bearer {admin_token}"},
        files={"file": (filename, content, "application/pdf")},
    )
    assert response.status_code == 201
    return response.json()


def _process_and_wait(client, admin_token, act_id: str) -> dict:
    return process_and_wait(client, admin_token, act_id)


def _artifact_exists(pointer: str) -> bool:
    try:
        get_storage().read_artifact(pointer)
    except FileNotFoundError:
        return False
    return True


def _replace_stored_path(act_id: str, stored_file_path: str) -> None:
    with SessionLocal() as db:
        act = db.get(LegalAct, act_id)
        assert act is not None
        act.stored_file_path = stored_file_path
        db.commit()


def _section_count(act_id: str) -> int:
    with SessionLocal() as db:
        return db.query(ActSection).filter(ActSection.act_id == act_id).count()


def _section_rows(act_id: str) -> list[dict]:
    with SessionLocal() as db:
        sections = (
            db.query(ActSection)
            .filter(ActSection.act_id == act_id)
            .order_by(ActSection.sort_order)
            .all()
        )
        return [
            {
                "id": section.id,
                "section_number": section.section_number,
                "verification_status": section.verification_status,
            }
            for section in sections
        ]


def _reference_rows(act_id: str) -> list[dict]:
    with SessionLocal() as db:
        references = db.query(LegalReference).filter(LegalReference.source_act_id == act_id).all()
        return [
            {
                "id": reference.id,
                "source_section_id": reference.source_section_id,
                "verification_status": reference.verification_status,
            }
            for reference in references
        ]


def _verify_section(client, admin_token: str, section_id: str) -> None:
    response = client.post(
        f"/api/v1/sections/{section_id}/verify",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200


def test_processing_marks_new_sections_ready_with_source_hash_and_metadata(client, admin_token):
    act = _upload_pdf(client, admin_token, _pdf_bytes_with_text(SAMPLE_ACT_TEXT))

    job = _process_and_wait(client, admin_token, act["id"])
    assert job["status"] == "COMPLETED"

    with SessionLocal() as db:
        act_row = db.get(LegalAct, act["id"])
        assert act_row is not None
        sections = (
            db.query(ActSection)
            .filter(ActSection.act_id == act["id"])
            .order_by(ActSection.sort_order)
            .all()
        )
        assert sections
        service = EmbeddingService()
        for section in sections:
            assert section.embedding_status == EmbeddingStatus.READY
            assert section.embedding_provider == "hash-test"
            assert section.embedding_model == "hash-test"
            assert section.embedding_dimension == 384
            assert section.embedding is not None
            assert len(section.embedding) == 384
            assert section.embedded_at is not None
            assert section.embedding_error is None
            expected_hash = service.source_hash(
                service.truncate_text(service.build_section_text(act_row, section))
            )
            assert section.embedding_source_hash == expected_hash


def test_processing_records_embedding_counts_in_job_summary(client, admin_token):
    act = _upload_pdf(client, admin_token, _pdf_bytes_with_text(SAMPLE_ACT_TEXT))

    job = _process_and_wait(client, admin_token, act["id"])
    summary = job["summary_json"]

    assert job["status"] == "COMPLETED"
    assert summary["embeddings"]["embedded"] == summary["sections_created"]
    assert summary["embeddings"]["failed"] == 0
    assert summary["embeddings"]["skipped"] == 0
    assert summary["embeddings"]["stale"] == 0


def test_embedding_provider_failure_keeps_extracted_content_and_records_warning(
    client, admin_token, monkeypatch
):
    def explode(_self, texts):
        raise RuntimeError("embedding provider unavailable")

    monkeypatch.setattr(
        "app.services.embedding_providers.DeterministicTestProvider.embed_documents",
        explode,
    )
    act = _upload_pdf(client, admin_token, _pdf_bytes_with_text(SAMPLE_ACT_TEXT))

    job = _process_and_wait(client, admin_token, act["id"])
    summary = job["summary_json"]

    assert job["status"] == "COMPLETED"
    assert summary["sections_created"] >= 1
    assert summary["references_created"] >= 1
    assert summary["embeddings"]["failed"] == summary["sections_created"]
    assert summary["embeddings"]["embedded"] == 0
    assert any("embedding" in warning.lower() for warning in summary["warnings"])
    assert summary["errors"] == []

    detail = client.get(
        f"/api/v1/acts/{act['id']}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert detail.status_code == 200
    assert detail.json()["processing_status"] == "PROCESSED"

    with SessionLocal() as db:
        sections = db.query(ActSection).filter(ActSection.act_id == act["id"]).all()
        references = (
            db.query(LegalReference).filter(LegalReference.source_act_id == act["id"]).all()
        )
        assert sections
        assert references
        for section in sections:
            assert section.text
            assert section.embedding_status == EmbeddingStatus.FAILED
            assert section.embedding_error is not None
            assert section.text not in section.embedding_error


def test_admin_can_trigger_processing_for_valid_pdf(client, admin_token):
    act = _upload_pdf(client, admin_token, _pdf_bytes_with_text(SAMPLE_ACT_TEXT))

    job = _process_and_wait(client, admin_token, act["id"])
    summary = job["summary_json"]
    assert job["status"] == "COMPLETED"
    assert summary["parser_requested"] == "pymupdf"
    assert summary["parser_used"] == "PYMUPDF"
    assert summary["page_count"] == 1
    assert summary["extracted_character_count"] > 0
    assert summary["sections_created"] >= 1
    assert summary["segmentation"]["sections_detected"] >= 1
    assert summary["segmentation"]["fallback_used"] is False
    assert summary["references"]["references_detected"] >= 1
    assert "CROSS_REFERENCE" in summary["references"]["by_type"]
    assert summary["mapping"]["total_references"] == summary["references"]["references_detected"]
    assert summary["mapping"]["unresolved_count"] >= 1
    assert summary["errors"] == []

    detail = client.get(
        f"/api/v1/acts/{act['id']}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert detail.status_code == 200
    assert detail.json()["processing_status"] == "PROCESSED"
    assert detail.json()["parser_used"] == "PYMUPDF"


def test_successful_processing_persists_extraction_artifact(client, admin_token):
    act = _upload_pdf(client, admin_token, _pdf_bytes_with_text(SAMPLE_ACT_TEXT))

    job = _process_and_wait(client, admin_token, act["id"])
    summary = job["summary_json"]
    pointer = summary["extraction_artifact_key"]
    payload = json.loads(get_storage().read_artifact(pointer))

    assert job["status"] == "COMPLETED"
    assert pointer
    assert summary["extraction_artifact_sha256"]
    assert payload["processing_text"]
    assert payload["page_spans"] is not None
    assert len(payload["page_spans"]) == summary["page_count"]

    with SessionLocal() as db:
        stored = db.get(LegalAct, act["id"])
        assert stored is not None
        assert stored.extraction_artifact_key == pointer
        assert stored.extraction_artifact_sha256 == summary["extraction_artifact_sha256"]

    detail = client.get(
        f"/api/v1/acts/{act['id']}",
        headers={"Authorization": f"Bearer {admin_token}"},
    ).json()
    artifact = detail["extraction_artifact"]
    assert artifact["present"] is True
    assert artifact["has_physical_pages"] is True
    assert artifact["integrity_warning"] is False
    assert artifact["parser_name"] == "PYMUPDF"
    assert "s3://" not in json.dumps(artifact)
    assert artifact["sha256_prefix"] == summary["extraction_artifact_sha256"][:12]


def test_reprocess_writes_new_artifact_and_retains_the_previous_object(client, admin_token):
    act = _upload_pdf(client, admin_token, _pdf_bytes_with_text(SAMPLE_ACT_TEXT))
    first = _process_and_wait(client, admin_token, act["id"])
    first_pointer = first["summary_json"]["extraction_artifact_key"]
    second = _process_and_wait(client, admin_token, act["id"])
    second_pointer = second["summary_json"]["extraction_artifact_key"]

    assert first_pointer != second_pointer
    get_storage().read_artifact(first_pointer)
    get_storage().read_artifact(second_pointer)
    with SessionLocal() as db:
        stored = db.get(LegalAct, act["id"])
        assert stored is not None
        assert stored.extraction_artifact_key == second_pointer


def test_delete_act_removes_current_and_historical_extraction_artifacts(client, admin_token):
    act = _upload_pdf(client, admin_token, _pdf_bytes_with_text(SAMPLE_ACT_TEXT))
    first = _process_and_wait(client, admin_token, act["id"])
    second = _process_and_wait(client, admin_token, act["id"])
    pointers = [
        first["summary_json"]["extraction_artifact_key"],
        second["summary_json"]["extraction_artifact_key"],
    ]
    assert all(_artifact_exists(pointer) for pointer in pointers)

    deleted = client.delete(
        f"/api/v1/acts/{act['id']}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert deleted.status_code == 200
    assert all(not _artifact_exists(pointer) for pointer in pointers)


def test_failed_artifact_persist_records_cleanup_warning(client, admin_token, monkeypatch):
    def fail_persist(*args, **kwargs):
        raise ArtifactPersistError(
            "extraction artifact hash mismatch after write",
            cleanup_warning="Failed to delete orphan extraction artifact: cannot delete",
        )

    monkeypatch.setattr(
        "app.services.document_processor.persist_extraction_artifact",
        fail_persist,
    )
    act = _upload_pdf(client, admin_token, _pdf_bytes_with_text(SAMPLE_ACT_TEXT))
    job = _process_and_wait(client, admin_token, act["id"])
    summary = job["summary_json"]

    assert job["status"] == "FAILED"
    assert "hash mismatch" in job["error_message"]
    assert "cannot delete" in summary["artifact_cleanup_warning"]
    assert "extraction_artifact_key" not in summary
    with SessionLocal() as db:
        stored = db.get(LegalAct, act["id"])
        assert stored is not None
        assert stored.extraction_artifact_key is None


def _capture_persist_and_fail_completed_commit(monkeypatch):
    original_execute = processor_module._execute_processing_job
    original_persist = processor_module.persist_extraction_artifact
    written: list[str] = []

    def persist(*args, **kwargs):
        pointer, digest = original_persist(*args, **kwargs)
        written.append(pointer)
        return pointer, digest

    def execute(db, job, act_row):
        original_commit = db.commit

        def commit():
            if job.status == ProcessingJobStatus.COMPLETED:
                raise RuntimeError("commit failed after artifact write")
            return original_commit()

        db.commit = commit
        return original_execute(db, job, act_row)

    monkeypatch.setattr(processor_module, "persist_extraction_artifact", persist)
    monkeypatch.setattr(processor_module, "_execute_processing_job", execute)
    return written


def test_commit_failure_after_artifact_write_deletes_orphan_and_keeps_previous_pointer(
    client, admin_token, monkeypatch
):
    act = _upload_pdf(client, admin_token, _pdf_bytes_with_text(SAMPLE_ACT_TEXT))
    first = _process_and_wait(client, admin_token, act["id"])
    previous_pointer = first["summary_json"]["extraction_artifact_key"]
    written = _capture_persist_and_fail_completed_commit(monkeypatch)

    job = _process_and_wait(client, admin_token, act["id"])
    summary = job["summary_json"]

    assert job["status"] == "FAILED"
    assert "commit failed after artifact write" in job["error_message"]
    assert "extraction_artifact_key" not in summary
    assert "extraction_artifact_sha256" not in summary
    assert "artifact_cleanup_warning" not in summary
    assert written
    assert not _artifact_exists(written[-1])
    assert _artifact_exists(previous_pointer)
    with SessionLocal() as db:
        stored = db.get(LegalAct, act["id"])
        assert stored is not None
        assert stored.extraction_artifact_key == previous_pointer


def test_commit_failure_records_cleanup_warning_when_orphan_delete_fails(
    client, admin_token, monkeypatch
):
    act = _upload_pdf(client, admin_token, _pdf_bytes_with_text(SAMPLE_ACT_TEXT))
    first = _process_and_wait(client, admin_token, act["id"])
    previous_pointer = first["summary_json"]["extraction_artifact_key"]
    written = _capture_persist_and_fail_completed_commit(monkeypatch)
    storage = get_storage()
    original_delete = storage.delete

    def delete(key):
        if key != previous_pointer:
            raise RuntimeError("cannot delete")
        return original_delete(key)

    monkeypatch.setattr(storage, "delete", delete)

    job = _process_and_wait(client, admin_token, act["id"])
    summary = job["summary_json"]

    assert job["status"] == "FAILED"
    assert "cannot delete" in summary["artifact_cleanup_warning"]
    assert "extraction_artifact_key" not in summary
    assert "extraction_artifact_sha256" not in summary
    assert written
    assert _artifact_exists(written[-1])
    assert _artifact_exists(previous_pointer)
    with SessionLocal() as db:
        stored = db.get(LegalAct, act["id"])
        assert stored is not None
        assert stored.extraction_artifact_key == previous_pointer


def test_refresh_failure_after_successful_commit_does_not_mark_job_failed(
    client, admin_token, monkeypatch
):
    original_execute = processor_module._execute_processing_job

    def execute(db, job, act_row):
        original_commit = db.commit
        original_refresh = db.refresh
        success_committed = {"value": False}

        def commit():
            original_commit()
            if job.status == ProcessingJobStatus.COMPLETED:
                success_committed["value"] = True

        def refresh(instance):
            if success_committed["value"]:
                raise RuntimeError("refresh failed after commit")
            return original_refresh(instance)

        db.commit = commit
        db.refresh = refresh
        return original_execute(db, job, act_row)

    monkeypatch.setattr(processor_module, "_execute_processing_job", execute)
    act = _upload_pdf(client, admin_token, _pdf_bytes_with_text(SAMPLE_ACT_TEXT))
    job = _process_and_wait(client, admin_token, act["id"])

    assert job["status"] == "COMPLETED"
    assert job["summary_json"]["extraction_artifact_key"]
    with SessionLocal() as db:
        stored = db.get(LegalAct, act["id"])
        assert stored is not None
        assert stored.processing_status == ProcessingStatus.PROCESSED
        assert stored.extraction_artifact_key


def test_non_admin_cannot_trigger_processing(client, admin_token, lawyer_token, user_token):
    act = _upload_pdf(client, admin_token, _pdf_bytes_with_text(SAMPLE_ACT_TEXT))

    lawyer_response = client.post(
        f"/api/v1/acts/{act['id']}/process",
        headers={"Authorization": f"Bearer {lawyer_token}"},
    )
    user_response = client.post(
        f"/api/v1/acts/{act['id']}/process",
        headers={"Authorization": f"Bearer {user_token}"},
    )

    assert lawyer_response.status_code == 403
    assert user_response.status_code == 403


def test_missing_pdf_file_path_fails_safely(client, admin_token):
    act = _upload_pdf(client, admin_token, _pdf_bytes_with_text(SAMPLE_ACT_TEXT))
    _replace_stored_path(act["id"], str(Path("test_uploads") / "missing.pdf"))

    job = _process_and_wait(client, admin_token, act["id"])
    assert job["status"] == "FAILED"
    assert "could not be found" in job["error_message"]
    assert "could not be found" in job["summary_json"]["errors"][0]


def test_corrupted_pdf_fails_gracefully(client, admin_token):
    act = _upload_pdf(client, admin_token, b"%PDF-1.4\nnot a valid pdf body\n")

    job = _process_and_wait(client, admin_token, act["id"])
    assert job["status"] == "FAILED"
    assert "corrupted" in job["error_message"]
    assert job["summary_json"]["parser_used"] == "PYMUPDF"


def test_image_only_pdf_is_marked_ocr_required(client, admin_token):
    act = _upload_pdf(client, admin_token, _blank_pdf_bytes())

    job = _process_and_wait(client, admin_token, act["id"])
    summary = job["summary_json"]
    assert job["status"] == "FAILED"
    assert "native/OCR routes" in job["error_message"]
    assert summary["page_count"] == 1
    assert summary["extracted_character_count"] == 0
    assert any("did not produce text" in warning for warning in summary["warnings"])
    assert any("native/OCR routes" in warning for warning in summary["warnings"])
    assert all("OCR extraction was attempted" not in warning for warning in summary["warnings"])
    assert "extraction_artifact_key" not in summary


def test_multi_page_act_records_section_page_numbers(client, admin_token):
    act = _upload_pdf(
        client,
        admin_token,
        _pdf_bytes_with_pages(
            [
                "1. Short title.\nThis Act may be cited as the Example Act.",
                "2. Duties.\nThe Minister may make regulations.",
            ]
        ),
    )

    job = _process_and_wait(client, admin_token, act["id"])
    assert job["status"] == "COMPLETED"
    assert job["summary_json"]["page_count"] == 2

    response = client.get(
        f"/api/v1/acts/{act['id']}/sections",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    numbered = {
        section["section_number"]: section
        for section in response.json()
        if section["section_type"] == "SECTION"
    }
    assert numbered["1"]["page_start"] == 1
    assert numbered["1"]["page_end"] == 1
    assert numbered["2"]["page_start"] == 2
    assert numbered["2"]["page_end"] == 2


def test_unstructured_dense_pdf_records_structural_warning_on_the_job(client, admin_token):
    unstructured = "Long unstructured extraction without numbered sections. " * 40
    act = _upload_pdf(client, admin_token, _pdf_bytes_with_text(unstructured))

    job = _process_and_wait(client, admin_token, act["id"])
    summary = job["summary_json"]

    assert job["status"] == "COMPLETED"
    assert any(
        "Native structural validation failed and no fallback passed" in warning
        for warning in summary["warnings"]
    )


def test_failed_reprocessing_does_not_replace_existing_sections(client, admin_token):
    act = _upload_pdf(client, admin_token, _pdf_bytes_with_text(SAMPLE_ACT_TEXT))
    first = _process_and_wait(client, admin_token, act["id"])
    assert first["status"] == "COMPLETED"
    section_count = _section_count(act["id"])
    assert section_count > 0

    with SessionLocal() as db:
        act_row = db.get(LegalAct, act["id"])
        assert act_row is not None
        Path(act_row.stored_file_path).write_bytes(_blank_pdf_bytes())

    second = _process_and_wait(client, admin_token, act["id"])
    assert second["status"] == "FAILED"
    assert _section_count(act["id"]) == section_count


def test_reprocessing_preserves_verified_section_and_its_references(client, admin_token):
    act = _upload_pdf(client, admin_token, _pdf_bytes_with_text(SAMPLE_ACT_TEXT))
    first = _process_and_wait(client, admin_token, act["id"])
    assert first["status"] == "COMPLETED"

    sections_before = _section_rows(act["id"])
    references_before = _reference_rows(act["id"])
    assert sections_before
    assert references_before
    verified_section_id = sections_before[0]["id"]
    verified_reference_id = references_before[0]["id"]

    verify_section_response = client.post(
        f"/api/v1/sections/{verified_section_id}/verify",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert verify_section_response.status_code == 200
    verify_reference_response = client.post(
        f"/api/v1/references/{verified_reference_id}/verify",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert verify_reference_response.status_code == 200

    job = _process_and_wait(client, admin_token, act["id"])
    assert job["status"] == "COMPLETED"
    summary = job["summary_json"]
    assert summary["sections_preserved"] >= 1
    assert summary["references_preserved"] >= 1

    sections_after = {row["id"]: row for row in _section_rows(act["id"])}
    references_after = {row["id"]: row for row in _reference_rows(act["id"])}

    assert verified_section_id in sections_after
    assert sections_after[verified_section_id]["verification_status"] == "VERIFIED"
    assert verified_reference_id in references_after
    assert references_after[verified_reference_id]["verification_status"] == "VERIFIED"
    # The reference must still point at a section that actually exists.
    preserved_reference_section_id = references_after[verified_reference_id]["source_section_id"]
    assert preserved_reference_section_id in sections_after


def test_reprocessing_preserves_rejected_section(client, admin_token):
    act = _upload_pdf(client, admin_token, _pdf_bytes_with_text(SAMPLE_ACT_TEXT))
    _process_and_wait(client, admin_token, act["id"])

    sections_before = _section_rows(act["id"])
    rejected_section_id = sections_before[-1]["id"]
    reject_response = client.post(
        f"/api/v1/sections/{rejected_section_id}/reject",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert reject_response.status_code == 200

    second = _process_and_wait(client, admin_token, act["id"])
    assert second["status"] == "COMPLETED"

    sections_after = {row["id"]: row for row in _section_rows(act["id"])}
    assert rejected_section_id in sections_after
    assert sections_after[rejected_section_id]["verification_status"] == "REJECTED"


def test_reprocessing_does_not_overwrite_current_verified_embedding(client, admin_token):
    act = _upload_pdf(client, admin_token, _pdf_bytes_with_text(SAMPLE_ACT_TEXT))
    first = _process_and_wait(client, admin_token, act["id"])
    assert first["status"] == "COMPLETED"

    sections_before = _section_rows(act["id"])
    verified_section_id = sections_before[0]["id"]
    _verify_section(client, admin_token, verified_section_id)

    with SessionLocal() as db:
        section = db.get(ActSection, verified_section_id)
        assert section is not None
        original_embedding = list(section.embedding)
        original_hash = section.embedding_source_hash
        original_embedded_at = section.embedded_at

    job = _process_and_wait(client, admin_token, act["id"])
    summary = job["summary_json"]

    assert job["status"] == "COMPLETED"
    assert summary["embeddings"]["skipped"] >= 1
    with SessionLocal() as db:
        section = db.get(ActSection, verified_section_id)
        assert section is not None
        assert section.verification_status.value == "VERIFIED"
        assert section.embedding_status == EmbeddingStatus.READY
        assert list(section.embedding) == original_embedding
        assert section.embedding_source_hash == original_hash
        assert section.embedded_at == original_embedded_at


def test_reprocessing_marks_preserved_embedding_stale_when_model_changes(client, admin_token):
    act = _upload_pdf(client, admin_token, _pdf_bytes_with_text(SAMPLE_ACT_TEXT))
    _process_and_wait(client, admin_token, act["id"])
    verified_section_id = _section_rows(act["id"])[0]["id"]
    _verify_section(client, admin_token, verified_section_id)

    with SessionLocal() as db:
        section = db.get(ActSection, verified_section_id)
        assert section is not None
        original_embedding = list(section.embedding)
        section.embedding_model = "old-model"
        db.commit()

    job = _process_and_wait(client, admin_token, act["id"])
    summary = job["summary_json"]

    assert job["status"] == "COMPLETED"
    assert summary["embeddings"]["stale"] >= 1
    with SessionLocal() as db:
        section = db.get(ActSection, verified_section_id)
        assert section is not None
        assert section.verification_status.value == "VERIFIED"
        assert section.embedding_status == EmbeddingStatus.STALE
        assert list(section.embedding) == original_embedding
        assert section.embedding_model == "old-model"


def test_reprocessing_marks_preserved_embedding_stale_when_source_hash_changes(client, admin_token):
    act = _upload_pdf(client, admin_token, _pdf_bytes_with_text(SAMPLE_ACT_TEXT))
    _process_and_wait(client, admin_token, act["id"])
    verified_section_id = _section_rows(act["id"])[0]["id"]
    _verify_section(client, admin_token, verified_section_id)

    with SessionLocal() as db:
        section = db.get(ActSection, verified_section_id)
        act_row = db.get(LegalAct, act["id"])
        assert section is not None
        assert act_row is not None
        original_embedding = list(section.embedding)
        original_hash = section.embedding_source_hash
        act_row.title = "Retitled Constitutional Act"
        act_row.category = "Constitutional"
        db.commit()

    job = _process_and_wait(client, admin_token, act["id"])
    summary = job["summary_json"]

    assert job["status"] == "COMPLETED"
    assert summary["embeddings"]["stale"] >= 1
    with SessionLocal() as db:
        section = db.get(ActSection, verified_section_id)
        assert section is not None
        assert section.verification_status.value == "VERIFIED"
        assert section.embedding_status == EmbeddingStatus.STALE
        assert list(section.embedding) == original_embedding
        assert section.embedding_source_hash == original_hash


def test_admin_can_view_processing_jobs(client, admin_token):
    act = _upload_pdf(client, admin_token, _pdf_bytes_with_text(SAMPLE_ACT_TEXT))
    _process_and_wait(client, admin_token, act["id"])

    response = client.get(
        f"/api/v1/acts/{act['id']}/processing-jobs",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    jobs = response.json()
    assert jobs[0]["status"] == "COMPLETED"
    assert jobs[0]["summary_json"]["parser_used"] == "PYMUPDF"
