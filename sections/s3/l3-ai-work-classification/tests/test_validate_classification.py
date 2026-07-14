from __future__ import annotations

import importlib.util
import json
import unittest
from copy import deepcopy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "validate_classification.py"
SPEC = importlib.util.spec_from_file_location("validate_classification", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


def load_example() -> str:
    return (ROOT / "examples" / "completed-ai-work-classification.md").read_text(
        encoding="utf-8"
    )


def load_fixture() -> dict[str, object]:
    return json.loads(
        (ROOT / "fixtures" / "work-scenarios.json").read_text(encoding="utf-8")
    )


class ValidateClassificationTests(unittest.TestCase):
    def test_completed_example_is_valid(self) -> None:
        self.assertEqual([], VALIDATOR.validate_text(load_example(), load_fixture()))

    def test_unfilled_template_is_invalid(self) -> None:
        text = (ROOT / "templates" / "ai-work-classification.md").read_text(
            encoding="utf-8"
        )
        errors = VALIDATOR.validate_text(text, load_fixture())
        self.assertTrue(any("unresolved placeholders" in error for error in errors))
        self.assertTrue(any("decision mismatch" in error for error in errors))

    def test_every_fixture_scenario_requires_exact_row(self) -> None:
        example = load_example()
        fixture = load_fixture()
        for scenario in fixture["scenarios"]:
            scenario_id = scenario["id"]
            changed = "\n".join(
                line
                for line in example.splitlines()
                if not line.startswith(f"| {scenario_id} |")
            )
            errors = VALIDATOR.validate_text(changed, fixture)
            self.assertIn(f"missing classification row: {scenario_id}", errors)

    def test_decision_cannot_contradict_matching_fixture(self) -> None:
        changed = load_example().replace(
            "| CHANGE-01 | 本番アラームのしきい値を変更する | PROHIBIT |",
            "| CHANGE-01 | 本番アラームのしきい値を変更する | HUMAN_REVIEW |",
        )
        errors = VALIDATOR.validate_text(changed, load_fixture())
        self.assertIn(
            "decision mismatch for CHANGE-01: expected PROHIBIT, got HUMAN_REVIEW",
            errors,
        )

    def test_evidence_cannot_be_borrowed_from_another_scenario(self) -> None:
        changed = load_example().replace(
            "METRICS-01はローカルの承認済み情報源を読むだけで、出力も根拠付きメモに限定される",
            "LOGS-01を参照して別シナリオの分類根拠とする",
        )
        errors = VALIDATOR.validate_text(changed, load_fixture())
        self.assertIn("evidence must cite matching scenario id: METRICS-01", errors)

    def test_prohibited_action_has_precedence_over_review_trigger(self) -> None:
        flags = {name: False for name in VALIDATOR.REQUIRED_FLAGS}
        flags["mutating_action"] = True
        flags["production_impact_decision"] = True
        flags["approved_read_only"] = True
        flags["evidence_only_output"] = True
        self.assertEqual("PROHIBIT", VALIDATOR.derive_decision(flags))

    def test_fixture_is_local_without_aws_or_credentials(self) -> None:
        fixture = deepcopy(load_fixture())
        fixture["local_only"] = False
        fixture["aws_connection"] = True
        fixture["credentials_required"] = True
        errors = VALIDATOR.validate_text(load_example(), fixture)
        self.assertIn("fixture must declare local_only: true", errors)
        self.assertIn("fixture must declare aws_connection: false", errors)
        self.assertIn("fixture must declare credentials_required: false", errors)

    def test_fixture_expected_decision_is_derived_from_flags(self) -> None:
        fixture = deepcopy(load_fixture())
        fixture["scenarios"][0]["expected_decision"] = "HUMAN_REVIEW"
        errors = VALIDATOR.validate_text(load_example(), fixture)
        self.assertTrue(
            any(
                error.startswith("fixture decision mismatch for METRICS-01")
                for error in errors
            )
        )


if __name__ == "__main__":
    unittest.main()
