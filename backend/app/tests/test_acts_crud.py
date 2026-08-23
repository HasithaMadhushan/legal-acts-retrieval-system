from pathlib import Path

from app.core.roles import ProcessingStatus, RelationshipType, VerificationStatus
from app.db.session import SessionLocal
from app.models.legal_act import LegalAct
from app.models.legal_reference import LegalReference
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
