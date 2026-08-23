
from app.core.roles import ExtractionMethod, RelationshipType, VerificationStatus
from app.services.llm_reference_extractor import extract_references_with_llm
from app.services.reference_extractor import extract_references, extract_references_hybrid

SAMPLE = (
    "Section 3 of the Penal Code Act, No. 2 of 1883 is hereby amended. "
    "The principal enactment is also referred to in this section."
)


def test_regex_extraction_still_finds_structured_citation():
    drafts = extract_references(SAMPLE)
    assert drafts
    assert any(draft.target_act_number == "2" for draft in drafts)


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
