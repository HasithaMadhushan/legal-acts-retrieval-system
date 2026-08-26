import re
from dataclasses import dataclass

from app.core.roles import SectionType
from app.services.text_cleaner import normalize_for_search

SECTION_START_RE = re.compile(r"(?m)^\s*(?P<number>\d{1,3}[A-Z]?)\.\s*(?P<heading>.*)$")
SCHEDULE_RE = re.compile(
    r"(?im)^\s*(?P<number>"
    r"(?:(?:FIRST|SECOND|THIRD|FOURTH|FIFTH|SIXTH|SEVENTH|EIGHTH|NINTH|TENTH)\s+)?"
    r"SCHEDULE(?:\s+(?:[IVXLCDM]+|\d+))?"
    r")\s*$"
)
PART_RE = re.compile(
    r"(?m)^\s*(?P<number>(?:PART|Part)\s+[IVXLCDM]+)"
    r"(?:\s+(?P<heading>[A-Z][A-Z0-9\s&,'()/-]*))?\s*$"
)
COVER_LINE_RE = re.compile(
    r"("
    r"parliament of the democratic socialist republic|government printing|department of "
    r"government printing|printed at|published as a supplement|price\s*:|postage\s*:|"
    r"this act can be downloaded|gazette|ld[-\s]*o|legal supplement"
    r")",
    re.I,
)
TITLE_LINE_RE = re.compile(
    r"\b(act|no\.\s*\d+\s+of\s+\d{4}|certified on|date of certification)\b",
    re.I,
)
MARGINAL_HEADING_RE = re.compile(
    r"\b(short title|amendment|insertion|replacement|repeal|schedule|sinhala|tamil|"
    r"interpretation|validation|commencement|principal enactment|section)\b",
    re.I,
)


@dataclass
class SectionDraft:
    section_number: str
    section_path: str
    heading: str | None
    section_type: SectionType
    text: str
    normalized_text: str
    sort_order: int
    page_start: int | None = None
    page_end: int | None = None


@dataclass
class SegmentationResult:
    sections: list[SectionDraft]
    summary: dict[str, object]


@dataclass
class _Boundary:
    start: int
    marker_start: int
    kind: SectionType
    number: str
    heading: str | None


def segment_sections(text: str) -> list[SectionDraft]:
    return segment_act_text(text).sections


def segment_act_text(text: str) -> SegmentationResult:
    normalized_text = text.strip()
    warnings: list[str] = []
    possible_cover_text_removed = False

    if not normalized_text:
        warnings.append("No text was available for section segmentation.")
        return _fallback_result("", warnings, possible_cover_text_removed)

    boundaries = _find_boundaries(normalized_text)
    if not any(boundary.kind == SectionType.SECTION for boundary in boundaries):
        warnings.append("No numbered sections were detected; fallback section was created.")
        return _fallback_result(normalized_text, warnings, possible_cover_text_removed)

    drafts: list[SectionDraft] = []
    preamble_text, removed_cover = _clean_preamble(normalized_text[: boundaries[0].start])
    possible_cover_text_removed = removed_cover
    if preamble_text:
        drafts.append(
            _draft(
                section_number="PREAMBLE",
                section_path="PREAMBLE",
                heading="Preamble",
                section_type=SectionType.PREAMBLE,
                text=preamble_text,
                sort_order=len(drafts),
            )
        )

    for index, boundary in enumerate(boundaries):
        end = boundaries[index + 1].start if index + 1 < len(boundaries) else len(normalized_text)
        block = normalized_text[boundary.start:end].strip()
        if not block:
            continue
        drafts.append(
            _draft(
                section_number=boundary.number,
                section_path=boundary.number,
                heading=boundary.heading,
                section_type=boundary.kind,
                text=block,
                sort_order=len(drafts),
            )
        )

    if not drafts:
        warnings.append("Segmentation produced no records; fallback section was created.")
        return _fallback_result(normalized_text, warnings, possible_cover_text_removed)

    main_sections = [draft for draft in drafts if draft.section_type == SectionType.SECTION]
    schedules = [draft for draft in drafts if draft.section_type == SectionType.SCHEDULE]
    parts = [draft for draft in drafts if draft.section_type == SectionType.PART]
    summary = {
        "sections_detected": len(main_sections),
        "schedules_detected": len(schedules),
        "parts_detected": len(parts),
        "fallback_used": False,
        "warnings": warnings,
        "possible_cover_text_removed": possible_cover_text_removed,
    }
    if any(draft.section_type == SectionType.PREAMBLE for draft in drafts):
        warnings.append("Preamble text was retained separately from numbered sections.")
    return SegmentationResult(sections=drafts, summary=summary)


def _find_boundaries(text: str) -> list[_Boundary]:
    schedule_matches = list(SCHEDULE_RE.finditer(text))
    first_schedule_start = min((match.start() for match in schedule_matches), default=None)
    boundaries: list[_Boundary] = []

    for match in PART_RE.finditer(text):
        if first_schedule_start is not None and match.start() >= first_schedule_start:
            continue
        line = match.group(0).strip()
        number = match.group("number").upper()
        boundaries.append(
            _Boundary(
                start=match.start(),
                marker_start=match.start(),
                kind=SectionType.PART,
                number=number,
                heading=line,
            )
        )

    for match in SECTION_START_RE.finditer(text):
        if first_schedule_start is not None and match.start() >= first_schedule_start:
            continue
        start, marginal_heading = _include_previous_marginal_heading(text, match.start())
        inline_heading = _extract_heading(match.group("heading"))
        boundaries.append(
            _Boundary(
                start=start,
                marker_start=match.start(),
                kind=SectionType.SECTION,
                number=match.group("number"),
                heading=inline_heading or marginal_heading,
            )
        )

    for match in schedule_matches:
        line = match.group("number").strip()
        boundaries.append(
            _Boundary(
                start=match.start(),
                marker_start=match.start(),
                kind=SectionType.SCHEDULE,
                number=line,
                heading=line,
            )
        )

    return _dedupe_and_sort_boundaries(boundaries)


def _dedupe_and_sort_boundaries(boundaries: list[_Boundary]) -> list[_Boundary]:
    ordered = sorted(boundaries, key=lambda boundary: (boundary.start, boundary.marker_start))
    deduped: list[_Boundary] = []
    for boundary in ordered:
        if deduped and boundary.start == deduped[-1].start and boundary.kind == deduped[-1].kind:
            continue
        deduped.append(boundary)
    return deduped


def _include_previous_marginal_heading(text: str, marker_start: int) -> tuple[int, str | None]:
    prefix = text[:marker_start]
    lines = list(re.finditer(r"(?m)^.*$", prefix))
    for line_match in reversed(lines[-4:]):
        line = line_match.group(0).strip()
        if not line:
            continue
        if _looks_like_marginal_heading(line):
            return line_match.start(), _clean_heading(line)
        break
    return marker_start, None


def _looks_like_marginal_heading(line: str) -> bool:
    if len(line) > 120 or line.endswith("."):
        return False
    if COVER_LINE_RE.search(line) or re.search(
        r"\b(no\.\s*\d+\s+of\s+\d{4}|certified on|date of certification)\b",
        line,
        re.I,
    ):
        return False
    if SECTION_START_RE.match(line) or PART_RE.match(line) or SCHEDULE_RE.match(line):
        return False
    return bool(MARGINAL_HEADING_RE.search(line))


def _clean_preamble(text: str) -> tuple[str, bool]:
    kept_lines: list[str] = []
    removed = False
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            if kept_lines and kept_lines[-1]:
                kept_lines.append("")
            continue
        if _is_cover_or_title_line(line):
            removed = True
            continue
        kept_lines.append(line)
    cleaned = "\n".join(kept_lines).strip()
    return cleaned, removed


def _is_cover_or_title_line(line: str) -> bool:
    if COVER_LINE_RE.search(line):
        return True
    if TITLE_LINE_RE.search(line) and len(line) <= 180:
        return True
    if line.isupper() and len(line) <= 180 and "ENACTED" not in line:
        return True
    return False


def _fallback_result(
    text: str, warnings: list[str], possible_cover_text_removed: bool
) -> SegmentationResult:
    fallback_text, removed_cover = _clean_preamble(text)
    if not fallback_text:
        fallback_text = text.strip()
    possible_cover_text_removed = possible_cover_text_removed or removed_cover
    draft = _draft(
        section_number="0",
        section_path="0",
        heading="Document text",
        section_type=SectionType.OTHER,
        text=fallback_text,
        sort_order=0,
    )
    return SegmentationResult(
        sections=[draft],
        summary={
            "sections_detected": 0,
            "schedules_detected": 0,
            "parts_detected": 0,
            "fallback_used": True,
            "warnings": warnings,
            "possible_cover_text_removed": possible_cover_text_removed,
        },
    )


def _draft(
    *,
    section_number: str,
    section_path: str,
    heading: str | None,
    section_type: SectionType,
    text: str,
    sort_order: int,
) -> SectionDraft:
    cleaned_text = text.strip()
    return SectionDraft(
        section_number=section_number,
        section_path=section_path,
        heading=heading,
        section_type=section_type,
        text=cleaned_text,
        normalized_text=normalize_for_search(cleaned_text),
        sort_order=sort_order,
    )


def _extract_heading(raw_heading: str) -> str | None:
    heading = raw_heading.strip()
    if not heading:
        return None
    if _looks_like_body_text(heading):
        return None
    first_sentence = re.split(r"(?<=[.;])\s+", heading, maxsplit=1)[0].strip()
    if len(first_sentence) <= 160:
        return _clean_heading(first_sentence)
    return None


def _looks_like_body_text(value: str) -> bool:
    return bool(
        re.match(
            r"(?i)^(this act|the provisions|section \d+|in section|for the purposes|where)",
            value.strip(),
        )
    )


def _clean_heading(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip(".;: -")
