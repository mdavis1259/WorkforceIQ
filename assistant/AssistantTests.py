"""Tests for the AI Assistant pipeline. No real Ollama or database needed."""
import unittest
from datetime import date
from types import SimpleNamespace

import requests

from assistant.AssistantData import AssistantData
from assistant.AssistantService import AssistantService
from assistant.IntentParser import (IntentError, IntentParser, build_prompt,
                                    resolve_date, validate_intent)
from assistant.OllamaClient import OllamaClient, OllamaError
from shared.exceptions import PermissionDeniedError, ValidationError

TODAY = date(2026, 11, 16)  # a Monday


def emp(i, first, last, role_id, quals=(), active=True):
    return SimpleNamespace(employee_id=i, first_name=first, last_name=last,
                           role_id=role_id, hourly_rate=99.0, active=active,
                           qualification_ids=tuple(quals))


ROLES = [{"role_id": 1, "role_name": "Server"}, {"role_id": 2, "role_name": "Cook"}]
QUALS = [{"qualification_id": 10, "qualification_name": "Food Handler"}]
EMPLOYEES = [emp(1, "Ana", "Ruiz", 1, [10]), emp(2, "Ben", "Lee", 2),
             emp(3, "Cy", "Fox", 1), emp(4, "Di", "Old", 1, active=False),
             emp(5, "Eli", "Gray", 1)]
AVAIL = [
    {"employee_id": 1, "shift_id": 3, "shift_name": "Evening Shift", "availability": 0},
    {"employee_id": 2, "shift_id": 3, "shift_name": "Evening Shift", "availability": 0},
    {"employee_id": 3, "shift_id": 3, "shift_name": "Evening Shift", "availability": 2},
    {"employee_id": 4, "shift_id": 3, "shift_name": "Evening Shift", "availability": 0},
    {"employee_id": 5, "shift_id": 3, "shift_name": "Evening Shift", "availability": 1},
    {"employee_id": 1, "shift_id": 1, "shift_name": "Morning Shift", "availability": 0},
]


def make_data():
    return AssistantData(lambda: EMPLOYEES, lambda: ROLES, lambda: QUALS,
                         lambda: AVAIL)


class FakeClient:
    """Stands in for OllamaClient. Records prompts, replays outputs."""
    def __init__(self, *outputs):
        self.outputs = list(outputs)
        self.prompts = []

    def generate_json(self, prompt):
        self.prompts.append(prompt)
        out = self.outputs.pop(0)
        if isinstance(out, Exception):
            raise out
        return out


MANAGER = SimpleNamespace(system_role_id=2, id=5)
ASSOCIATE = SimpleNamespace(system_role_id=1, id=6)


def service(client):
    return AssistantService(make_data(), client, today=TODAY)


class OllamaClientTests(unittest.TestCase):
    class Resp:
        def __init__(self, body, ok=True):
            self.body, self.ok = body, ok
        def raise_for_status(self):
            if not self.ok:
                raise requests.HTTPError("500")
        def json(self):
            return self.body

    def client(self, resp=None, error=None):
        calls = []
        def post(url, json=None, timeout=None):
            calls.append((url, json, timeout))
            if error:
                raise error
            return resp
        c = OllamaClient(http_post=post)
        c.calls = calls
        return c

    def test_sends_sds_request_and_parses_json(self):
        c = self.client(self.Resp({"response": '{"query_type": "UNSUPPORTED"}'}))
        self.assertEqual(c.generate_json("hi"), {"query_type": "UNSUPPORTED"})
        url, payload, timeout = c.calls[0]
        self.assertEqual(url, "http://localhost:11434/api/generate")
        self.assertEqual(payload["model"], "llama3.2")
        self.assertEqual(payload["format"], "json")
        self.assertIs(payload["stream"], False)
        self.assertEqual(payload["options"], {"temperature": 0})
        self.assertEqual(timeout, 10)

    def test_connection_error_and_timeout(self):
        for err in (requests.ConnectionError("down"), requests.Timeout("slow")):
            with self.assertRaises(OllamaError):
                self.client(error=err).generate_json("x")

    def test_bad_output(self):
        for body in ({"response": "not json"}, {"response": "[1]"}, {"nope": 1}, "x"):
            with self.assertRaises(OllamaError):
                self.client(self.Resp(body)).generate_json("x")

    def test_http_error(self):
        with self.assertRaises(OllamaError):
            self.client(self.Resp({}, ok=False)).generate_json("x")


class IntentTests(unittest.TestCase):
    def test_resolve_date(self):
        self.assertEqual(resolve_date("friday", TODAY), "2026-11-20")
        self.assertEqual(resolve_date("Monday", TODAY), "2026-11-16")
        self.assertEqual(resolve_date("tomorrow", TODAY), "2026-11-17")
        self.assertEqual(resolve_date("2026-12-01", TODAY), "2026-12-01")
        self.assertIsNone(resolve_date(None, TODAY))
        with self.assertRaises(IntentError):
            resolve_date("sometime", TODAY)

    def test_validate_rejects_bad_output(self):
        for raw in ("text", {"query_type": "DROP_TABLE"},
                    {"query_type": "AVAILABLE_FOR_SHIFT", "employee_id": 3},
                    {"query_type": "AVAILABLE_FOR_SHIFT", "date": 5}):
            with self.assertRaises(IntentError):
                validate_intent(raw, TODAY)

    def test_prompt_has_only_question_and_format(self):
        prompt = build_prompt("Who is free Friday?")
        self.assertIn("Who is free Friday?", prompt)
        for secret in ("Ana", "Ruiz", "hourly", "99.0"):
            self.assertNotIn(secret, prompt)

    def parser(self, client):
        return IntentParser(client, ["Morning Shift", "Evening Shift"],
                            ["Server", "Cook"], today=TODAY)

    def test_llm_path_not_degraded(self):
        c = FakeClient({"query_type": "AVAILABLE_FOR_SHIFT", "date": "friday",
                        "shift_name": "evening", "role_name": None, "week_start": None})
        intent = self.parser(c).parse("Who can cover Friday evening?")
        self.assertFalse(intent["degraded"])
        self.assertEqual(intent["date"], "2026-11-20")

    def test_typo_day_is_understood(self):
        c = FakeClient({"query_type": "AVAILABLE_FOR_SHIFT", "date": "2026-11-17",
                        "shift_name": "evening"})
        intent = self.parser(c).parse("who is available to cover fiday evening shift")
        self.assertEqual(intent["date"], "2026-11-20")

    def test_model_guessed_date_is_ignored(self):
        c = FakeClient({"query_type": "AVAILABLE_FOR_SHIFT", "date": "2026-11-17",
                        "shift_name": "evening"})
        intent = self.parser(c).parse("who is available for the evening shift")
        self.assertIsNone(intent["date"])

    def test_retries_once_then_succeeds(self):
        good = {"query_type": "UNSUPPORTED"}
        c = FakeClient({"junk": 1}, good)
        intent = self.parser(c).parse("hello there")
        self.assertFalse(intent["degraded"])
        self.assertEqual(len(c.prompts), 2)

    def test_falls_back_to_keywords_when_ollama_down(self):
        c = FakeClient(OllamaError("down"), OllamaError("down"))
        intent = self.parser(c).parse("Who is available Friday evening?")
        self.assertTrue(intent["degraded"])
        self.assertEqual(intent["query_type"], "AVAILABLE_FOR_SHIFT")
        self.assertEqual(intent["shift_name"], "Evening Shift")
        self.assertEqual(intent["date"], "2026-11-20")

    def test_falls_back_on_invalid_json_twice(self):
        c = FakeClient({"query_type": "NOPE"}, "garbage")
        self.assertTrue(self.parser(c).parse("who is qualified as a cook?")["degraded"])

    def test_keyword_unsupported(self):
        c = FakeClient(OllamaError("x"), OllamaError("x"))
        intent = self.parser(c).parse("What is the weather?")
        self.assertEqual(intent["query_type"], "UNSUPPORTED")
        self.assertTrue(intent["degraded"])


class ServiceTests(unittest.TestCase):
    def ask(self, intent, question="Who is available Friday evening?", user=MANAGER):
        return service(FakeClient(intent)).ask(question, user)

    def test_available_for_shift(self):
        r = self.ask({"query_type": "AVAILABLE_FOR_SHIFT", "date": "friday",
                      "shift_name": "evening", "role_name": None, "week_start": None})
        self.assertEqual(r["status"], "answered")
        self.assertEqual([e["name"] for e in r["employees"]], ["Ana Ruiz", "Ben Lee"])
        self.assertTrue(r["validation"]["passed"])
        self.assertFalse(r["degraded"])
        self.assertIn("2 employees are available", r["answer"])
        self.assertIn("2026-11-20", r["answer"])

    def test_inactive_unavailable_and_unspecified_excluded(self):
        r = self.ask({"query_type": "AVAILABLE_FOR_SHIFT", "date": "friday",
                      "shift_name": "evening"})
        ids = [e["employee_id"] for e in r["employees"]]
        self.assertNotIn(3, ids)
        self.assertNotIn(4, ids)
        self.assertNotIn(5, ids)

    def test_no_wages_in_response(self):
        r = self.ask({"query_type": "AVAILABLE_FOR_SHIFT", "date": "friday",
                      "shift_name": "evening"})
        self.assertNotIn("99.0", str(r))
        self.assertNotIn("hourly", str(r))

    def test_missing_day_asks_for_it(self):
        s = service(FakeClient({"query_type": "AVAILABLE_FOR_SHIFT",
                                "date": "2026-11-17", "shift_name": "evening"}))
        r = s.ask("who is available for the evening shift", MANAGER)
        self.assertEqual(r["status"], "needs_clarification")
        self.assertIn("day", r["answer"])

    def test_day_inside_shift_name_still_matches(self):
        r = self.ask({"query_type": "AVAILABLE_FOR_SHIFT", "date": "friday",
                      "shift_name": "Friday Evening"})
        self.assertEqual(r["status"], "answered")
        self.assertEqual(len(r["employees"]), 2)

    def test_role_put_in_shift_field_is_fixed(self):
        r = self.ask({"query_type": "QUALIFIED_FOR_SHIFT", "shift_name": "cook"})
        self.assertEqual(r["status"], "answered")
        self.assertEqual([e["name"] for e in r["employees"]], ["Ben Lee"])

    def test_junk_role_from_model_is_ignored(self):
        s = service(FakeClient({"query_type": "AVAILABLE_FOR_SHIFT", "date": None,
                                "shift_name": "evening",
                                "role_name": "fiday evening shift cover"}))
        r = s.ask("who is available to cover fiday evening shift", MANAGER)
        self.assertEqual(r["status"], "answered")
        self.assertEqual(len(r["employees"]), 2)

    def test_swapped_fields_with_junk_role(self):
        s = service(FakeClient({"query_type": "QUALIFIED_FOR_SHIFT",
                                "shift_name": "cook", "role_name": "qualified"}))
        r = s.ask("Who is qualified as a cook?", MANAGER)
        self.assertEqual([e["name"] for e in r["employees"]], ["Ben Lee"])

    def test_role_copied_into_both_fields(self):
        s = service(FakeClient({"query_type": "QUALIFIED_FOR_SHIFT",
                                "shift_name": "cook", "role_name": "cook"}))
        r = s.ask("Who is qualified as a cook?", MANAGER)
        self.assertEqual(r["status"], "answered")
        self.assertEqual([e["name"] for e in r["employees"]], ["Ben Lee"])

    def test_partial_role_name_matches(self):
        r = self.ask({"query_type": "QUALIFIED_FOR_SHIFT", "role_name": "cooks"})
        self.assertEqual([e["name"] for e in r["employees"]], ["Ben Lee"])

    def test_unknown_names_list_valid_ones(self):
        r = self.ask({"query_type": "AVAILABLE_FOR_SHIFT", "date": "friday",
                      "shift_name": "midnight"})
        self.assertIn("Evening Shift", r["answer"])
        r = self.ask({"query_type": "QUALIFIED_FOR_SHIFT", "role_name": "pilot"})
        self.assertIn("Cook", r["answer"])

    def test_role_filter(self):
        r = self.ask({"query_type": "AVAILABLE_FOR_SHIFT", "date": "friday",
                      "shift_name": "evening", "role_name": "cook"})
        self.assertEqual([e["name"] for e in r["employees"]], ["Ben Lee"])

    def test_qualified_by_role_and_qualification(self):
        r = self.ask({"query_type": "QUALIFIED_FOR_SHIFT", "role_name": "Food Handler",
                      "shift_name": "evening", "date": "friday"})
        self.assertEqual([e["name"] for e in r["employees"]], ["Ana Ruiz"])
        r = self.ask({"query_type": "QUALIFIED_FOR_SHIFT", "role_name": "Cook"})
        self.assertEqual([e["name"] for e in r["employees"]], ["Ben Lee"])

    def test_needs_clarification(self):
        r = self.ask({"query_type": "AVAILABLE_FOR_SHIFT", "date": "friday"})
        self.assertEqual(r["status"], "needs_clarification")
        r = self.ask({"query_type": "AVAILABLE_FOR_SHIFT", "shift_name": "evening"},
                     "Who is available for the evening shift?")
        self.assertEqual(r["status"], "needs_clarification")
        r = self.ask({"query_type": "AVAILABLE_FOR_SHIFT", "date": "friday",
                      "shift_name": "midnight"})
        self.assertEqual(r["status"], "needs_clarification")
        r = self.ask({"query_type": "QUALIFIED_FOR_SHIFT"})
        self.assertEqual(r["status"], "needs_clarification")

    def test_unsupported_lists_supported_types(self):
        r = self.ask({"query_type": "UNSUPPORTED"}, "What is the weather?")
        self.assertEqual(r["status"], "unsupported")
        self.assertIn("available", r["answer"])
        self.assertIn("qualified", r["answer"])
        self.assertIn("budget", r["answer"])

    def test_budget_not_available_yet(self):
        r = self.ask({"query_type": "SCHEDULE_WITHIN_BUDGET", "week_start": "2026-11-16"},
                     "Is next week within budget?")
        self.assertIn("not available yet", r["answer"])
        self.assertEqual(r["employees"], [])

    def test_degraded_flag_when_ollama_down(self):
        s = service(FakeClient(OllamaError("down"), OllamaError("down")))
        r = s.ask("Who is available Friday evening?", MANAGER)
        self.assertEqual(r["status"], "answered")
        self.assertTrue(r["degraded"])
        self.assertEqual(len(r["employees"]), 2)

    def test_associate_forbidden(self):
        with self.assertRaises(PermissionDeniedError):
            service(FakeClient()).ask("Who is available Friday evening?", ASSOCIATE)

    def test_length_rules(self):
        for q in ("", "ab", "x" * 501):
            with self.assertRaises(ValidationError):
                service(FakeClient()).ask(q, MANAGER)

    def test_validator_removes_rule_breakers(self):
        from assistant.RuleValidator import RuleValidator
        plan = {"candidates": [EMPLOYEES[2], EMPLOYEES[0]],
                "context": {"shift_id": 3, "shift_name": "Evening Shift",
                            "role": (1, "Server")}}
        out = RuleValidator(make_data()).validate(plan)
        self.assertEqual([e.employee_id for e in out["employees"]], [1])
        self.assertEqual(out["violations"][0]["rule"], "AVAILABILITY")
        self.assertEqual(out["violations"][0]["employee_id"], 3)


if __name__ == "__main__":
    unittest.main()
