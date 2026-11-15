# The Response Builder builds the answer from a template 
# and attaches the supporting records.
# It must not add facts that did not come from the database.

class ResponseBuilder:

    def build(self, intent, results):

        query_type = intent.get("query_type")

        if query_type == "AVAILABLE_FOR_SHIFT":
            return self._build_available_response(intent, results)

        if query_type == "QUALIFIED_FOR_SHIFT":
            return self._build_qualified_response(intent, results)
        
        if query_type == "SCHEDULE_WITHIN_BUDGET":
            return self._build_budget_response(intent, results)

        return {
            "status": "unsupported",
            "answer": (
                "Supported query types are "
                "AVAILABLE_FOR_SHIFT, "
                "QUALIFIED_FOR_SHIFT, and"
                "SCHEDULE_WITHIN_BUDGET."
            ),
            "employees": [],
            "validation": {
                "passed": False
            },
            "degraded": intent.get("degraded", False)
        }

    def _build_available_response(self, intent, results):

         return {
             "status": "answered",
             "query_type": intent.get("query_type"),
             "answer": "Available employees found.",
             "employees": results,
             "validation": {
                 "passed": True
             },
             "degraded":intent.get("degraded", False)
         }

    def _build_qualified_response(self, intent, results):

        return {
            "status": "answered",
            "query_type": intent.get("query_type"),
            "answer": "Qualified employees found.",
            "employees": results,
            "validation": {
                "passed": True
            },
            "degraded": intent.get("degraded", False)
        }

    def _build_budget_response(self, intent, results):

        return {
            "status": "answered",
            "query_type": intent.get("query_type"),
            "answer": "Budget analysis not yet implemented.",
            "employees": [],
            "validation": {
                "passed": True
            },
            "degraded": intent.get("degraded", False)
        }