from datetime import date
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import pytest

from src.utils import calendar_feed
from src.utils.calendar_feed import parse_today, validate_feed_url
from src.utils.config import Config


ZONE = ZoneInfo("America/Sao_Paulo")
TODAY = date(2026, 11, 10)


def feed(*events: str) -> bytes:
    return ("BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:-//Toolbox//Tests//EN\n" + "\n".join(
        f"BEGIN:VEVENT\nUID:{index}\n{event}\nEND:VEVENT" for index, event in enumerate(events)
    ) + "\nEND:VCALENDAR").encode()


def test_today_includes_all_day_overnight_and_local_times_in_order():
    events = parse_today(feed(
        "DTSTART:20261110T150000Z\nDTEND:20261110T160000Z\nSUMMARY:Lunch [literal]\nDESCRIPTION:Join https://meet.google.com/test",
        "DTSTART;VALUE=DATE:20261110\nDTEND;VALUE=DATE:20261111\nSUMMARY:Holiday",
        "DTSTART:20261109T230000\nDTEND:20261110T010000\nSUMMARY:Overnight",
        "DTSTART:20261111T030000Z\nSUMMARY:Tomorrow",
        "DTSTART:20261110T090000\nSUMMARY:Cancelled\nSTATUS:CANCELLED",
        "DTSTART;VALUE=DATE:20261109\nDTEND;VALUE=DATE:20261110\nSUMMARY:Yesterday",
        "DTSTART:20261110T100000\nSUMMARY:Floating",
    ), TODAY, ZONE)
    assert [event.title for event in events] == ["Holiday", "Overnight", "Floating", "Lunch [literal]"]
    assert events[0].all_day
    assert events[-1].start.hour == 12
    assert events[-1].link == "https://meet.google.com/test"
    assert events[2].start.hour == 10


def test_recurrences_exclusions_and_rescheduled_occurrences():
    data = b"""BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:daily
DTSTART;TZID=America/Sao_Paulo:20261101T090000
DTEND;TZID=America/Sao_Paulo:20261101T100000
RRULE:FREQ=DAILY
EXDATE;TZID=America/Sao_Paulo:20261109T090000
SUMMARY:Daily
END:VEVENT
BEGIN:VEVENT
UID:daily
RECURRENCE-ID;TZID=America/Sao_Paulo:20261110T090000
DTSTART;TZID=America/Sao_Paulo:20261110T140000
DTEND;TZID=America/Sao_Paulo:20261110T150000
SUMMARY:Moved daily
END:VEVENT
END:VCALENDAR"""
    assert not parse_today(data, date(2026, 11, 9), ZONE)
    events = parse_today(data, TODAY, ZONE)
    assert len(events) == 1
    assert events[0].title == "Moved daily"
    assert events[0].start.hour == 14


@pytest.mark.parametrize("url", ["", "http://example.com/a.ics", "file:///a.ics", "https://user:secret@example.com/a", "https://", "https://example.com:bad"])
def test_invalid_urls_are_rejected_without_secrets(url):
    with pytest.raises(ValueError, match="valid HTTPS") as error:
        validate_feed_url(url)
    assert "secret" not in str(error.value)


def test_webcal_and_https():
    assert validate_feed_url(" webcal://example.com/private.ics ") == "https://example.com/private.ics"
    assert validate_feed_url("https://example.com/a.ics") == "https://example.com/a.ics"


def test_fetch_timeout_size_limit_and_empty_feed(monkeypatch):
    response = MagicMock()
    response.url = "https://example.com/private.ics"
    response.read.return_value = feed()
    opener = MagicMock()
    opener.return_value.__enter__.return_value = response
    monkeypatch.setattr(calendar_feed, "urlopen", opener)
    assert calendar_feed.load_today(response.url) == []
    assert opener.call_args.kwargs["timeout"] == 15
    response.read.assert_called_once_with(calendar_feed.MAX_FEED_BYTES + 1)
    response.read.return_value = b"x" * (calendar_feed.MAX_FEED_BYTES + 1)
    with pytest.raises(ValueError, match="size limit"):
        calendar_feed.load_today(response.url)


def test_invalid_feed():
    with pytest.raises(ValueError):
        parse_today(b"<html>Login required</html>", TODAY, ZONE)


def test_local_day_boundaries_across_daylight_saving():
    events = parse_today(feed(
        "DTSTART:20261101T053000Z\nDTEND:20261101T063000Z\nSUMMARY:DST meeting",
        "DTSTART:20261102T043000Z\nDTEND:20261102T050000Z\nSUMMARY:Late meeting",
        "DTSTART:20261102T050000Z\nSUMMARY:Next day",
    ), date(2026, 11, 1), ZoneInfo("America/New_York"))
    assert [event.title for event in events] == ["DST meeting", "Late meeting"]
    assert events[0].start.hour == events[0].end.hour == 1
    assert events[0].start.utcoffset() != events[0].end.utcoffset()


def test_subscription_is_saved_only_to_override(tmp_path):
    defaults = tmp_path / "config.toml"
    defaults.write_text('[ui]\ntheme="textual-dark"\n', encoding="utf-8")
    override = tmp_path / "config.override.toml"
    settings = Config(defaults, override)
    assert settings.calendar_url == ""
    settings.update("calendar", "url", "https://example.com/private.ics")
    assert Config(defaults, override).calendar_url == "https://example.com/private.ics"
    assert "private" not in defaults.read_text(encoding="utf-8")
    settings.update("calendar", "url", "")
    assert Config(defaults, override).calendar_url == ""
