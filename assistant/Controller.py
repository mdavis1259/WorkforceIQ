# The Controller checks login and role, 
# and checks the length of the question.
# It must not contain business logic.
from flask import jsonify
from flask_login import current_user

from shared.exceptions import (PermissionDeniedError, ValidationError)
from assistant.IntentParser import IntentParser


class Controller:

    MAX_QUESTION_LENGTH = 500
    MIN_QUESTION_LENGTH = 3

    def __init__(self):
        self.intent_parser = IntentParser()

    def query(self, request):

        # role check
        if current_user.system_role_id < 2:
            
            raise PermissionDeniedError(
                "AI Assistant requires Manager role."
            )

        question = request.form.get("question", "").strip()

        if not question:
        
            raise ValidationError("Please type a question.")

        # length validation
        if len(question) < self.MIN_QUESTION_LENGTH:

            raise ValidationError("Question must be at least 3 characters.")


        if len(question) > self.MAX_QUESTION_LENGTH:

            raise ValidationError("Question exceeds maximum length.")

        # hand off to next pipeline stage
        return self.intent_parser.parse(question)

    def health(self):

        return jsonify({
            "status": "healthy"
        })