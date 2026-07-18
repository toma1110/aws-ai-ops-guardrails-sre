import copy
import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("validate_handoffs", ROOT / "validate_handoffs.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class HandoffValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.safe = MODULE.load_json(ROOT / "fixtures" / "fixture-safe-readonly.json")

    def test_exact_fixture_population_matches_expected(self):
        results, errors = MODULE.validate_population(ROOT / "fixtures", ROOT / "expected-results.json")
        self.assertEqual(errors, [])
        self.assertEqual(len(results), 7)
        self.assertEqual(sum(item["decision"] == "NEED_HUMAN_DECISION" for item in results.values()), 6)
        for result in results.values():
            if result["decision"] == "NEED_HUMAN_DECISION":
                self.assertEqual(set(result["handoff"]), {"evidence", "unknowns", "choices", "next_actor"})

    def test_production_impact_stops(self):
        for value in ("possible", "confirmed"):
            with self.subTest(value=value):
                scenario = copy.deepcopy(self.safe)
                scenario["conditions"]["production_impact"] = value
                scenario["unknowns"] = ["production impact needs a human decision"]
                self.assertEqual(MODULE.evaluate_scenario(scenario)["decision"], "NEED_HUMAN_DECISION")

    def test_cost_boundary_stops(self):
        for value in ("unknown", "exceeds_approved_limit"):
            with self.subTest(value=value):
                scenario = copy.deepcopy(self.safe)
                scenario["conditions"]["cost_impact"] = value
                scenario["unknowns"] = ["cost boundary needs a human decision"]
                self.assertEqual(MODULE.evaluate_scenario(scenario)["decision"], "NEED_HUMAN_DECISION")

    def test_exception_stops(self):
        scenario = copy.deepcopy(self.safe)
        scenario["conditions"]["exception_required"] = True
        scenario["unknowns"] = ["exception approval is unknown"]
        self.assertIn("exception_requires_approval", MODULE.evaluate_scenario(scenario)["reason_codes"])

    def test_permission_change_stops(self):
        scenario = copy.deepcopy(self.safe)
        scenario["conditions"]["permission_change_required"] = True
        scenario["unknowns"] = ["permission scope is unknown"]
        self.assertIn("permission_change_requires_approval", MODULE.evaluate_scenario(scenario)["reason_codes"])

    def test_rollback_boundary_stops(self):
        for value in ("missing", "unverified"):
            with self.subTest(value=value):
                scenario = copy.deepcopy(self.safe)
                scenario["conditions"]["rollback"] = value
                scenario["unknowns"] = ["rollback is unresolved"]
                self.assertEqual(MODULE.evaluate_scenario(scenario)["decision"], "NEED_HUMAN_DECISION")

    def test_safe_readonly_can_continue(self):
        self.assertEqual(MODULE.evaluate_scenario(self.safe), {"decision": "CONTINUE_READONLY", "reason_codes": []})

    def test_incomplete_or_malformed_handoff_fails_closed(self):
        mutations = []
        no_evidence = copy.deepcopy(self.safe)
        no_evidence["evidence"] = []
        mutations.append(no_evidence)
        one_option = copy.deepcopy(self.safe)
        one_option["options"] = one_option["options"][:1]
        mutations.append(one_option)
        bad_actor = copy.deepcopy(self.safe)
        bad_actor["next_actor"]["role"] = ""
        mutations.append(bad_actor)
        bad_enum = copy.deepcopy(self.safe)
        bad_enum["conditions"]["rollback"] = "assumed"
        mutations.append(bad_enum)
        for scenario in mutations:
            with self.subTest(scenario=scenario):
                self.assertEqual(MODULE.evaluate_scenario(scenario)["decision"], "INVALID_INPUT")

    def test_stopped_scenario_requires_explicit_unknown(self):
        scenario = copy.deepcopy(self.safe)
        scenario["conditions"]["production_impact"] = "possible"
        self.assertEqual(MODULE.evaluate_scenario(scenario)["reason_codes"], ["stopped_scenario_unknowns_missing"])


if __name__ == "__main__":
    unittest.main()
