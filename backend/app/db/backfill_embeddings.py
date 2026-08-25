"""Idempotent embedding backfill for processed Act sections."""

from app.db.session import SessionLocal
from app.models.act_section import ActSection
from app.services.embedding_service import embed_text


def backfill_embeddings() -> int:
    updated = 0
    with SessionLocal() as db:
        sections = db.query(ActSection).filter(ActSection.embedding.is_(None)).all()
        for section in sections:
            section.embedding = embed_text(section.text or section.heading or "")
            updated += 1
        db.commit()
    return updated


if __name__ == "__main__":
    print(backfill_embeddings())
