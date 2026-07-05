from uuid import uuid4

from app.core.roles import SectionType, VerificationStatus
from app.db.session import SessionLocal
from app.models.act_section import ActSection
from app.models.legal_act import LegalAct
from app.services.text_cleaner import normalize_for_search


def _create_section() -> str:
    return _create_section_with_status(VerificationStatus.PENDING)[1]


def _create_section_with_status(status: VerificationStatus) -> tuple[str, str]:
    with SessionLocal() as db:
        act = LegalAct(
            title="Section Route Act",
            normalized_title=normalize_for_search("Section Route Act"),
            source_file_name="sections.pdf",
            stored_file_path="sections.pdf",
            file_sha256=uuid4().hex.ljust(64, "0")[:64],
        )
        db.add(act)
        db.flush()
        section = ActSection(
            act_id=act.id,
            section_number="1",
            section_path="1",
            heading="Short title",
            section_type=SectionType.SECTION,
            text="1. Short title. Original text.",
            normalized_text=normalize_for_search("1. Short title. Original text."),
            sort_order=0,
            verification_status=status,
        )
        db.add(section)
        db.commit()
        return act.id, section.id


def test_admin_can_update_and_verify_section(client, admin_token):
    section_id = _create_section()

    update = client.patch(
        f"/api/v1/sections/{section_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"text": "1. Short title. Updated reviewed text.", "heading": "Short title"},
    )
    assert update.status_code == 200
    assert update.json()["text"] == "1. Short title. Updated reviewed text."
    assert "updated reviewed" in update.json()["normalized_text"]

    verify = client.post(
        f"/api/v1/sections/{section_id}/verify",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert verify.status_code == 200
    assert verify.json()["verification_status"] == "VERIFIED"


def test_admin_can_reject_section(client, admin_token):
    section_id = _create_section()

    response = client.post(
        f"/api/v1/sections/{section_id}/reject",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    assert response.json()["verification_status"] == "REJECTED"


def test_admin_can_edit_section_correction_fields(client, admin_token):
    section_id = _create_section()

    response = client.patch(
        f"/api/v1/sections/{section_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "section_number": "S1",
            "section_path": "First Schedule",
            "heading": "Corrected schedule",
            "section_type": "SCHEDULE",
            "text": "First Schedule corrected text.",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["section_number"] == "S1"
    assert data["section_path"] == "First Schedule"
    assert data["heading"] == "Corrected schedule"
    assert data["section_type"] == "SCHEDULE"
    assert "corrected text" in data["normalized_text"]


def test_lawyer_and_general_user_cannot_update_section(
    client, lawyer_token, user_token
):
    section_id = _create_section()

    lawyer_response = client.patch(
        f"/api/v1/sections/{section_id}",
        headers={"Authorization": f"Bearer {lawyer_token}"},
        json={"text": "Lawyer edit"},
    )
    user_response = client.patch(
        f"/api/v1/sections/{section_id}",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"text": "User edit"},
    )

    assert lawyer_response.status_code == 403
    assert user_response.status_code == 403


def test_lawyer_and_general_user_cannot_verify_or_reject_section(
    client, lawyer_token, user_token
):
    section_id = _create_section()

    for token in (lawyer_token, user_token):
        verify = client.post(
            f"/api/v1/sections/{section_id}/verify",
            headers={"Authorization": f"Bearer {token}"},
        )
        reject = client.post(
            f"/api/v1/sections/{section_id}/reject",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert verify.status_code == 403
        assert reject.status_code == 403


def test_general_user_only_sees_verified_sections(client, user_token):
    act_id, pending_id = _create_section_with_status(VerificationStatus.PENDING)
    with SessionLocal() as db:
        verified = ActSection(
            act_id=act_id,
            section_number="2",
            section_path="2",
            heading="Verified",
            section_type=SectionType.SECTION,
            text="2. Verified section.",
            normalized_text=normalize_for_search("2. Verified section."),
            sort_order=1,
            verification_status=VerificationStatus.VERIFIED,
        )
        db.add(verified)
        db.commit()
        verified_id = verified.id

    list_response = client.get(
        f"/api/v1/acts/{act_id}/sections",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    pending_detail = client.get(
        f"/api/v1/sections/{pending_id}",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    verified_detail = client.get(
        f"/api/v1/sections/{verified_id}",
        headers={"Authorization": f"Bearer {user_token}"},
    )

    assert list_response.status_code == 200
    assert [section["id"] for section in list_response.json()] == [verified_id]
    assert pending_detail.status_code == 403
    assert verified_detail.status_code == 200
