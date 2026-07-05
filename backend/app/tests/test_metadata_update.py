from pathlib import Path

import fitz

from app.db.session import SessionLocal
from app.models.legal_act import LegalAct
from app.services.text_cleaner import normalize_for_search


def _create_act() -> str:
    with SessionLocal() as db:
        act = LegalAct(
            title="Uploaded Act",
            normalized_title=normalize_for_search("Uploaded Act"),
            source_file_name="uploaded.pdf",
            stored_file_path="uploaded.pdf",
            file_sha256="b" * 64,
        )
        db.add(act)
        db.commit()
        return act.id


def _pdf_bytes_with_text(text: str) -> bytes:
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), text, fontsize=11)
    content = document.tobytes()
    document.close()
    return content


def _upload_pdf(client, admin_token, content: bytes, filename: str = "metadata.pdf") -> dict:
    response = client.post(
        "/api/v1/acts/upload",
        headers={"Authorization": f"Bearer {admin_token}"},
        files={"file": (filename, content, "application/pdf")},
    )
    assert response.status_code == 201
    return response.json()


def test_admin_can_update_metadata(client, admin_token):
    act_id = _create_act()

    response = client.patch(
        f"/api/v1/acts/{act_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "title": "Manual Reviewed Act",
            "act_number": "12A",
            "year": 2024,
            "category": "Tax",
            "source_name": "Official Gazette",
            "source_url": "https://example.test/act.pdf",
            "certification_date": "2024-01-12",
            "publication_date": "2024-01-20",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Manual Reviewed Act"
    assert data["normalized_title"] == "manual reviewed act"
    assert data["act_number"] == "12A"
    assert data["year"] == 2024
    assert data["category"] == "Tax"
    assert data["source_file_name"] == "uploaded.pdf"
    assert data["certification_date"] == "2024-01-12"
    assert data["publication_date"] == "2024-01-20"


def test_lawyer_and_general_user_cannot_update_metadata(
    client, admin_token, lawyer_token, user_token
):
    act_id = _create_act()

    lawyer_response = client.patch(
        f"/api/v1/acts/{act_id}",
        headers={"Authorization": f"Bearer {lawyer_token}"},
        json={"title": "Lawyer Edit"},
    )
    user_response = client.patch(
        f"/api/v1/acts/{act_id}",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"title": "User Edit"},
    )

    assert lawyer_response.status_code == 403
    assert user_response.status_code == 403


def test_metadata_update_rejects_invalid_title_and_year(client, admin_token):
    act_id = _create_act()

    empty_title = client.patch(
        f"/api/v1/acts/{act_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"title": "   "},
    )
    old_year = client.patch(
        f"/api/v1/acts/{act_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"year": 1700},
    )
    bad_number = client.patch(
        f"/api/v1/acts/{act_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"act_number": "<script>"},
    )

    assert empty_title.status_code == 422
    assert old_year.status_code == 422
    assert bad_number.status_code == 422


def test_reprocessing_preserves_reviewed_metadata(client, admin_token):
    initial_pdf = _pdf_bytes_with_text(
        """
        ORIGINAL TEST ACT
        Act, No. 1 of 2024
        Certified on 1st January 2024
        """
    )
    act = _upload_pdf(client, admin_token, initial_pdf)
    first_process = client.post(
        f"/api/v1/acts/{act['id']}/process",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert first_process.status_code == 200
    assert first_process.json()["status"] == "COMPLETED"

    update = client.patch(
        f"/api/v1/acts/{act['id']}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "title": "Admin Reviewed Title",
            "act_number": "99",
            "year": 1999,
            "category": "Reviewed",
            "certification_date": "1999-02-03",
        },
    )
    assert update.status_code == 200

    replacement_pdf = _pdf_bytes_with_text(
        """
        REPLACEMENT TEST ACT
        Act, No. 2 of 2025
        Certified on 2nd February 2025
        """
    )
    with SessionLocal() as db:
        act_row = db.get(LegalAct, act["id"])
        assert act_row is not None
        Path(act_row.stored_file_path).write_bytes(replacement_pdf)

    second_process = client.post(
        f"/api/v1/acts/{act['id']}/process",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert second_process.status_code == 200
    job = second_process.json()
    assert job["status"] == "COMPLETED"
    assert "title" in job["summary_json"]["metadata"]["preserved_fields"]
    assert job["summary_json"]["metadata"]["extracted"]["act_number"] == "2"

    detail = client.get(
        f"/api/v1/acts/{act['id']}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    data = detail.json()
    assert data["title"] == "Admin Reviewed Title"
    assert data["act_number"] == "99"
    assert data["year"] == 1999
    assert data["category"] == "Reviewed"
    assert data["certification_date"] == "1999-02-03"
