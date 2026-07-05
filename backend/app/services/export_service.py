import csv
import io

from sqlalchemy.orm import Session

from app.core.config import LEGAL_DISCLAIMER
from app.models.legal_reference import LegalReference
from app.models.saved_item import SavedItem
from app.models.user import User
from app.services.saved_item_service import enrich_saved_item

# Cell values starting with these characters can be interpreted as formulas by
# spreadsheet applications (Excel/Google Sheets/LibreOffice). Since exported cells
# may contain user-entered notes or text extracted from uploaded PDFs, every cell is
# sanitized before being written to guard against CSV formula injection.
_RISKY_CSV_PREFIXES = ("=", "+", "-", "@")


def safe_csv_cell(value: object) -> str:
    """Return a CSV-safe string form of value, neutralizing formula-injection prefixes."""
    text = "" if value is None else str(value)
    if text.startswith(_RISKY_CSV_PREFIXES):
        return f"'{text}"
    return text


def _safe_row(values: list[object]) -> list[str]:
    return [safe_csv_cell(value) for value in values]


def saved_items_csv(db: Session, user: User) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(_safe_row([LEGAL_DISCLAIMER]))
    writer.writerow(
        _safe_row(
            [
                "item_type",
                "item_title",
                "act_id",
                "act_title",
                "act_number",
                "year",
                "section_id",
                "section_number",
                "section_heading",
                "reference_id",
                "relationship_type",
                "raw_reference_text",
                "target_act_title",
                "target_section",
                "mapped_status",
                "verification_status",
                "processing_status",
                "note",
            ]
        )
    )
    for item in _saved_items_for_user(db, user):
        data = enrich_saved_item(item)
        writer.writerow(
            _safe_row(
                [
                    data["item_type"].value,
                    data["item_title"],
                    data["act_id"],
                    data["act_title"],
                    data["act_number"],
                    data["year"],
                    data["section_id"],
                    data["section_number"],
                    data["section_heading"],
                    data["reference_id"],
                    data["relationship_type"].value if data["relationship_type"] else "",
                    data["raw_reference_text"],
                    data["target_act_title"],
                    data["target_section_number"] or data["target_section_path"],
                    _mapped_status(data["mapped"]),
                    data["verification_status"].value if data["verification_status"] else "",
                    data["processing_status"].value if data["processing_status"] else "",
                    data["note"],
                ]
            )
        )
    return buffer.getvalue()


def saved_items_markdown(db: Session, user: User) -> str:
    lines = [
        f"> {LEGAL_DISCLAIMER}",
        "",
        "| Type | Item | Act | Section | Reference | Mapping | Status | Note |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for item in _saved_items_for_user(db, user):
        data = enrich_saved_item(item)
        lines.append(
            "| "
            f"{data['item_type'].value} | "
            f"{_md(data['item_title'])} | "
            f"{_md(data['act_title'])} | "
            f"{_md(_section_label(data))} | "
            f"{_md(data['raw_reference_text'])} | "
            f"{_mapped_status(data['mapped'])} | "
            f"{data['verification_status'].value if data['verification_status'] else ''} | "
            f"{_md(data['note'])} |"
        )
    return "\n".join(lines) + "\n"


def act_references_csv(db: Session, act_id: str) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(_safe_row([LEGAL_DISCLAIMER]))
    writer.writerow(
        _safe_row(
            [
                "source_act_id",
                "source_section_id",
                "relationship_type",
                "raw_reference_text",
                "target_act_title",
                "target_section",
                "confidence",
                "verification_status",
            ]
        )
    )
    references = db.query(LegalReference).filter(LegalReference.source_act_id == act_id).all()
    for reference in references:
        writer.writerow(
            _safe_row(
                [
                    reference.source_act_id,
                    reference.source_section_id,
                    reference.relationship_type.value,
                    reference.raw_reference_text,
                    reference.target_act_title_raw,
                    reference.target_section_number,
                    reference.confidence_score,
                    reference.verification_status.value,
                ]
            )
        )
    return buffer.getvalue()


def _saved_items_for_user(db: Session, user: User) -> list[SavedItem]:
    return (
        db.query(SavedItem)
        .filter(SavedItem.user_id == user.id)
        .order_by(SavedItem.created_at.desc())
        .all()
    )


def _mapped_status(value: bool | None) -> str:
    if value is None:
        return ""
    return "mapped" if value else "unresolved"


def _section_label(data: dict) -> str:
    if not data["section_number"]:
        return ""
    heading = f": {data['section_heading']}" if data["section_heading"] else ""
    return f"Section {data['section_number']}{heading}"


def _md(value: object) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", " ")
