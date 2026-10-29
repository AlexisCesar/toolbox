"""Pure-Python helpers for the offline utilities view."""

from __future__ import annotations

import ast
import base64
import binascii
import difflib
import json
import re
import secrets
import string
import uuid
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from xml.dom import minidom


@dataclass(frozen=True)
class Utility:
    """A tool shown in the searchable utilities catalog."""

    id: str
    name: str
    category: str
    description: str
    input_label: str = "Input"
    second_input_label: str | None = None
    option_label: str | None = None
    option_default: str = ""


UTILITIES = (
    Utility("format-json", "Format JSON", "Formatters", "Validate and pretty-print JSON."),
    Utility("format-xml", "Format XML", "Formatters", "Validate and indent XML."),
    Utility(
        "compare-text", "Compare text", "Text",
        "Show the differences between two text snippets.", "Text A", "Text B",
    ),
    Utility("base64-encode", "Encode Base64", "Encoders / Decoders", "Encode UTF-8 text as Base64."),
    Utility("base64-decode", "Decode Base64", "Encoders / Decoders", "Decode Base64 text as UTF-8."),
    Utility(
        "decode-jwt", "Decode JWT", "Encoders / Decoders",
        "Decode a JWT header and payload without verifying its signature.",
    ),
    Utility(
        "generate-uuid", "Generate UUIDs", "Generators",
        "Generate one or more random UUID version 4 values.",
        option_label="Count", option_default="1",
    ),
    Utility("generate-lorem", "Generate Lorem Ipsum", "Generators", "Generate placeholder text.", option_label="Sentence count", option_default="3"),
    Utility(
        "generate-password", "Generate password", "Generators",
        "Generate a cryptographically random password.",
        option_label="Length (4–256)", option_default="24",
    ),
    Utility("validate-json", "Validate JSON", "Validators / Testers", "Check whether input is valid JSON."),
    Utility("validate-xml", "Validate XML", "Validators / Testers", "Check whether input is well-formed XML."),
    Utility("validate-python", "Validate Python syntax", "Validators / Testers", "Check Python source syntax without executing it."),
    Utility(
        "test-regex", "Test regular expression", "Validators / Testers",
        "Find matches for a Python regular expression.", "Regular expression", "Text",
    ),
    Utility(
        "cron-next-runs", "Cron next runs", "Converters",
        "Validate a numeric five-field cron expression and show its next five local run times.",
    ),
    Utility(
        "convert-date", "Convert date / timestamp", "Converters",
        "Convert an ISO 8601 date or Unix timestamp to local time, UTC, and Unix seconds.",
    ),
)

_LOREM_SENTENCES = (
    "Lorem ipsum dolor sit amet, consectetur adipiscing elit.",
    "Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.",
    "Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat.",
    "Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur.",
    "Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt mollit anim id est laborum.",
)


def run_utility(
    utility_id: str,
    text: str = "",
    second_text: str = "",
    option: str = "",
) -> str:
    """Run one utility and return its displayable result."""
    if utility_id in {"format-json", "validate-json"}:
        value = json.loads(text)
        if utility_id == "validate-json":
            return "Valid JSON."
        return json.dumps(value, indent=2, ensure_ascii=False)

    if utility_id in {"format-xml", "validate-xml"}:
        try:
            root = ET.fromstring(text)
        except ET.ParseError as error:
            raise ValueError(f"Invalid XML: {error}") from error
        if utility_id == "validate-xml":
            return "Valid XML."
        formatted = minidom.parseString(ET.tostring(root, encoding="utf-8"))
        return formatted.toprettyxml(indent="  ", encoding=None).strip()

    if utility_id == "compare-text":
        if text == second_text:
            return "No differences."
        difference = difflib.unified_diff(
            text.splitlines(), second_text.splitlines(),
            fromfile="Text A", tofile="Text B", lineterm="",
        )
        result = "\n".join(difference)
        return result or "The text differs only by line endings."

    if utility_id == "base64-encode":
        return base64.b64encode(text.encode("utf-8")).decode("ascii")

    if utility_id == "base64-decode":
        try:
            return base64.b64decode(text, validate=True).decode("utf-8")
        except (binascii.Error, UnicodeDecodeError, ValueError) as error:
            raise ValueError(f"Invalid Base64 or non-UTF-8 content: {error}") from error

    if utility_id == "decode-jwt":
        parts = text.strip().split(".")
        if len(parts) != 3 or not all(parts):
            raise ValueError("A JWT must contain three non-empty dot-separated parts.")
        header = _decode_jwt_json_part(parts[0], "header")
        payload = _decode_jwt_json_part(parts[1], "payload")
        return (
            "JWT signature is not verified.\n\n"
            "Header:\n"
            f"{json.dumps(header, indent=2, ensure_ascii=False)}\n\n"
            "Payload:\n"
            f"{json.dumps(payload, indent=2, ensure_ascii=False)}"
        )

    if utility_id == "generate-uuid":
        count = _parse_bounded_int(option, "Count", 1, 100)
        return "\n".join(str(uuid.uuid4()) for _ in range(count))

    if utility_id == "generate-lorem":
        count = _parse_bounded_int(option, "Sentence count", 1, 100)
        return " ".join(
            _LOREM_SENTENCES[index % len(_LOREM_SENTENCES)]
            for index in range(count)
        )

    if utility_id == "generate-password":
        length = _parse_bounded_int(option, "Length", 4, 256)
        groups = (
            string.ascii_lowercase,
            string.ascii_uppercase,
            string.digits,
            string.punctuation,
        )
        characters = [secrets.choice(group) for group in groups]
        alphabet = "".join(groups)
        characters.extend(secrets.choice(alphabet) for _ in range(length - len(characters)))
        secrets.SystemRandom().shuffle(characters)
        return "".join(characters)

    if utility_id == "validate-python":
        ast.parse(text)
        return "Valid Python syntax."

    if utility_id == "test-regex":
        try:
            matches = list(re.finditer(text, second_text))
        except re.error as error:
            raise ValueError(f"Invalid regular expression: {error}") from error
        if not matches:
            return "No matches."
        lines = [f"{len(matches)} match(es):"]
        for index, match in enumerate(matches, start=1):
            lines.append(
                f"{index}. {match.group(0)!r} at [{match.start()}, {match.end()})"
            )
            if match.groups():
                lines.append(f"   groups: {match.groups()!r}")
        return "\n".join(lines)

    if utility_id == "cron-next-runs":
        return "\n".join(run.isoformat(sep=" ", timespec="minutes") for run in next_cron_runs(text))

    if utility_id == "convert-date":
        return convert_date(text)

    raise ValueError(f"Unknown utility: {utility_id}")


def _parse_bounded_int(value: str, label: str, minimum: int, maximum: int) -> int:
    try:
        result = int(value)
    except ValueError as error:
        raise ValueError(f"{label} must be a whole number.") from error
    if not minimum <= result <= maximum:
        raise ValueError(f"{label} must be between {minimum} and {maximum}.")
    return result


def _decode_jwt_json_part(part: str, label: str) -> object:
    try:
        padded = part + "=" * (-len(part) % 4)
        decoded = base64.b64decode(padded.encode("ascii"), altchars=b"-_", validate=True)
        value = json.loads(decoded)
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"The JWT {label} is not valid Base64URL-encoded JSON.") from error
    if not isinstance(value, dict):
        raise ValueError(f"The JWT {label} must be a JSON object.")
    return value


def convert_date(value: str) -> str:
    """Convert an ISO 8601 datetime or integer Unix timestamp."""
    candidate = value.strip()
    if not candidate:
        raise ValueError("Enter an ISO 8601 datetime or Unix timestamp.")

    try:
        timestamp = int(candidate)
    except ValueError:
        timestamp = None

    if timestamp is not None:
        try:
            parsed = datetime.fromtimestamp(timestamp, tz=UTC).astimezone()
        except (OverflowError, OSError, ValueError) as error:
            raise ValueError(f"Unix timestamp is out of range: {error}") from error
    else:
        try:
            parsed = datetime.fromisoformat(candidate.replace("Z", "+00:00"))
        except ValueError as error:
            raise ValueError(
                "Use an ISO 8601 datetime (for example, 2026-10-29T12:30:00Z) "
                "or Unix timestamp."
            ) from error
        if parsed.tzinfo is None:
            parsed = parsed.astimezone()

    utc_value = parsed.astimezone(UTC)
    return (
        f"Local: {parsed.isoformat()}\n"
        f"UTC: {utc_value.isoformat()}\n"
        f"Unix seconds: {int(parsed.timestamp())}"
    )


def next_cron_runs(
    expression: str,
    start: datetime | None = None,
    count: int = 5,
) -> list[datetime]:
    """Return upcoming local times for a standard five-field cron expression."""
    if not 1 <= count <= 100:
        raise ValueError("The number of upcoming runs must be between 1 and 100.")
    fields = expression.split()
    if len(fields) != 5:
        raise ValueError("Use a standard five-field cron expression: minute hour day month weekday.")

    minute_values = _parse_cron_field(fields[0], 0, 59, "minute")
    hour_values = _parse_cron_field(fields[1], 0, 23, "hour")
    day_values = _parse_cron_field(fields[2], 1, 31, "day of month")
    month_values = _parse_cron_field(fields[3], 1, 12, "month")
    weekday_values = _parse_cron_field(fields[4], 0, 7, "weekday")
    weekdays = {(day + 6) % 7 for day in weekday_values}

    current = start or datetime.now().astimezone()
    if current.tzinfo is None:
        current = current.astimezone()
    first_minute = current.replace(second=0, microsecond=0) + timedelta(minutes=1)
    day_of_month_wildcard = fields[2] == "*"
    weekday_wildcard = fields[4] == "*"
    matches: list[datetime] = []

    for day_offset in range(366 * 5 + 2):
        date = (first_minute + timedelta(days=day_offset)).date()
        if date.month not in month_values:
            continue
        dom_matches = date.day in day_values
        dow_matches = date.weekday() in weekdays
        if day_of_month_wildcard and weekday_wildcard:
            day_matches = True
        elif day_of_month_wildcard:
            day_matches = dow_matches
        elif weekday_wildcard:
            day_matches = dom_matches
        else:
            day_matches = dom_matches or dow_matches
        if not day_matches:
            continue

        for hour in sorted(hour_values):
            for minute in sorted(minute_values):
                candidate = datetime.combine(
                    date, datetime.min.time(), tzinfo=current.tzinfo
                ).replace(hour=hour, minute=minute)
                if candidate >= first_minute and (not matches or candidate > matches[-1]):
                    matches.append(candidate)
                    if len(matches) == count:
                        return matches

    raise ValueError(f"Could not find {count} upcoming runs within five years for this expression.")


def _parse_cron_field(field: str, minimum: int, maximum: int, name: str) -> set[int]:
    values: set[int] = set()
    try:
        for part in field.split(","):
            if not part:
                raise ValueError
            range_part, slash, step_text = part.partition("/")
            step = int(step_text) if slash else 1
            if step < 1:
                raise ValueError

            if range_part == "*":
                lower, upper = minimum, maximum
            elif "-" in range_part:
                lower_text, upper_text = range_part.split("-", maxsplit=1)
                lower, upper = int(lower_text), int(upper_text)
            else:
                lower = int(range_part)
                upper = maximum if slash else lower
            if lower < minimum or upper > maximum or lower > upper:
                raise ValueError
            values.update(range(lower, upper + 1, step))
    except ValueError as error:
        raise ValueError(f"Invalid {name} field in cron expression: {field!r}.") from error
    return values
