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


    def budget_answer(self, intent, budget, checked):
        """Answer SCHEDULE_WITHIN_BUDGET from the saved schedule and the
        forecast labor budget. Only totals and per-day figures are returned;
        employee wages are never included."""
        if not checked["passed"]:
            return self._base("unsupported", intent["query_type"],
                              "The budget figures did not pass the rule "
                              "check, so I will not report them.", [], False,
                              intent.get("degraded", False))
        cost = budget["projected_labor_cost"]
        plan = budget["labor_budget"]
        gap = abs(round(plan - cost, 2))
        week = budget["week_start"]
        if budget["within_budget"]:
            verdict = f"within budget with ${gap:,.2f} to spare"
        else:
            verdict = f"over budget by ${gap:,.2f}"
        answer = (f"The projected labor cost for the week of {week} is "
                  f"${cost:,.2f} against a labor budget of ${plan:,.2f}: "
                  f"{verdict}.")
        if budget["draft_forecast"]:
            answer += " The forecast it is based on is not approved yet."
        response = self._base("answered", intent["query_type"], answer, [],
                              True, intent.get("degraded", False))
        if checked["violations"]:
            response["validation"]["over_budget_days"] = checked["violations"]
        response["budget"] = {
            "week_start": week,
            "projected_labor_cost": cost,
            "labor_budget": plan,
            "within_budget": budget["within_budget"],
            "days": budget["days"],
        }
        return response
