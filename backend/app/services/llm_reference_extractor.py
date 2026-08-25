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


def _post_json_with_retry(url: str, **kwargs):
    """POST once, retrying one transient network or provider failure."""
    import httpx

    for attempt in range(2):
        try:
            response = httpx.post(url, **kwargs)
        except (httpx.TimeoutException, httpx.NetworkError):
            if attempt == 1:
                raise
            continue
        status_code = getattr(response, "status_code", 200)
        if attempt == 0 and (status_code == 429 or status_code >= 500):
            continue
        response.raise_for_status()
        return response
    raise RuntimeError("LLM request failed without a response.")


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
    settings = get_settings()
    cache_material = "\n".join(
        (
            "legal-reference-schema-v1",
            settings.llm_provider.strip().lower(),
            settings.llm_model.strip(),
            text,
        )
    )
    return hashlib.sha256(cache_material.encode("utf-8")).hexdigest()


def _source_numbers(text: str) -> set[str]:
    return set(re.findall(r"\d+", text))


def _fetch_llm_payload(
    text: str,
    *,
    caller: JsonCaller | None,
) -> dict[str, Any] | None:
    digest = _content_hash(text)
    use_cache = caller is None
    with SessionLocal() as db:
        cached = db.get(LlmExtractionCache, digest) if use_cache else None
        if cached is not None:
            return cached.response_json
        prompt = LLM_PROMPT.format(
            relationships=", ".join(sorted(ALLOWED_RELATIONSHIPS)),
            text=text[:8000],
        )
        try:
            payload = (caller or call_llm_json)(prompt)
        except Exception:
            logger.warning("llm_extraction_failed", exc_info=True)
            return None
        if use_cache:
            db.add(LlmExtractionCache(content_hash=digest, response_json=payload))
            try:
                db.commit()
            except Exception:
                db.rollback()
        return payload


def _draft_from_item(item: LlmReferenceItem, text: str) -> ReferenceDraft | None:
    try:
        relationship = RelationshipType(item.relationship)
    except ValueError:
        return None
    confidence = item.confidence
    return ReferenceDraft(
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
            VerificationStatus.PENDING if confidence >= 0.7 else VerificationStatus.NEEDS_REVIEW
        ),
    )


def extract_references_with_llm(
    text: str,
    *,
    caller: JsonCaller | None = None,
) -> list[ReferenceDraft]:
    """Extract citations via an LLM. Returns [] on timeout, bad JSON, or invented numbers."""
    if not (text or "").strip():
        return []
    payload = _fetch_llm_payload(text, caller=caller)
    if payload is None:
        return []
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
        draft = _draft_from_item(item, text)
        if draft is not None:
            drafts.append(draft)
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


def call_llm_json(prompt: str) -> dict[str, Any]:
    """Call the configured provider and return the shared extraction payload."""
    settings = get_settings()
    provider = settings.llm_provider.strip().lower().replace("-", "_")
    if provider == "gemini":
        return _call_gemini(prompt)
    if provider == "openai":
        return _call_openai_compatible(
            prompt,
            base_url="https://api.openai.com/v1",
            api_key=settings.llm_api_key,
            model=settings.llm_model,
        )
    if provider == "anthropic":
        return _call_anthropic(prompt)
    if provider == "mistral":
        return _call_openai_compatible(
            prompt,
            base_url="https://api.mistral.ai/v1",
            api_key=settings.llm_api_key,
            model=settings.llm_model,
        )
    if provider == "openai_compatible":
        if not settings.llm_base_url:
            raise RuntimeError("LLM_BASE_URL is required for an OpenAI-compatible provider.")
        return _call_openai_compatible(
            prompt,
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
            model=settings.llm_model,
        )
    raise ValueError(f"Unsupported LLM provider: {settings.llm_provider}")


def _call_gemini(prompt: str) -> dict[str, Any]:
    settings = get_settings()
    if not settings.llm_api_key:
        raise RuntimeError("LLM API key is not configured.")
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{settings.llm_model}:generateContent"
    )
    response = _post_json_with_retry(
        url,
        params={"key": settings.llm_api_key},
        json={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseJsonSchema": LlmReferencePayload.model_json_schema(),
                "temperature": 0,
            },
        },
        timeout=20.0,
    )
    data = response.json()
    text = data["candidates"][0]["content"]["parts"][0]["text"]
    text = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return json.loads(text)


def _call_openai_compatible(
    prompt: str,
    *,
    base_url: str,
    api_key: str | None,
    model: str,
) -> dict[str, Any]:
    if not api_key:
        raise RuntimeError("LLM API key is not configured.")
    response = _post_json_with_retry(
        f"{base_url.rstrip('/')}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "legal_references",
                    "strict": True,
                    "schema": LlmReferencePayload.model_json_schema(),
                },
            },
        },
        timeout=20.0,
    )
    data = response.json()
    return json.loads(data["choices"][0]["message"]["content"])


def _call_anthropic(prompt: str) -> dict[str, Any]:
    settings = get_settings()
    if not settings.llm_api_key:
        raise RuntimeError("LLM API key is not configured.")
    response = _post_json_with_retry(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": settings.llm_api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        },
        json={
            "model": settings.llm_model,
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": prompt}],
            "output_config": {
                "format": {
                    "type": "json_schema",
                    "schema": LlmReferencePayload.model_json_schema(),
                }
            },
        },
        timeout=20.0,
    )
    data = response.json()
    text_block = next(item for item in data["content"] if item.get("type") == "text")
    return json.loads(text_block["text"])
