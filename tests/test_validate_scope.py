from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "validate_scope.py"
SPEC = importlib.util.spec_from_file_location("validate_scope", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


class ValidateScopeTests(unittest.TestCase):
    def test_completed_example_is_valid(self) -> None:
        text = (ROOT / "examples" / "completed-adoption-scope.md").read_text(
            encoding="utf-8"
        )
        self.assertEqual([], VALIDATOR.validate_text(text))

    def test_unfilled_template_is_invalid(self) -> None:
        text = (ROOT / "templates" / "adoption-scope.md").read_text(encoding="utf-8")
        errors = VALIDATOR.validate_text(text)
        self.assertTrue(any("unresolved placeholders" in error for error in errors))

    def test_missing_decision_class_is_invalid(self) -> None:
        text = (ROOT / "examples" / "completed-adoption-scope.md").read_text(
            encoding="utf-8"
        )
        errors = VALIDATOR.validate_text(text.replace(" | PROHIBIT |", " | DENY |"))
        self.assertIn("missing classified work row: PROHIBIT", errors)

    def test_missing_auditability_traceability_terms_is_invalid(self) -> None:
        text = (ROOT / "examples" / "completed-adoption-scope.md").read_text(
            encoding="utf-8"
        )
        for field in VALIDATOR.TRACEABILITY_FIELDS:
            text = text.replace(field, "traceability-field-removed")
        errors = VALIDATOR.validate_text(text)
        for field in VALIDATOR.TRACEABILITY_FIELDS:
            self.assertIn(f"missing auditability traceability field: {field}", errors)


if __name__ == "__main__":
    unittest.main()
