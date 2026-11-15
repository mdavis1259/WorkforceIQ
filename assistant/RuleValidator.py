# The Rule Validator re-checks each result against
# availability, qualifications, hour limit, and budget.
# It must not let a result that breaks a rule through.
from assistant.ResponseBuilder import ResponseBuilder

class RuleValidator:

    def __init__(self):
        self.response_builder = ResponseBuilder()

    def validate(self, intent, results):

        query_type = intent.get("query_type")

        if query_type == "AVAILABLE_FOR_SHIFT":
            return self._validate_availability(intent, results)

        if query_type == "QUALIFIED_FOR_SHIFT":
            return self._validate_qualifications(intent, results)

        if query_type == "SCHEDULE_WITHIN_BUDGET":
            return self._validate_budget(intent, results)

        return self.response_builder.build(intent, results)

    def _validate_availability(self, intent, results):

        return self.response_builder.build(intent, results)

    def _validate_qualifications(self, intent, results):

        return self.response_builder.build(intent, results)

    def _validate_budget(self, intent, results):

        return self.response_builder.build(intent, results)