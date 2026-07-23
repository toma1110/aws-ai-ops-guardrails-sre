import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "validate_integration", ROOT / "validate_integration.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class IntegrationValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.index = MODULE.load_json(ROOT / "deliverable-index.json")
        cls.sample = MODULE.load_json(ROOT / "fixtures" / "sample-integration-package.json")
        cls.invalid = MODULE.load_json(ROOT / "fixtures" / "invalid-write-enabled.json")
        cls.schema = MODULE.load_json(ROOT / "integration-package.schema.json")

    def test_full_local_package_passes(self):
        self.assertEqual(
            MODULE.run_validation(ROOT / "fixtures" / "sample-integration-package.json"),
            [],
        )

    def test_exact_twelve_deliverables_and_dependency_graph(self):
        self.assertEqual(self.index, MODULE.CANONICAL_INDEX)
        self.assertEqual([item["id"] for item in self.index["deliverables"]], MODULE.IDS)
        self.assertEqual(self.index["deliverables"][-1]["depends_on"], MODULE.IDS[:11])

    def test_aws_connection_is_rejected(self):
        package = copy.deepcopy(self.sample)
        package["safety_boundary"]["aws_connection"] = True
        self.assertIn("aws_connection_must_be_false", MODULE.validate_package(package, self.index))

    def test_iam_application_is_rejected(self):
        package = copy.deepcopy(self.sample)
        package["safety_boundary"]["iam_policy_application"] = True
        self.assertIn("iam_policy_application_must_be_false", MODULE.validate_package(package, self.index))

    def test_resource_change_is_rejected(self):
        package = copy.deepcopy(self.sample)
        package["safety_boundary"]["resource_change"] = True
        self.assertIn("resource_change_must_be_false", MODULE.validate_package(package, self.index))

    def test_production_change_authorization_is_rejected(self):
        errors = MODULE.validate_package(self.invalid, self.index)
        self.assertIn("production_change_must_not_be_authorized", errors)

    def test_missing_artifact_is_rejected(self):
        package = copy.deepcopy(self.sample)
        package["artifacts"].pop()
        self.assertIn("artifact_population_invalid", MODULE.validate_package(package, self.index))

    def test_reordered_artifact_is_rejected(self):
        package = copy.deepcopy(self.sample)
        package["artifacts"][0], package["artifacts"][1] = package["artifacts"][1], package["artifacts"][0]
        self.assertIn("artifact_order_or_identity_invalid", MODULE.validate_package(package, self.index))

    def test_dependency_graph_change_is_rejected(self):
        package = copy.deepcopy(self.sample)
        package["artifacts"][-1]["depends_on"] = MODULE.IDS[:10]
        self.assertIn("dependency_graph_invalid", MODULE.validate_package(package, self.index))

    def test_evidence_path_substitution_is_rejected(self):
        package = copy.deepcopy(self.sample)
        package["artifacts"][5]["evidence_path"] = package["artifacts"][6]["evidence_path"]
        self.assertIn("evidence_path_mismatch", MODULE.validate_package(package, self.index))

    def test_schema_safety_relaxation_is_rejected(self):
        schema = copy.deepcopy(self.schema)
        schema["properties"]["safety_boundary"]["properties"]["aws_connection"] = {"type": "boolean"}
        self.assertIn("schema_contract_invalid", MODULE.validate_schema_contract(schema))

    def test_schema_artifact_count_relaxation_is_rejected(self):
        schema = copy.deepcopy(self.schema)
        schema["properties"]["artifacts"]["minItems"] = 1
        self.assertIn("schema_contract_invalid", MODULE.validate_schema_contract(schema))

    def test_checklist_requires_all_twelve_ids(self):
        checklist = (ROOT / "readonly-adoption-checklist.md").read_text(encoding="utf-8")
        checked = MODULE.re.findall(r"^- \[x\] (D\d{2})\b", checklist, flags=MODULE.re.MULTILINE)
        self.assertEqual(checked, MODULE.IDS)

    def test_broken_markdown_link_is_rejected(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            markdown = Path(directory) / "broken.md"
            markdown.write_text("[missing](does-not-exist.md)\n", encoding="utf-8")
            errors = MODULE.validate_markdown_links([markdown])
        self.assertTrue(any(error.startswith("markdown_link_missing:") for error in errors))

    def test_all_index_artifacts_are_real_public_files(self):
        self.assertEqual(MODULE.validate_index(self.index), [])

    def test_artifact_semantics_preserve_readonly_boundary(self):
        self.assertEqual(MODULE.validate_artifact_semantics(), [])

    def test_package_audit_has_no_secret_pii_or_large_files(self):
        self.assertEqual(MODULE.audit_package_files(), [])

    def test_expected_results_bind_positive_and_negative_fixtures(self):
        expected = MODULE.load_json(ROOT / "expected-results.json")
        self.assertEqual(
            expected["fixtures"]["sample-integration-package.json"],
            {"result": "PASS", "errors": []},
        )
        invalid_errors = MODULE.validate_package(self.invalid, self.index)
        for error in expected["fixtures"]["invalid-write-enabled.json"]["required_errors"]:
            self.assertIn(error, invalid_errors)

    def test_json_files_parse(self):
        for path in ROOT.rglob("*.json"):
            with self.subTest(path=path.name):
                json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
