"""AssistantService.ask(question, user) (SDS section 8.6).

Runs the pipeline: IntentParser -> QueryPlanner -> RuleValidator ->
ResponseBuilder. Read-only. A problem with the AI never raises: the keyword
parser takes over and the response is marked degraded.
"""
import logging

from assistant.ResponseBuilder import ResponseBuilder
from assistant.RuleValidator import RuleValidator
from assistant.QueryPlanner import QueryPlanner
from assistant.IntentParser import IntentParser, UNSUPPORTED
from shared.exceptions import PermissionDeniedError, ValidationError

MIN_QUESTION_LENGTH = 3
MAX_QUESTION_LENGTH = 500
MANAGER_LEVEL = 2
log = logging.getLogger("assistant.queries")


class AssistantService:
    def __init__(self, data, ollama_client, today=None, budget=None):
        self.data = data
        self.parser = IntentParser(
            ollama_client,
            shift_names=list(data.shift_names().values()),
            role_names=(list(data.role_names().values())
                        + list(data.qualification_names().values())),
            today=today)
        self.planner = QueryPlanner(data, budget)
        self.validator = RuleValidator(data)
        self.builder = ResponseBuilder()

    def ask(self, question, user):
        if getattr(user, "system_role_id", 0) < MANAGER_LEVEL:
            raise PermissionDeniedError("AI Assistant requires the Manager role.")
        question = (question or "").strip()
        if len(question) < MIN_QUESTION_LENGTH or len(question) > MAX_QUESTION_LENGTH:
            raise ValidationError("Question must be 3 to 500 characters.")

        intent = self.parser.parse(question)
        if intent["query_type"] == UNSUPPORTED:
            response = self.builder.unsupported(intent["degraded"])
        else:
            plan = self.planner.execute(intent)
            if plan["status"] == "needs_clarification":
                response = self.builder.needs_clarification(intent, plan["message"])
            elif plan["status"] == "budget":
                response = self.builder.budget_answer(
                    intent, plan["budget"],
                    self.validator.validate_budget(plan["budget"]))
            elif plan["status"] == "unavailable":
                response = self.builder.unavailable(intent, plan["message"])
            elif plan["status"] == "unsupported":
                response = self.builder.unsupported(intent["degraded"])
            else:
                response = self.builder.answered(
                    intent, plan, self.validator.validate(plan))
        log.info("assistant query user=%s type=%s status=%s degraded=%s",
                 getattr(user, "id", "?"), response["query_type"],
                 response["status"], response["degraded"])
        return response
