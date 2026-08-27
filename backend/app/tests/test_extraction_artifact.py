import json
from datetime import datetime
from types import SimpleNamespace

import pytest

from app.services.extraction_artifact import (
    ARTIFACT_SCHEMA_VERSION,
    ArtifactPersistError,
    artifact_logical_key,
    artifact_sha256,
    build_extraction_payload,
    canonical_artifact_bytes,
    collect_artifact_pointers,
    delete_orphan_artifact,
    load_extraction_artifact_view,
    persist_extraction_artifact,
)
from app.services.pdf_parser.base import PAGE_SEPARATOR, ParsedPdf, structured_pages_from_texts
from app.services.pdf_parser.preparation import prepare_act_pages
from app.services.storage import LocalStorage


def _parsed_pages(page_texts: list[str]) -> ParsedPdf:
    return ParsedPdf(
        full_text=PAGE_SEPARATOR.join(page_texts),
        page_count=len(page_texts),
        page_texts=page_texts,
        parser_name="PYMUPDF",
        warnings=[],
        structured_document=structured_pages_from_texts(page_texts, extraction_method="native"),
    )


def test_canonical_artifact_bytes_are_stable_for_hashing():
    payload = {"b": 2, "a": 1}
    first = canonical_artifact_bytes(payload)
    second = canonical_artifact_bytes({"a": 1, "b": 2})

    assert first == second
    assert first == b'{"a":1,"b":2}'
    assert artifact_sha256(first) == artifact_sha256(second)


def test_artifact_logical_key_uses_schema_version():
    assert artifact_logical_key("act-1", "job-2") == (
        f"act-1/extractions/job-2.schema-v{ARTIFACT_SCHEMA_VERSION}.json"
    )


def test_build_extraction_payload_includes_processing_text_and_one_span_per_page():
    parsed = _parsed_pages(["1. Short title.\nBody.", ""])
    prepared = prepare_act_pages(parsed)
    act = SimpleNamespace(file_sha256="a" * 64)
    job = SimpleNamespace(id="job-1")

    payload = build_extraction_payload(
        parsed=parsed,
        prepared=prepared,
        act=act,
        job=job,
        warnings=["note"],
        created_at=datetime(2026, 8, 27, 12, 0, 0),
    )

    assert payload["processing_text"] == prepared.text
    assert payload["page_spans"] is not None
    assert len(payload["page_spans"]) == parsed.page_count
    assert payload["page_spans"][-1]["start"] == payload["page_spans"][-1]["end"]
    assert payload["pages"] is not None
    assert payload["provenance"]["processing_job_id"] == "job-1"


def test_build_extraction_payload_leaves_page_spans_null_without_physical_pages():
    parsed = ParsedPdf(
        full_text="1. Short title.\nBody.",
        page_count=65,
        page_texts=["1. Short title.\nBody."],
        parser_name="DOCLING",
        warnings=[],
    )
    prepared = prepare_act_pages(parsed)

    payload = build_extraction_payload(
        parsed=parsed,
        prepared=prepared,
        act=SimpleNamespace(file_sha256="b" * 64),
        job=SimpleNamespace(id="job-2"),
        warnings=[],
        created_at=datetime(2026, 8, 27, 12, 0, 0),
    )

    assert payload["pages"] is None
    assert payload["page_spans"] is None


def test_persist_extraction_artifact_returns_storage_pointer(tmp_path):
    storage = LocalStorage(tmp_path)
    payload = {"schema_version": "1", "processing_text": "text"}

    pointer, digest = persist_extraction_artifact(
        storage, logical_key="act/extractions/job.json", payload=payload
    )

    assert pointer == str(tmp_path / "act/extractions/job.json")
    assert digest == artifact_sha256(canonical_artifact_bytes(payload))
    assert json.loads(storage.read_artifact(pointer))["processing_text"] == "text"


def test_persist_deletes_orphan_when_read_back_fails(tmp_path):
    class ReadFailsStorage(LocalStorage):
        def read_artifact(self, stored_key: str) -> bytes:
            raise RuntimeError("read-back failed")

    storage = ReadFailsStorage(tmp_path)
    with pytest.raises(ArtifactPersistError, match="read-back failed"):
        persist_extraction_artifact(
            storage, logical_key="act/extractions/job.json", payload={"a": 1}
        )

    with pytest.raises(FileNotFoundError):
        LocalStorage(tmp_path).read_artifact(str(tmp_path / "act/extractions/job.json"))


def test_persist_records_cleanup_warning_when_hash_mismatch_delete_fails():
    class MismatchAndDeleteFails:
        def save_artifact(self, key: str, content: bytes, content_type: str) -> str:
            return "ptr"
        def read_artifact(self, stored_key: str) -> bytes:
            return b"not-the-original"
        def delete(self, stored_key: str) -> None:
            raise RuntimeError("cannot delete")

    with pytest.raises(ArtifactPersistError) as error:
        persist_extraction_artifact(
            MismatchAndDeleteFails(), logical_key="act/job.json", payload={"a": 1}
        )

    assert "hash mismatch" in str(error.value)
    assert error.value.cleanup_warning is not None
    assert "cannot delete" in error.value.cleanup_warning


def test_persist_hash_mismatch_deletes_orphan_without_cleanup_warning():
    class MismatchThenDeletes:
        def __init__(self):
            self.deleted = False

        def save_artifact(self, key: str, content: bytes, content_type: str) -> str:
            return "ptr"

        def read_artifact(self, stored_key: str) -> bytes:
            return b"not-the-original"

        def delete(self, stored_key: str) -> None:
            self.deleted = True

    storage = MismatchThenDeletes()
    with pytest.raises(ArtifactPersistError, match="hash mismatch") as error:
        persist_extraction_artifact(storage, logical_key="act/job.json", payload={"a": 1})

    assert error.value.cleanup_warning is None
    assert storage.deleted is True


def test_delete_orphan_artifact_omits_pointer_from_failed_job_summary(tmp_path):
    storage = LocalStorage(tmp_path)
    pointer = storage.save_artifact("act/job.json", b"{}", "application/json")
    summary = {"extraction_artifact_key": pointer, "extraction_artifact_sha256": "abc"}

    delete_orphan_artifact(storage, pointer, summary)

    assert "extraction_artifact_key" not in summary
    assert "extraction_artifact_sha256" not in summary
    assert "artifact_cleanup_warning" not in summary
    with pytest.raises(FileNotFoundError):
        storage.read_artifact(pointer)


def test_collect_artifact_pointers_includes_current_and_historical_job_keys():
    act = SimpleNamespace(extraction_artifact_key="current.json")
    jobs = [
        SimpleNamespace(summary_json={"extraction_artifact_key": "old.json"}),
        SimpleNamespace(summary_json={"extraction_artifact_key": "current.json"}),
        SimpleNamespace(summary_json={}),
    ]

    assert collect_artifact_pointers(act, jobs) == ["current.json", "old.json"]


def test_load_extraction_artifact_view_warns_on_hash_mismatch(tmp_path):
    storage = LocalStorage(tmp_path)
    pointer = storage.save_artifact("act/job.json", b'{"pages":null}', "application/json")
    act = SimpleNamespace(
        extraction_artifact_key=pointer,
        extraction_artifact_sha256="0" * 64,
        extraction_schema_version="1",
        extraction_created_at=None,
    )

    view = load_extraction_artifact_view(storage, act)

    assert view.present is True
    assert view.integrity_warning is True
    assert view.has_physical_pages is None
    assert view.sha256_prefix == "0" * 12
    assert view.parser_name is None


def _valid_provenance(**overrides):
    provenance = {
        "source_pdf_sha256": "a" * 64,
        "processing_job_id": "job-1",
        "parser_name": "PDF_INSPECTOR",
        "parser_library_version": None,
        "created_at": "2026-08-27T12:00:00Z",
        "page_count": 1,
        "warnings": [],
    }
    provenance.update(overrides)
    return provenance


def _valid_artifact_payload(**overrides):
    payload = {
        "schema_version": ARTIFACT_SCHEMA_VERSION,
        "processing_text": "a",
        "markdown": None,
        "pages": [{"page_number": 1, "text": "a", "extraction_method": "native"}],
        "page_spans": [{"page_number": 1, "start": 0, "end": 1}],
        "provenance": _valid_provenance(),
    }
    payload.update(overrides)
    return payload


def _view_from_payload(tmp_path, payload: dict):
    storage = LocalStorage(tmp_path)
    content = canonical_artifact_bytes(payload)
    pointer = storage.save_artifact("act/job.json", content, "application/json")
    act = SimpleNamespace(
        extraction_artifact_key=pointer,
        extraction_artifact_sha256=artifact_sha256(content),
        extraction_schema_version="1",
        extraction_created_at=None,
        parser_used="DOCLING",
    )
    return load_extraction_artifact_view(storage, act)


def test_load_extraction_artifact_view_uses_provenance_parser_not_act_parser(tmp_path):
    view = _view_from_payload(tmp_path, _valid_artifact_payload())

    assert view.integrity_warning is False
    assert view.parser_name == "PDF_INSPECTOR"
    assert view.has_physical_pages is True


def test_load_extraction_artifact_view_null_pages_means_no_physical_map(tmp_path):
    payload = _valid_artifact_payload(
        pages=None,
        page_spans=None,
        provenance=_valid_provenance(parser_name="DOCLING", page_count=65),
    )
    view = _view_from_payload(tmp_path, payload)

    assert view.integrity_warning is False
    assert view.parser_name == "DOCLING"
    assert view.has_physical_pages is False


def test_load_extraction_artifact_view_warns_on_malformed_json(tmp_path):
    storage = LocalStorage(tmp_path)
    pointer = storage.save_artifact("act/job.json", b"not-json", "application/json")
    digest = artifact_sha256(b"not-json")
    act = SimpleNamespace(
        extraction_artifact_key=pointer,
        extraction_artifact_sha256=digest,
        extraction_schema_version="1",
        extraction_created_at=None,
    )

    view = load_extraction_artifact_view(storage, act)

    assert view.present is True
    assert view.integrity_warning is True
    assert view.has_physical_pages is None
    assert view.parser_name is None


def test_load_extraction_artifact_view_warns_on_non_object_json(tmp_path):
    storage = LocalStorage(tmp_path)
    pointer = storage.save_artifact("act/job.json", b'["not","an","object"]', "application/json")
    digest = artifact_sha256(b'["not","an","object"]')
    act = SimpleNamespace(
        extraction_artifact_key=pointer,
        extraction_artifact_sha256=digest,
        extraction_schema_version="1",
        extraction_created_at=None,
    )

    view = load_extraction_artifact_view(storage, act)

    assert view.present is True
    assert view.integrity_warning is True
    assert view.parser_name is None


@pytest.mark.parametrize(
    "payload",
    [
        {},
        _valid_artifact_payload(schema_version=1),
        _valid_artifact_payload(pages="bad"),
        _valid_artifact_payload(pages=[{}]),
        _valid_artifact_payload(pages=None),
        _valid_artifact_payload(schema_version="2"),
        _valid_artifact_payload(provenance="nope"),
        _valid_artifact_payload(provenance={"parser_name": ""}),
        _valid_artifact_payload(processing_text=None),
        _valid_artifact_payload(markdown=12),
    ],
)
def test_load_extraction_artifact_view_warns_on_invalid_schema(tmp_path, payload):
    view = _view_from_payload(tmp_path, payload)

    assert view.present is True
    assert view.integrity_warning is True
    assert view.has_physical_pages is None
    assert view.parser_name is None


def test_load_extraction_artifact_view_warns_on_unsupported_schema_version(tmp_path):
    view = _view_from_payload(tmp_path, _valid_artifact_payload(schema_version="2"))

    assert view.integrity_warning is True
    assert view.parser_name is None


def test_load_extraction_artifact_view_warns_on_mismatched_page_numbers(tmp_path):
    payload = _valid_artifact_payload(
        pages=[
            {"page_number": 1, "text": "a", "extraction_method": "native"},
            {"page_number": 2, "text": "b", "extraction_method": "native"},
        ],
        page_spans=[
            {"page_number": 1, "start": 0, "end": 1},
            {"page_number": 3, "start": 1, "end": 2},
        ],
        provenance=_valid_provenance(page_count=2),
    )
    view = _view_from_payload(tmp_path, payload)

    assert view.integrity_warning is True
    assert view.has_physical_pages is None


def test_load_extraction_artifact_view_warns_on_invalid_span_bounds(tmp_path):
    view = _view_from_payload(
        tmp_path, _valid_artifact_payload(page_spans=[{"page_number": 1, "start": 5, "end": 1}])
    )

    assert view.integrity_warning is True
    assert view.has_physical_pages is None
