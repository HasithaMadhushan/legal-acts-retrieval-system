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
    # Spans already captured by a specific, well-structured pattern (e.g. "Section 9
    # of the X Act ... is hereby amended"). Generic bare-number patterns matching
    # inside one of these spans are redundant fragments of the same statutory
    # sentence, not a separate reference (F-009).
    strong_spans: list[tuple[int, int]] = []

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
        is_strong: bool = False,
        require_operative_signal: bool = False,
    ) -> None:
        if not is_strong and any(
            start <= match.start() and match.end() <= end for start, end in strong_spans
        ):
            return
        # Sentence-bounded, not the wider fixed-width context: a fixed 160-char
        # window can bleed into an adjacent, unrelated sentence and pick up a verb
        # ("is hereby amended") that doesn't actually govern this match (F-009).
        sentence = _sentence_context(text, match.start(), match.end())
        needs_signal = require_operative_signal and not relationship_type
        if needs_signal and not _has_operative_signal(sentence):
            return
        context = _context(text, match.start(), match.end())
        detected_relationship = relationship_type or classify_relationship(sentence)
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
        if is_strong:
            strong_spans.append((match.start(), match.end()))
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
            is_strong=True,
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
            is_strong=True,
        )

    for match in PRINCIPAL_SECTION_AMENDED_RE.finditer(text):
        add(
            match,
            title="principal enactment",
            section=match.group("section"),
            path=match.group("section"),
            relationship_type=RelationshipType.AMENDS,
            is_strong=True,
        )

    for match in NEW_SECTION_INSERT_RE.finditer(text):
        path = f"after section {match.group('after')}; section {match.group('section')}"
        add(
            match,
            section=match.group("section"),
            path=path,
            relationship_type=RelationshipType.INSERTS,
            is_strong=True,
        )

    for match in EFFECT_AS_SECTION_RE.finditer(text):
        add(
            match,
            section=match.group("section"),
            path=match.group("section"),
            relationship_type=RelationshipType.INSERTS,
            is_strong=True,
        )

    for match in REPEAL_PARAGRAPH_RE.finditer(text):
        path = f"subsection ({match.group('subsection')}) paragraph ({match.group('paragraph')})"
        add(
            match,
            section=f"({match.group('paragraph')})",
            path=path,
            relationship_type=RelationshipType.REPEALS,
            is_strong=True,
        )

    for match in SUBSTITUTION_RE.finditer(text):
        add(match, relationship_type=RelationshipType.SUBSTITUTES, is_strong=True)

    for match in ADDITION_RE.finditer(text):
        target = match.group("target")
        target_type = match.group("target_type").lower()
        add(
            match,
            section=target,
            path=f"{target_type} {target}",
            relationship_type=RelationshipType.ADDS,
            is_strong=True,
        )

    for match in NEW_PARAGRAPH_ITEM_RE.finditer(text):
        add(
            match,
            path=f"new {match.group('target_type').lower()}",
            relationship_type=RelationshipType.ADDS,
            is_strong=True,
        )

    for match in SCHEDULE_AMENDMENT_RE.finditer(text):
        add(
            match,
            title="principal enactment",
            path=match.group("schedule").strip(),
            relationship_type=RelationshipType.AMENDS,
            is_strong=True,
        )

    for match in ACT_CITATION_RE.finditer(text):
        add(
            match,
            title=f"{match.group('title')} Act",
            number=match.group("number"),
            year=match.group("year"),
            is_strong=True,
        )

    # From here on, patterns match a bare structural number ("section 9",
    # "item 3", ...) with no Act name attached, which is ambiguous on its own
    # (it could be the source Act's own numbering, not a cross-reference at
    # all). Require some operative/relationship language in the same sentence
    # before creating a reference for these, to cut down on false positives
    # from purely descriptive mentions (F-009).
    for match in SECTION_RE.finditer(text):
        add(
            match,
            section=match.group("section"),
            path=match.group("section"),
            require_operative_signal=True,
        )

    for match in SUBSECTION_RE.finditer(text):
        subsection = f"({match.group('subsection')})"
        add(match, section=subsection, path=subsection, require_operative_signal=True)

    for match in PARAGRAPH_RE.finditer(text):
        paragraph = f"({match.group('paragraph')})"
        add(match, section=paragraph, path=paragraph, require_operative_signal=True)

    for match in ITEM_RE.finditer(text):
        add(
            match,
            section=match.group("item"),
            path=f"item {match.group('item')}",
            require_operative_signal=True,
        )

    # Chapter/Schedule mentions are kept ungated: unlike a bare section number,
    # "Chapter 218" or "the Second Schedule" is itself an identifying citation
    # (akin to an Act number) even without a nearby amendment verb.
    for match in SCHEDULE_RE.finditer(text):
        add(match, path=match.group("schedule").strip())

    for match in CHAPTER_RE.finditer(text):
        add(match, title=f"Chapter {match.group('chapter')}")

    return drafts


_LLM_GATE_RE = re.compile(r"\b(act|chapter|section)\s+\d", re.IGNORECASE)


def extract_references_hybrid(
    text: str,
    *,
    llm_caller=None,
    allow_llm: bool = True,
) -> list[ReferenceDraft]:
    """Regex first, then optional LLM merge. Fail open to regex on LLM errors."""
    regex_drafts = extract_references(text)
    from app.core.config import get_settings

    if not allow_llm or not get_settings().llm_extraction_enabled:
        return regex_drafts
    if not _LLM_GATE_RE.search(text or ""):
        return regex_drafts
    try:
        from app.services.llm_reference_extractor import extract_references_with_llm

        llm_drafts = extract_references_with_llm(text, caller=llm_caller)
    except Exception:
        return regex_drafts
    return _merge_reference_drafts(regex_drafts, llm_drafts)


def extract_act_references(
    section_texts: list[str],
    *,
    llm_caller=None,
) -> list[list[ReferenceDraft]]:
    """Extract every section with regex and cap optional LLM work per Act."""
    from app.core.config import get_settings

    llm_limit = max(0, get_settings().llm_max_sections_per_act)
    return [
        extract_references_hybrid(
            text,
            llm_caller=llm_caller,
            allow_llm=index < llm_limit,
        )
        for index, text in enumerate(section_texts)
    ]


def _fill_missing_targets(existing: ReferenceDraft, draft: ReferenceDraft) -> None:
    if draft.relationship_type != RelationshipType.UNKNOWN:
        existing.relationship_type = draft.relationship_type
    if draft.target_act_title_raw and not existing.target_act_title_raw:
        existing.target_act_title_raw = draft.target_act_title_raw
    if draft.target_act_number and not existing.target_act_number:
        existing.target_act_number = draft.target_act_number
    if draft.target_act_year and not existing.target_act_year:
        existing.target_act_year = draft.target_act_year
    if draft.target_section_number and not existing.target_section_number:
        existing.target_section_number = draft.target_section_number


def _merge_reference_drafts(
    regex_drafts: list[ReferenceDraft],
    llm_drafts: list[ReferenceDraft],
) -> list[ReferenceDraft]:
    merged: dict[str, ReferenceDraft] = {
        normalized_reference_key(draft.raw_reference_text): draft for draft in regex_drafts
    }
    for draft in llm_drafts:
        key = normalized_reference_key(draft.raw_reference_text)
        existing = merged.get(key)
        if existing is None:
            if draft.confidence_score >= 0.5:
                draft.verification_status = VerificationStatus.NEEDS_REVIEW
                merged[key] = draft
            continue
        existing.confidence_score = min(0.98, existing.confidence_score + 0.1)
        existing.extraction_method = ExtractionMethod.LLM
        _fill_missing_targets(existing, draft)
    return list(merged.values())


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


_ALL_RELATIONSHIP_PHRASES = tuple(
    phrase for phrases in RELATIONSHIP_PHRASES.values() for phrase in phrases
)


def _sentence_context(text: str, start: int, end: int) -> str:
    """Return the text of the sentence/clause containing `text[start:end]`.

    Bounded by the nearest '.', ';', or newline on either side (or the string
    boundaries), rather than a fixed character width, so relationship
    classification isn't influenced by an adjacent, unrelated sentence
    (F-009).
    """
    left_bound = max(
        text.rfind(".", 0, start), text.rfind(";", 0, start), text.rfind("\n", 0, start)
    )
    span_start = left_bound + 1 if left_bound != -1 else 0
    right_positions = [
        pos for pos in (text.find(".", end), text.find(";", end), text.find("\n", end)) if pos != -1
    ]
    span_end = min(right_positions) + 1 if right_positions else len(text)
    return " ".join(text[span_start:span_end].split())


def _has_operative_signal(sentence: str) -> bool:
    lowered = sentence.lower()
    return any(phrase in lowered for phrase in _ALL_RELATIONSHIP_PHRASES)


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
