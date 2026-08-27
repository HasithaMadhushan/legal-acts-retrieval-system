from pathlib import Path

from app.core.roles import (
    ProcessingJobStatus,
    ProcessingStatus,
    RelationshipType,
    VerificationStatus,
)
from app.db.session import SessionLocal
from app.models.legal_act import LegalAct
from app.models.legal_reference import LegalReference
from app.models.processing_job import ProcessingJob
from app.services.text_cleaner import normalize_for_search

VALID_PDF = b"%PDF-1.4\n% test legal act pdf\n"


def test_admin_can_patch_act_metadata(client, admin_token):
    upload = client.post(
        "/api/v1/acts/upload",
        headers={"Authorization": f"Bearer {admin_token}"},
        files={"file": ("sample.pdf", VALID_PDF, "application/pdf")},
    )
    assert upload.status_code == 201
    act_id = upload.json()["id"]
    response = client.patch(
        f"/api/v1/acts/{act_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"title": "Updated Title", "year": 2021, "act_number": "4"},
    )
    assert response.status_code == 200
    assert response.json()["title"] == "Updated Title"
    assert response.json()["year"] == 2021
    assert response.json()["act_number"] == "4"


def test_non_admin_cannot_patch_or_delete_act(client, user_token, admin_token):
    upload = client.post(
        "/api/v1/acts/upload",
        headers={"Authorization": f"Bearer {admin_token}"},
        files={"file": ("sample.pdf", VALID_PDF, "application/pdf")},
    )
    act_id = upload.json()["id"]
    patched = client.patch(
        f"/api/v1/acts/{act_id}",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"title": "Nope"},
    )
    assert patched.status_code == 403
    deleted = client.delete(
        f"/api/v1/acts/{act_id}",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert deleted.status_code == 403


def test_delete_act_removes_stored_file(client, admin_token):
    upload = client.post(
        "/api/v1/acts/upload",
        headers={"Authorization": f"Bearer {admin_token}"},
        files={"file": ("sample.pdf", VALID_PDF, "application/pdf")},
    )
    assert upload.status_code == 201
    act_id = upload.json()["id"]
    with SessionLocal() as db:
        stored_path = db.get(LegalAct, act_id).stored_file_path
    assert Path(stored_path).exists()
    deleted = client.delete(
        f"/api/v1/acts/{act_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert deleted.status_code == 200
    assert not Path(stored_path).exists()


def test_delete_act_while_processing_is_queued_returns_409(client, admin_token):
    _assert_delete_blocked_while_processing(client, admin_token, ProcessingJobStatus.QUEUED)


def test_delete_act_while_processing_is_running_returns_409(client, admin_token):
    _assert_delete_blocked_while_processing(client, admin_token, ProcessingJobStatus.RUNNING)


def _assert_delete_blocked_while_processing(client, admin_token, status):
    upload = client.post(
        "/api/v1/acts/upload",
        headers={"Authorization": f"Bearer {admin_token}"},
        files={"file": ("sample.pdf", VALID_PDF, "application/pdf")},
    )
    act_id = upload.json()["id"]
    with SessionLocal() as db:
        db.add(
            ProcessingJob(
                act_id=act_id,
                status=status,
                current_step="Working",
            )
        )
        db.commit()

    response = client.delete(
        f"/api/v1/acts/{act_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 409
    assert "processing is queued or running" in response.json()["detail"]
    with SessionLocal() as db:
        assert db.get(LegalAct, act_id) is not None


def test_delete_referenced_act_returns_409(client, admin_token):
    with SessionLocal() as db:
        source = LegalAct(
            title="Source Act",
            normalized_title=normalize_for_search("Source Act"),
            source_file_name="source.pdf",
            stored_file_path="source.pdf",
            file_sha256="a" * 64,
            processing_status=ProcessingStatus.PROCESSED,
        )
        target = LegalAct(
            title="Target Act",
            normalized_title=normalize_for_search("Target Act"),
            source_file_name="target.pdf",
            stored_file_path="target.pdf",
            file_sha256="b" * 64,
            processing_status=ProcessingStatus.PROCESSED,
        )
        db.add_all([source, target])
        db.flush()
        db.add(
            LegalReference(
                source_act_id=source.id,
                raw_reference_text="the Target Act",
                context_snippet="refers to the Target Act",
                relationship_type=RelationshipType.REFERS_TO,
                target_act_id=target.id,
                verification_status=VerificationStatus.PENDING,
            )
        )
        db.commit()
        target_id = target.id

    response = client.delete(
        f"/api/v1/acts/{target_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 409
    assert "referenced by other Acts" in response.json()["detail"]


def test_delete_act_allows_its_own_self_mapped_references(client, admin_token):
    with SessionLocal() as db:
        act = LegalAct(
            title="Self Referencing Act",
            normalized_title=normalize_for_search("Self Referencing Act"),
            source_file_name="self.pdf",
            stored_file_path="self.pdf",
            file_sha256="c" * 64,
            processing_status=ProcessingStatus.PROCESSED,
        )
        db.add(act)
        db.flush()
        db.add(
            LegalReference(
                source_act_id=act.id,
                raw_reference_text="section 2 of this Act",
                context_snippet="Section 1 refers to section 2 of this Act.",
                relationship_type=RelationshipType.REFERS_TO,
                target_act_id=act.id,
                verification_status=VerificationStatus.PENDING,
            )
        )
        db.add(
            ProcessingJob(
                act_id=act.id,
                status=ProcessingJobStatus.COMPLETED,
                current_step="Completed",
                progress_percent=100,
            )
        )
        db.commit()
        act_id = act.id

    response = client.delete(
        f"/api/v1/acts/{act_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    with SessionLocal() as db:
        assert db.get(LegalAct, act_id) is None
        assert db.query(LegalReference).filter_by(source_act_id=act_id).count() == 0
        assert db.query(ProcessingJob).filter_by(act_id=act_id).count() == 0


def test_admin_can_remap_unverified_references_without_changing_locked_rows(
    client, admin_token
):
    with SessionLocal() as db:
        source = LegalAct(
            title="Value Added Tax Act",
            normalized_title=normalize_for_search("Value Added Tax Act"),
            act_number="14",
            year=2002,
            source_file_name="vat.pdf",
            stored_file_path="vat.pdf",
            file_sha256="d" * 64,
            processing_status=ProcessingStatus.PROCESSED,
        )
        inland_revenue = LegalAct(
            title="Inland Revenue Act",
            normalized_title=normalize_for_search("Inland Revenue Act"),
            act_number="24",
            year=2017,
            source_file_name="ira.pdf",
            stored_file_path="ira.pdf",
            file_sha256="e" * 64,
            processing_status=ProcessingStatus.PROCESSED,
        )
        db.add_all([source, inland_revenue])
        db.flush()
        pending = LegalReference(
            source_act_id=source.id,
            raw_reference_text="director has the same meaning as in the Inland Revenue Act",
            context_snippet="director has the same meaning as in the Inland Revenue Act",
            relationship_type=RelationshipType.REFERS_TO,
            target_act_title_raw="means a director as defined in the Inland Revenue Act",
            confidence_score=0.4,
            verification_status=VerificationStatus.PENDING,
        )
        verified = LegalReference(
            source_act_id=source.id,
            raw_reference_text="Inland Revenue Act",
            context_snippet="Inland Revenue Act",
            relationship_type=RelationshipType.REFERS_TO,
            target_act_title_raw="Inland Revenue Act",
            confidence_score=0.9,
            verification_status=VerificationStatus.VERIFIED,
        )
        db.add_all([pending, verified])
        db.commit()
        source_id = source.id
        inland_revenue_id = inland_revenue.id
        pending_id = pending.id
        verified_id = verified.id

    remapped = client.post(
        f"/api/v1/acts/{source_id}/remap-references",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert remapped.status_code == 200
    body = remapped.json()
    assert body["mapped_act_count"] == 1
    assert body["skipped_locked_count"] == 1

    with SessionLocal() as db:
        assert db.get(LegalReference, pending_id).target_act_id == inland_revenue_id
        assert db.get(LegalReference, verified_id).target_act_id is None


def test_lawyer_cannot_remap_references(client, lawyer_token, admin_token):
    upload = client.post(
        "/api/v1/acts/upload",
        headers={"Authorization": f"Bearer {admin_token}"},
        files={"file": ("sample.pdf", VALID_PDF, "application/pdf")},
    )
    act_id = upload.json()["id"]
    blocked = client.post(
        f"/api/v1/acts/{act_id}/remap-references",
        headers={"Authorization": f"Bearer {lawyer_token}"},
    )
    assert blocked.status_code == 403


def test_remap_unknown_act_returns_404(client, admin_token):
    response = client.post(
        "/api/v1/acts/missing-act/remap-references",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 404


def test_admin_review_queue_lists_acts_with_needs_review_references(
    client, admin_token, lawyer_token
):
    with SessionLocal() as db:
        queued = LegalAct(
            title="Queued Review Act",
            normalized_title=normalize_for_search("Queued Review Act"),
            source_file_name="queued.pdf",
            stored_file_path="queued.pdf",
            file_sha256="f" * 64,
            processing_status=ProcessingStatus.PROCESSED,
        )
        clean = LegalAct(
            title="Clean Act",
            normalized_title=normalize_for_search("Clean Act"),
            source_file_name="clean.pdf",
            stored_file_path="clean.pdf",
            file_sha256="g" * 64,
            processing_status=ProcessingStatus.PROCESSED,
        )
        db.add_all([queued, clean])
        db.flush()
        db.add(
            LegalReference(
                source_act_id=queued.id,
                raw_reference_text="Needs review",
                context_snippet="Needs review.",
                relationship_type=RelationshipType.REFERS_TO,
                confidence_score=0.4,
                verification_status=VerificationStatus.NEEDS_REVIEW,
            )
        )
        db.add(
            LegalReference(
                source_act_id=clean.id,
                raw_reference_text="Verified",
                context_snippet="Verified.",
                relationship_type=RelationshipType.REFERS_TO,
                confidence_score=0.9,
                verification_status=VerificationStatus.VERIFIED,
            )
        )
        db.commit()
        queued_id = queued.id
        clean_id = clean.id

    response = client.get(
        "/api/v1/acts/review-queue",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    blocked = client.get(
        "/api/v1/acts/review-queue",
        headers={"Authorization": f"Bearer {lawyer_token}"},
    )
    assert response.status_code == 200
    ids = {item["act_id"] for item in response.json()}
    assert queued_id in ids
    assert clean_id not in ids
    queued_row = next(item for item in response.json() if item["act_id"] == queued_id)
    assert queued_row["needs_review_references"] == 1
    assert queued_row["title"] == "Queued Review Act"
    assert blocked.status_code == 403
