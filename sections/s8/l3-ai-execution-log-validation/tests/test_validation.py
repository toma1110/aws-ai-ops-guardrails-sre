import copy
import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("validate_logs", ROOT / "validate_logs.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class ValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = MODULE.load_json(ROOT / "ai-execution-log.schema.json")
        cls.valid = MODULE.load_json(ROOT / "fixtures" / "valid-local.json")

    def test_exact_fixture_population_matches_expected(self):
        actual, errors = MODULE.validate_population(ROOT / "fixtures", ROOT / "expected-results.json")
        self.assertEqual(errors, [])
        self.assertEqual(len(actual), 9)
        self.assertEqual(sum(item["valid"] for item in actual.values()), 2)

    def test_correlation_fields_fail_closed(self):
        for field in MODULE.CORRELATION_FIELDS:
            with self.subTest(field=field):
                record = copy.deepcopy(self.valid)
                del record[field]
                result = MODULE.validate_record(record, self.schema)
                self.assertFalse(result["valid"])
                self.assertIn("missing_correlation_field", result["reason_codes"])

    def test_retention_window_must_match_declared_boundary(self):
        record = copy.deepcopy(self.valid)
        record["retention"]["expires_at"] = "2026-09-01T00:00:00Z"
        result = MODULE.validate_record(record, self.schema)
        self.assertIn("retention_window_mismatch", result["reason_codes"])

    def test_non_string_retention_timestamps_fail_closed(self):
        cases = (
            (("occurred_at",), 42),
            (("retention", "expires_at"), 42),
        )
        for path, value in cases:
            with self.subTest(path=".".join(path)):
                record = copy.deepcopy(self.valid)
                target = record
                for segment in path[:-1]:
                    target = target[segment]
                target[path[-1]] = value
                result = MODULE.validate_record(record, self.schema)
                self.assertFalse(result["valid"])
                self.assertIn("schema_validation_failed", result["reason_codes"])
                self.assertIn("retention_window_mismatch", result["reason_codes"])

    def test_unapproved_external_send_fails_closed(self):
        record = copy.deepcopy(self.valid)
        record["external_send"] = {"allowed": True, "destination": "approved-service", "approval_ticket": None}
        self.assertIn("external_send_unapproved", MODULE.validate_record(record, self.schema)["reason_codes"])

    def test_sensitive_marker_fails_even_when_masking_claims_true(self):
        record = copy.deepcopy(self.valid)
        record["input"]["customer_email"] = "PLAINTEXT-SENSITIVE-VALUE"
        self.assertIn("sensitive_data_detected", MODULE.validate_record(record, self.schema)["reason_codes"])

    def test_declared_plaintext_is_not_accepted_as_redaction(self):
        record = copy.deepcopy(self.valid)
        record["input"]["customer_email"] = "alice@example.com"
        self.assertIn("masking_value_invalid", MODULE.validate_record(record, self.schema)["reason_codes"])

    def test_every_declared_masking_path_must_exist(self):
        record = copy.deepcopy(self.valid)
        record["data_handling"]["masked_fields"] = ["input.nonexistent"]
        self.assertIn("masking_path_missing", MODULE.validate_record(record, self.schema)["reason_codes"])

    def test_unsupported_and_non_scalar_paths_fail_closed(self):
        cases = (
            ("metadata.owner", "masking_path_unsupported"),
            ("input.customer_email", "masking_path_non_scalar"),
        )
        for path, expected_code in cases:
            with self.subTest(path=path):
                record = copy.deepcopy(self.valid)
                record["data_handling"]["masked_fields"] = [path]
                if expected_code == "masking_path_non_scalar":
                    record["input"]["customer_email"] = {"value": "[REDACTED]"}
                self.assertIn(expected_code, MODULE.validate_record(record, self.schema)["reason_codes"])

    def test_each_documented_strategy_has_an_unambiguous_format(self):
        examples = {
            "redact": "[REDACTED]",
            "tokenize": "token-customer-001",
            "hash": "sha256:" + "a" * 64,
        }
        for strategy, value in examples.items():
            with self.subTest(strategy=strategy):
                record = copy.deepcopy(self.valid)
                record["data_handling"]["strategy"] = strategy
                record["input"]["customer_email"] = value
                self.assertTrue(MODULE.validate_record(record, self.schema)["valid"])

    def test_expected_population_drift_is_rejected(self):
        expected = json.loads((ROOT / "expected-results.json").read_text(encoding="utf-8"))
        expected.pop("valid-local.json")
        temporary = ROOT / "tests" / "expected-results.temporary.json"
        try:
            temporary.write_text(json.dumps(expected), encoding="utf-8")
            _, errors = MODULE.validate_population(ROOT / "fixtures", temporary)
            self.assertIn("fixture population does not exactly match expected-results.json", errors)
        finally:
            temporary.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
