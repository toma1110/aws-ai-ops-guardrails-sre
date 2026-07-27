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

    def test_learner_markdown_uses_plain_human_confirmation_wording(self) -> None:
        for relative_path in (
            "README.md",
            "templates/adoption-scope.md",
            "examples/completed-adoption-scope.md",
            "exercises/scenarios.md",
        ):
            text = (ROOT / relative_path).read_text(encoding="utf-8")
            self.assertNotIn("人間の停止条件", text)
            self.assertNotIn("人間へ渡す情報", text)
            self.assertNotIn("人間へ引き継ぐ", text)

    def test_readme_explains_validation_architecture_before_code_steps(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        architecture_heading = "## なぜValidation Scriptを書くのか"
        self.assertLess(readme.index(architecture_heading), readme.index("## セットアップ"))
        for required_text in (
            "AWSやクラウドを操作するスクリプトではありません",
            "組織のルールやAI運用ポリシー",
            "Policy as Code",
            "本番向け完成品ではありません",
            "AIが成果物を生成",
            "Validation Script（品質チェック）",
            "ルールを満たしているか確認",
            "Human Review",
            "本番利用",
            "最終判断は必ず人間が行います",
            "Azure",
            "Google Cloud",
            "GitHub",
            "社内システム",
            "AWSへ接続しないため、AWS Regionの選択や設定も不要です",
        ):
            self.assertIn(required_text, readme)
        self.assertLess(
            readme.index("AIが成果物を生成"),
            readme.index("Validation Script（品質チェック）"),
        )
        self.assertLess(
            readme.index("Validation Script（品質チェック）"),
            readme.index("Human Review"),
        )
        self.assertLess(readme.index("Human Review"), readme.index("本番利用"))

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
