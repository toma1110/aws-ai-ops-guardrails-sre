import copy
import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("validate_adoption_package", ROOT / "validate_adoption_package.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)
BUILD_SPEC = importlib.util.spec_from_file_location("build_materials", ROOT / "build_materials.py")
BUILD_MODULE = importlib.util.module_from_spec(BUILD_SPEC)
assert BUILD_SPEC.loader is not None
BUILD_SPEC.loader.exec_module(BUILD_MODULE)


class AdoptionPackageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.complete = MODULE.load_json(ROOT / "fixtures" / "fixture-complete.json")

    def test_exact_fixture_population_matches_expected(self):
        results, errors = MODULE.validate_population(ROOT / "fixtures", ROOT / "expected-results.json")
        self.assertEqual(errors, [])
        self.assertEqual(len(results), 3)

    def test_complete_package_is_ready(self):
        self.assertEqual(MODULE.evaluate_package(self.complete), {"decision": "READY_FOR_STAKEHOLDER_REVIEW", "reason_codes": []})

    def test_each_required_concern_is_fail_closed(self):
        for concern_id in MODULE.CONCERNS:
            with self.subTest(concern_id=concern_id):
                package = copy.deepcopy(self.complete)
                package["concerns"] = [item for item in package["concerns"] if item["id"] != concern_id]
                self.assertIn("concern_ids_invalid", MODULE.validate_package(package))

    def test_existing_processes_cannot_be_replaced(self):
        package = copy.deepcopy(self.complete)
        package["adoption"]["role"] = "autonomous_operations"
        package["adoption"]["preserved_processes"].remove("release")
        errors = MODULE.validate_package(package)
        self.assertIn("adoption_role_invalid", errors)
        self.assertIn("preserved_processes_invalid", errors)

    def test_responsibility_and_review_populations_are_exact(self):
        package = copy.deepcopy(self.complete)
        package["responsibilities"].pop()
        package["security_review"].pop()
        errors = MODULE.validate_package(package)
        self.assertIn("responsibility_roles_invalid", errors)
        self.assertIn("review_check_ids_invalid", errors)

    def test_empty_review_evidence_is_fail_closed(self):
        package = copy.deepcopy(self.complete)
        package["security_review"][0]["evidence"] = ""
        self.assertIn("review_content_invalid", MODULE.validate_package(package))

    def test_fixture_production_change_claim_is_rejected(self):
        package = copy.deepcopy(self.complete)
        package["concerns"][0]["control"] = "AIが本番変更を実行する"
        self.assertIn("concern_safety_control_invalid:change_control", MODULE.validate_package(package))

    def test_fixture_release_recovery_iam_and_deletion_claims_are_rejected(self):
        for unsafe_text in ("AIがreleaseを実行する", "AIが自動復旧する", "AIがIAMを変更する", "AIがresourceを削除する"):
            with self.subTest(unsafe_text=unsafe_text):
                package = copy.deepcopy(self.complete)
                package["concerns"][0]["control"] = unsafe_text
                self.assertIn("concern_safety_control_invalid:change_control", MODULE.validate_package(package))

    def test_fixture_approval_bypass_and_human_approval_replacement_are_rejected(self):
        package = copy.deepcopy(self.complete)
        package["faq"][0]["answer"] = "AIが既存承認を迂回する"
        package["security_review"][5]["evidence"] = "AIが人間承認を置き換える"
        errors = MODULE.validate_package(package)
        self.assertIn("faq_safety_answer_invalid:change_control", errors)
        self.assertIn("review_safety_evidence_invalid:human_approval", errors)

    def test_fixture_accountability_reassignment_is_rejected(self):
        package = copy.deepcopy(self.complete)
        package["responsibilities"][0]["accountable_for"] = "最終判断と承認を行う"
        package["faq"][2]["owner"] = "ai_assistant"
        errors = MODULE.validate_package(package)
        self.assertIn("responsibility_assignment_invalid:ai_assistant", errors)
        self.assertIn("faq_safety_answer_invalid:wrong_answer_accountability", errors)

    def test_fixture_api_connection_safety_claim_is_rejected(self):
        package = copy.deepcopy(self.complete)
        package["faq"][3]["answer"] = "APIへ接続できれば安全である"
        self.assertIn("faq_safety_answer_invalid:api_connectivity", MODULE.validate_package(package))


class GeneratedMaterialSafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = BUILD_MODULE.load_json(ROOT / "stakeholder-input.json")
        cls.templates = BUILD_MODULE.load_templates(ROOT / "templates")

    def assert_rejected_before_render(self, concern_id, field, unsafe_text):
        data = copy.deepcopy(self.source)
        concern = next(item for item in data["concerns"] if item["id"] == concern_id)
        concern[field] = unsafe_text
        self.assertIn(f"safety_control_not_canonical:{concern_id}", BUILD_MODULE.validate_input(data))
        with self.assertRaisesRegex(ValueError, f"safety_control_not_canonical:{concern_id}"):
            BUILD_MODULE.build_documents(data, self.templates)

    def test_production_change_claim_is_rejected_before_render(self):
        self.assert_rejected_before_render("CHANGE", "boundary", "AIが本番変更を実行する")

    def test_release_recovery_iam_and_deletion_claims_are_rejected_before_render(self):
        for unsafe_text in (
            "AIがreleaseを実行する",
            "AIが自動復旧を実行する",
            "AIがIAMを変更する",
            "AIがresourceを削除する",
        ):
            with self.subTest(unsafe_text=unsafe_text):
                self.assert_rejected_before_render("CHANGE", "review_check", unsafe_text)

    def test_approval_bypass_claim_is_rejected_before_render(self):
        self.assert_rejected_before_render("CHANGE", "faq_answer", "AIは既存承認を迂回して実行する")

    def test_api_connection_safety_claim_is_rejected_before_render(self):
        self.assert_rejected_before_render("API_CONNECTION", "faq_answer", "APIへ接続できれば安全である")

    def test_accountability_control_cannot_be_reassigned(self):
        self.assert_rejected_before_render("ACCOUNTABILITY", "owner_role", "ai assistant")


if __name__ == "__main__":
    unittest.main()
