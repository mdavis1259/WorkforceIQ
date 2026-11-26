"""Works out which week a budget question is about (SDS section 8.5: the
Query Planner works out words like 'next week' using the server date; the
model is never trusted for dates)."""
import re
from datetime import date, timedelta


def monday_of(day):
    return day - timedelta(days=day.weekday())


def resolve_week(question, today):
    """Return an ISO week_start for 'this week', 'next week', 'last week' or
    an explicit YYYY-MM-DD date in the question, otherwise None."""
    text = question.lower()
    iso = re.search(r"\d{4}-\d{2}-\d{2}", text)
    if iso:
        try:
            return date.fromisoformat(iso.group(0)).isoformat()
        except ValueError:
            return None
    if re.search(r"\bnext week\b", text):
        return (monday_of(today) + timedelta(days=7)).isoformat()
    if re.search(r"\blast week\b|\bprevious week\b", text):
        return (monday_of(today) - timedelta(days=7)).isoformat()
    if re.search(r"\bthis week\b|\bcurrent week\b|\bthe week\b", text):
        return monday_of(today).isoformat()
    return None
