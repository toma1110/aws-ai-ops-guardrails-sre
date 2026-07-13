from __future__ import annotations

import importlib.util
import json
import unittest
from copy import deepcopy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "validate_checklist.py"
SPEC = importlib.util.spec_from_file_location("validate_checklist", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


def load_example() -> str:
    return (ROOT / "examples" / "completed-mcp-preconnection-checklist.md").read_text(
        encoding="utf-8"
    )


def load_fixture() -> dict[str, object]:
    return json.loads(
        (ROOT / "fixtures" / "risk-scenarios.json").read_text(encoding="utf-8")
    )


class ValidateChecklistTests(unittest.TestCase):
    def test_completed_example_is_valid(self) -> None:
        self.assertEqual([], VALIDATOR.validate_text(load_example(), load_fixture()))

    def test_unfilled_template_is_invalid(self) -> None:
        template = (ROOT / "templates" / "mcp-preconnection-checklist.md").read_text(
            encoding="utf-8"
        )
        errors = VALIDATOR.validate_text(template, load_fixture())
        self.assertTrue(any("unresolved placeholders" in error for error in errors))
        self.assertTrue(any("invalid decision" in error for error in errors))

    def test_every_required_category_is_enforced(self) -> None:
        example = load_example()
        for category in VALIDATOR.REQUIRED_CATEGORIES:
            lines = [
                line
                for line in example.splitlines()
                if not line.startswith(f"| {category} |")
            ]
            errors = VALIDATOR.validate_text("\n".join(lines), load_fixture())
            self.assertIn(f"missing risk category: {category}", errors)

    def test_decision_must_match_overall(self) -> None:
        changed = load_example().replace("| PERMISSIONS | BLOCK |", "| PERMISSIONS | REVIEW |")
        changed = changed.replace("| SENSITIVE_DATA | BLOCK |", "| SENSITIVE_DATA | REVIEW |")
        errors = VALIDATOR.validate_text(changed, load_fixture())
        self.assertIn(
            "overall decision mismatch: expected NEEDS_REVIEW, got DO_NOT_CONNECT",
            errors,
        )

    def test_evidence_cannot_be_borrowed_from_another_category(self) -> None:
        changed = load_example().replace(
            "CONNECTION-01: network経路と利用環境のレビュー記録がない",
            "COST-01: 別分類の根拠",
        )
        errors = VALIDATOR.validate_text(changed, load_fixture())
        self.assertIn(
            "evidence must cite matching scenario id: CONNECTION", errors
        )

    def test_all_pass_contradicting_fixture_is_invalid(self) -> None:
        changed = load_example()
        for decision in ("REVIEW", "BLOCK"):
            changed = changed.replace(f"| {decision} |", "| PASS |")
        changed = changed.replace(
            "- 接続前判定: DO_NOT_CONNECT",
            "- 接続前判定: READY_FOR_APPROVAL",
        )
        errors = VALIDATOR.validate_text(changed, load_fixture())
        for category in (
            "CONNECTION",
            "PERMISSIONS",
            "AUDIT",
            "SENSITIVE_DATA",
            "COST",
        ):
            self.assertTrue(
                any(
                    error.startswith(f"decision contradicts fixture for {category}:")
                    for error in errors
                )
            )

    def test_non_aws_url_cannot_replace_matching_scenario_id(self) -> None:
        changed = load_example().replace(
            "CONNECTION-01: network経路と利用環境のレビュー記録がない",
            "https://example.com/not-fixture-evidence",
        )
        errors = VALIDATOR.validate_text(changed, load_fixture())
        self.assertIn("evidence must cite matching scenario id: CONNECTION", errors)

    def test_unrelated_category_url_cannot_replace_matching_scenario_id(self) -> None:
        changed = load_example().replace(
            "CONNECTION-01: network経路と利用環境のレビュー記録がない",
            "https://docs.aws.amazon.com/billing/ unrelated COST evidence",
        )
        errors = VALIDATOR.validate_text(changed, load_fixture())
        self.assertIn("evidence must cite matching scenario id: CONNECTION", errors)

    def test_calendar_date_must_be_real(self) -> None:
        changed = load_example().replace("2026-07-13 | 許可環境", "2026-02-30 | 許可環境")
        errors = VALIDATOR.validate_text(changed, load_fixture())
        self.assertIn("invalid recheck date: CONNECTION", errors)

    def test_fixture_requires_local_only_and_full_population(self) -> None:
        fixture = deepcopy(load_fixture())
        fixture["local_only"] = False
        fixture["scenarios"] = fixture["scenarios"][:-1]
        errors = VALIDATOR.validate_text(load_example(), fixture)
        self.assertIn("fixture must declare local_only: true", errors)
        self.assertIn("missing fixture category: COST", errors)


if __name__ == "__main__":
    unittest.main()
