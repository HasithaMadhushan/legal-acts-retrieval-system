from pathlib import Path

import fitz

from app.db.session import SessionLocal
from app.models.act_section import ActSection
from app.models.legal_act import LegalAct
from app.models.legal_reference import LegalReference
from app.tests.helpers import process_and_wait

SAMPLE_ACT_TEXT = """TEST LEGAL ACT
Act, No. 1 of 2024

1. Short title.
This Act may be cited as the Test Legal Act.

2. Interpretation.
For the purposes of section 1, this section provides sample text.
"""


def _pdf_bytes_with_text(text: str) -> bytes:
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), text, fontsize=11)
    content = document.tobytes()
    document.close()
    return content


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
        references = (
            db.query(LegalReference).filter(LegalReference.source_act_id == act_id).all()
        )
        return [
            {
                "id": reference.id,
                "source_section_id": reference.source_section_id,
                "verification_status": reference.verification_status,
            }
            for reference in references
        ]


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
    assert "OCR is disabled" in job["error_message"]
    assert summary["page_count"] == 1
    assert summary["extracted_character_count"] == 0
    assert any("did not produce text" in warning for warning in summary["warnings"])
    assert any("OCR is disabled" in warning for warning in summary["warnings"])


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
