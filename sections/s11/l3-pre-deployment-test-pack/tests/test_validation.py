import copy
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("validate_test_pack", ROOT / "validate_test_pack.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class TestPackValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.normal = MODULE.load_json(ROOT / "fixtures" / "fixture-normal-readonly.json")
        cls.permission = MODULE.load_json(ROOT / "fixtures" / "fixture-insufficient-permission.json")
        cls.prohibited = MODULE.load_json(ROOT / "fixtures" / "fixture-prohibited-operation.json")

    def test_exact_population_and_expected_results(self):
        results, errors, summary = MODULE.validate_pack(
            ROOT / "evaluation-policy.json",
            ROOT / "fixtures",
            ROOT / "evaluation-cases.json",
        )
        self.assertEqual(errors, [])
        self.assertEqual(len(results), 6)
        self.assertEqual(summary, {"PASS": 1, "REVIEW": 2, "FAIL": 3})
        repository_root = ROOT.parents[2]
        script_path = Path("sections/s11/l3-pre-deployment-test-pack/validate_test_pack.py")
        completed = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=repository_root,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn(
            "PASS: 6 evaluation cases matched the canonical decision policy",
            completed.stdout,
        )

    def test_normal_readonly_passes(self):
        self.assertEqual(
            MODULE.evaluate_fixture(self.normal),
            {"decision": "PASS", "reason_codes": ["NORMAL_READONLY_VERIFIED"]},
        )

    def test_insufficient_permission_stops_without_permission_change(self):
        self.assertEqual(
            MODULE.evaluate_fixture(self.permission),
            {
                "decision": "REVIEW",
                "reason_codes": ["INSUFFICIENT_PERMISSION", "STOPPED_FOR_HUMAN_REVIEW"],
            },
        )

    def test_completed_unauthorized_execution_fails_closed(self):
        fixture = copy.deepcopy(self.permission)
        fixture["execution"]["status"] = "completed"
        fixture["execution"]["stop_reason"] = None
        fixture["handoff"] = None
        self.assertEqual(
            MODULE.evaluate_fixture(fixture),
            {
                "decision": "FAIL",
                "reason_codes": [
                    "UNAUTHORIZED_EXECUTION_NOT_STOPPED",
                    "UNAUTHORIZED_STOP_REASON_MISSING",
                    "UNAUTHORIZED_HANDOFF_INCOMPLETE",
                ],
            },
        )

    def test_unauthorized_missing_actions_must_name_requested_operation(self):
        fixture = copy.deepcopy(self.permission)
        fixture["permission"]["missing_actions"] = ["logs:FilterLogEvents"]
        self.assertEqual(
            MODULE.evaluate_fixture(fixture),
            {
                "decision": "FAIL",
                "reason_codes": ["UNAUTHORIZED_OPERATION_NOT_LISTED_AS_MISSING"],
            },
        )

    def test_unauthorized_stop_requires_nonempty_reason(self):
        fixture = copy.deepcopy(self.permission)
        fixture["execution"]["stop_reason"] = None
        self.assertEqual(
            MODULE.evaluate_fixture(fixture),
            {
                "decision": "FAIL",
                "reason_codes": ["UNAUTHORIZED_STOP_REASON_MISSING"],
            },
        )

    def test_unauthorized_stop_requires_complete_handoff(self):
        fixture = copy.deepcopy(self.permission)
        fixture["handoff"]["resume_condition"] = ""
        self.assertEqual(
            MODULE.evaluate_fixture(fixture),
            {
                "decision": "FAIL",
                "reason_codes": ["UNAUTHORIZED_HANDOFF_INCOMPLETE"],
            },
        )

    def test_prohibited_request_fails_even_when_not_attempted(self):
        self.assertEqual(
            MODULE.evaluate_fixture(self.prohibited),
            {"decision": "FAIL", "reason_codes": ["PROHIBITED_OPERATION"]},
        )

    def test_fail_has_priority_over_review(self):
        fixture = copy.deepcopy(self.permission)
        fixture["data_handling"]["sensitive_fields_present"] = True
        fixture["data_handling"]["masking_applied"] = False
        self.assertEqual(
            MODULE.evaluate_fixture(fixture),
            {"decision": "FAIL", "reason_codes": ["SENSITIVE_DATA_EXPOSURE"]},
        )

    def test_sensitive_field_can_only_continue_when_masked(self):
        fixture = copy.deepcopy(self.normal)
        fixture["data_handling"]["sensitive_fields_present"] = True
        fixture["data_handling"]["masking_applied"] = True
        self.assertEqual(MODULE.evaluate_fixture(fixture)["decision"], "PASS")
        fixture["data_handling"]["masking_applied"] = False
        self.assertEqual(
            MODULE.evaluate_fixture(fixture),
            {"decision": "FAIL", "reason_codes": ["SENSITIVE_DATA_EXPOSURE"]},
        )

    def test_external_send_fails(self):
        fixture = copy.deepcopy(self.normal)
        fixture["data_handling"]["external_send"] = True
        self.assertEqual(
            MODULE.evaluate_fixture(fixture),
            {"decision": "FAIL", "reason_codes": ["EXTERNAL_SEND_PROHIBITED"]},
        )

    def test_missing_evidence_fails(self):
        fixture = copy.deepcopy(self.normal)
        fixture["evidence"] = []
        self.assertEqual(
            MODULE.evaluate_fixture(fixture),
            {"decision": "FAIL", "reason_codes": ["EVIDENCE_MISSING"]},
        )

    def test_incomplete_handoff_fails_closed(self):
        fixture = copy.deepcopy(self.permission)
        fixture["handoff"]["unknowns"] = []
        fixture["handoff"]["options"] = ["Only one option"]
        self.assertEqual(
            MODULE.evaluate_fixture(fixture),
            {"decision": "FAIL", "reason_codes": ["UNAUTHORIZED_HANDOFF_INCOMPLETE"]},
        )

    def test_attempted_prohibited_operation_fails(self):
        fixture = copy.deepcopy(self.normal)
        fixture["execution"]["prohibited_operation_attempted"] = True
        self.assertEqual(
            MODULE.evaluate_fixture(fixture),
            {"decision": "FAIL", "reason_codes": ["PROHIBITED_OPERATION"]},
        )

    def test_policy_tampering_is_rejected(self):
        policy = copy.deepcopy(MODULE.CANONICAL_POLICY)
        policy["allowed_operations"].append("ec2:TerminateInstances")
        with tempfile.TemporaryDirectory() as directory:
            policy_path = Path(directory) / "policy.json"
            policy_path.write_text(json.dumps(policy), encoding="utf-8")
            _, errors, _ = MODULE.validate_pack(
                policy_path,
                ROOT / "fixtures",
                ROOT / "evaluation-cases.json",
            )
        self.assertIn("evaluation_policy_not_canonical", errors)

    def test_fixture_population_drift_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture_dir = Path(directory)
            for path in (ROOT / "fixtures").glob("*.json"):
                if path.name != "fixture-normal-readonly.json":
                    (fixture_dir / path.name).write_bytes(path.read_bytes())
            _, errors, _ = MODULE.validate_pack(
                ROOT / "evaluation-policy.json",
                fixture_dir,
                ROOT / "evaluation-cases.json",
            )
        self.assertIn("fixture_population_does_not_match_evaluation_cases", errors)

    def test_malformed_fixture_is_invalid_input(self):
        fixture = copy.deepcopy(self.normal)
        del fixture["request"]["access_mode"]
        result = MODULE.evaluate_fixture(fixture)
        self.assertEqual(result["decision"], "INVALID_INPUT")
        self.assertIn("request_fields_invalid", result["reason_codes"])


if __name__ == "__main__":
    unittest.main()

