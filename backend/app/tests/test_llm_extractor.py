
from app.core.roles import ExtractionMethod, RelationshipType, VerificationStatus
from app.services.llm_reference_extractor import call_llm_json, extract_references_with_llm
from app.services.reference_extractor import (
    extract_act_references,
    extract_references,
    extract_references_hybrid,
)

SAMPLE = (
    "Section 3 of the Penal Code Act, No. 2 of 1883 is hereby amended. "
    "The principal enactment is also referred to in this section."
)


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


def test_gemini_provider_requests_schema_constrained_json(monkeypatch):
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "llm_provider", "gemini")
    monkeypatch.setattr(settings, "llm_model", "gemini-3.6-flash")
    monkeypatch.setattr(settings, "llm_api_key", "test-gemini-key")

    def fake_post(url, **kwargs):
        assert url.endswith("/gemini-3.6-flash:generateContent")
        generation_config = kwargs["json"]["generationConfig"]
        assert generation_config["responseMimeType"] == "application/json"
        assert generation_config["responseJsonSchema"]["type"] == "object"
        return FakeResponse(
            {"candidates": [{"content": {"parts": [{"text": '{"references": []}'}]}}]}
        )

    monkeypatch.setattr("httpx.post", fake_post)
    assert call_llm_json("Extract references") == {"references": []}


def test_openai_provider_returns_the_shared_reference_payload(monkeypatch):
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "llm_provider", "openai")
    monkeypatch.setattr(settings, "llm_model", "gpt-5.4-mini")
    monkeypatch.setattr(settings, "llm_api_key", "test-openai-key")

    expected = {"references": []}

    def fake_post(url, **kwargs):
        assert url == "https://api.openai.com/v1/chat/completions"
        assert kwargs["headers"]["Authorization"] == "Bearer test-openai-key"
        assert kwargs["json"]["response_format"]["type"] == "json_schema"
        return FakeResponse({"choices": [{"message": {"content": '{"references": []}'}}]})

    monkeypatch.setattr("httpx.post", fake_post)
    assert call_llm_json("Extract references") == expected


def test_provider_retries_once_after_a_transient_timeout(monkeypatch):
    import httpx

    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "llm_provider", "openai")
    monkeypatch.setattr(settings, "llm_model", "gpt-5.4-mini")
    monkeypatch.setattr(settings, "llm_api_key", "test-openai-key")
    attempts = 0

    def fake_post(_url, **_kwargs):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise httpx.TimeoutException("temporary timeout")
        return FakeResponse({"choices": [{"message": {"content": '{"references": []}'}}]})

    monkeypatch.setattr("httpx.post", fake_post)
    assert call_llm_json("Extract references") == {"references": []}
    assert attempts == 2


def test_anthropic_provider_returns_the_shared_reference_payload(monkeypatch):
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "llm_provider", "anthropic")
    monkeypatch.setattr(settings, "llm_model", "claude-haiku-4-5")
    monkeypatch.setattr(settings, "llm_api_key", "test-anthropic-key")

    def fake_post(url, **kwargs):
        assert url == "https://api.anthropic.com/v1/messages"
        assert kwargs["headers"]["x-api-key"] == "test-anthropic-key"
        assert kwargs["json"]["output_config"]["format"]["type"] == "json_schema"
        return FakeResponse({"content": [{"type": "text", "text": '{"references": []}'}]})

    monkeypatch.setattr("httpx.post", fake_post)
    assert call_llm_json("Extract references") == {"references": []}


def test_mistral_provider_uses_its_openai_compatible_endpoint(monkeypatch):
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "llm_provider", "mistral")
    monkeypatch.setattr(settings, "llm_model", "mistral-small-2603")
    monkeypatch.setattr(settings, "llm_api_key", "test-mistral-key")

    def fake_post(url, **kwargs):
        assert url == "https://api.mistral.ai/v1/chat/completions"
        assert kwargs["headers"]["Authorization"] == "Bearer test-mistral-key"
        return FakeResponse({"choices": [{"message": {"content": '{"references": []}'}}]})

    monkeypatch.setattr("httpx.post", fake_post)
    assert call_llm_json("Extract references") == {"references": []}


def test_custom_openai_compatible_provider_uses_configured_base_url(monkeypatch):
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "llm_provider", "openai-compatible")
    monkeypatch.setattr(settings, "llm_model", "local-legal-model")
    monkeypatch.setattr(settings, "llm_api_key", "local-key")
    monkeypatch.setattr(settings, "llm_base_url", "http://model-gateway:11434/v1/")

    def fake_post(url, **kwargs):
        assert url == "http://model-gateway:11434/v1/chat/completions"
        return FakeResponse({"choices": [{"message": {"content": '{"references": []}'}}]})

    monkeypatch.setattr("httpx.post", fake_post)
    assert call_llm_json("Extract references") == {"references": []}


def test_llm_cache_is_scoped_to_provider_and_model(monkeypatch):
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "llm_provider", "gemini")
    monkeypatch.setattr(settings, "llm_model", "gemini-3.6-flash")
    calls = []

    def fake_call(_prompt):
        calls.append((settings.llm_provider, settings.llm_model))
        return {"references": []}

    monkeypatch.setattr(
        "app.services.llm_reference_extractor.call_llm_json",
        fake_call,
    )
    assert extract_references_with_llm(SAMPLE) == []

    monkeypatch.setattr(settings, "llm_provider", "openai")
    monkeypatch.setattr(settings, "llm_model", "gpt-5.4-mini")
    assert extract_references_with_llm(SAMPLE) == []
    assert calls == [
        ("gemini", "gemini-3.6-flash"),
        ("openai", "gpt-5.4-mini"),
    ]


def test_regex_extraction_still_finds_structured_citation():
    drafts = extract_references(SAMPLE)
    assert drafts
    assert any(draft.target_act_number == "2" for draft in drafts)


def test_act_extraction_limits_llm_calls_to_configured_section_count(monkeypatch):
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "llm_extraction_enabled", True)
    monkeypatch.setattr(settings, "llm_max_sections_per_act", 2)
    calls: list[str] = []

    def caller(prompt: str):
        calls.append(prompt)
        return {"references": []}

    results = extract_act_references(
        [f"{SAMPLE} Section marker {index}." for index in range(5)],
        llm_caller=caller,
    )

    assert len(results) == 5
    assert len(calls) == 2


def test_llm_extractor_accepts_valid_payload(monkeypatch):
    payload = {
        "references": [
            {
                "raw_text": "Section 3 of the Penal Code, No. 2 of 1883",
                "relationship": "AMENDS",
                "target_act_title": "Penal Code",
                "target_act_number": "2",
                "target_act_year": 1883,
                "target_section_number": "3",
                "confidence": 0.82,
            }
        ]
    }
    drafts = extract_references_with_llm(SAMPLE, caller=lambda _prompt: payload)
    assert len(drafts) == 1
    assert drafts[0].extraction_method == ExtractionMethod.LLM
    assert drafts[0].relationship_type == RelationshipType.AMENDS
    assert drafts[0].verification_status == VerificationStatus.PENDING
    assert drafts[0].confidence_score == 0.82


def test_llm_extractor_drops_malformed_and_invented_numbers():
    payload = {
        "references": [
            {"raw_text": "x", "relationship": "NOT_A_TYPE", "confidence": 9},
            {
                "raw_text": "Act No. 99 of 2099",
                "relationship": "AMENDS",
                "target_act_number": "99",
                "target_act_year": 2099,
                "confidence": 0.9,
            },
        ]
    }
    drafts = extract_references_with_llm(
        "Section 3 of the Penal Code is hereby amended.",
        caller=lambda _prompt: payload,
    )
    assert drafts == []


def test_llm_timeout_returns_no_drafts():
    def boom(_prompt: str):
        raise TimeoutError("deadline")

    drafts = extract_references_with_llm(SAMPLE, caller=boom)
    assert drafts == []


def test_hybrid_merges_agreement_and_keeps_regex_on_llm_failure(monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "llm_extraction_enabled", True)

    regex = extract_references(SAMPLE)
    assert regex

    def echo(_prompt: str):
        draft = regex[0]
        return {
            "references": [
                {
                    "raw_text": draft.raw_reference_text,
                    "relationship": draft.relationship_type.value,
                    "target_act_title": draft.target_act_title_raw,
                    "target_act_number": draft.target_act_number,
                    "target_act_year": draft.target_act_year,
                    "target_section_number": draft.target_section_number,
                    "confidence": 0.8,
                },
                {
                    "raw_text": "the principal enactment",
                    "relationship": "AMENDS",
                    "target_act_title": "the principal enactment",
                    "confidence": 0.6,
                },
            ]
        }

    merged = extract_references_hybrid(SAMPLE, llm_caller=echo)
    assert any(item.extraction_method == ExtractionMethod.LLM for item in merged)
    llm_only = [item for item in merged if "principal enactment" in item.raw_reference_text.lower()]
    assert llm_only
    assert llm_only[0].verification_status == VerificationStatus.NEEDS_REVIEW

    def fail(_prompt: str):
        raise RuntimeError("provider down")

    fallback = extract_references_hybrid(SAMPLE, llm_caller=fail)
    assert [item.raw_reference_text for item in fallback] == [
        item.raw_reference_text for item in regex
    ]


def test_hybrid_disabled_path_matches_regex(monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "llm_extraction_enabled", False)
    assert [d.raw_reference_text for d in extract_references_hybrid(SAMPLE)] == [
        d.raw_reference_text for d in extract_references(SAMPLE)
    ]
