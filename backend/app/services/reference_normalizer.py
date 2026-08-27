import re
from dataclasses import dataclass

from app.core.roles import RelationshipType
from app.services.text_cleaner import normalize_for_search

ACT_NUMBER_RE = re.compile(
    r"\b(?:Act,?\s+)?No\.?\s*(?P<number>\d+[A-Z]?)\s+of\s+(?P<year>\d{4})\b",
    re.I,
)
CHAPTER_RE = re.compile(r"\bChapter\s+(?P<chapter>\d+[A-Z]?)\b", re.I)
SCHEDULE_RE = re.compile(
    r"\b(?P<schedule>(?:(?:First|Second|Third|Fourth|Fifth|Sixth|Seventh|Eighth|Ninth|"
    r"Tenth)\s+)?Schedule(?:\s+[IVXLCDM]+)?)\b",
    re.I,
)
PART_RE = re.compile(r"\bPart\s+(?P<part>[IVXLCDM]+[A-Z]?)\b", re.I)
CITED_ACT_NAME_RE = re.compile(
    r"\b([A-Z][A-Za-z0-9'’]*(?:\s+(?:and|of|the|for|&|[A-Z][A-Za-z0-9'’-]*)){0,5})"
    r"\s+(Act|Ordinance)\b"
)
WEAK_ACT_TITLES = frozenset({"fund act", "trust act", "the code", "code"})


@dataclass(frozen=True)
class ActCitation:
    number: str | None = None
    year: int | None = None
    title: str | None = None


def extract_cited_act_title(value: str | None) -> str | None:
    """Pull a short Act/Ordinance name out of a noisy citation snippet."""
    if not value:
        return None
    padded = re.sub(r"([a-z])(Act|Ordinance)\b", r"\1 \2", value)
    best: str | None = None
    for match in CITED_ACT_NAME_RE.finditer(padded):
        name = _tidy_cited_act_title(f"{match.group(1)} {match.group(2)}")
        if len(name) < 5 or name.lower() in WEAK_ACT_TITLES:
            continue
        if best is None or len(name) > len(best):
            best = name
    return best


def _tidy_cited_act_title(name: str) -> str:
    stripped = re.sub(r"^(?:The|And|Of)\s+", "", name, flags=re.I)
    return collapse_whitespace(stripped)


def normalize_act_title(title: str | None) -> str:
    if not title:
        return ""
    cleaned = collapse_whitespace(title)
    cleaned = re.sub(r",?\s+No\.?\s*\d+[A-Z]?\s+of\s+\d{4}\b", "", cleaned, flags=re.I)
    cleaned = re.sub(r"\((?:Chapter\s+\d+[A-Z]?)\)", "", cleaned, flags=re.I)
    cleaned = re.sub(r"[,:;]+$", "", cleaned).strip()
    return normalize_for_search(cleaned)


def collapse_whitespace(value: str | None) -> str:
    if not value:
        return ""
    return " ".join(str(value).replace("\n", " ").replace("\r", " ").split())


def parse_act_citation(value: str | None) -> ActCitation:
    if not value:
        return ActCitation()
    cleaned = collapse_whitespace(value)
    match = ACT_NUMBER_RE.search(cleaned)
    if not match:
        return ActCitation(title=cleaned or None)

    title = cleaned[: match.start()].strip(" ,.;:")
    return ActCitation(
        number=match.group("number"),
        year=int(match.group("year")),
        title=title or None,
    )


def normalize_act_number(value: str | int | None) -> str | None:
    if value is None:
        return None
    match = re.search(r"\d+[A-Z]?", str(value), re.I)
    return match.group(0).upper() if match else None


def normalize_chapter_reference(value: str | None) -> str | None:
    if not value:
        return None
    match = CHAPTER_RE.search(value)
    if not match:
        return None
    return f"Chapter {match.group('chapter').upper()}"


def normalize_section_reference(section: str | None) -> str | None:
    if not section:
        return None
    section = collapse_whitespace(section)
    section = re.sub(
        r"^(?:section|sections|s\.|sec\.|subsection|paragraph|item)\s+",
        "",
        section,
        flags=re.I,
    )
    section = re.sub(r"\s+", "", section)
    return section.upper() if re.match(r"^\d+[A-Z]*$", section, re.I) else section.lower()


def normalize_target_path(path: str | None) -> str | None:
    if not path:
        return None
    cleaned = collapse_whitespace(path).strip(" ,.;:")
    schedule = normalize_schedule_reference(cleaned)
    if schedule:
        return schedule

    chapter = normalize_chapter_reference(cleaned)
    if chapter:
        return chapter

    part_match = PART_RE.search(cleaned)
    if part_match:
        return f"Part {part_match.group('part').upper()}"

    replacements = [
        (r"\bsubsection\s+\(([^)]+)\)", r"subsection (\1)"),
        (r"\bparagraph\s+\(([^)]+)\)", r"paragraph (\1)"),
        (r"\bitem\s+(\d+[A-Z]?)", r"item \1"),
        (r"\bsection\s+(\d+[A-Z]?)", r"section \1"),
    ]
    normalized = cleaned
    for pattern, replacement in replacements:
        normalized = re.sub(pattern, replacement, normalized, flags=re.I)
    return normalized.strip()


def normalize_schedule_reference(value: str | None) -> str | None:
    if not value:
        return None
    match = SCHEDULE_RE.search(value)
    if not match:
        return None
    words = collapse_whitespace(match.group("schedule")).split()
    return " ".join(word.capitalize() if not word.isupper() else word for word in words)


def normalize_relationship_type(value: str | RelationshipType | None) -> RelationshipType | None:
    if value is None:
        return None
    if isinstance(value, RelationshipType):
        return value
    key = str(value).strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "refer": RelationshipType.REFERS_TO,
        "refers": RelationshipType.REFERS_TO,
        "refers_to": RelationshipType.REFERS_TO,
        "cross_reference": RelationshipType.CROSS_REFERENCE,
        "cross_references": RelationshipType.CROSS_REFERENCE,
        "cross_reference_to": RelationshipType.CROSS_REFERENCE,
        "amend": RelationshipType.AMENDS,
        "amends": RelationshipType.AMENDS,
        "amended": RelationshipType.AMENDS,
        "repeal": RelationshipType.REPEALS,
        "repeals": RelationshipType.REPEALS,
        "insert": RelationshipType.INSERTS,
        "inserts": RelationshipType.INSERTS,
        "substitute": RelationshipType.SUBSTITUTES,
        "substitutes": RelationshipType.SUBSTITUTES,
        "add": RelationshipType.ADDS,
        "adds": RelationshipType.ADDS,
        "addition": RelationshipType.ADDS,
    }
    if key in aliases:
        return aliases[key]
    for relationship_type in RelationshipType:
        if key == relationship_type.value.lower():
            return relationship_type
    return None


def normalize_year(value: str | int | None) -> int | None:
    if value is None:
        return None
    match = re.search(r"\d{4}", str(value))
    return int(match.group(0)) if match else None
