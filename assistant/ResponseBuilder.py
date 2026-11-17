"""ResponseBuilder (SDS section 7, step 6).

Builds the answer from a template and attaches the supporting records. Every
fact in the answer comes from the database results, never from the model.
Wages are never included.
"""
SUPPORTED_TEXT = ("I can answer three kinds of questions: who is available "
                  "for a shift, who is qualified for a shift, and whether a "
                  "schedule stays within budget.")


def _plural(count, word):
    return f"{count} {word}" + ("" if count == 1 else "s")


class ResponseBuilder:
    def unsupported(self, degraded):
        return self._base("unsupported", None, SUPPORTED_TEXT, [], True, degraded)

    def needs_clarification(self, intent, message):
        return self._base("needs_clarification", intent.get("query_type"),
                          message, [], True, intent.get("degraded", False))

    def unavailable(self, intent, message):
        return self._base("unsupported", intent.get("query_type"), message,
                          [], True, intent.get("degraded", False))

    def answered(self, intent, plan, checked):
        context = plan["context"]
        roles = context.get("roles", {})
        people = [{
            "employee_id": e.employee_id,
            "name": f"{e.first_name} {e.last_name}",
            "role": roles.get(e.role_id, ""),
            "reasons": self._reasons(intent, context, e),
        } for e in checked["employees"]]
        count = _plural(len(people), "employee")
        shift = context.get("shift_name")
        day = context.get("date")
        where = f" for the {shift}" if shift else ""
        when = f" on {day}" if day else ""
        if intent["query_type"] == "AVAILABLE_FOR_SHIFT":
            answer = f"{count} {'is' if len(people) == 1 else 'are'} available{where}{when}."
        else:
            role = (context.get("role") or context.get("qualification") or ("", ""))[1]
            answer = f"{count} {'is' if len(people) == 1 else 'are'} qualified as {role}{where}{when}."
        # Anyone who broke a rule was already removed by the RuleValidator,
        # so every returned employee passes. Removed ones are listed.
        return self._base("answered", intent["query_type"], answer, people,
                          True, intent.get("degraded", False),
                          checked["violations"])

    @staticmethod
    def _reasons(intent, context, employee):
        reasons = []
        if context.get("shift_name"):
            reasons.append(f"Marked available for {context['shift_name']}")
        role = context.get("role")
        if role and employee.role_id == role[0]:
            reasons.append(f"Role: {role[1]}")
        qual = context.get("qualification")
        if qual and qual[0] in employee.qualification_ids:
            reasons.append(f"Qualification: {qual[1]}")
        return reasons

    @staticmethod
    def _base(status, query_type, answer, employees, passed, degraded,
              violations=None):
        validation = {"passed": passed}
        if violations:
            validation["removed"] = violations
        return {"status": status, "query_type": query_type, "answer": answer,
                "employees": employees, "validation": validation,
                "degraded": degraded}
