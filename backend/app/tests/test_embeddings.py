from app.core.roles import EmbeddingStatus, ProcessingStatus, VerificationStatus
from app.db.session import SessionLocal
from app.models.act_section import ActSection
from app.models.legal_act import LegalAct


def test_embedding_status_requires_admin(client, lawyer_token):
    assert client.get("/api/v1/embeddings/status").status_code == 401
    response = client.get(
        "/api/v1/embeddings/status",
        headers={"Authorization": f"Bearer {lawyer_token}"},
    )
    assert response.status_code == 403


def test_embedding_status_reports_counts_and_privacy_safe_failure_samples(
    client, admin_token
):
    with SessionLocal() as db:
        act = LegalAct(
            title="Status Act",
            normalized_title="status act",
            source_file_name="status.pdf",
            stored_file_path="status.pdf",
            file_sha256="b" * 64,
            processing_status=ProcessingStatus.VERIFIED,
        )
        db.add(act)
        db.flush()
        for index, status in enumerate(
            [
                EmbeddingStatus.READY,
                EmbeddingStatus.PENDING,
                EmbeddingStatus.STALE,
                EmbeddingStatus.FAILED,
            ],
            start=1,
        ):
            db.add(
                ActSection(
                    act_id=act.id,
                    section_number=str(index),
                    section_path=str(index),
                    text=f"private legal text {index}",
                    normalized_text=f"private legal text {index}",
                    sort_order=index,
                    verification_status=VerificationStatus.VERIFIED,
                    embedding_status=status,
                    embedding_error=(
                        "provider timeout" if status == EmbeddingStatus.FAILED else None
                    ),
                )
            )
        db.commit()

    response = client.get(
        "/api/v1/embeddings/status",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["counts"] == {
        "total": 4,
        "ready": 1,
        "pending": 1,
        "stale": 1,
        "failed": 1,
    }
    assert payload["failure_samples"][0]["error"] == "provider timeout"
    assert "private legal text" not in response.text
    assert payload["remediation_command"].startswith("python -m app.db.backfill_embeddings")
