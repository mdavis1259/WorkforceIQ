"""QueryPlanner (SDS section 7, step 3).

Matches the intent to one of the 3 allowed queries, looks up names (shift,
role) in the database, and runs the query through AssistantData. It never
runs anything outside the allowed list. Returns a plan result dict:
  {"status": "ready", "candidates": [...], "context": {...}}   or
  {"status": "needs_clarification" | "unsupported", "message": "..."}
"""
from assistant.IntentParser import ALLOWED_QUERY_TYPES


DAY_WORDS = {"monday", "tuesday", "wednesday", "thursday", "friday",
             "saturday", "sunday", "today", "tomorrow", "shift", "the", "a",
             "an", "for", "on", "as"}


def _find(name, options):
    """Return the (id, name) whose name matches the given text, or None.
    Day words are ignored, so 'Friday Evening' still finds 'Evening Shift'."""
    wanted = name.lower().strip()
    for option_id, option_name in options.items():
        full = option_name.lower()
        if wanted == full or wanted in full or full in wanted:
            return option_id, option_name
    words = {w for w in wanted.replace("-", " ").split()
             if w not in DAY_WORDS}
    for option_id, option_name in options.items():
        option_words = {w for w in option_name.lower().split()
                        if w not in DAY_WORDS}
        if words & option_words:
            return option_id, option_name
    return None


def _names(options):
    return ", ".join(sorted(options.values()))


class QueryPlanner:
    def __init__(self, data, budget=None):
        self.data = data
        self.budget = budget

    def execute(self, intent):
        query_type = intent.get("query_type")
        if query_type not in ALLOWED_QUERY_TYPES:
            return {"status": "unsupported"}
        if query_type == "AVAILABLE_FOR_SHIFT":
            return self._available_for_shift(intent)
        if query_type == "QUALIFIED_FOR_SHIFT":
            return self._qualified_for_shift(intent)
        return self._schedule_within_budget(intent)

    # -- AVAILABLE_FOR_SHIFT --------------------------------------
    def _available_for_shift(self, intent):
        if not intent.get("shift_name"):
            return self._clarify("Which shift do you mean (for example morning, afternoon or evening)?")
        if not intent.get("date"):
            return self._clarify("Which day do you mean (for example Friday or 2026-11-20)?")
        shift = _find(intent["shift_name"], self.data.shift_names())
        if shift is None:
            return self._clarify(f"I could not find a shift called '{intent['shift_name']}'. Known shifts: {_names(self.data.shift_names())}.")
        shift_id, shift_name = shift
        roles = self.data.role_names()
        available_ids = self.data.available_employee_ids(shift_id)
        candidates = [e for e in self.data.employees()
                      if e.employee_id in available_ids]
        role = None
        if intent.get("role_name"):
            role = _find(intent["role_name"], roles)
            if role is None:
                return self._clarify(f"I could not find a role called '{intent['role_name']}'. Known roles: {_names(roles)}.")
            candidates = [e for e in candidates if e.role_id == role[0]]
        return {"status": "ready", "candidates": candidates,
                "context": {"shift_id": shift_id, "shift_name": shift_name,
                            "date": intent["date"], "role": role,
                            "roles": roles, "qualifications": {}}}

    # -- QUALIFIED_FOR_SHIFT --------------------------------------
    def _qualified_for_shift(self, intent):
        intent = self._fix_swapped_fields(intent)
        if not intent.get("role_name"):
            return self._clarify("Which role or qualification do you mean (for example Server or Cook)?")
        roles = self.data.role_names()
        quals = self.data.qualification_names()
        role = _find(intent["role_name"], roles)
        qual = _find(intent["role_name"], quals)
        if role is None and qual is None:
            return self._clarify(f"I could not find a role or qualification called '{intent['role_name']}'. Known roles: {_names(roles)}. Known qualifications: {_names(quals)}.")
        employees = self.data.employees()
        candidates = [e for e in employees
                      if (role and e.role_id == role[0])
                      or (qual and qual[0] in e.qualification_ids)]
        shift = None
        if intent.get("shift_name"):
            shift = _find(intent["shift_name"], self.data.shift_names())
            if shift is None:
                return self._clarify(f"I could not find a shift called '{intent['shift_name']}'. Known shifts: {_names(self.data.shift_names())}.")
            ok = self.data.available_employee_ids(shift[0])
            candidates = [e for e in candidates if e.employee_id in ok]
        return {"status": "ready", "candidates": candidates,
                "context": {"shift_id": shift[0] if shift else None,
                            "shift_name": shift[1] if shift else None,
                            "date": intent.get("date"), "role": role,
                            "qualification": qual, "roles": roles,
                            "qualifications": quals}}

    def _fix_swapped_fields(self, intent):
        """Models sometimes put the role in shift_name (and sometimes in
        both fields). If shift_name is not a real shift but matches a role
        or qualification, treat it as the role and drop the shift."""
        if not intent.get("shift_name"):
            return intent
        if _find(intent["shift_name"], self.data.shift_names()):
            return intent
        text = intent["shift_name"]
        if (_find(text, self.data.role_names())
                or _find(text, self.data.qualification_names())):
            fixed = dict(intent)
            known_role = intent.get("role_name") and (
                _find(intent["role_name"], self.data.role_names())
                or _find(intent["role_name"], self.data.qualification_names()))
            if not known_role:
                fixed["role_name"] = text
            fixed["shift_name"] = None
            return fixed
        return intent

    # -- SCHEDULE_WITHIN_BUDGET -----------------------------------
    def _schedule_within_budget(self, intent):
        if self.budget is None:
            return {"status": "unavailable",
                    "message": "The budget check is not available yet. It "
                               "will work once weekly scheduling is "
                               "finished."}
        week = intent.get("week_start")
        if not week:
            return self._clarify("Which week do you mean (for example this "
                                 "week, next week, or 2026-11-30)?")
        result = self.budget.weekly_budget(week)
        if result is None:
            return {"status": "unavailable",
                    "message": f"No schedule has been generated for the "
                               f"week of {week}. Generate it on the "
                               f"Schedule page first."}
        if not result["has_assignments"]:
            return {"status": "unavailable",
                    "message": f"The schedule for the week of "
                               f"{result['week_start']} has no assignments "
                               f"yet."}
        if result["within_budget"] is None:
            days = ", ".join(result["missing_forecast_days"]) or "that week"
            return {"status": "unavailable",
                    "message": f"No forecast labor budget is saved for "
                               f"{days}, so cost cannot be compared. "
                               f"Generate the forecast first."}
        return {"status": "budget", "budget": result}

    @staticmethod
    def _clarify(message):
        return {"status": "needs_clarification", "message": message}
