import re
from dataclasses import dataclass
from re import Match

from app.core.roles import ExtractionMethod, RelationshipType, VerificationStatus
from app.services.reference_normalizer import normalize_act_title, normalize_section_reference
from app.services.reference_patterns import (
    ACT_CITATION_RE,
    ADDITION_RE,
    AMENDING_ACT_RE,
    CHAPTER_RE,
    EFFECT_AS_SECTION_RE,
    ITEM_RE,
    NEW_PARAGRAPH_ITEM_RE,
    NEW_SECTION_INSERT_RE,
    PARAGRAPH_RE,
    PRINCIPAL_SECTION_AMENDED_RE,
    RELATIONSHIP_PHRASES,
    REPEAL_PARAGRAPH_RE,
    SCHEDULE_AMENDMENT_RE,
    SCHEDULE_RE,
    SECTION_OF_ACT_AMENDED_RE,
    SECTION_RE,
    SUBSECTION_RE,
    SUBSTITUTION_RE,
)


@dataclass
class ReferenceDraft:
    raw_reference_text: str
    context_snippet: str
    relationship_type: RelationshipType
    target_act_title_raw: str | None = None
    target_act_number: str | None = None
    target_act_year: int | None = None
    target_section_number: str | None = None
    target_section_path: str | None = None
    confidence_score: float = 0.3
    extraction_method: ExtractionMethod = ExtractionMethod.REGEX
    verification_status: VerificationStatus = VerificationStatus.PENDING


def extract_references(text: str) -> list[ReferenceDraft]:
    drafts: list[ReferenceDraft] = []
    seen: set[str] = set()

    def add(
        match: Match[str],
        *,
        title=None,
        number=None,
        year=None,
        section=None,
        path=None,
        relationship_type: RelationshipType | None = None,
        raw: str | None = None,
    ) -> None:
        context = _context(text, match.start(), match.end())
        detected_relationship = relationship_type or classify_relationship(context)
        confidence = score_reference(
            relationship_type=detected_relationship,
            has_act_number=bool(number and year),
            has_title=bool(title),
            has_section=bool(section or path),
        )
        raw_text = raw or match.group(0).strip()
        target_title = _clean_target_title(title)
        key = normalized_reference_key(raw_text)
        if key in seen:
            return
        seen.add(key)
        drafts.append(
            ReferenceDraft(
                raw_reference_text=raw_text,
                context_snippet=context,
                relationship_type=detected_relationship,
                target_act_title_raw=target_title,
                target_act_number=str(number) if number else None,
                target_act_year=int(year) if year else None,
                target_section_number=normalize_section_reference(section),
                target_section_path=path,
                confidence_score=confidence,
                verification_status=(
                    VerificationStatus.PENDING
                    if confidence >= 0.7
                    else VerificationStatus.NEEDS_REVIEW
                ),
            )
        )

    for match in AMENDING_ACT_RE.finditer(text):
        chapter = match.group("chapter")
        add(
            match,
            title=match.group("title"),
            number=match.group("number"),
            year=match.group("year"),
            path=chapter,
            relationship_type=RelationshipType.AMENDS,
        )

    for match in SECTION_OF_ACT_AMENDED_RE.finditer(text):
        add(
            match,
            title=match.group("title"),
            number=match.group("number"),
            year=match.group("year"),
            section=match.group("section"),
            path=match.group("section"),
            relationship_type=RelationshipType.AMENDS,
        )

    for match in PRINCIPAL_SECTION_AMENDED_RE.finditer(text):
        add(
            match,
            title="principal enactment",
            section=match.group("section"),
            path=match.group("section"),
            relationship_type=RelationshipType.AMENDS,
        )

    for match in NEW_SECTION_INSERT_RE.finditer(text):
        path = f"after section {match.group('after')}; section {match.group('section')}"
        add(
            match,
            section=match.group("section"),
            path=path,
            relationship_type=RelationshipType.INSERTS,
        )

    for match in EFFECT_AS_SECTION_RE.finditer(text):
        add(
            match,
            section=match.group("section"),
            path=match.group("section"),
            relationship_type=RelationshipType.INSERTS,
        )

    for match in REPEAL_PARAGRAPH_RE.finditer(text):
        path = f"subsection ({match.group('subsection')}) paragraph ({match.group('paragraph')})"
        add(
            match,
            section=f"({match.group('paragraph')})",
            path=path,
            relationship_type=RelationshipType.REPEALS,
        )

    for match in SUBSTITUTION_RE.finditer(text):
        add(match, relationship_type=RelationshipType.SUBSTITUTES)

    for match in ADDITION_RE.finditer(text):
        target = match.group("target")
        target_type = match.group("target_type").lower()
        add(
            match,
            section=target,
            path=f"{target_type} {target}",
            relationship_type=RelationshipType.ADDS,
        )

    for match in NEW_PARAGRAPH_ITEM_RE.finditer(text):
        add(
            match,
            path=f"new {match.group('target_type').lower()}",
            relationship_type=RelationshipType.ADDS,
        )

    for match in SCHEDULE_AMENDMENT_RE.finditer(text):
        add(
            match,
            title="principal enactment",
            path=match.group("schedule").strip(),
            relationship_type=RelationshipType.AMENDS,
        )

    for match in ACT_CITATION_RE.finditer(text):
        add(
            match,
            title=f"{match.group('title')} Act",
            number=match.group("number"),
            year=match.group("year"),
        )

    for match in SECTION_RE.finditer(text):
        add(match, section=match.group("section"), path=match.group("section"))

    for match in SUBSECTION_RE.finditer(text):
        subsection = f"({match.group('subsection')})"
        add(match, section=subsection, path=subsection)

    for match in PARAGRAPH_RE.finditer(text):
        paragraph = f"({match.group('paragraph')})"
        add(match, section=paragraph, path=paragraph)

    for match in ITEM_RE.finditer(text):
        add(match, section=match.group("item"), path=f"item {match.group('item')}")

    for match in SCHEDULE_RE.finditer(text):
        add(match, path=match.group("schedule").strip())

    for match in CHAPTER_RE.finditer(text):
        add(match, title=f"Chapter {match.group('chapter')}")

    return drafts


def summarize_references(references: list[ReferenceDraft]) -> dict[str, object]:
    by_type: dict[str, int] = {}
    unresolved_target_count = 0
    for reference in references:
        relationship_value = reference.relationship_type.value
        by_type[relationship_value] = by_type.get(relationship_value, 0) + 1
        if not (
            reference.target_act_title_raw
            or reference.target_act_number
            or reference.target_section_number
            or reference.target_section_path
        ):
            unresolved_target_count += 1
    warnings: list[str] = []
    if unresolved_target_count:
        warnings.append("Some references have no structured target and require Admin review.")
    return {
        "references_detected": len(references),
        "by_type": by_type,
        "unresolved_target_count": unresolved_target_count,
        "warnings": warnings,
    }


def classify_relationship(context: str) -> RelationshipType:
    lowered = context.lower()
    for relationship_type, phrases in RELATIONSHIP_PHRASES.items():
        if any(phrase in lowered for phrase in phrases):
            return relationship_type
    if "section" in lowered or "act" in lowered:
        return RelationshipType.REFERS_TO
    return RelationshipType.UNKNOWN


def score_reference(
    *, relationship_type: RelationshipType, has_act_number: bool, has_title: bool, has_section: bool
) -> float:
    has_relationship = relationship_type not in {
        RelationshipType.UNKNOWN,
        RelationshipType.REFERS_TO,
    }
    if has_act_number and has_relationship:
        return 0.95
    if has_title and has_section and has_relationship:
        return 0.85
    if (has_title or has_section) and has_relationship:
        return 0.70
    if has_relationship:
        return 0.50
    if has_section or has_title:
        return 0.30
    return 0.20


def _context(text: str, start: int, end: int, width: int = 160) -> str:
    snippet = text[max(0, start - width) : min(len(text), end + width)]
    return " ".join(snippet.split())


def normalized_reference_key(raw: str) -> str:
    return normalize_act_title(raw)


def _clean_target_title(title: str | None) -> str | None:
    if not title:
        return None
    cleaned = " ".join(title.split()).strip(" ,.;:")
    cleaned = cleaned.removeprefix("the ").removeprefix("The ")
    cleaned = re.sub(
        r"(?i)^section\s+\d+[A-Z]?\s+of\s+(?:the\s+)?",
        "",
        cleaned,
    )
    return cleaned or None
