"""Controller (SDS section 7, step 1).

Checks login and role and the question length, then hands off to
AssistantService. It contains no business logic.
"""
from flask import current_app
from flask_login import current_user

from assistant.AssistantService import AssistantService
from assistant.AssistantData import build_default_data
from assistant.OllamaClient import OllamaClient


class Controller:
    def _service(self):
        factory = current_app.config.get("ASSISTANT_SERVICE_FACTORY")
        if factory:
            return factory()
        return AssistantService(build_default_data(), OllamaClient())

    def query(self, question):
        # Role and length are checked inside AssistantService.ask so the
        # same rules protect every entry point (SDS 8.8).
        return self._service().ask(question, current_user)

    def health(self):
        return {"status": "healthy",
                "ollama": "up" if OllamaClient().is_available() else "down"}
