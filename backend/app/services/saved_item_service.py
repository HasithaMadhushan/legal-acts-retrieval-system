from typing import Any

from app.models.saved_item import SavedItem


def enrich_saved_item(item: SavedItem) -> dict[str, Any]:
    act = item.act
    if not act and item.section:
        act = item.section.act
    reference = item.reference
    section = item.section

    if reference:
        act = reference.source_act or act
        section = reference.source_section or section

    item_title = _item_title(item)
    verification_status = None
    if section and not reference:
        verification_status = section.verification_status
    if reference:
        verification_status = reference.verification_status

    return {
        "id": item.id,
        "user_id": item.user_id,
        "item_type": item.item_type,
        "act_id": item.act_id,
        "section_id": item.section_id,
        "reference_id": item.reference_id,
        "note": item.note,
        "item_title": item_title,
        "act_title": act.title if act else None,
        "act_number": act.act_number if act else None,
        "year": act.year if act else None,
        "section_number": section.section_number if section else None,
        "section_heading": section.heading if section else None,
        "relationship_type": reference.relationship_type if reference else None,
        "raw_reference_text": reference.raw_reference_text if reference else None,
        "context_snippet": reference.context_snippet if reference else None,
        "verification_status": verification_status,
        "processing_status": act.processing_status if act else None,
        "mapped": _is_mapped(reference) if reference else None,
        "target_act_title": _target_act_title(reference),
        "target_act_number": reference.target_act_number if reference else None,
        "target_act_year": reference.target_act_year if reference else None,
        "target_section_number": reference.target_section_number if reference else None,
        "target_section_path": reference.target_section_path if reference else None,
        "mapped_target_act_id": reference.target_act_id if reference else None,
        "mapped_target_section_id": reference.target_section_id if reference else None,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


def _item_title(item: SavedItem) -> str | None:
    if item.reference:
        return item.reference.raw_reference_text
    if item.section:
        heading = f": {item.section.heading}" if item.section.heading else ""
        return f"Section {item.section.section_number}{heading}"
    if item.act:
        title = item.act.title
        if item.act.act_number or item.act.year:
            return f"{title} {item.act.act_number or ''} {item.act.year or ''}".strip()
        return title
    return None


def _is_mapped(reference) -> bool:
    return bool(reference and (reference.target_act_id or reference.target_section_id))


def _target_act_title(reference) -> str | None:
    if not reference:
        return None
    if reference.target_act:
        return reference.target_act.title
    return reference.target_act_title_raw
