from __future__ import annotations

import importlib.util
import json
import unittest
from copy import deepcopy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "validate_iam_guardrails.py"
SPEC = importlib.util.spec_from_file_location("validate_iam_guardrails", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


def load(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def requirements() -> dict[str, object]:
    return load(ROOT / "fixtures" / "guardrail-requirements.json")  # type: ignore[return-value]


def policy() -> dict[str, object]:
    return load(ROOT / "examples" / "iam-guardrail-package" / "iam-policy.json")  # type: ignore[return-value]


def profile() -> dict[str, object]:
    return load(ROOT / "examples" / "iam-guardrail-package" / "role-session-boundary.json")  # type: ignore[return-value]


def cases() -> dict[str, object]:
    return load(ROOT / "fixtures" / "evaluation-cases.json")  # type: ignore[return-value]


class ValidateIamGuardrailsTests(unittest.TestCase):
    def test_completed_package_is_valid(self) -> None:
        allow, deny, errors = VALIDATOR.validate_policy(policy(), requirements())
        self.assertEqual([], errors)
        self.assertEqual([], VALIDATOR.validate_profile(profile(), requirements()))
        counts, errors = VALIDATOR.validate_cases(cases(), allow, deny)
        self.assertEqual([], errors)
        self.assertEqual({"ALLOW": 4, "EXPLICIT_DENY": 3, "IMPLICIT_DENY": 2}, counts)

    def test_allow_wildcard_fixture_is_rejected(self) -> None:
        candidate = load(ROOT / "tests" / "fixtures" / "invalid-allow-wildcard.json")
        _, _, errors = VALIDATOR.validate_policy(candidate, requirements())
        self.assertTrue(any("must not use wildcards" in error for error in errors))

    def test_missing_explicit_deny_fixture_is_rejected(self) -> None:
        candidate = load(ROOT / "tests" / "fixtures" / "invalid-missing-explicit-deny.json")
        _, _, errors = VALIDATOR.validate_policy(candidate, requirements())
        self.assertTrue(any("exactly the approved Allow and explicit Deny" in error for error in errors))

    def test_invalid_json_fixture_cannot_be_loaded(self) -> None:
        _, errors = VALIDATOR.load_json(ROOT / "tests" / "fixtures" / "invalid-json-syntax.json", "policy")
        self.assertTrue(any("cannot read policy" in error for error in errors))

    def test_extra_allow_action_is_rejected(self) -> None:
        candidate = deepcopy(policy())
        candidate["Statement"][0]["Action"].append("ec2:DescribeInstances")
        _, _, errors = VALIDATOR.validate_policy(candidate, requirements())
        self.assertIn("Allow actions must exactly match the ordered least-privilege list", errors)

    def test_missing_required_deny_action_is_rejected(self) -> None:
        candidate = deepcopy(policy())
        candidate["Statement"][1]["Action"].remove("logs:DeleteLogGroup")
        _, _, errors = VALIDATOR.validate_policy(candidate, requirements())
        self.assertIn("Deny actions must exactly match the ordered prohibited-action list", errors)

    def test_explicit_deny_wins_over_allow(self) -> None:
        allow = ["ec2:StopInstances"]
        deny = ["ec2:StopInstances"]
        self.assertEqual("EXPLICIT_DENY", VALIDATOR.evaluate_action("ec2:StopInstances", allow, deny))

    def test_iam_wildcard_explicitly_denies_iam_mutation(self) -> None:
        self.assertEqual("EXPLICIT_DENY", VALIDATOR.evaluate_action("iam:CreatePolicyVersion", [], ["iam:*"]))

    def test_unlisted_action_is_implicitly_denied(self) -> None:
        allow, deny, errors = VALIDATOR.validate_policy(policy(), requirements())
        self.assertEqual([], errors)
        self.assertEqual("IMPLICIT_DENY", VALIDATOR.evaluate_action("s3:GetObject", allow, deny))

    def test_same_role_for_ai_and_human_is_rejected(self) -> None:
        candidate = deepcopy(profile())
        candidate["human_role"]["name"] = candidate["ai_role"]["name"]
        errors = VALIDATOR.validate_profile(candidate, requirements())
        self.assertIn("AI and human roles must be distinct", errors)

    def test_untracked_session_is_rejected(self) -> None:
        candidate = deepcopy(profile())
        candidate["session"]["required"] = False
        candidate["session"]["trace_fields"] = ["actor"]
        errors = VALIDATOR.validate_profile(candidate, requirements())
        self.assertIn("tracked session must be required", errors)
        self.assertIn("session trace fields do not match requirements", errors)

    def test_local_safety_declaration_is_fail_closed(self) -> None:
        candidate = deepcopy(cases())
        candidate["aws_connection"] = True
        errors = VALIDATOR.validate_local_declarations(candidate, "cases")
        self.assertIn("cases must declare aws_connection: false", errors)

    def test_case_decision_must_match_static_policy(self) -> None:
        candidate = deepcopy(cases())
        candidate["cases"][0]["expected"] = "EXPLICIT_DENY"
        allow, deny, errors = VALIDATOR.validate_policy(policy(), requirements())
        self.assertEqual([], errors)
        _, errors = VALIDATOR.validate_cases(candidate, allow, deny)
        self.assertTrue(any("ALLOW-01 decision mismatch" in error for error in errors))

    def test_template_placeholders_are_rejected(self) -> None:
        candidate = load(ROOT / "templates" / "iam-policy.json")
        _, _, errors = VALIDATOR.validate_policy(candidate, requirements())
        self.assertTrue(any("unresolved placeholders" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
