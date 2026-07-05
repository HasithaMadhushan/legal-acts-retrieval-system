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
