import pytest

from app.services.export_service import safe_csv_cell


@pytest.mark.parametrize(
    "value",
    [
        "=HYPERLINK(\"https://evil.example\",\"click\")",
        "+1+1",
        "-1+1",
        "@SUM(1+1)",
    ],
)
def test_safe_csv_cell_prefixes_risky_values(value):
    result = safe_csv_cell(value)
    assert result.startswith("'")
    assert result == f"'{value}"


@pytest.mark.parametrize("value", ["Section 5", "AMENDS", "12", 0.9, None, "", "Act No. 5"])
def test_safe_csv_cell_leaves_safe_values_untouched(value):
    result = safe_csv_cell(value)
    assert not result.startswith("'")
    assert result == ("" if value is None else str(value))
