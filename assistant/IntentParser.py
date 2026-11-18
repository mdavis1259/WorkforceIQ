"""IntentParser (SDS section 7, step 2).

Asks Llama 3.2 (through OllamaClient) to turn the question into a JSON intent
and checks that it matches the expected format. If Ollama is down, too slow,
or returns invalid output twice, it switches to a keyword parser and marks
the intent degraded. The model's output is never trusted without checking.

The prompt contains only the question and the output format. It never
contains employee records.
"""
import difflib
import re
from datetime import date, datetime, timedelta

from assistant.OllamaClient import OllamaError

ALLOWED_QUERY_TYPES = (
    "AVAILABLE_FOR_SHIFT",
    "QUALIFIED_FOR_SHIFT",
    "SCHEDULE_WITHIN_BUDGET",
)
UNSUPPORTED = "UNSUPPORTED"
INTENT_FIELDS = ("query_type", "date", "shift_name", "role_name", "week_start")
WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday",
            "saturday", "sunday"]
MAX_LLM_ATTEMPTS = 2


class IntentError(Exception):
    """The parsed intent did not match the expected format."""


PROMPT_TEMPLATE = """You convert a manager's staffing question into JSON.
Reply with ONLY a JSON object with exactly these keys:
  "query_type": one of AVAILABLE_FOR_SHIFT, QUALIFIED_FOR_SHIFT, SCHEDULE_WITHIN_BUDGET, UNSUPPORTED
  "date": a weekday name, "today", "tomorrow", or YYYY-MM-DD, or null
  "shift_name": a shift name such as morning, afternoon or evening, or null
  "role_name": a job role name, or null
  "week_start": YYYY-MM-DD for budget questions, or null
Use names, never database IDs. Use null for anything the question does not say.
Use UNSUPPORTED if the question is not about who is available for a shift,
who is qualified for a shift, or whether a schedule stays within budget.

Question: {question}
"""


def build_prompt(question):
    return PROMPT_TEMPLATE.format(question=question)


def resolve_date(value, today):
    """Turn 'friday', 'today', 'tomorrow' or YYYY-MM-DD into an ISO date.
    Weekday names mean the next such day on or after today."""
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise IntentError("date must be text or null")
    text = value.strip().lower()
    if text == "today":
        return today.isoformat()
    if text == "tomorrow":
        return (today + timedelta(days=1)).isoformat()
    if text in WEEKDAYS:
        ahead = (WEEKDAYS.index(text) - today.weekday()) % 7
        return (today + timedelta(days=ahead)).isoformat()
    try:
        return datetime.strptime(text, "%Y-%m-%d").date().isoformat()
    except ValueError as error:
        raise IntentError(f"unrecognized date: {value!r}") from error


def _clean_name(value, field):
    if value is None:
        return None
    if not isinstance(value, str):
        raise IntentError(f"{field} must be text or null")
    value = value.strip()
    if len(value) > 60:
        raise IntentError(f"{field} is too long")
    return value or None


def validate_intent(raw, today):
    """Check model output against the expected format. Raises IntentError."""
    if not isinstance(raw, dict):
        raise IntentError("intent must be a JSON object")
    extra = set(raw) - set(INTENT_FIELDS)
    if extra:
        raise IntentError(f"unexpected keys: {sorted(extra)}")
    query_type = raw.get("query_type")
    if query_type not in ALLOWED_QUERY_TYPES and query_type != UNSUPPORTED:
        raise IntentError("query_type is not allowed")
    return {
        "query_type": query_type,
        "date": resolve_date(raw.get("date"), today),
        "shift_name": _clean_name(raw.get("shift_name"), "shift_name"),
        "role_name": _clean_name(raw.get("role_name"), "role_name"),
        "week_start": resolve_date(raw.get("week_start"), today),
    }


def find_day_in_question(question, today):
    """Find the day the manager typed, tolerating small typos ('fiday').
    Returns an ISO date or None. The model is never trusted for dates."""
    text = question.lower()
    iso = re.search(r"\d{4}-\d{2}-\d{2}", text)
    if iso:
        try:
            return resolve_date(iso.group(0), today)
        except IntentError:
            return None
    words = re.findall(r"[a-z]+", text)
    candidates = ["today", "tomorrow"] + WEEKDAYS
    for word in words:
        if word in candidates:
            return resolve_date(word, today)
    for word in words:
        if len(word) >= 4:
            close = difflib.get_close_matches(word, candidates, n=1,
                                              cutoff=0.8)
            if close:
                return resolve_date(close[0], today)
    return None


ROLE_STOP_WORDS = {"shift", "the", "a", "an", "for", "on", "as", "cover",
                   "who", "is", "are", "available", "qualified", "to"}


def names_a_known_role(text, role_names):
    """True if the text really names one of the known roles or
    qualifications (so junk copied from the question is rejected)."""
    wanted = text.lower().strip()
    words = set(re.findall(r"[a-z]+", wanted)) - ROLE_STOP_WORDS
    for name in role_names:
        full = name.lower()
        if wanted == full or wanted in full or full in wanted:
            return True
        if words & (set(re.findall(r"[a-z]+", full)) - ROLE_STOP_WORDS):
            return True
    return False


class KeywordIntentParser:
    """Simple fallback used when the model cannot be used."""

    def __init__(self, shift_names=(), role_names=()):
        self.shift_names = list(shift_names)
        self.role_names = list(role_names)

    def parse(self, question, today):
        text = question.lower()
        if "budget" in text or "over budget" in text:
            query_type = "SCHEDULE_WITHIN_BUDGET"
        elif "qualified" in text or "certified" in text:
            query_type = "QUALIFIED_FOR_SHIFT"
        elif "available" in text or "cover" in text or "free" in text:
            query_type = "AVAILABLE_FOR_SHIFT"
        else:
            query_type = UNSUPPORTED

        found_date = None
        iso = re.search(r"\d{4}-\d{2}-\d{2}", text)
        if iso:
            found_date = iso.group(0)
        else:
            for word in ["today", "tomorrow"] + WEEKDAYS:
                if re.search(rf"\b{word}\b", text):
                    found_date = word
                    break

        intent = {
            "query_type": query_type,
            "date": found_date,
            "shift_name": self._match(text, self.shift_names, first_word=True),
            "role_name": self._match(text, self.role_names),
            "week_start": found_date if query_type == "SCHEDULE_WITHIN_BUDGET"
            else None,
        }
        return validate_intent(intent, today)

    @staticmethod
    def _match(text, names, first_word=False):
        for name in names:
            key = name.lower().split()[0] if first_word else name.lower()
            if re.search(rf"\b{re.escape(key)}s?\b", text):
                return name
        return None


class IntentParser:
    def __init__(self, ollama_client, shift_names=(), role_names=(),
                 today=None):
        self.client = ollama_client
        self.keyword = KeywordIntentParser(shift_names, role_names)
        self._today = today  # injectable for tests

    def parse(self, question):
        """Return an intent dict that always includes a 'degraded' flag."""
        today = self._today() if callable(self._today) else (
            self._today or date.today())
        prompt = build_prompt(question)
        for _ in range(MAX_LLM_ATTEMPTS):
            try:
                intent = validate_intent(self.client.generate_json(prompt),
                                         today)
            except (OllamaError, IntentError):
                continue
            # A role the model made up from nothing is dropped.
            if (intent["role_name"] and not names_a_known_role(
                    intent["role_name"], self.keyword.role_names)):
                intent["role_name"] = None
            # Dates come from the question text, not from the model.
            day = find_day_in_question(question, today)
            intent["date"] = day
            intent["week_start"] = (day if intent["query_type"] ==
                                    "SCHEDULE_WITHIN_BUDGET" else None)
            intent["degraded"] = False
            return intent
        try:
            intent = self.keyword.parse(question, today)
        except IntentError:
            intent = {"query_type": UNSUPPORTED, "date": None,
                      "shift_name": None, "role_name": None,
                      "week_start": None}
        intent["degraded"] = True
        return intent
