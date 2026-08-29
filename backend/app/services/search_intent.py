"""Parse structured legal-identifier intent from a search query."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.core.roles import RelationshipType
from app.services.reference_normalizer import (
    normalize_act_number,
    normalize_act_title,
    normalize_relationship_type,
)
from app.services.text_cleaner import normalize_for_search

ACT_NUMBER_YEAR_RE = re.compile(
    r"\bNo\.?\s*(?P<number>\d+[A-Z]?)\s+of\s+(?P<year>\d{4})\b",
    re.I,
)
SECTION_IDENTIFIER_RE = re.compile(
    r"\b(?:section|sections|s\.|sec\.)\s+" r"(?P<number>\d+[A-Z]*)(?P<tail>(?:\([^)]+\))*)",
    re.I,
)
_LEADING_ARTICLE_RE = re.compile(r"^(the|an|a)\s+")
_ACT_TITLE_SUFFIX_RE = re.compile(r"(?:act|ordinance)$")
_TITLE_NOISE_TOKENS = frozenset(
    {
        "section",
        "sections",
        "amend",
        "amends",
        "repeal",
        "repeals",
        "insert",
        "inserts",
        "substitute",
        "substitutes",
    }
)

EXACT_IDENTIFIER_BOOST = 200.0


@dataclass(frozen=True)
class SearchIntent:
    raw_query: str
    act_number: str | None = None
    act_year: int | None = None
    act_title: str | None = None
    section_number: str | None = None
    section_path: str | None = None
    relationship_type: RelationshipType | None = None

    @property
    def has_act_identifier(self) -> bool:
        return self.act_number is not None and self.act_year is not None

    @property
    def has_section_identifier(self) -> bool:
        return bool(self.section_path or self.section_number)

    @property
    def has_exact_identifier(self) -> bool:
        return bool(self.has_act_identifier or self.has_section_identifier or self.act_title)


def parse_search_intent(query: str) -> SearchIntent:
    raw = (query or "").strip()
    if not raw:
        return SearchIntent(raw_query=raw)

    act_number, act_year, act_title = _parse_act_identifier(raw)
    section_number, section_path = _parse_section(raw)
    return SearchIntent(
        raw_query=raw,
        act_number=act_number,
        act_year=act_year,
        act_title=act_title,
        section_number=section_number,
        section_path=section_path,
        relationship_type=_parse_relationship(raw),
    )


def exact_identifier_boost(
    intent: SearchIntent,
    *,
    result_type: str,
    act_number: str | None = None,
    year: int | None = None,
    title: str | None = None,
    section_number: str | None = None,
    section_path: str | None = None,
) -> float:
    """Return a boost larger than the semantic 0–100 score scale for exact identifiers."""
    if result_type == "ACT" and _matches_exact_act(intent, act_number, year, title):
        return EXACT_IDENTIFIER_BOOST
    if result_type == "SECTION":
        section_matches = _matches_exact_section(intent, section_number, section_path)
        act_matches = _matches_exact_act(intent, act_number, year, title)
        has_act_context = intent.has_act_identifier or bool(intent.act_title)
        if intent.has_section_identifier and has_act_context:
            return EXACT_IDENTIFIER_BOOST if section_matches and act_matches else 0.0
        if intent.has_section_identifier and section_matches:
            return EXACT_IDENTIFIER_BOOST
        if has_act_context and act_matches:
            return EXACT_IDENTIFIER_BOOST
    return 0.0


def _matches_exact_act(
    intent: SearchIntent,
    act_number: str | None,
    year: int | None,
    title: str | None,
) -> bool:
    if intent.has_act_identifier:
        return normalize_act_number(act_number) == intent.act_number and year == intent.act_year
    return bool(intent.act_title and _as_act_title(title) == intent.act_title)


def _matches_exact_section(
    intent: SearchIntent,
    section_number: str | None,
    section_path: str | None,
) -> bool:
    if intent.section_path and intent.section_path != intent.section_number:
        return section_path == intent.section_path or section_number == intent.section_path
    if intent.section_number:
        return section_number == intent.section_number or section_path == intent.section_number
    return False


def _parse_act_identifier(query: str) -> tuple[str | None, int | None, str | None]:
    match = ACT_NUMBER_YEAR_RE.search(query)
    if not match:
        return None, None, _as_act_title(query)
    prefix = query[: match.start()].strip(" ,.;:")
    return (
        normalize_act_number(match.group("number")),
        int(match.group("year")),
        _as_act_title(prefix),
    )


def _parse_section(query: str) -> tuple[str | None, str | None]:
    match = SECTION_IDENTIFIER_RE.search(query)
    if not match:
        return None, None
    number = match.group("number")
    path = f"{number}{match.group('tail') or ''}"
    return number, path


def _as_act_title(value: str | None) -> str | None:
    if not value:
        return None
    title = _LEADING_ARTICLE_RE.sub("", normalize_act_title(value)).strip()
    tokens = title.split()
    if (
        not title
        or title in {"act", "ordinance"}
        or not _ACT_TITLE_SUFFIX_RE.search(title)
        or any(token in _TITLE_NOISE_TOKENS for token in tokens)
    ):
        return None
    return title


def _parse_relationship(query: str) -> RelationshipType | None:
    normalized = normalize_for_search(query)
    whole = normalize_relationship_type(normalized)
    if whole:
        return whole
    for token in normalized.split():
        found = normalize_relationship_type(token)
        if found:
            return found
    return None
