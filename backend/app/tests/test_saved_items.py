from uuid import uuid4

from app.core.roles import RelationshipType, VerificationStatus
from app.db.session import SessionLocal
from app.models.act_section import ActSection
from app.models.legal_act import LegalAct
from app.models.legal_reference import LegalReference
from app.services.text_cleaner import normalize_for_search


def _sha() -> str:
    return uuid4().hex.ljust(64, "0")[:64]


def _create_saved_item_fixture() -> dict[str, str]:
    with SessionLocal() as db:
        act = LegalAct(
            title="Workspace Research Act",
            normalized_title=normalize_for_search("Workspace Research Act"),
            act_number="12",
            year=2026,
            category="Research",
            source_file_name="workspace.pdf",
            stored_file_path="workspace.pdf",
            file_sha256=_sha(),
        )
        target_act = LegalAct(
            title="Mapped Target Act",
            normalized_title=normalize_for_search("Mapped Target Act"),
            act_number="2",
            year=2020,
            source_file_name="target.pdf",
            stored_file_path="target.pdf",
            file_sha256=_sha(),
        )
        db.add_all([act, target_act])
        db.flush()
        section = ActSection(
            act_id=act.id,
            section_number="5",
            section_path="5",
            heading="Saved section heading",
            text="Section 5 text.",
            normalized_text=normalize_for_search("Section 5 text."),
            sort_order=1,
            verification_status=VerificationStatus.VERIFIED,
        )
        db.add(section)
        db.flush()
        reference = LegalReference(
            source_act_id=act.id,
            source_section_id=section.id,
            raw_reference_text="Section 9 of the Mapped Target Act is amended",
            context_snippet="Section 9 of the Mapped Target Act is amended.",
            relationship_type=RelationshipType.AMENDS,
            target_act_title_raw="Mapped Target Act",
            target_act_number="2",
            target_act_year=2020,
            target_act_id=target_act.id,
            target_section_number="9",
            confidence_score=0.9,
            verification_status=VerificationStatus.VERIFIED,
        )
        db.add(reference)
        db.commit()
        return {
            "act_id": act.id,
            "section_id": section.id,
            "reference_id": reference.id,
            "target_act_id": target_act.id,
        }


def test_lawyer_can_save_act_section_reference_and_list_enriched(client, lawyer_token):
    fixture = _create_saved_item_fixture()

    for payload in (
        {"item_type": "ACT", "act_id": fixture["act_id"], "note": "Act note"},
        {"item_type": "SECTION", "section_id": fixture["section_id"], "note": "Section note"},
        {
            "item_type": "REFERENCE",
            "reference_id": fixture["reference_id"],
            "note": "Reference note",
        },
    ):
        response = client.post(
            "/api/v1/saved-items",
            headers={"Authorization": f"Bearer {lawyer_token}"},
            json=payload,
        )
        assert response.status_code == 201

    response = client.get(
        "/api/v1/saved-items",
        headers={"Authorization": f"Bearer {lawyer_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total_results"] == 3
    assert data["counts_by_type"] == {"ACT": 1, "SECTION": 1, "REFERENCE": 1}
    assert {item["item_type"] for item in data["items"]} == {"ACT", "SECTION", "REFERENCE"}
    reference_item = next(item for item in data["items"] if item["item_type"] == "REFERENCE")
    assert reference_item["relationship_type"] == "AMENDS"
    assert reference_item["mapped"] is True
    assert reference_item["verification_status"] == "VERIFIED"
    assert reference_item["target_act_title"] == "Mapped Target Act"


def test_duplicate_saved_item_is_prevented(client, lawyer_token):
    fixture = _create_saved_item_fixture()
    payload = {"item_type": "ACT", "act_id": fixture["act_id"]}

    first = client.post(
        "/api/v1/saved-items",
        headers={"Authorization": f"Bearer {lawyer_token}"},
        json=payload,
    )
    second = client.post(
        "/api/v1/saved-items",
        headers={"Authorization": f"Bearer {lawyer_token}"},
        json=payload,
    )

    assert first.status_code == 201
    assert second.status_code == 409


def test_saved_item_target_must_exist(client, lawyer_token):
    response = client.post(
        "/api/v1/saved-items",
        headers={"Authorization": f"Bearer {lawyer_token}"},
        json={"item_type": "SECTION", "section_id": str(uuid4())},
    )

    assert response.status_code == 404


def test_lawyer_can_unsave_own_item_and_cannot_manage_another_users_item(
    client, lawyer_token, admin_token
):
    fixture = _create_saved_item_fixture()
    create = client.post(
        "/api/v1/saved-items",
        headers={"Authorization": f"Bearer {lawyer_token}"},
        json={"item_type": "SECTION", "section_id": fixture["section_id"], "note": "Initial"},
    )
    item_id = create.json()["id"]

    blocked_update = client.patch(
        f"/api/v1/saved-items/{item_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"note": "Admin cannot edit another workspace"},
    )
    update = client.patch(
        f"/api/v1/saved-items/{item_id}",
        headers={"Authorization": f"Bearer {lawyer_token}"},
        json={"note": "Updated note"},
    )
    blocked_delete = client.delete(
        f"/api/v1/saved-items/{item_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    delete = client.delete(
        f"/api/v1/saved-items/{item_id}",
        headers={"Authorization": f"Bearer {lawyer_token}"},
    )

    assert blocked_update.status_code == 404
    assert update.status_code == 200
    assert update.json()["note"] == "Updated note"
    assert blocked_delete.status_code == 404
    assert delete.status_code == 200


def test_general_user_cannot_access_saved_items(client, user_token):
    response = client.post(
        "/api/v1/saved-items",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"item_type": "ACT", "act_id": str(uuid4())},
    )

    assert response.status_code == 403


def test_lawyer_cannot_use_admin_verification_endpoint(client, lawyer_token):
    fixture = _create_saved_item_fixture()

    response = client.post(
        f"/api/v1/sections/{fixture['section_id']}/verify",
        headers={"Authorization": f"Bearer {lawyer_token}"},
    )

    assert response.status_code == 403


def test_saved_item_filters_and_pagination(client, lawyer_token):
    fixture = _create_saved_item_fixture()
    for payload in (
        {"item_type": "ACT", "act_id": fixture["act_id"]},
        {"item_type": "SECTION", "section_id": fixture["section_id"]},
        {"item_type": "REFERENCE", "reference_id": fixture["reference_id"]},
    ):
        client.post(
            "/api/v1/saved-items",
            headers={"Authorization": f"Bearer {lawyer_token}"},
            json=payload,
        )

    section_filter = client.get(
        "/api/v1/saved-items",
        headers={"Authorization": f"Bearer {lawyer_token}"},
        params={"item_type": "SECTION", "verification_status": "VERIFIED"},
    )
    reference_filter = client.get(
        "/api/v1/saved-items",
        headers={"Authorization": f"Bearer {lawyer_token}"},
        params={"relationship_type": "AMENDS", "mapped_status": "mapped"},
    )
    paged = client.get(
        "/api/v1/saved-items",
        headers={"Authorization": f"Bearer {lawyer_token}"},
        params={"limit": 1, "offset": 1},
    )

    assert section_filter.status_code == 200
    assert [item["item_type"] for item in section_filter.json()["items"]] == ["SECTION"]
    assert reference_filter.status_code == 200
    assert [item["reference_id"] for item in reference_filter.json()["items"]] == [
        fixture["reference_id"]
    ]
    assert paged.status_code == 200
    assert paged.json()["limit"] == 1
    assert paged.json()["offset"] == 1
    assert len(paged.json()["items"]) == 1


def test_saved_item_exports_include_disclaimer_and_research_fields(client, lawyer_token):
    fixture = _create_saved_item_fixture()
    client.post(
        "/api/v1/saved-items",
        headers={"Authorization": f"Bearer {lawyer_token}"},
        json={
            "item_type": "REFERENCE",
            "reference_id": fixture["reference_id"],
            "note": "Export note",
        },
    )

    csv_response = client.get(
        "/api/v1/exports/saved-items.csv",
        headers={"Authorization": f"Bearer {lawyer_token}"},
    )
    md_response = client.get(
        "/api/v1/exports/saved-items.md",
        headers={"Authorization": f"Bearer {lawyer_token}"},
    )

    assert csv_response.status_code == 200
    assert "does not provide legal advice" in csv_response.text
    assert "relationship_type" in csv_response.text
    assert "mapped" in csv_response.text
    assert "Export note" in csv_response.text
    assert md_response.status_code == 200
    assert "does not provide legal advice" in md_response.text
    assert "Mapped Target Act" in md_response.text
    assert "Export note" in md_response.text


def test_csv_export_neutralizes_formula_injection_in_note(client, lawyer_token):
    import csv
    import io

    fixture = _create_saved_item_fixture()
    malicious_note = '=HYPERLINK("https://evil.example","click me")'
    create = client.post(
        "/api/v1/saved-items",
        headers={"Authorization": f"Bearer {lawyer_token}"},
        json={
            "item_type": "REFERENCE",
            "reference_id": fixture["reference_id"],
            "note": malicious_note,
        },
    )
    assert create.status_code == 201

    csv_response = client.get(
        "/api/v1/exports/saved-items.csv",
        headers={"Authorization": f"Bearer {lawyer_token}"},
    )

    assert csv_response.status_code == 200
    rows = list(csv.reader(io.StringIO(csv_response.text)))
    note_cell = rows[-1][-1]
    assert note_cell == f"'{malicious_note}"
    assert not note_cell.startswith("=")
