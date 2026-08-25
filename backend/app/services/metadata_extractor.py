import re
from dataclasses import dataclass
from datetime import date

from app.services.text_cleaner import normalize_for_search

DATE_TEXT_RE = r"\d{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+\s+\d{4}"
ACT_NUMBER_RE = re.compile(
    r"\b(?:Act\s*,?\s*)?No\.?\s*(?P<number>\d+[A-Za-z]?)\s+of\s+(?P<year>\d{4})\b",
    re.I,
)
ACT_NUMBER_SUFFIX_RE = re.compile(
    r",?\s*No\.?\s*\d+[A-Za-z]?\s+of\s+\d{4}\b",
    re.I,
)
CERTIFIED_RES = [
    re.compile(rf"\bCertified\s+on\s+(?P<date>{DATE_TEXT_RE})", re.I),
    re.compile(rf"\bDate\s+of\s+Certification\s*:?\s*(?P<date>{DATE_TEXT_RE})", re.I),
]
PUBLICATION_RES = [
    re.compile(rf"\bPublished\s+on\s+(?P<date>{DATE_TEXT_RE})", re.I),
    re.compile(rf"\bDate\s+of\s+Publication\s*:?\s*(?P<date>{DATE_TEXT_RE})", re.I),
    re.compile(rf"\bPublication\s+Date\s*:?\s*(?P<date>{DATE_TEXT_RE})", re.I),
]
TITLE_NOISE_RE = re.compile(
    r"\b("
    r"parliament|democratic socialist republic|sri lanka|gazette|printed|published|"
    r"arrangement of sections|certified on|date of certification|supplement"
    r"|can be downloaded|documents\.gov\.lk"
    r")\b",
    re.I,
)
# Sri Lankan enactments are titled either "... Act" (post-independence) or "...
# Ordinance" (colonial-era, still in force and still amended today, e.g. the
# Poisons, Opium and Dangerous Drugs Ordinance). Both must be recognized as a
# legal-act-shaped title, not just "Act" (F-010).
TITLE_DESIGNATOR_RE = re.compile(r"\b(act|ordinance)\b", re.I)
# How far into the document to look for the Act/Ordinance number, year, and
# certification/publication dates. Some Acts have a longer preamble (multi-page
# gazette header, long titles, etc.) that pushes this metadata past the first
# ~4000 characters (F-010).
METADATA_SCAN_WINDOW = 8000


@dataclass
class ExtractedMetadata:
    title: str
    normalized_title: str
    act_number: str | None
    year: int | None
    certification_date: date | None = None
    publication_date: date | None = None
    confidence_score: float = 0.0
    warnings: list[str] | None = None


def extract_metadata(text: str, fallback_title: str) -> ExtractedMetadata:
    first_lines = [line.strip() for line in text.splitlines()[:40] if line.strip()]
    scan_window = text[:METADATA_SCAN_WINDOW]
    act_match = ACT_NUMBER_RE.search(scan_window)
    warnings: list[str] = []

    title, title_confidence = _extract_title(first_lines, fallback_title)
    if title_confidence < 0.5:
        warnings.append("Act title was inferred from the source filename.")

    if not act_match:
        warnings.append("Act number and year were not detected near the beginning of the text.")

    certification_date = _find_date(scan_window, CERTIFIED_RES)
    publication_date = _find_date(scan_window, PUBLICATION_RES)
    confidence_score = _metadata_confidence(
        title_confidence=title_confidence,
        has_act_number=bool(act_match),
        has_certification_date=bool(certification_date),
    )

    return ExtractedMetadata(
        title=title,
        normalized_title=normalize_for_search(title),
        act_number=act_match.group("number") if act_match else None,
        year=int(act_match.group("year")) if act_match else None,
        certification_date=certification_date,
        publication_date=publication_date,
        confidence_score=confidence_score,
        warnings=warnings,
    )


def _extract_title(first_lines: list[str], fallback_title: str) -> tuple[str, float]:
    for index, line in enumerate(first_lines):
        line_without_number = _remove_act_number(line)
        if _looks_like_title(line_without_number):
            return _clean_title(line_without_number), 0.9

        if ACT_NUMBER_RE.search(line):
            previous_title = _previous_title(first_lines, index)
            if previous_title:
                return _clean_title(previous_title), 0.85
            if index > 0:
                combined_title = f"{first_lines[index - 1]} {line_without_number}"
                if _looks_like_title(combined_title):
                    return _clean_title(combined_title), 0.85

    for line in first_lines[:20]:
        if TITLE_DESIGNATOR_RE.search(line) and not TITLE_NOISE_RE.search(line):
            title = _remove_act_number(line)
            if len(title) >= 8:
                return _clean_title(title), 0.65

    return _clean_title(fallback_title.rsplit(".", 1)[0].replace("_", " ")), 0.35


def _previous_title(first_lines: list[str], index: int) -> str | None:
    candidates: list[str] = []
    for line in reversed(first_lines[max(0, index - 3) : index]):
        if _looks_like_title(line):
            candidates.insert(0, line)
        elif candidates:
            break
    if not candidates:
        return None
    return " ".join(candidates)


def _looks_like_title(value: str) -> bool:
    value = value.strip(" -:;")
    if len(value) < 8 or len(value) > 220:
        return False
    if TITLE_NOISE_RE.search(value):
        return False
    has_designator_word = bool(TITLE_DESIGNATOR_RE.search(value))
    mostly_upper = value.upper() == value and any(char.isalpha() for char in value)
    return has_designator_word and (mostly_upper or len(value) < 160)


def _remove_act_number(value: str) -> str:
    return ACT_NUMBER_SUFFIX_RE.sub("", value).strip(" ,-:;")


def _clean_title(value: str) -> str:
    value = re.sub(r"\s+", " ", value).strip(" -:;")
    value = re.sub(r"\s*-\s*", "-", value)
    return value.title() if value.isupper() else value


def _find_date(text: str, patterns: list[re.Pattern[str]]) -> date | None:
    for pattern in patterns:
        match = pattern.search(text)
        if match:
            parsed = _parse_loose_date(match.group("date"))
            if parsed:
                return parsed
    return None


def _metadata_confidence(
    *, title_confidence: float, has_act_number: bool, has_certification_date: bool
) -> float:
    score = title_confidence
    if has_act_number:
        score += 0.08
    if has_certification_date:
        score += 0.04
    return min(round(score, 2), 0.98)


def _parse_loose_date(value: str) -> date | None:
    value = re.sub(r"(\d{1,2})(st|nd|rd|th)", r"\1", value, flags=re.I)
    for fmt in ("%d %B %Y", "%d %b %Y"):
        try:
            from datetime import datetime

            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None
