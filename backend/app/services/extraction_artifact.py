from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any, NoReturn

from app.models.legal_act import LegalAct
from app.models.processing_job import ProcessingJob
from app.schemas.legal_act import ExtractionArtifactRead
from app.services.pdf_parser.base import ParsedPdf
from app.services.pdf_parser.preparation import PreparedPages
from app.services.storage import Storage

ARTIFACT_SCHEMA_VERSION = "1"
SHA256_PREFIX_LENGTH = 12


class ArtifactPersistError(RuntimeError):
    def __init__(self, message: str, *, cleanup_warning: str | None = None) -> None:
        super().__init__(message)
        self.cleanup_warning = cleanup_warning


def artifact_logical_key(act_id: str, job_id: str) -> str:
    return f"{act_id}/extractions/{job_id}.schema-v{ARTIFACT_SCHEMA_VERSION}.json"


def canonical_artifact_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def artifact_sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def build_extraction_payload(
    *,
    parsed: ParsedPdf,
    prepared: PreparedPages,
    act: LegalAct,
    job: ProcessingJob,
    warnings: list[str],
    created_at: datetime,
) -> dict[str, Any]:
    structured = parsed.structured_document
    pages = None
    if structured is not None and structured.pages is not None:
        pages = [
            {
                "page_number": page.page_number,
                "text": page.text,
                "extraction_method": page.extraction_method,
            }
            for page in structured.pages
        ]
    page_spans = None
    if prepared.page_spans is not None:
        page_spans = [
            {"page_number": span.page_number, "start": span.start, "end": span.end}
            for span in prepared.page_spans
        ]
    markdown = structured.markdown if structured is not None else None
    return {
        "schema_version": ARTIFACT_SCHEMA_VERSION,
        "processing_text": prepared.text,
        "markdown": markdown,
        "pages": pages,
        "page_spans": page_spans,
        "provenance": {
            "source_pdf_sha256": act.file_sha256,
            "processing_job_id": job.id,
            "parser_name": parsed.parser_name,
            "parser_library_version": _parser_library_version(parsed.parser_name),
            "created_at": _isoformat_utc(created_at),
            "page_count": parsed.page_count,
            "warnings": warnings,
        },
    }


def persist_extraction_artifact(
    storage: Storage, *, logical_key: str, payload: dict[str, Any]
) -> tuple[str, str]:
    content = canonical_artifact_bytes(payload)
    digest = artifact_sha256(content)
    pointer = storage.save_artifact(logical_key, content, "application/json")
    try:
        _verify_written_artifact(storage, pointer, digest)
    except Exception as exc:
        _reraise_after_orphan_cleanup(storage, pointer, exc)
    return pointer, digest


def _verify_written_artifact(storage: Storage, pointer: str, digest: str) -> None:
    stored = storage.read_artifact(pointer)
    if artifact_sha256(stored) != digest:
        raise ArtifactPersistError("extraction artifact hash mismatch after write")


def _reraise_after_orphan_cleanup(
    storage: Storage, pointer: str, cause: Exception
) -> NoReturn:
    cleanup_warning = _try_delete_orphan(storage, pointer)
    if isinstance(cause, ArtifactPersistError) and cleanup_warning is None:
        raise cause
    raise ArtifactPersistError(str(cause), cleanup_warning=cleanup_warning) from cause


def _try_delete_orphan(storage: Storage, pointer: str) -> str | None:
    try:
        storage.delete(pointer)
    except Exception as cleanup_exc:
        return f"Failed to delete orphan extraction artifact: {cleanup_exc}"
    return None


def delete_orphan_artifact(storage: Storage, pointer: str | None, summary: dict[str, Any]) -> None:
    summary.pop("extraction_artifact_key", None)
    summary.pop("extraction_artifact_sha256", None)
    if not pointer:
        return
    try:
        storage.delete(pointer)
    except Exception as exc:
        summary["artifact_cleanup_warning"] = (
            f"Failed to delete orphan extraction artifact: {exc}"
        )


def load_extraction_artifact_view(storage: Storage, act: LegalAct) -> ExtractionArtifactRead:
    prefix = _sha_prefix(act.extraction_artifact_sha256)
    if not act.extraction_artifact_key:
        return ExtractionArtifactRead(present=False)
    try:
        raw = storage.read_artifact(act.extraction_artifact_key)
    except Exception:
        return _integrity_warning_view(act, prefix)
    if act.extraction_artifact_sha256 and artifact_sha256(raw) != act.extraction_artifact_sha256:
        return _integrity_warning_view(act, prefix)
    try:
        payload = _decode_artifact_payload(raw)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
        return _integrity_warning_view(act, prefix)
    pages = payload.get("pages")
    return ExtractionArtifactRead(
        present=True,
        schema_version=payload["schema_version"],
        sha256_prefix=prefix,
        created_at=act.extraction_created_at,
        parser_name=_parser_name_from_payload(payload),
        has_physical_pages=isinstance(pages, list),
        integrity_warning=False,
    )


def _integrity_warning_view(act: LegalAct, prefix: str | None) -> ExtractionArtifactRead:
    return ExtractionArtifactRead(
        present=True,
        schema_version=act.extraction_schema_version,
        sha256_prefix=prefix,
        created_at=act.extraction_created_at,
        integrity_warning=True,
    )


def _decode_artifact_payload(raw: bytes) -> dict[str, Any]:
    payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("artifact payload must be an object")
    _validate_artifact_payload(payload)
    return payload


def _validate_artifact_payload(payload: dict[str, Any]) -> None:
    if payload.get("schema_version") != ARTIFACT_SCHEMA_VERSION:
        raise ValueError("schema_version must match the supported artifact schema")
    if not isinstance(payload.get("processing_text"), str):
        raise ValueError("processing_text must be a string")
    markdown = payload.get("markdown")
    if markdown is not None and not isinstance(markdown, str):
        raise ValueError("markdown must be a string or null")
    pages = payload.get("pages")
    _validate_pages_and_spans(pages, payload.get("page_spans"))
    provenance = payload.get("provenance")
    _validate_provenance(provenance)
    if (
        isinstance(pages, list)
        and isinstance(provenance, dict)
        and provenance.get("page_count") != len(pages)
    ):
        raise ValueError("provenance.page_count must match the page list")


def _validate_pages_and_spans(pages: object, spans: object) -> None:
    if pages is None:
        if spans is not None:
            raise ValueError("page_spans must be null when pages is null")
        return
    if not isinstance(pages, list) or not all(_is_page_entry(item) for item in pages):
        raise ValueError("pages must be a list of page objects or null")
    if not isinstance(spans, list) or len(spans) != len(pages):
        raise ValueError("page_spans must have one span per page")
    if not all(_is_span_entry(item) for item in spans):
        raise ValueError("page_spans entries are invalid")
    _validate_span_alignment(pages, spans)


def _validate_span_alignment(pages: list, spans: list) -> None:
    for index, page in enumerate(pages):
        span = spans[index]
        expected = index + 1
        if page["page_number"] != expected or span["page_number"] != expected:
            raise ValueError("page and span numbers must be ordered and matching")
        if span["start"] < 0 or span["end"] < span["start"]:
            raise ValueError("page span bounds must satisfy 0 <= start <= end")


def _is_page_entry(page: object) -> bool:
    if not isinstance(page, dict):
        return False
    return (
        isinstance(page.get("page_number"), int)
        and isinstance(page.get("text"), str)
        and isinstance(page.get("extraction_method"), str)
    )


def _is_span_entry(span: object) -> bool:
    if not isinstance(span, dict):
        return False
    return (
        isinstance(span.get("page_number"), int)
        and isinstance(span.get("start"), int)
        and isinstance(span.get("end"), int)
    )


_PROVENANCE_REQUIRED_STRINGS = (
    "source_pdf_sha256",
    "processing_job_id",
    "parser_name",
    "created_at",
)


def _validate_provenance(provenance: object) -> None:
    if not isinstance(provenance, dict):
        raise ValueError("provenance must be an object")
    for key in _PROVENANCE_REQUIRED_STRINGS:
        value = provenance.get(key)
        if not isinstance(value, str) or not value:
            raise ValueError(f"provenance.{key} must be a non-empty string")
    library_version = provenance.get("parser_library_version")
    if library_version is not None and not isinstance(library_version, str):
        raise ValueError("provenance.parser_library_version must be a string or null")
    if not isinstance(provenance.get("page_count"), int):
        raise ValueError("provenance.page_count must be an integer")
    warnings = provenance.get("warnings")
    if not isinstance(warnings, list) or not all(isinstance(item, str) for item in warnings):
        raise ValueError("provenance.warnings must be a list of strings")


def _parser_name_from_payload(payload: dict[str, Any]) -> str | None:
    provenance = payload.get("provenance")
    if not isinstance(provenance, dict):
        return None
    parser_name = provenance.get("parser_name")
    if isinstance(parser_name, str) and parser_name:
        return parser_name
    return None


def collect_artifact_pointers(act: LegalAct, jobs: list[ProcessingJob]) -> list[str]:
    pointers: list[str] = []
    seen: set[str] = set()
    for pointer in _iter_artifact_pointers(act, jobs):
        if pointer not in seen:
            seen.add(pointer)
            pointers.append(pointer)
    return pointers


def _iter_artifact_pointers(act: LegalAct, jobs: list[ProcessingJob]):
    if act.extraction_artifact_key:
        yield act.extraction_artifact_key
    for job in jobs:
        summary = job.summary_json or {}
        pointer = summary.get("extraction_artifact_key")
        if isinstance(pointer, str) and pointer:
            yield pointer


def _sha_prefix(digest: str | None) -> str | None:
    if not digest:
        return None
    return digest[:SHA256_PREFIX_LENGTH]


def _isoformat_utc(created_at: datetime) -> str:
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=UTC)
    return created_at.isoformat().replace("+00:00", "Z")


def _parser_library_version(parser_name: str) -> str | None:
    if parser_name != "PYMUPDF":
        return None
    try:
        import fitz
    except ImportError:
        return None
    version = getattr(fitz, "version", None)
    if isinstance(version, tuple) and version:
        return str(version[0])
    if version is None:
        return None
    return str(version)
