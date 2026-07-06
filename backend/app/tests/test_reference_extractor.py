from app.core.roles import RelationshipType, VerificationStatus
from app.services.reference_extractor import extract_references


def _refs_of_type(text: str, relationship_type: RelationshipType):
    return [
        reference
        for reference in extract_references(text)
        if reference.relationship_type == relationship_type
    ]


def test_extracts_amending_act_reference_with_chapter():
    refs = extract_references(
        "An Act To Amend The Poisons, Opium And Dangerous Drugs Ordinance (Chapter 218)"
    )

    amend_refs = [ref for ref in refs if ref.relationship_type == RelationshipType.AMENDS]
    assert amend_refs
    assert amend_refs[0].target_act_title_raw == "Poisons, Opium And Dangerous Drugs Ordinance"
    assert amend_refs[0].target_section_path == "Chapter 218"


def test_extracts_section_of_named_act_amendment():
    refs = extract_references(
        "Section 9 of the Judicature Act, No. 2 of 1978 is hereby amended "
        "by the repeal of paragraph (d) of subsection (1)."
    )

    assert any(
        ref.relationship_type == RelationshipType.AMENDS
        and ref.target_act_title_raw == "Judicature Act"
        and ref.target_act_number == "2"
        and ref.target_act_year == 1978
        and ref.target_section_number == "9"
        for ref in refs
    )


def test_extracts_insertion_of_new_section_after_existing_section():
    refs = extract_references(
        "The following new section is hereby inserted immediately after section 54A "
        "and shall have effect as section 54AA of the principal enactment."
    )

    assert any(
        ref.relationship_type == RelationshipType.INSERTS
        and ref.target_section_number == "54AA"
        and "after section 54A" in (ref.target_section_path or "")
        for ref in refs
    )


def test_extracts_repeal_of_paragraph_and_subsection():
    refs = extract_references("by the repeal of paragraph (d) of subsection (1)")

    assert any(
        ref.relationship_type == RelationshipType.REPEALS
        and ref.target_section_number == "(d)"
        and ref.target_section_path == "subsection (1) paragraph (d)"
        for ref in refs
    )


def test_extracts_substitution_language():
    refs = extract_references(
        "Section 54B is amended by the substitution for the words and figures "
        "appearing in that section."
    )

    assert any(ref.relationship_type == RelationshipType.SUBSTITUTES for ref in refs)


def test_extracts_addition_after_paragraph_and_new_item():
    refs = extract_references(
        "by the addition immediately after paragraph (d) of the following new item"
    )

    assert any(
        ref.relationship_type == RelationshipType.ADDS
        and ref.target_section_path == "paragraph (d)"
        for ref in refs
    )
    assert any(
        ref.relationship_type == RelationshipType.ADDS
        and ref.target_section_path == "new item"
        for ref in refs
    )


def test_extracts_schedule_amendment():
    refs = extract_references(
        "The First Schedule to the principal enactment is hereby amended by the addition "
        "of the following new item."
    )

    assert any(
        ref.relationship_type == RelationshipType.AMENDS
        and ref.target_section_path == "First Schedule"
        for ref in refs
    )


def test_extracts_chapter_reference():
    refs = extract_references("Poisons, Opium and Dangerous Drugs Ordinance (Chapter 218)")

    assert any(ref.target_act_title_raw == "Chapter 218" for ref in refs)


def test_extracts_act_no_and_act_comma_no_patterns():
    refs = extract_references(
        "An Act to amend the Social Security Contribution Levy Act, No. 25 of 2022. "
        "The Conventions Against Illicit Traffic in Narcotic Drugs and Psychotropic "
        "Substances Act No. 1 of 2008 is referred to."
    )

    assert any(ref.target_act_number == "25" and ref.target_act_year == 2022 for ref in refs)
    assert any(ref.target_act_number == "1" and ref.target_act_year == 2008 for ref in refs)


def test_deduplicates_repeated_raw_references_from_same_section():
    refs = extract_references("Section 54B is hereby amended. Section 54B is hereby amended.")
    repeated = [ref for ref in refs if ref.raw_reference_text.lower() == "section 54b"]

    assert len(repeated) == 1


def test_weak_cross_reference_is_marked_for_review():
    refs = extract_references("This shall apply in accordance with section 9.")
    assert refs[0].relationship_type == RelationshipType.CROSS_REFERENCE
    assert refs[0].verification_status in {
        VerificationStatus.PENDING,
        VerificationStatus.NEEDS_REVIEW,
    }


def test_bare_section_mention_with_no_operative_verb_is_not_extracted():
    """F-009 regression: a purely descriptive mention of a section number, with
    no amendment/repeal/insert/cross-reference language nearby, is noise (it
    doesn't identify which Act's section 12 is even meant) and should not
    create a reference row at all."""
    refs = extract_references(
        "The Committee discussed several matters, including section 12, before adjourning."
    )

    assert refs == []


def test_bare_subsection_and_item_mentions_without_operative_verb_are_dropped():
    refs = extract_references(
        "For illustration only, subsection (2) and item 5 are mentioned here as examples."
    )

    assert refs == []


def test_sentence_boundary_prevents_borrowing_verb_from_adjacent_sentence():
    """F-009 regression: a fixed-width context window used to bleed across
    sentence boundaries, so a bare section mention in one sentence could pick
    up an unrelated "is hereby amended" from a neighbouring sentence. With a
    sentence-bounded window, a purely descriptive sentence gets no reference
    even when the previous sentence contains real amendment language."""
    refs = extract_references(
        "Section 3 of the Judicature Act, No. 2 of 1978 is hereby amended. "
        "For general context, section 12 is mentioned in the explanatory memorandum."
    )

    bare_section_12 = [ref for ref in refs if ref.raw_reference_text.lower() == "section 12"]
    assert bare_section_12 == []


def test_generic_pattern_does_not_duplicate_a_strong_pattern_match():
    """F-009 regression: a bare "paragraph (d)"/"subsection (1)" match that
    falls entirely inside an already-captured structured amendment (e.g. "by
    the repeal of paragraph (d) of subsection (1)") is a redundant fragment
    of the same sentence, not a second, independent reference."""
    refs = extract_references(
        "Section 9 of the Judicature Act, No. 2 of 1978 is hereby amended by the "
        "repeal of paragraph (d) of subsection (1)."
    )

    bare_paragraph = [ref for ref in refs if ref.raw_reference_text.lower() == "paragraph (d)"]
    bare_subsection = [ref for ref in refs if ref.raw_reference_text.lower() == "subsection (1)"]
    assert bare_paragraph == []
    assert bare_subsection == []
    assert any(ref.relationship_type == RelationshipType.REPEALS for ref in refs)


def test_chapter_and_schedule_mentions_remain_ungated():
    """Chapter/Schedule mentions are identifying citations in their own right
    (like an Act number), so -- unlike bare section/subsection/paragraph/item
    numbers -- they should still be extracted without a nearby operative verb."""
    refs = extract_references("Poisons, Opium and Dangerous Drugs Ordinance (Chapter 218)")

    assert any(ref.target_act_title_raw == "Chapter 218" for ref in refs)
