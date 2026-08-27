from datetime import UTC, datetime
from uuid import uuid4

from app.core.roles import EmbeddingStatus, ProcessingStatus
from app.db.session import SessionLocal
from app.db.types import SECTION_EMBEDDING_DIMENSION
from app.models.act_section import ActSection
from app.models.legal_act import LegalAct
from app.services.text_cleaner import normalize_for_search


def _sample_embedding() -> list[float]:
    return [
        float(index) / SECTION_EMBEDDING_DIMENSION
        for index in range(SECTION_EMBEDDING_DIMENSION)
    ]


def test_act_section_embedding_round_trips_on_sqlite():
    vector = _sample_embedding()
    embedded_at = datetime(2026, 8, 28, 12, 0, 0, tzinfo=UTC).replace(tzinfo=None)

    with SessionLocal() as db:
        act = LegalAct(
            title="Embedding Round Trip Act",
            normalized_title=normalize_for_search("Embedding Round Trip Act"),
            source_file_name="embed-round-trip.pdf",
            stored_file_path="embed-round-trip.pdf",
            file_sha256=uuid4().hex.ljust(64, "0")[:64],
            processing_status=ProcessingStatus.VERIFIED,
            raw_text="Section embedding round-trip probe.",
        )
        db.add(act)
        db.flush()

        section = ActSection(
            act_id=act.id,
            section_number="1",
            section_path="1",
            heading="Embedding probe",
            text="Section embedding round-trip probe.",
            normalized_text=normalize_for_search("Section embedding round-trip probe."),
            sort_order=1,
            embedding=vector,
            embedding_provider="sentence-transformers",
            embedding_model="sentence-transformers/all-MiniLM-L6-v2",
            embedding_dimension=SECTION_EMBEDDING_DIMENSION,
            embedding_source_hash="a" * 64,
            embedding_status=EmbeddingStatus.READY,
            embedded_at=embedded_at,
        )
        db.add(section)
        db.commit()
        section_id = section.id

    with SessionLocal() as db:
        loaded = db.get(ActSection, section_id)
        assert loaded is not None
        assert loaded.embedding == vector
        assert len(loaded.embedding) == SECTION_EMBEDDING_DIMENSION
        assert loaded.embedding_provider == "sentence-transformers"
        assert loaded.embedding_model == "sentence-transformers/all-MiniLM-L6-v2"
        assert loaded.embedding_dimension == SECTION_EMBEDDING_DIMENSION
        assert loaded.embedding_source_hash == "a" * 64
        assert loaded.embedding_status == EmbeddingStatus.READY
        assert loaded.embedded_at == embedded_at
        assert loaded.embedding_error is None


def test_act_section_embedding_status_defaults_to_pending():
    with SessionLocal() as db:
        act = LegalAct(
            title="Embedding Default Status Act",
            normalized_title=normalize_for_search("Embedding Default Status Act"),
            source_file_name="embed-default.pdf",
            stored_file_path="embed-default.pdf",
            file_sha256=uuid4().hex.ljust(64, "1")[:64],
            processing_status=ProcessingStatus.VERIFIED,
            raw_text="Default embedding status probe.",
        )
        db.add(act)
        db.flush()

        section = ActSection(
            act_id=act.id,
            section_number="1",
            section_path="1",
            heading="Default status probe",
            text="Default embedding status probe.",
            normalized_text=normalize_for_search("Default embedding status probe."),
            sort_order=1,
        )
        db.add(section)
        db.commit()
        section_id = section.id

    with SessionLocal() as db:
        loaded = db.get(ActSection, section_id)
        assert loaded is not None
        assert loaded.embedding_status == EmbeddingStatus.PENDING
        assert loaded.embedding is None
