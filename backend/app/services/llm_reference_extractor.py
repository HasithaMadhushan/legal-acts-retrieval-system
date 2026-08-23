from __future__ import annotations

import hashlib
import json
import logging
import re
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, Field, ValidationError, field_validator

from app.core.config import get_settings
from app.core.roles import ExtractionMethod, RelationshipType, VerificationStatus
from app.db.session import SessionLocal
from app.models.llm_extraction_cache import LlmExtractionCache
from app.services.reference_extractor import ReferenceDraft
from app.services.reference_normalizer import normalize_act_title, normalize_section_reference

logger = logging.getLogger(__name__)

ALLOWED_RELATIONSHIPS = {item.value for item in RelationshipType}

LLM_PROMPT = """You extract citations from Sri Lankan legal text.
Return JSON only with a "references" array. Each item has:
raw_text, relationship, target_act_title, target_act_number,
target_act_year, target_section_number, confidence.
Allowed relationship values: {relationships}.
Never invent Act numbers, years, or section numbers that are not written in the source text.
If a number is not present, omit it rather than guessing.
Include ADDS when the text adds a new provision.
Source text:
{text}
"""

JsonCaller = Callable[[str], dict[str, Any]]


class LlmReferenceItem(BaseModel):
    raw_text: str = Field(min_length=3, max_length=1000)
    relationship: str = RelationshipType.REFERS_TO.value
    target_act_title: str | None = None
    target_act_number: str | None = None
    target_act_year: int | None = None
    target_section_number: str | None = None
    confidence: float = 0.5

    @field_validator("confidence")
    @classmethod
    def clamp_confidence(cls, value: float) -> float:
        return max(0.0, min(float(value), 1.0))

    @field_validator("relationship")
    @classmethod
    def validate_relationship(cls, value: str) -> str:
        upper = value.upper()
        if upper not in ALLOWED_RELATIONSHIPS:
            raise ValueError("unsupported relationship")
        return upper


class LlmReferencePayload(BaseModel):
    references: list[LlmReferenceItem] = Field(default_factory=list)


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _source_numbers(text: str) -> set[str]:
    return set(re.findall(r"\d+", text))


def extract_references_with_llm(
    text: str,
    *,
    caller: JsonCaller | None = None,
) -> list[ReferenceDraft]:
    """Extract citations via an LLM. Returns [] on timeout, bad JSON, or invented numbers."""
    if not (text or "").strip():
        return []
    digest = _content_hash(text)
    use_cache = caller is None
    with SessionLocal() as db:
        cached = db.get(LlmExtractionCache, digest) if use_cache else None
        if cached is not None:
            payload = cached.response_json
        else:
            prompt = LLM_PROMPT.format(
                relationships=", ".join(sorted(ALLOWED_RELATIONSHIPS)),
                text=text[:8000],
            )
            try:
                payload = (caller or _call_gemini)(prompt)
            except Exception:
                logger.warning("llm_extraction_failed", exc_info=True)
                return []
            if use_cache:
                db.add(LlmExtractionCache(content_hash=digest, response_json=payload))
                try:
                    db.commit()
                except Exception:
                    db.rollback()
    try:
        parsed = LlmReferencePayload.model_validate(payload)
    except ValidationError:
        logger.warning("llm_extraction_invalid_payload")
        return []

    allowed_numbers = _source_numbers(text)
    drafts: list[ReferenceDraft] = []
    for item in parsed.references:
        if _is_invented_number(item, allowed_numbers):
            continue
        try:
            relationship = RelationshipType(item.relationship)
        except ValueError:
            continue
        confidence = item.confidence
        drafts.append(
            ReferenceDraft(
                raw_reference_text=item.raw_text.strip(),
                context_snippet=text[:280],
                relationship_type=relationship,
                target_act_title_raw=(
                    normalize_act_title(item.target_act_title) if item.target_act_title else None
                ),
                target_act_number=str(item.target_act_number) if item.target_act_number else None,
                target_act_year=item.target_act_year,
                target_section_number=normalize_section_reference(item.target_section_number),
                confidence_score=confidence,
                extraction_method=ExtractionMethod.LLM,
                verification_status=(
                    VerificationStatus.PENDING
                    if confidence >= 0.7
                    else VerificationStatus.NEEDS_REVIEW
                ),
            )
        )
    return drafts


def _is_invented_number(item: LlmReferenceItem, allowed_numbers: set[str]) -> bool:
    if item.target_act_number and item.target_act_number not in allowed_numbers:
        return True
    if item.target_act_year is not None and str(item.target_act_year) not in allowed_numbers:
        return True
    if item.target_section_number:
        section_digits = "".join(ch for ch in item.target_section_number if ch.isdigit())
        if section_digits and section_digits not in allowed_numbers:
            return True
    return False


def _call_gemini(prompt: str) -> dict[str, Any]:
    settings = get_settings()
    if not settings.llm_api_key:
        raise RuntimeError("LLM API key is not configured.")
    import httpx

    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{settings.llm_model}:generateContent"
    )
    response = httpx.post(
        url,
        params={"key": settings.llm_api_key},
        json={"contents": [{"parts": [{"text": prompt}]}]},
        timeout=20.0,
    )
    response.raise_for_status()
    data = response.json()
    text = data["candidates"][0]["content"]["parts"][0]["text"]
    text = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return json.loads(text)
