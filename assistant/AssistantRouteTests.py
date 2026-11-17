"""Route tests: JSON API status codes and error format."""
import os
import tempfile
import unittest

from flask import Flask, render_template_string
from flask_login import LoginManager, UserMixin, login_user
from jinja2 import DictLoader

from assistant.AssistantRoutes import ai_bp
from assistant.AssistantService import AssistantService
from assistant.AssistantTests import FakeClient, make_data, TODAY
from assistant.OllamaClient import OllamaError


class U(UserMixin):
    def __init__(self, role):
        self.id, self.system_role_id = str(role), role


def make_app(client):
    app = Flask(__name__)
    app.secret_key = "t"
    app.jinja_loader = __import__("jinja2").ChoiceLoader([
        DictLoader({"base.html": "{% block content %}{% endblock %}"}),
        app.jinja_loader])
    app.config["ASSISTANT_SERVICE_FACTORY"] = lambda: AssistantService(
        make_data(), client, today=TODAY)
    lm = LoginManager(app)
    lm.user_loader(lambda uid: U(int(uid)))

    @app.route("/login/<int:role>")
    def login(role):
        login_user(U(role))
        return "ok"
    app.register_blueprint(ai_bp)
    return app


class AssistantRouteTests(unittest.TestCase):
    def signed_in(self, role, client=None):
        client = client or FakeClient(OllamaError("x"), OllamaError("x"))
        c = make_app(client).test_client()
        c.get(f"/login/{role}")
        return c

    def test_manager_gets_answer(self):
        r = self.signed_in(2).post("/api/assistant/query",
                                   json={"question": "Who is available Friday evening?"})
        self.assertEqual(r.status_code, 200)
        body = r.get_json()
        self.assertEqual(body["status"], "answered")
        self.assertTrue(body["degraded"])

    def test_associate_gets_403_error_format(self):
        r = self.signed_in(1).post("/api/assistant/query", json={"question": "Who is available?"})
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.get_json()["error"]["code"], "PERMISSION_DENIED")

    def test_short_question_400(self):
        r = self.signed_in(2).post("/api/assistant/query", json={"question": "hi"})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.get_json()["error"]["code"], "VALIDATION_ERROR")

    def test_login_required(self):
        c = make_app(FakeClient()).test_client()
        self.assertIn(c.post("/api/assistant/query", json={"question": "abc"}).status_code, (302, 401))

    def test_page_renders_answer_and_error(self):
        c = self.signed_in(2)
        page = c.post("/ai", data={"question": "Who is available Friday evening?"})
        self.assertEqual(page.status_code, 200)
        self.assertIn(b"Ana Ruiz", page.data)
        self.assertIn(b"keyword search", page.data)
        self.assertIn(b"3 to 500", c.post("/ai", data={"question": "x"}).data)
        self.assertEqual(c.get("/ai").status_code, 200)


if __name__ == "__main__":
    unittest.main()
