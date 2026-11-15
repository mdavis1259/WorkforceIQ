# The Query Planner matches the intent to one of the 
# 3 allowed queries and looks up names in the database.
# It must not run any query outside the allowed list.
from assistant.RuleValidator import RuleValidator


class QueryPlanner:

    def __init__(self):
        self.rule_validator = RuleValidator()
        
    def execute(self, intent):

        query_type = intent.get("query_type")

        if query_type == "AVAILABLE_FOR_SHIFT":
            return self._available_for_shift(intent)

        if query_type == "QUALIFIED_FOR_SHIFT":
            return self._qualified_for_shift(intent)

        if query_type == "SCHEDULE_WITHIN_BUDGET":
            return self._schedule_within_budget(intent)

        return {
            "status": "unsupported",
            "degraded": intent.get("degraded", False)
        }

    def _available_for_shift(self, intent):

        results = []

        return self.rule_validator.validate(intent, results)


    def _qualified_for_shift(self, intent):

        results = []

        return self.rule_validator.validate(intent, results)    


    def _schedule_within_budget(self, intent):

        results = []

        return self.rule_validator.validate(intent, results)
    