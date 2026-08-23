from uuid import uuid4

from app.core.roles import ProcessingStatus, SectionType, VerificationStatus
from app.db.session import SessionLocal
from app.models.act_section import ActSection
from app.models.legal_act import LegalAct
from app.models.reading_history import ReadingHistoryItem
from app.services.text_cleaner import normalize_for_search


def _create_act_and_section() -> tuple[str, str]:
    with SessionLocal() as db:
        act = LegalAct(
            title="Reading History Act",
            normalized_title=normalize_for_search("Reading History Act"),
            source_file_name="history.pdf",
            stored_file_path="history.pdf",
            file_sha256=uuid4().hex.ljust(64, "1")[:64],
            processing_status=ProcessingStatus.VERIFIED,
        )
        db.add(act)
        db.flush()
        section = ActSection(
            act_id=act.id,
            section_number="12",
            section_path="12",
            heading="Obligations of controllers",
            section_type=SectionType.SECTION,
            text="A controller shall implement appropriate measures.",
            normalized_text=normalize_for_search("A controller shall implement appropriate measures."),
            sort_order=0,
            verification_status=VerificationStatus.VERIFIED,
        )
        db.add(section)
        db.commit()
        return act.id, section.id


def test_record_and_list_reading_history(client, user_token):
    act_id, section_id = _create_act_and_section()
    headers = {"Authorization": f"Bearer {user_token}"}

    create_response = client.post(
        "/api/v1/reading-history",
        json={"item_type": "SECTION", "act_id": act_id, "section_id": section_id},
        headers=headers,
    )
    assert create_response.status_code == 201
    payload = create_response.json()
    assert payload["act_title"] == "Reading History Act"
    assert payload["section_number"] == "12"
    assert payload["href"] == f"/sections/{section_id}"

    list_response = client.get("/api/v1/reading-history", headers=headers)
    assert list_response.status_code == 200
    items = list_response.json()["items"]
    assert len(items) == 1
    assert items[0]["item_type"] == "SECTION"

    client.post(
        "/api/v1/reading-history",
        json={"item_type": "SECTION", "act_id": act_id, "section_id": section_id},
        headers=headers,
    )
    with SessionLocal() as db:
        assert db.query(ReadingHistoryItem).count() == 1


def test_reading_history_requires_auth(client):
    act_id, _ = _create_act_and_section()
    response = client.get("/api/v1/reading-history")
    assert response.status_code == 401

    response = client.post(
        "/api/v1/reading-history",
        json={"item_type": "ACT", "act_id": act_id},
    )
    assert response.status_code == 401


def test_browse_acts_returns_verified_counts(client, user_token):
    act_id, section_id = _create_act_and_section()
    headers = {"Authorization": f"Bearer {user_token}"}

    response = client.get("/api/v1/acts/browse", headers=headers)
    assert response.status_code == 200
    rows = response.json()
    match = next(item for item in rows if item["id"] == act_id)
    assert match["verified_section_count"] == 1
    assert match["verified_reference_count"] == 0
    assert section_id
