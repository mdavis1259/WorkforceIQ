"""RuleValidator (SDS section 7, step 5).

Re-checks every candidate against the rules and removes any employee who
fails one. Rule violations use the SDS 8.7 shape {rule, employee_id, issue}.
Rules checked here: AVAILABILITY, QUALIFICATION. WEEKLY_HOUR_LIMIT, OVERLAP
and BUDGET need schedule data from the Scheduling module (US-8) and are added
when that module is available.
"""


class RuleValidator:
    def __init__(self, data):
        self.data = data

    def validate(self, plan):
        context = plan["context"]
        passed, violations = [], []
        available = (self.data.available_employee_ids(context["shift_id"])
                     if context.get("shift_id") is not None else None)
        for employee in plan["candidates"]:
            problems = []
            if available is not None and employee.employee_id not in available:
                problems.append(("AVAILABILITY",
                                 f"Not marked available for {context['shift_name']}"))
            role = context.get("role")
            qual = context.get("qualification")
            if role or qual:
                has_role = bool(role) and employee.role_id == role[0]
                has_qual = bool(qual) and qual[0] in employee.qualification_ids
                if not (has_role or has_qual):
                    problems.append(("QUALIFICATION",
                                     "Does not hold the required role or qualification"))
            if problems:
                violations.extend({"rule": rule, "employee_id": employee.employee_id,
                                   "issue": issue} for rule, issue in problems)
            else:
                passed.append(employee)
        return {"employees": passed, "violations": violations}
