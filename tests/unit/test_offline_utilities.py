from datetime import UTC, datetime

import pytest

from src.utils.offline_utilities import convert_date, next_cron_runs, run_utility


def test_json_formatting_preserves_unicode_and_validation_reports_errors() -> None:
    assert run_utility("format-json", '{"name":"café","active":true}') == '{\n  "name": "café",\n  "active": true\n}'
    assert run_utility("validate-json", "[1, 2]") == "Valid JSON."
    with pytest.raises(ValueError):
        run_utility("validate-json", "{invalid}")


def test_xml_formatting_and_validation() -> None:
    assert run_utility("validate-xml", "<root><item /></root>") == "Valid XML."
    assert "<item/>" in run_utility("format-xml", "<root><item /></root>")
    with pytest.raises(ValueError, match="Invalid XML"):
        run_utility("format-xml", "<root>")


def test_text_comparison_reports_changes_and_equal_inputs() -> None:
    assert run_utility("compare-text", "same", "same") == "No differences."
    assert "line endings" in run_utility("compare-text", "same", "same\n")
    difference = run_utility("compare-text", "one\ntwo", "one\nthree")
    assert "-two" in difference
    assert "+three" in difference


def test_base64_round_trip_and_invalid_input() -> None:
    encoded = run_utility("base64-encode", "olá")
    assert run_utility("base64-decode", encoded) == "olá"
    with pytest.raises(ValueError, match="Invalid Base64"):
        run_utility("base64-decode", "not base64!")


def test_jwt_decodes_header_and_payload_without_claiming_verification() -> None:
    result = run_utility("decode-jwt", "eyJhbGciOiJub25lIn0.eyJzdWIiOiIxMjMifQ.signature")
    assert "signature is not verified" in result
    assert '"alg": "none"' in result
    assert '"sub": "123"' in result
    with pytest.raises(ValueError, match="three non-empty"):
        run_utility("decode-jwt", "not-a-jwt")


def test_generators_enforce_bounds() -> None:
    assert len(run_utility("generate-uuid", option="3").splitlines()) == 3
    lorem = run_utility("generate-lorem", option="2")
    assert lorem.count(".") == 2
    password = run_utility("generate-password", option="16")
    assert len(password) == 16
    assert any(character.islower() for character in password)
    assert any(character.isupper() for character in password)
    assert any(character.isdigit() for character in password)
    assert any(character in "!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~" for character in password)
    with pytest.raises(ValueError, match="between 4 and 256"):
        run_utility("generate-password", option="3")


def test_python_and_regex_validation() -> None:
    assert run_utility("validate-python", "value = 1") == "Valid Python syntax."
    with pytest.raises(SyntaxError):
        run_utility("validate-python", "if:")
    result = run_utility("test-regex", r"(cat)", "a cat and a catapult")
    assert "2 match(es)" in result
    assert "('cat',)" in result
    with pytest.raises(ValueError, match="Invalid regular expression"):
        run_utility("test-regex", "[", "text")


def test_cron_next_runs_and_sunday_numbering() -> None:
    start = datetime(2026, 10, 29, 12, 34, tzinfo=UTC)
    runs = next_cron_runs("*/15 * * * *", start=start)
    assert runs[:2] == [
        datetime(2026, 10, 29, 12, 45, tzinfo=UTC),
        datetime(2026, 10, 29, 13, 0, tzinfo=UTC),
    ]

    sunday_start = datetime(2026, 10, 25, 8, 59, tzinfo=UTC)
    sunday_runs = next_cron_runs("0 9 * * 0", start=sunday_start, count=1)
    assert sunday_runs == [datetime(2026, 10, 25, 9, 0, tzinfo=UTC)]
    with pytest.raises(ValueError, match="Invalid minute field"):
        next_cron_runs("60 * * * *", start=start)


def test_date_converter_accepts_iso_and_unix_timestamp() -> None:
    assert "UTC: 1970-01-01T00:00:00+00:00" in convert_date("0")
    assert "UTC: 2026-10-29T12:30:00+00:00" in convert_date("2026-10-29T12:30:00Z")
    with pytest.raises(ValueError, match="ISO 8601"):
        convert_date("yesterday")
