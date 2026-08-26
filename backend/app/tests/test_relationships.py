from uuid import uuid4

from app.core.roles import RelationshipType, VerificationStatus
from app.db.session import SessionLocal
from app.models.act_section import ActSection
from app.models.legal_act import LegalAct
from app.models.legal_reference import LegalReference
from app.services.text_cleaner import normalize_for_search


def _sha() -> str:
    return uuid4().hex.ljust(64, "0")[:64]


def _create_relationship_fixture() -> dict[str, str]:
    with SessionLocal() as db:
        source_act = LegalAct(
            title="Source Relationship Act",
            normalized_title=normalize_for_search("Source Relationship Act"),
            source_file_name="source.pdf",
            stored_file_path="source.pdf",
            file_sha256=_sha(),
        )
        target_act = LegalAct(
            title="Target Relationship Act",
            normalized_title=normalize_for_search("Target Relationship Act"),
            source_file_name="target.pdf",
            stored_file_path="target.pdf",
            file_sha256=_sha(),
        )
        db.add_all([source_act, target_act])
        db.flush()
        source_section = ActSection(
            act_id=source_act.id,
            section_number="1",
            section_path="1",
            heading="Source section",
            text="Source section text.",
            normalized_text=normalize_for_search("Source section text."),
            sort_order=1,
            verification_status=VerificationStatus.VERIFIED,
        )
        target_section = ActSection(
            act_id=target_act.id,
            section_number="9",
            section_path="9",
            heading="Target section",
            text="Target section text.",
            normalized_text=normalize_for_search("Target section text."),
            sort_order=1,
            verification_status=VerificationStatus.VERIFIED,
        )
        db.add_all([source_section, target_section])
        db.flush()
        outgoing = LegalReference(
            source_act_id=source_act.id,
            source_section_id=source_section.id,
            raw_reference_text="Section 9 is amended",
            context_snippet="Section 9 of the target Act is amended.",
            relationship_type=RelationshipType.AMENDS,
            target_act_id=target_act.id,
            target_section_id=target_section.id,
            target_section_number="9",
            confidence_score=0.95,
            verification_status=VerificationStatus.VERIFIED,
        )
        incoming = LegalReference(
            source_act_id=target_act.id,
            source_section_id=target_section.id,
            raw_reference_text="Source Act section 1 is repealed",
            context_snippet="Source Act section 1 is repealed.",
            relationship_type=RelationshipType.REPEALS,
            target_act_id=source_act.id,
            target_section_id=source_section.id,
            target_section_number="1",
            confidence_score=0.9,
            verification_status=VerificationStatus.VERIFIED,
        )
        unresolved = LegalReference(
            source_act_id=source_act.id,
            source_section_id=source_section.id,
            raw_reference_text="Missing Act schedule is amended",
            context_snippet="The First Schedule of the Missing Act is amended.",
            relationship_type=RelationshipType.ADDS,
            target_act_title_raw="Missing Act",
            target_section_path="First Schedule",
            confidence_score=0.5,
            verification_status=VerificationStatus.NEEDS_REVIEW,
        )
        rejected = LegalReference(
            source_act_id=source_act.id,
            source_section_id=source_section.id,
            raw_reference_text="Rejected relationship",
            context_snippet="Rejected relationship context.",
            relationship_type=RelationshipType.SUBSTITUTES,
            confidence_score=0.2,
            verification_status=VerificationStatus.REJECTED,
        )
        pending = LegalReference(
            source_act_id=source_act.id,
            source_section_id=source_section.id,
            raw_reference_text="Pending relationship",
            context_snippet="Pending relationship context.",
            relationship_type=RelationshipType.CROSS_REFERENCE,
            confidence_score=0.3,
            verification_status=VerificationStatus.PENDING,
        )
        db.add_all([outgoing, incoming, unresolved, rejected, pending])
        db.commit()
        return {
            "source_act_id": source_act.id,
            "target_act_id": target_act.id,
            "source_section_id": source_section.id,
            "target_section_id": target_section.id,
            "outgoing_id": outgoing.id,
            "incoming_id": incoming.id,
            "unresolved_id": unresolved.id,
            "rejected_id": rejected.id,
            "pending_id": pending.id,
        }


def test_act_outgoing_relationships(client, admin_token):
    ids = _create_relationship_fixture()

    response = client.get(
        f"/api/v1/relationships/act/{ids['source_act_id']}",
        headers={"Authorization": f"Bearer {admin_token}"},
        params={"direction": "outgoing"},
    )

    assert response.status_code == 200
    relationship_ids = {row["id"] for row in response.json()["relationships"]}
    assert ids["outgoing_id"] in relationship_ids
    assert ids["incoming_id"] not in relationship_ids
    assert all(row["direction"] == "outgoing" for row in response.json()["relationships"])


def test_act_incoming_relationships(client, admin_token):
    ids = _create_relationship_fixture()

    response = client.get(
        f"/api/v1/relationships/act/{ids['source_act_id']}",
        headers={"Authorization": f"Bearer {admin_token}"},
        params={"direction": "incoming"},
    )

    assert response.status_code == 200
    relationship_ids = {row["id"] for row in response.json()["relationships"]}
    assert relationship_ids == {ids["incoming_id"]}
    assert response.json()["relationships"][0]["direction"] == "incoming"


def test_section_outgoing_and_incoming_relationships(client, admin_token):
    ids = _create_relationship_fixture()

    outgoing = client.get(
        f"/api/v1/relationships/section/{ids['source_section_id']}",
        headers={"Authorization": f"Bearer {admin_token}"},
        params={"direction": "outgoing"},
    )
    incoming = client.get(
        f"/api/v1/relationships/section/{ids['source_section_id']}",
        headers={"Authorization": f"Bearer {admin_token}"},
        params={"direction": "incoming"},
    )

    assert outgoing.status_code == 200
    assert ids["outgoing_id"] in {row["id"] for row in outgoing.json()["relationships"]}
    assert incoming.status_code == 200
    assert [row["id"] for row in incoming.json()["relationships"]] == [ids["incoming_id"]]


def test_relationship_filters(client, admin_token):
    ids = _create_relationship_fixture()

    by_type = client.get(
        f"/api/v1/relationships/act/{ids['source_act_id']}",
        headers={"Authorization": f"Bearer {admin_token}"},
        params={"relationship_type": "AMENDS"},
    )
    unresolved = client.get(
        f"/api/v1/relationships/act/{ids['source_act_id']}",
        headers={"Authorization": f"Bearer {admin_token}"},
        params={"mapped_status": "unresolved"},
    )

    assert by_type.status_code == 200
    assert [row["id"] for row in by_type.json()["relationships"]] == [ids["outgoing_id"]]
    assert unresolved.status_code == 200
    unresolved_rows = unresolved.json()["relationships"]
    assert ids["unresolved_id"] in {row["id"] for row in unresolved_rows}
    assert all(row["mapped"] is False for row in unresolved_rows)


def test_admin_sees_pending_rejected_and_unresolved(client, admin_token):
    ids = _create_relationship_fixture()

    response = client.get(
        f"/api/v1/relationships/act/{ids['source_act_id']}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    statuses = {row["verification_status"] for row in response.json()["relationships"]}
    assert {"PENDING", "REJECTED", "NEEDS_REVIEW", "VERIFIED"}.issubset(statuses)


def test_general_user_only_sees_verified_relationships(client, user_token):
    ids = _create_relationship_fixture()

    response = client.get(
        f"/api/v1/relationships/act/{ids['source_act_id']}",
        headers={"Authorization": f"Bearer {user_token}"},
    )

    assert response.status_code == 200
    rows = response.json()["relationships"]
    assert {row["id"] for row in rows} == {ids["outgoing_id"], ids["incoming_id"]}
    assert all(row["verification_status"] == "VERIFIED" for row in rows)


def test_general_user_does_not_see_verified_unresolved_relationships(client, user_token):
    ids = _create_relationship_fixture()
    with SessionLocal() as db:
        unresolved_verified = LegalReference(
            source_act_id=ids["source_act_id"],
            source_section_id=ids["source_section_id"],
            raw_reference_text="Verified unresolved relationship",
            context_snippet="Verified unresolved relationship context.",
            relationship_type=RelationshipType.REFERS_TO,
            target_act_title_raw="Unresolved Target Act",
            confidence_score=0.7,
            verification_status=VerificationStatus.VERIFIED,
        )
        db.add(unresolved_verified)
        db.commit()
        unresolved_verified_id = unresolved_verified.id

    response = client.get(
        f"/api/v1/relationships/act/{ids['source_act_id']}",
        headers={"Authorization": f"Bearer {user_token}"},
    )

    assert response.status_code == 200
    relationship_ids = {row["id"] for row in response.json()["relationships"]}
    assert unresolved_verified_id not in relationship_ids


def test_relationship_summary_counts(client, admin_token):
    ids = _create_relationship_fixture()

    response = client.get(
        f"/api/v1/relationships/act/{ids['source_act_id']}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    summary = response.json()["summary"]
    assert summary["outgoing_count"] == 4
    assert summary["incoming_count"] == 1
    assert summary["mapped_count"] == 2
    assert summary["unresolved_count"] == 3
    assert summary["by_relationship_type"]["AMENDS"] == 1
    assert summary["by_verification_status"]["VERIFIED"] == 2


def test_unresolved_target_details_do_not_create_fake_ids(client, admin_token):
    ids = _create_relationship_fixture()

    response = client.get(
        f"/api/v1/relationships/act/{ids['source_act_id']}",
        headers={"Authorization": f"Bearer {admin_token}"},
        params={"mapped_status": "unresolved", "relationship_type": "ADDS"},
    )

    assert response.status_code == 200
    row = response.json()["relationships"][0]
    assert row["id"] == ids["unresolved_id"]
    assert row["target_act_id"] is None
    assert row["target_section_id"] is None
    assert row["target_act_title_raw"] == "Missing Act"
    assert row["target_section_path"] == "First Schedule"


def test_relationship_graph_uses_mapped_act_edges_only(client, admin_token):
    ids = _create_relationship_fixture()
    with SessionLocal() as db:
        self_map = LegalReference(
            source_act_id=ids["source_act_id"],
            source_section_id=ids["source_section_id"],
            raw_reference_text="Section 1 of this Act",
            context_snippet="Section 1 of this Act applies.",
            relationship_type=RelationshipType.CROSS_REFERENCE,
            target_act_id=ids["source_act_id"],
            target_section_id=ids["source_section_id"],
            target_section_number="1",
            confidence_score=0.95,
            verification_status=VerificationStatus.VERIFIED,
        )
        db.add(self_map)
        db.commit()
        self_map_id = self_map.id

    response = client.get(
        "/api/v1/relationships/graph",
        headers={"Authorization": f"Bearer {admin_token}"},
        params={"act_id": ids["source_act_id"]},
    )

    assert response.status_code == 200
    data = response.json()
    assert {edge["id"] for edge in data["edges"]} == {ids["outgoing_id"], ids["incoming_id"]}
    assert self_map_id not in {edge["id"] for edge in data["edges"]}
    assert all(edge["source"] != edge["target"] for edge in data["edges"])
    assert data["summary"]["mapped_count"] == 2
    assert data["summary"]["unresolved_count"] == 3


def test_relationship_graph_edges_are_not_starved_by_newer_unresolved_rows(
    client, admin_token
):
    ids = _create_relationship_fixture()
    with SessionLocal() as db:
        db.add_all(
            [
                LegalReference(
                    source_act_id=ids["source_act_id"],
                    source_section_id=ids["source_section_id"],
                    raw_reference_text=f"Unresolved relationship {index}",
                    context_snippet=f"Unresolved relationship context {index}.",
                    relationship_type=RelationshipType.REFERS_TO,
                    target_act_title_raw=f"Missing Act {index}",
                    confidence_score=0.5,
                    verification_status=VerificationStatus.NEEDS_REVIEW,
                )
                for index in range(101)
            ]
        )
        db.commit()

    response = client.get(
        "/api/v1/relationships/graph",
        headers={"Authorization": f"Bearer {admin_token}"},
        params={"act_id": ids["source_act_id"]},
    )

    assert response.status_code == 200
    assert {edge["id"] for edge in response.json()["edges"]} == {
        ids["outgoing_id"],
        ids["incoming_id"],
    }
