"""Read today's events from a read-only iCalendar subscription."""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, tzinfo
import re
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from icalendar import Calendar
import recurring_ical_events
from tzlocal import get_localzone


MAX_FEED_BYTES = 10 * 1024 * 1024


@dataclass(frozen=True)
class CalendarEvent:
    title: str
    start: datetime
    end: datetime
    all_day: bool
    location: str = ""
    link: str = ""


def validate_feed_url(value: str) -> str:
    """Require HTTPS, without including subscription secrets in errors."""
    value = value.strip()
    if value.startswith("webcal://"):
        value = "https://" + value[len("webcal://"):]
    try:
        parsed = urlsplit(value)
        valid = parsed.scheme == "https" and parsed.hostname and not parsed.username and not parsed.password
        parsed.port
    except ValueError:
        valid = False
    if not valid:
        raise ValueError("Enter a valid HTTPS iCal subscription URL.")
    return value


def parse_today(data: bytes, today: date, zone: tzinfo) -> list[CalendarEvent]:
    """Expand recurrences and select occurrences overlapping the local day."""
    calendar = Calendar.from_ical(data)
    if calendar.name != "VCALENDAR":
        raise ValueError("The response is not an iCalendar feed.")
    day_start = datetime.combine(today, time.min, zone)
    day_end = datetime.combine(today + timedelta(days=1), time.min, zone)

    def local_datetime(value: date | datetime) -> datetime:
        if not isinstance(value, datetime):
            return datetime.combine(value, time.min, zone)
        return value.replace(tzinfo=zone) if value.tzinfo is None else value.astimezone(zone)

    # Floating event times belong to the computer's local timezone.
    for component in calendar.walk("VEVENT"):
        for key in ("DTSTART", "DTEND", "RECURRENCE-ID"):
            prop = component.get(key)
            if prop is not None and isinstance(prop.dt, datetime) and prop.dt.tzinfo is None:
                prop.dt = prop.dt.replace(tzinfo=zone)

    result = []
    for event in recurring_ical_events.of(calendar).between(day_start, day_end):
        if str(event.get("STATUS", "")).upper() == "CANCELLED":
            continue
        start_value = event.decoded("DTSTART")
        all_day = not isinstance(start_value, datetime)
        start = local_datetime(start_value)
        end_value = event.decoded("DTEND", None)
        end = local_datetime(end_value) if end_value is not None else start + (
            event.decoded("DURATION", timedelta(days=1) if all_day else timedelta())
        )
        if not (start < day_end and (end > day_start or start == end and start >= day_start)):
            continue
        location = str(event.get("LOCATION", ""))
        link = str(event.get("URL", ""))
        if not link:
            match = re.search(r"https?://[^\s<>\"]+", location + " " + str(event.get("DESCRIPTION", "")))
            link = match.group(0) if match else ""
        result.append(CalendarEvent(str(event.get("SUMMARY", "Untitled event")), start, end, all_day, location, link))
    return sorted(result, key=lambda event: (not event.all_day, event.start, event.title.casefold()))


def load_today(url: str) -> list[CalendarEvent]:
    """Fetch with a timeout and size limit; callers must sanitize failures."""
    request = Request(validate_feed_url(url), headers={"User-Agent": "ToolboxTUI/Calendar"})
    with urlopen(request, timeout=15) as response:
        if urlsplit(response.url).scheme != "https":
            raise ValueError("Calendar redirects must use HTTPS.")
        data = response.read(MAX_FEED_BYTES + 1)
    if len(data) > MAX_FEED_BYTES:
        raise ValueError("Calendar feed exceeds the size limit.")
    zone = get_localzone()
    return parse_today(data, datetime.now(zone).date(), zone)
