from uuid import uuid4

from app.core.roles import ProcessingStatus, UserRole, VerificationStatus
from app.db.session import SessionLocal
from app.models.act_section import ActSection
from app.models.legal_act import LegalAct
from app.services.embedding_service import embed_text
from app.services.search_service import search
from app.services.text_cleaner import normalize_for_search


def test_search_paginates_beyond_two_hundred_fifty_acts(client, admin_token):
    with SessionLocal() as db:
        for index in range(260):
            title = f"Pagination Probe Act {index}"
            db.add(
                LegalAct(
                    title=title,
                    normalized_title=normalize_for_search(title),
                    act_number=str(index),
                    year=2000,
                    category="Probe",
                    source_file_name=f"probe-{index}.pdf",
                    stored_file_path=f"probe-{index}.pdf",
                    file_sha256=uuid4().hex.ljust(64, "0")[:64],
                    raw_text="Pagination probe body",
                    processing_status=ProcessingStatus.VERIFIED,
                )
            )
        db.commit()

    first = client.get(
        "/api/v1/search",
        params={"q": "Pagination Probe", "limit": 25, "offset": 0},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    deep = client.get(
        "/api/v1/search",
        params={"q": "Pagination Probe", "limit": 25, "offset": 250},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert first.status_code == 200
    assert deep.status_code == 200
    assert first.json()["total_results"] >= 260
    assert len(deep.json()["results"]) >= 1
    first_ids = {item["id"] for item in first.json()["results"]}
    deep_ids = {item["id"] for item in deep.json()["results"]}
    assert first_ids.isdisjoint(deep_ids)


def test_semantic_search_disabled_returns_400(client, user_token):
    response = client.get(
        "/api/v1/search",
        params={"q": "jurisdiction", "search_mode": "semantic"},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert response.status_code == 400
    assert "not enabled" in response.json()["detail"].lower()


def test_semantic_search_hides_unverified_sections_from_general_users(monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "semantic_search_enabled", True)
    with SessionLocal() as db:
        act = LegalAct(
            title="Embedding Visibility Act",
            normalized_title=normalize_for_search("Embedding Visibility Act"),
            source_file_name="embed.pdf",
            stored_file_path="embed.pdf",
            file_sha256="c" * 64,
            processing_status=ProcessingStatus.VERIFIED,
            raw_text="High Court jurisdiction over civil matters.",
        )
        db.add(act)
        db.flush()
        verified = ActSection(
            act_id=act.id,
            section_number="1",
            section_path="1",
            heading="Verified jurisdiction",
            text="High Court jurisdiction over civil matters.",
            normalized_text=normalize_for_search("High Court jurisdiction over civil matters."),
            sort_order=1,
            verification_status=VerificationStatus.VERIFIED,
            embedding=embed_text("High Court jurisdiction over civil matters."),
        )
        pending = ActSection(
            act_id=act.id,
            section_number="2",
            section_path="2",
            heading="Pending jurisdiction",
            text="High Court jurisdiction draft notes.",
            normalized_text=normalize_for_search("High Court jurisdiction draft notes."),
            sort_order=2,
            verification_status=VerificationStatus.PENDING,
            embedding=embed_text("High Court jurisdiction draft notes."),
        )
        db.add_all([verified, pending])
        db.commit()

        public = search(
            db,
            query="High Court jurisdiction",
            role=UserRole.GENERAL_USER,
            search_mode="semantic",
        )
        lawyer = search(
            db,
            query="High Court jurisdiction",
            role=UserRole.LAWYER,
            search_mode="semantic",
        )
        public_section_ids = {item.section_id for item in public.results}
        lawyer_section_ids = {item.section_id for item in lawyer.results}
        assert verified.id in public_section_ids
        assert pending.id not in public_section_ids
        assert pending.id in lawyer_section_ids
