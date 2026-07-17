from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import unittest
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "investigate_incident.py"
SPEC = importlib.util.spec_from_file_location("investigate_incident", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
INVESTIGATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(INVESTIGATE)


def load(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


class InvestigateIncidentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.raw = load(ROOT / "fixtures" / "incident-observations.json")
        self.expected = load(ROOT / "fixtures" / "expected-investigation.json")

    def evidence_ids(self, data: dict) -> set[str]:
        return {item["evidence_id"] for key in ("metrics","logs","cloudtrail_events","config_changes","resource_states") for item in data[key]}

    def test_positive_report_exactly_matches_expected(self) -> None:
        data = INVESTIGATE.validate_fixture(self.raw)
        report = INVESTIGATE.build_report(data)
        INVESTIGATE.validate_report(report, self.evidence_ids(data))
        self.assertEqual(self.expected, report)

    def test_timeline_keeps_change_before_anomaly(self) -> None:
        report = INVESTIGATE.build_report(INVESTIGATE.validate_fixture(self.raw))
        self.assertEqual("2026-07-17T00:03:30Z", report["anomaly_start"])
        self.assertLess(report["facts"][0]["time"], report["anomaly_start"])

    def test_redirected_stdout_is_exact_utf8_lf_expected_bytes(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(SCRIPT)],
            cwd=ROOT,
            capture_output=True,
            check=False,
        )
        self.assertEqual(0, completed.returncode, completed.stderr.decode("utf-8", errors="replace"))
        expected = (ROOT / "expected-results" / "investigation.txt").read_bytes()
        self.assertEqual(expected, completed.stdout)
        self.assertNotIn(b"\r\n", completed.stdout)

    def test_all_required_services_are_bound(self) -> None:
        report = INVESTIGATE.build_report(INVESTIGATE.validate_fixture(self.raw))
        bound = {ref for fact in report["facts"] for ref in fact["evidence_ids"]}
        self.assertTrue({"MET-002","LOG-001","CT-001","CFG-001","ALB-001","EC2-001","RDS-001"} <= bound)

    def test_fact_hypothesis_unknown_and_human_decision_are_separate(self) -> None:
        report = INVESTIGATE.build_report(INVESTIGATE.validate_fixture(self.raw))
        groups = [set(item["id"] for item in report[key]) for key in ("facts","hypotheses","unknowns","human_decisions")]
        self.assertEqual(sum(len(group) for group in groups), len(set().union(*groups)))

    def test_aws_connection_drift_fails_closed(self) -> None:
        candidate = deepcopy(self.raw)
        candidate["aws_connection"] = True
        with self.assertRaisesRegex(ValueError, "local_only=true"):
            INVESTIGATE.validate_fixture(candidate)

    def test_duplicate_evidence_id_fails_closed(self) -> None:
        candidate = load(ROOT / "tests" / "fixtures" / "invalid-duplicate-evidence.json")
        with self.assertRaisesRegex(ValueError, "globally unique"):
            INVESTIGATE.validate_fixture(candidate)

    def test_observation_outside_window_fails_closed(self) -> None:
        candidate = deepcopy(self.raw)
        candidate["logs"][0]["timestamp"] = "2026-07-17T01:00:00Z"
        with self.assertRaisesRegex(ValueError, "outside the incident window"):
            INVESTIGATE.validate_fixture(candidate)

    def test_config_cloudtrail_mismatch_fails_closed(self) -> None:
        candidate = deepcopy(self.raw)
        candidate["config_changes"][0]["related_event_id"] = "wrong-event"
        data = INVESTIGATE.validate_fixture(candidate)
        with self.assertRaisesRegex(ValueError, "must correlate"):
            INVESTIGATE.build_report(data)

    def test_metric_below_threshold_fails_closed(self) -> None:
        candidate = deepcopy(self.raw)
        candidate["metrics"][1]["value"] = 9
        data = INVESTIGATE.validate_fixture(candidate)
        with self.assertRaisesRegex(ValueError, "cross its declared threshold"):
            INVESTIGATE.build_report(data)

    def test_unrelated_metric_state_resource_fails_closed(self) -> None:
        candidate = deepcopy(self.raw)
        candidate["resource_states"][1]["resource"] = "i-unrelated"
        data = INVESTIGATE.validate_fixture(candidate)
        with self.assertRaisesRegex(ValueError, "same resource"):
            INVESTIGATE.build_report(data)

    def test_wrong_metric_namespace_fails_closed(self) -> None:
        candidate = deepcopy(self.raw)
        candidate["metrics"][4]["namespace"] = "AWS/EC2"
        data = INVESTIGATE.validate_fixture(candidate)
        with self.assertRaisesRegex(ValueError, "namespace must be AWS/RDS"):
            INVESTIGATE.build_report(data)

    def test_wrong_state_service_fails_closed(self) -> None:
        candidate = deepcopy(self.raw)
        candidate["resource_states"][0]["service"] = "EC2"
        data = INVESTIGATE.validate_fixture(candidate)
        with self.assertRaisesRegex(ValueError, "service must be ALB"):
            INVESTIGATE.build_report(data)

    def test_metric_state_timestamp_mismatch_fails_closed(self) -> None:
        candidate = deepcopy(self.raw)
        candidate["resource_states"][2]["timestamp"] = "2026-07-17T00:05:00Z"
        data = INVESTIGATE.validate_fixture(candidate)
        with self.assertRaisesRegex(ValueError, "same timestamp"):
            INVESTIGATE.build_report(data)

    def test_unknown_evidence_reference_fails_closed(self) -> None:
        candidate = deepcopy(self.expected)
        candidate["facts"][0]["evidence_ids"] = ["MISSING"]
        with self.assertRaisesRegex(ValueError, "unknown evidence"):
            INVESTIGATE.validate_report(candidate, self.evidence_ids(self.raw))

    def test_missing_unknowns_fails_closed(self) -> None:
        candidate = load(ROOT / "tests" / "fixtures" / "invalid-expected-missing-unknowns.json")
        with self.assertRaisesRegex(ValueError, "unknowns must be a non-empty list"):
            INVESTIGATE.validate_report(candidate, self.evidence_ids(self.raw))

    def test_causal_claim_in_fact_fails_closed(self) -> None:
        candidate = deepcopy(self.expected)
        candidate["facts"][0]["statement"] = "The change caused the incident."
        with self.assertRaisesRegex(ValueError, "must not assert causality"):
            INVESTIGATE.validate_report(candidate, self.evidence_ids(self.raw))


if __name__ == "__main__":
    unittest.main()
