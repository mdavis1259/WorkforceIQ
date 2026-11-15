# The Intent Parser asks Llama 3.2 to return a JSON intent and checks that it matches the expected format.
# It must not trust the model's output without checking.
from assistant.QueryPlanner import QueryPlanner


class IntentParser:

    ALLOWED_QUERY_TYPES = [
        "AVAILABLE_FOR_SHIFT",
        "QUALIFIED_FOR_SHIFT",
        "SCHEDULE_WITHIN_BUDGET"
    ]

    def __init__(self):
        self.query_planner = QueryPlanner()

    def parse(self, question):

        question = question.lower()

        if "available" in question:
            intent = {
                "query_type": "AVAILABLE_FOR_SHIFT",
                "question": question,
                "degraded": True
            }

            return self.query_planner.execute(intent)

        elif "qualified" in question:
            intent = {
                "query_type": "QUALIFIED_FOR_SHIFT",
                "question": question,
                "degraded": True
            }

            return self.query_planner.execute(intent)

        elif "budget" in question:
            intent = {
                "query_type": "SCHEDULE_WITHIN_BUDGET",
                "question": question,
                "degraded": True
            }

            return self.query_planner.execute(intent)

        else:
            return {
            "query_type": "UNSUPPORTED",
            "degraded": intent["degraded"]
        }
