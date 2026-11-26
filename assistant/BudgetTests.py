"""Tests for the AI Assistant budget query (SCHEDULE_WITHIN_BUDGET).
Everything is faked: no database and no Ollama are needed."""
import unittest
from datetime import date
from types import SimpleNamespace

from assistant.AssistantService import AssistantService
from assistant.BudgetReader import BudgetReader
from assistant.OllamaClient import OllamaError
from assistant.WeekResolver import resolve_week
from shared.exceptions import PermissionDeniedError

WEEK = "2026-11-30"  # a Monday
TODAY = date(2026, 11, 26)  # a Thursday


def forecast(day, budget, status="Approved"):
    return SimpleNamespace(forecast_date=day, labor_budget=budget,
                           status=status)


def row(day, hours, rate):
    return {"schedule_date": day, "hours": hours, "hourly_rate": rate,
            "first_name": "A", "last_name": "B"}


def make_reader(weeks=None, assignments=None, forecasts=None):
    weeks = {WEEK: {"schedule_id": 1}} if weeks is None else weeks
    assignments = [] if assignments is None else assignments
    forecasts = [] if forecasts is None else forecasts
    return BudgetReader(
        load_schedule=lambda w: weeks.get(w),
        load_assignments=lambda sid: assignments,
        load_forecasts=lambda a, b: [f for f in forecasts
                                     if a <= f.forecast_date <= b])


class FakeData:
    def shift_names(self):
        return {1: "Morning Shift"}

    def role_names(self):
        return {1: "Associate"}

    def qualification_names(self):
        return {}


class DownClient:
    def generate_json(self, prompt):
        raise OllamaError("down")


class JsonClient:
    def __init__(self, payload):
        self.payload = payload

    def generate_json(self, prompt):
        return self.payload


MANAGER = SimpleNamespace(id=1, system_role_id=2)
ASSOCIATE = SimpleNamespace(id=2, system_role_id=1)


def make_service(reader, client=None):
    return AssistantService(FakeData(), client or DownClient(),
                            today=TODAY, budget=reader)


class WeekResolverTests(unittest.TestCase):
    def test_next_week_is_next_monday(self):
        self.assertEqual(resolve_week("is next week within budget", TODAY),
                         "2026-11-30")

    def test_this_and_last_week(self):
        self.assertEqual(resolve_week("this week over budget?", TODAY),
                         "2026-11-23")
        self.assertEqual(resolve_week("was last week ok", TODAY),
                         "2026-11-16")

    def test_explicit_date(self):
        self.assertEqual(resolve_week("week of 2026-12-07", TODAY),
                         "2026-12-07")

    def test_bad_date_and_no_week(self):
        self.assertIsNone(resolve_week("week of 2026-13-45", TODAY))
        self.assertIsNone(resolve_week("is the schedule within budget", TODAY))


class BudgetReaderTests(unittest.TestCase):
    def test_no_schedule_returns_none(self):
        self.assertIsNone(make_reader(weeks={}).weekly_budget(WEEK))

    def test_under_budget(self):
        reader = make_reader(
            assignments=[row("2026-11-30", 8, 20), row("2026-11-30", 8, 25)],
            forecasts=[forecast("2026-11-30", 500.0)])
        result = reader.weekly_budget(WEEK)
        self.assertEqual(result["projected_labor_cost"], 360.0)
        self.assertEqual(result["labor_budget"], 500.0)
        self.assertTrue(result["within_budget"])
        self.assertEqual(result["days"][0]["variance"], 140.0)

    def test_over_budget(self):
        reader = make_reader(
            assignments=[row("2026-11-30", 8, 30)],
            forecasts=[forecast("2026-11-30", 200.0)])
        result = reader.weekly_budget(WEEK)
        self.assertFalse(result["within_budget"])
        self.assertEqual(result["days"][0]["variance"], -40.0)

    def test_equal_counts_as_within(self):
        reader = make_reader(assignments=[row("2026-11-30", 10, 20)],
                             forecasts=[forecast("2026-11-30", 200.0)])
        self.assertTrue(reader.weekly_budget(WEEK)["within_budget"])

    def test_missing_forecast_cannot_be_judged(self):
        reader = make_reader(assignments=[row("2026-12-01", 8, 20)],
                             forecasts=[forecast("2026-11-30", 500.0)])
        result = reader.weekly_budget(WEEK)
        self.assertIsNone(result["within_budget"])
        self.assertEqual(result["missing_forecast_days"], ["2026-12-01"])

    def test_no_assignments(self):
        result = make_reader(
            forecasts=[forecast("2026-11-30", 500.0)]).weekly_budget(WEEK)
        self.assertFalse(result["has_assignments"])

    def test_mid_week_date_falls_back_to_monday(self):
        reader = make_reader(assignments=[row("2026-11-30", 8, 20)],
                             forecasts=[forecast("2026-11-30", 500.0)])
        self.assertEqual(reader.weekly_budget("2026-12-02")["week_start"], WEEK)

    def test_rows_outside_week_ignored(self):
        reader = make_reader(
            assignments=[row("2026-11-30", 8, 20), row("2026-12-09", 8, 99)],
            forecasts=[forecast("2026-11-30", 500.0)])
        self.assertEqual(reader.weekly_budget(WEEK)["projected_labor_cost"],
                         160.0)

    def test_draft_forecast_flagged(self):
        reader = make_reader(assignments=[row("2026-11-30", 8, 20)],
                             forecasts=[forecast("2026-11-30", 500.0, "Draft")])
        self.assertTrue(reader.weekly_budget(WEEK)["draft_forecast"])


class BudgetAssistantTests(unittest.TestCase):
    def good_reader(self, cost_rate=20, budget=500.0, status="Approved"):
        return make_reader(assignments=[row("2026-11-30", 8, cost_rate)],
                           forecasts=[forecast("2026-11-30", budget, status)])

    def ask(self, reader, question="Is next week within budget?", client=None):
        return make_service(reader, client).ask(question, MANAGER)

    def test_within_budget_answer(self):
        result = self.ask(self.good_reader())
        self.assertEqual(result["status"], "answered")
        self.assertIn("within budget", result["answer"])
        self.assertEqual(result["budget"]["projected_labor_cost"], 160.0)

    def test_over_budget_answer_lists_day(self):
        result = self.ask(self.good_reader(cost_rate=100))
        self.assertIn("over budget", result["answer"])
        self.assertEqual(len(result["validation"]["over_budget_days"]), 1)

    def test_draft_note(self):
        result = self.ask(self.good_reader(status="Draft"))
        self.assertIn("not approved", result["answer"])

    def test_no_wages_in_response(self):
        text = str(self.ask(self.good_reader(cost_rate=23.77)))
        self.assertNotIn("23.77", text)
        self.assertNotIn("hourly_rate", text)

    def test_no_schedule_message(self):
        result = self.ask(make_reader(weeks={}))
        self.assertIn("No schedule has been generated", result["answer"])

    def test_missing_week_asks_for_clarification(self):
        result = self.ask(self.good_reader(),
                          question="Is the schedule within budget?")
        self.assertEqual(result["status"], "needs_clarification")

    def test_llm_path_uses_server_date_not_model_date(self):
        client = JsonClient({"query_type": "SCHEDULE_WITHIN_BUDGET",
                             "week_start": "2031-01-06", "date": None,
                             "shift_name": None, "role_name": None})
        result = self.ask(self.good_reader(), client=client)
        self.assertEqual(result["status"], "answered")
        self.assertFalse(result["degraded"])
        self.assertEqual(result["budget"]["week_start"], WEEK)

    def test_keyword_fallback_is_degraded(self):
        result = self.ask(self.good_reader())
        self.assertTrue(result["degraded"])

    def test_without_reader_still_says_unavailable(self):
        service = AssistantService(FakeData(), DownClient(), today=TODAY)
        result = service.ask("Is next week within budget?", MANAGER)
        self.assertIn("not available yet", result["answer"])

    def test_associate_is_refused(self):
        with self.assertRaises(PermissionDeniedError):
            make_service(self.good_reader()).ask("Is next week within budget?",
                                                 ASSOCIATE)

    def test_validator_rejects_inconsistent_totals(self):
        from assistant.RuleValidator import RuleValidator
        budget = self.good_reader().weekly_budget(WEEK)
        budget["projected_labor_cost"] = 1.0
        self.assertFalse(RuleValidator(FakeData()).validate_budget(budget)["passed"])


if __name__ == "__main__":
    unittest.main()
