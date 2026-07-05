from uuid import uuid4

from app.core.roles import RelationshipType, VerificationStatus
from app.db.session import SessionLocal
from app.models.act_section import ActSection
from app.models.legal_act import LegalAct
from app.models.legal_reference import LegalReference
from app.services.text_cleaner import normalize_for_search


def _create_reference() -> str:
    return _create_reference_fixture()["reference_id"]


def _sha() -> str:
    return uuid4().hex.ljust(64, "0")[:64]


def _create_reference_fixture() -> dict[str, str]:
    with SessionLocal() as db:
        act = LegalAct(
            title="Reference Route Act",
            normalized_title=normalize_for_search("Reference Route Act"),
            source_file_name="references.pdf",
            stored_file_path="references.pdf",
            file_sha256=_sha(),
        )
        db.add(act)
        db.flush()
        section = ActSection(
            act_id=act.id,
            section_number="1",
            section_path="1",
            heading="Amendment",
            text="Section 9 is hereby amended.",
            normalized_text=normalize_for_search("Section 9 is hereby amended."),
            sort_order=0,
            verification_status=VerificationStatus.PENDING,
        )
        db.add(section)
        db.flush()
        target_act = LegalAct(
            title="Target Act",
            normalized_title=normalize_for_search("Target Act"),
            act_number="2",
            year=2020,
            source_file_name="target.pdf",
            stored_file_path="target.pdf",
            file_sha256=_sha(),
        )
        db.add(target_act)
        db.flush()
        target_section = ActSection(
            act_id=target_act.id,
            section_number="9",
            section_path="9",
            heading="Target section",
            text="Section 9 target.",
            normalized_text=normalize_for_search("Section 9 target."),
            sort_order=0,
            verification_status=VerificationStatus.VERIFIED,
        )
        db.add(target_section)
        db.flush()
        reference = LegalReference(
            source_act_id=act.id,
            source_section_id=section.id,
            raw_reference_text="Section 9",
            context_snippet="Section 9 is hereby amended.",
            relationship_type=RelationshipType.AMENDS,
            target_section_number="9",
            confidence_score=0.9,
            verification_status=VerificationStatus.PENDING,
        )
        db.add(reference)
        db.commit()
        return {
            "act_id": act.id,
            "section_id": section.id,
            "reference_id": reference.id,
            "target_act_id": target_act.id,
            "target_section_id": target_section.id,
        }


def test_admin_can_update_verify_and_reject_reference(client, admin_token):
    reference_id = _create_reference()

    update = client.patch(
        f"/api/v1/references/{reference_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"notes": "Reviewed by Admin", "relationship_type": "SUBSTITUTES"},
    )
    assert update.status_code == 200
    assert update.json()["notes"] == "Reviewed by Admin"
    assert update.json()["relationship_type"] == "SUBSTITUTES"

    verify = client.post(
        f"/api/v1/references/{reference_id}/verify",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert verify.status_code == 200
    assert verify.json()["verification_status"] == "VERIFIED"

    reject = client.post(
        f"/api/v1/references/{reference_id}/reject",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert reject.status_code == 200
    assert reject.json()["verification_status"] == "REJECTED"


def test_lawyer_and_general_user_cannot_verify_or_reject_reference(
    client, lawyer_token, user_token
):
    reference_id = _create_reference()

    for token in (lawyer_token, user_token):
        verify = client.post(
            f"/api/v1/references/{reference_id}/verify",
            headers={"Authorization": f"Bearer {token}"},
        )
        reject = client.post(
            f"/api/v1/references/{reference_id}/reject",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert verify.status_code == 403
        assert reject.status_code == 403


def test_admin_can_edit_reference_correction_fields(client, admin_token):
    fixture = _create_reference_fixture()

    response = client.patch(
        f"/api/v1/references/{fixture['reference_id']}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "raw_reference_text": "Corrected reference",
            "context_snippet": "Corrected context.",
            "relationship_type": "REPEALS",
            "target_act_title_raw": "Target Act",
            "target_act_number": "2",
            "target_act_year": 2020,
            "target_section_number": "9",
            "target_section_path": "9",
            "target_act_id": fixture["target_act_id"],
            "target_section_id": fixture["target_section_id"],
            "confidence_score": 0.8,
            "verification_status": "NEEDS_REVIEW",
            "notes": "Manual correction",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["raw_reference_text"] == "Corrected reference"
    assert data["relationship_type"] == "REPEALS"
    assert data["target_act_id"] == fixture["target_act_id"]
    assert data["target_section_id"] == fixture["target_section_id"]
    assert data["confidence_score"] == 0.8
    assert data["verification_status"] == "NEEDS_REVIEW"


def test_admin_can_manually_create_reference(client, admin_token):
    fixture = _create_reference_fixture()

    response = client.post(
        "/api/v1/references",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "source_act_id": fixture["act_id"],
            "source_section_id": fixture["section_id"],
            "raw_reference_text": "Manual reference",
            "context_snippet": "Manual reference noted by Admin.",
            "relationship_type": "REFERS_TO",
            "target_act_title_raw": "Target Act",
            "target_act_id": fixture["target_act_id"],
            "target_section_id": fixture["target_section_id"],
            "confidence_score": 0.7,
            "verification_status": "VERIFIED",
            "notes": "Created during Admin review",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["raw_reference_text"] == "Manual reference"
    assert data["extraction_method"] == "MANUAL"
    assert data["verification_status"] == "VERIFIED"
    assert data["verified_by_user_id"] is not None


def test_admin_can_link_and_clear_reference_mapping(client, admin_token):
    fixture = _create_reference_fixture()

    link = client.post(
        f"/api/v1/references/{fixture['reference_id']}/link-target",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "target_act_id": fixture["target_act_id"],
            "target_section_id": fixture["target_section_id"],
            "notes": "Linked during review",
        },
    )
    clear = client.post(
        f"/api/v1/references/{fixture['reference_id']}/link-target",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"target_act_id": None, "target_section_id": None, "notes": "Cleared mapping"},
    )

    assert link.status_code == 200
    assert link.json()["target_act_id"] == fixture["target_act_id"]
    assert link.json()["verification_status"] == "VERIFIED"
    assert clear.status_code == 200
    assert clear.json()["target_act_id"] is None
    assert clear.json()["target_section_id"] is None
    assert clear.json()["verification_status"] == "NEEDS_REVIEW"


def test_target_section_must_belong_to_target_act(client, admin_token):
    fixture = _create_reference_fixture()
    with SessionLocal() as db:
        other_act = LegalAct(
            title="Other Target Act",
            normalized_title=normalize_for_search("Other Target Act"),
            source_file_name="other.pdf",
            stored_file_path="other.pdf",
            file_sha256=_sha(),
        )
        db.add(other_act)
        db.commit()
        other_act_id = other_act.id

    response = client.post(
        f"/api/v1/references/{fixture['reference_id']}/link-target",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "target_act_id": other_act_id,
            "target_section_id": fixture["target_section_id"],
        },
    )

    assert response.status_code == 400


def test_lawyer_and_general_user_cannot_update_reference(client, lawyer_token, user_token):
    reference_id = _create_reference()

    lawyer_response = client.patch(
        f"/api/v1/references/{reference_id}",
        headers={"Authorization": f"Bearer {lawyer_token}"},
        json={"notes": "Lawyer edit"},
    )
    user_response = client.patch(
        f"/api/v1/references/{reference_id}",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"notes": "User edit"},
    )

    assert lawyer_response.status_code == 403
    assert user_response.status_code == 403


def test_general_user_only_sees_verified_references(client, user_token):
    fixture = _create_reference_fixture()
    with SessionLocal() as db:
        verified = LegalReference(
            source_act_id=fixture["act_id"],
            source_section_id=fixture["section_id"],
            raw_reference_text="Verified reference",
            context_snippet="Verified reference context.",
            relationship_type=RelationshipType.REFERS_TO,
            target_act_id=fixture["target_act_id"],
            target_section_id=fixture["target_section_id"],
            confidence_score=0.8,
            verification_status=VerificationStatus.VERIFIED,
        )
        unresolved_verified = LegalReference(
            source_act_id=fixture["act_id"],
            source_section_id=fixture["section_id"],
            raw_reference_text="Verified but unresolved reference",
            context_snippet="Verified but unresolved reference context.",
            relationship_type=RelationshipType.REFERS_TO,
            target_act_title_raw="Unresolved Target Act",
            confidence_score=0.7,
            verification_status=VerificationStatus.VERIFIED,
        )
        db.add_all([verified, unresolved_verified])
        db.commit()
        verified_id = verified.id
        unresolved_verified_id = unresolved_verified.id

    list_response = client.get(
        f"/api/v1/acts/{fixture['act_id']}/references",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    pending_detail = client.get(
        f"/api/v1/references/{fixture['reference_id']}",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    verified_detail = client.get(
        f"/api/v1/references/{verified_id}",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    unresolved_detail = client.get(
        f"/api/v1/references/{unresolved_verified_id}",
        headers={"Authorization": f"Bearer {user_token}"},
    )

    assert list_response.status_code == 200
    assert [reference["id"] for reference in list_response.json()] == [verified_id]
    assert pending_detail.status_code == 404
    assert verified_detail.status_code == 200
    assert unresolved_detail.status_code == 404


def test_verification_summary_counts_are_correct(client, admin_token, lawyer_token):
    fixture = _create_reference_fixture()
    with SessionLocal() as db:
        db.add_all(
            [
                ActSection(
                    act_id=fixture["act_id"],
                    section_number="2",
                    section_path="2",
                    heading="Needs review",
                    text="Needs review.",
                    normalized_text=normalize_for_search("Needs review."),
                    sort_order=1,
                    verification_status=VerificationStatus.NEEDS_REVIEW,
                ),
                ActSection(
                    act_id=fixture["act_id"],
                    section_number="3",
                    section_path="3",
                    heading="Verified",
                    text="Verified.",
                    normalized_text=normalize_for_search("Verified."),
                    sort_order=2,
                    verification_status=VerificationStatus.VERIFIED,
                ),
                ActSection(
                    act_id=fixture["act_id"],
                    section_number="4",
                    section_path="4",
                    heading="Rejected",
                    text="Rejected.",
                    normalized_text=normalize_for_search("Rejected."),
                    sort_order=3,
                    verification_status=VerificationStatus.REJECTED,
                ),
                LegalReference(
                    source_act_id=fixture["act_id"],
                    raw_reference_text="Needs review",
                    context_snippet="Needs review.",
                    relationship_type=RelationshipType.REFERS_TO,
                    confidence_score=0.4,
                    verification_status=VerificationStatus.NEEDS_REVIEW,
                ),
                LegalReference(
                    source_act_id=fixture["act_id"],
                    raw_reference_text="Verified mapped",
                    context_snippet="Verified mapped.",
                    relationship_type=RelationshipType.REFERS_TO,
                    target_act_id=fixture["target_act_id"],
                    confidence_score=0.9,
                    verification_status=VerificationStatus.VERIFIED,
                ),
                LegalReference(
                    source_act_id=fixture["act_id"],
                    raw_reference_text="Rejected",
                    context_snippet="Rejected.",
                    relationship_type=RelationshipType.REFERS_TO,
                    confidence_score=0.2,
                    verification_status=VerificationStatus.REJECTED,
                ),
            ]
        )
        db.commit()

    response = client.get(
        f"/api/v1/acts/{fixture['act_id']}/verification-summary",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    blocked = client.get(
        f"/api/v1/acts/{fixture['act_id']}/verification-summary",
        headers={"Authorization": f"Bearer {lawyer_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["pending_sections"] == 1
    assert data["needs_review_sections"] == 1
    assert data["verified_sections"] == 1
    assert data["rejected_sections"] == 1
    assert data["pending_references"] == 1
    assert data["needs_review_references"] == 1
    assert data["verified_references"] == 1
    assert data["rejected_references"] == 1
    assert data["mapped_references"] == 1
    assert data["unresolved_references"] == 3
    assert blocked.status_code == 403
