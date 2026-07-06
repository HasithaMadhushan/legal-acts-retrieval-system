from datetime import date

from app.services.metadata_extractor import extract_metadata


def test_extracts_act_number_year_and_certified_date_from_act_comma_format():
    metadata = extract_metadata(
        """
        VALUE ADDED TAX (AMENDMENT) ACT
        Act, No. 10 of 2020
        Certified on 12th January 2020
        """,
        "fallback.pdf",
    )

    assert metadata.title == "Value Added Tax (Amendment) Act"
    assert metadata.act_number == "10"
    assert metadata.year == 2020
    assert metadata.certification_date == date(2020, 1, 12)
    assert metadata.confidence_score >= 0.9


def test_extracts_act_number_from_act_no_and_plain_no_formats():
    act_no = extract_metadata("TEST ACT\nAct No. 11 of 2021", "fallback.pdf")
    plain_no = extract_metadata("ANOTHER TEST ACT\nNo. 12 of 2022", "fallback.pdf")

    assert act_no.act_number == "11"
    assert act_no.year == 2021
    assert plain_no.act_number == "12"
    assert plain_no.year == 2022


def test_extracts_date_of_certification_and_publication_date():
    metadata = extract_metadata(
        """
        SAMPLE LEGAL ACT
        No. 20 of 2023
        Date of Certification: 5th March 2023
        Publication Date: 8th March 2023
        """,
        "fallback.pdf",
    )

    assert metadata.certification_date == date(2023, 3, 5)
    assert metadata.publication_date == date(2023, 3, 8)


def test_falls_back_to_filename_when_title_is_uncertain():
    metadata = extract_metadata("No useful heading here.", "sample_legal_act.pdf")

    assert metadata.title == "sample legal act"
    assert metadata.confidence_score < 0.5
    assert "source filename" in metadata.warnings[0]


def test_recognizes_ordinance_titles_not_just_act_titles():
    """F-010 regression: colonial-era Sri Lankan enactments are titled
    "... Ordinance", not "... Act", but are still in force and still amended
    (e.g. the Poisons, Opium and Dangerous Drugs Ordinance). These must be
    recognized as a confident title, not fall back to the filename."""
    metadata = extract_metadata(
        """
        POISONS, OPIUM AND DANGEROUS DRUGS ORDINANCE
        Ordinance No. 17 of 1929
        Certified on 3rd June 1929
        """,
        "fallback.pdf",
    )

    assert metadata.title == "Poisons, Opium And Dangerous Drugs Ordinance"
    assert metadata.act_number == "17"
    assert metadata.year == 1929
    assert metadata.confidence_score >= 0.9


def test_recognizes_ordinance_title_via_secondary_heading_scan():
    # Too long (> 220 chars) to qualify as a clean title line (primary pass),
    # but should still be picked up by the more lenient secondary scan since it
    # mentions "Ordinance".
    long_line = "A" * 250 + " Evidence Ordinance"
    metadata = extract_metadata(f"{long_line}\nActual content follows.", "fallback.pdf")

    assert "ordinance" in metadata.title.lower()
    assert metadata.confidence_score == 0.65


def test_finds_act_number_and_dates_beyond_first_4000_characters():
    """F-010 regression: the metadata scan window used to stop at 4000
    characters, missing the Act number/dates on Acts with a long preamble."""
    padding = "This is preamble filler text. " * 200  # ~6200 characters
    assert 4000 < len(padding) < 8000
    text = f"SAMPLE PADDED ACT\n{padding}\nAct, No. 33 of 2024\nCertified on 9th July 2024"

    metadata = extract_metadata(text, "fallback.pdf")

    assert metadata.act_number == "33"
    assert metadata.year == 2024
    assert metadata.certification_date == date(2024, 7, 9)
