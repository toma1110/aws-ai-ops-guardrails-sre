from __future__ import annotations

import importlib.util
import json
import unittest
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "audit_cloudtrail.py"
SPEC = importlib.util.spec_from_file_location("audit_cloudtrail", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


def load(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


class AuditCloudTrailTests(unittest.TestCase):
    def setUp(self) -> None:
        self.executions = load(ROOT / "fixtures" / "ai-executions.json")
        self.cloudtrail = load(ROOT / "fixtures" / "cloudtrail-events.json")
        self.expected = load(ROOT / "fixtures" / "expected-audit.json")

    def test_positive_correlation_and_expected_comparison(self) -> None:
        execution = AUDIT.select_execution(self.executions, "AI-EXEC-006")
        events = AUDIT.correlate(self.cloudtrail, execution)
        AUDIT.compare_expected(self.expected, execution, events)
        self.assertEqual(["GetMetricData", "FilterLogEvents"], [event["event"] for event in events])
        self.assertIsNone(events[0]["error"])
        self.assertEqual("AccessDenied", events[1]["error"]["code"])

    def test_unrelated_human_and_other_execution_are_excluded(self) -> None:
        execution = AUDIT.select_execution(self.executions, "AI-EXEC-006")
        events = AUDIT.correlate(self.cloudtrail, execution)
        self.assertEqual(2, len(events))

    def test_unknown_execution_fails_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "exactly one"):
            AUDIT.select_execution(self.executions, "AI-EXEC-404")

    def test_ambiguous_overlapping_session_fails_closed(self) -> None:
        candidate = load(ROOT / "tests" / "fixtures" / "invalid-ambiguous-executions.json")
        with self.assertRaisesRegex(ValueError, "ambiguous correlation"):
            AUDIT.select_execution(candidate, "AI-EXEC-006")

    def test_missing_parameters_fails_closed(self) -> None:
        candidate = load(ROOT / "tests" / "fixtures" / "invalid-missing-parameters.json")
        execution = AUDIT.select_execution(self.executions, "AI-EXEC-006")
        with self.assertRaisesRegex(ValueError, "missing requestParameters"):
            AUDIT.correlate(candidate, execution)

    def test_inconsistent_session_arn_fails_closed(self) -> None:
        candidate = deepcopy(self.cloudtrail)
        candidate["events"][0]["userIdentity"]["arn"] = "arn:aws:sts::000000000000:assumed-role/SyntheticReadOnlyRole/wrong-session"
        execution = AUDIT.select_execution(self.executions, "AI-EXEC-006")
        with self.assertRaisesRegex(ValueError, "inconsistent session identity"):
            AUDIT.correlate(candidate, execution)

    def test_partial_error_fails_closed(self) -> None:
        candidate = deepcopy(self.cloudtrail)
        del candidate["events"][1]["errorMessage"]
        execution = AUDIT.select_execution(self.executions, "AI-EXEC-006")
        with self.assertRaisesRegex(ValueError, "must appear together"):
            AUDIT.correlate(candidate, execution)

    def test_expected_drift_fails_closed(self) -> None:
        candidate = load(ROOT / "tests" / "fixtures" / "invalid-expected-audit.json")
        execution = AUDIT.select_execution(self.executions, "AI-EXEC-006")
        events = AUDIT.correlate(self.cloudtrail, execution)
        with self.assertRaisesRegex(ValueError, "event_ids"):
            AUDIT.compare_expected(candidate, execution, events)

    def test_local_safety_declaration_fails_closed(self) -> None:
        candidate = deepcopy(self.cloudtrail)
        candidate["aws_connection"] = True
        with self.assertRaisesRegex(ValueError, "aws_connection: false"):
            AUDIT.check_local(candidate, "events")


if __name__ == "__main__":
    unittest.main()
