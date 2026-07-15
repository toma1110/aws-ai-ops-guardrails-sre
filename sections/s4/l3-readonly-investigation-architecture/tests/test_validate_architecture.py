from __future__ import annotations

import importlib.util
import json
import re
import unittest
from copy import deepcopy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "validate_architecture.py"
SPEC = importlib.util.spec_from_file_location("validate_architecture", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


def example() -> str:
    return (ROOT / "examples" / "completed-readonly-investigation-architecture.md").read_text(encoding="utf-8")


def fixture() -> dict[str, object]:
    return json.loads((ROOT / "fixtures" / "architecture-requirements.json").read_text(encoding="utf-8"))


class ValidateArchitectureTests(unittest.TestCase):
    def test_completed_example_is_valid(self) -> None:
        self.assertEqual([], VALIDATOR.validate_text(example(), fixture()))

    def test_unfilled_template_is_invalid(self) -> None:
        text = (ROOT / "templates" / "readonly-investigation-architecture.md").read_text(encoding="utf-8")
        errors = VALIDATOR.validate_text(text, fixture())
        self.assertTrue(any("unresolved placeholders" in error for error in errors))
        self.assertTrue(any("scope mismatch" in error for error in errors))

    def test_scope_must_match_introduction_boundary(self) -> None:
        changed = example().replace(
            "SC-03 | OUT: AIは変更・release・IAM変更・削除・自動復旧を実行しない",
            "SC-03 | IN: AIは自動復旧を実行する",
        )
        self.assertIn("scope mismatch: SC-03", VALIDATOR.validate_text(changed, fixture()))

    def test_all_information_sources_are_required(self) -> None:
        for node_id in ("CW", "CT", "CFG"):
            changed = "\n".join(line for line in example().splitlines() if not line.startswith(f"| {node_id} |"))
            self.assertIn(f"missing node row: {node_id}", VALIDATOR.validate_text(changed, fixture()))

    def test_permission_boundary_flow_cannot_be_relabelled_write(self) -> None:
        changed = example().replace(
            "| F04 | IAM | CW | readonly_query | メトリクスとログを参照 |",
            "| F04 | IAM | CW | write | メトリクスとログを変更 |",
        )
        errors = VALIDATOR.validate_text(changed, fixture())
        self.assertIn("flow kind mismatch: F04", errors)
        self.assertIn("flow label mismatch: F04", errors)

    def test_cloudtrail_and_ai_log_audit_paths_are_independent(self) -> None:
        changed = "\n".join(line for line in example().splitlines() if not line.startswith("| F11 |"))
        self.assertIn("missing flow row: F11", VALIDATOR.validate_text(changed, fixture()))

    def test_ai_cannot_connect_directly_to_existing_operations(self) -> None:
        requirements = deepcopy(fixture())
        requirements["required_flows"].append(
            {"id": "F14", "from": "AI", "to": "OPS", "kind": "human_decision", "label": "AIが既存運用を実行"}
        )
        changed = example().replace(
            "| F13 | HUMAN | OPS | human_decision | 人間が既存手順で判断・実行 |",
            "| F13 | HUMAN | OPS | human_decision | 人間が既存手順で判断・実行 |\n| F14 | AI | OPS | human_decision | AIが既存運用を実行 |",
        )
        self.assertIn("AI must not connect directly to existing operations", VALIDATOR.validate_text(changed, requirements))

    def test_local_only_safety_declarations_are_required(self) -> None:
        requirements = deepcopy(fixture())
        requirements["aws_connection"] = True
        requirements["credentials_required"] = True
        errors = VALIDATOR.validate_text(example(), requirements)
        self.assertIn("requirements must declare aws_connection: false", errors)
        self.assertIn("requirements must declare credentials_required: false", errors)

    def test_empty_mermaid_is_invalid(self) -> None:
        changed = re.sub(
            r"```mermaid\s*\n.*?```",
            "```mermaid\nflowchart LR\n```",
            example(),
            flags=re.DOTALL,
        )
        errors = VALIDATOR.validate_text(changed, fixture())
        self.assertIn("missing Mermaid node: HUMAN", errors)
        self.assertIn("missing Mermaid edge: F01", errors)

    def test_divergent_mermaid_edge_is_invalid(self) -> None:
        changed = example().replace(
            "AI -->|ReadOnly調査要求| MCP",
            "AI -->|ReadOnly調査要求| CT",
        )
        self.assertIn("Mermaid edge to mismatch: F02", VALIDATOR.validate_text(changed, fixture()))

    def test_inline_flow_id_comment_that_caused_mermaid_parse_failure_is_invalid(self) -> None:
        changed = example().replace(
            "  %% F02\n  AI -->|ReadOnly調査要求| MCP",
            "  AI -->|ReadOnly調査要求| MCP %% F02",
        )
        errors = VALIDATOR.validate_text(changed, fixture())
        self.assertIn("unrecognized Mermaid line: AI -->|ReadOnly調査要求| MCP %% F02", errors)
        self.assertIn("missing Mermaid edge: F02", errors)

    def test_mermaid_edge_without_flow_id_comment_is_invalid(self) -> None:
        changed = example().replace("  %% F02\n", "")
        self.assertIn(
            "Mermaid edge is missing a preceding Flow ID comment: AI->MCP",
            VALIDATOR.validate_text(changed, fixture()),
        )

    def test_duplicate_flow_id_comment_is_invalid(self) -> None:
        changed = example().replace("  %% F02\n", "  %% F02\n  %% F02\n")
        errors = VALIDATOR.validate_text(changed, fixture())
        self.assertIn("Flow ID comment is not bound to an edge: F02", errors)
        self.assertIn("duplicate Mermaid Flow ID comment: F02", errors)

    def test_flow_id_comment_must_be_immediately_adjacent_to_edge(self) -> None:
        changed = example().replace("  %% F02\n  AI -->", "  %% F02\n\n  AI -->")
        errors = VALIDATOR.validate_text(changed, fixture())
        self.assertIn("Flow ID comment must be immediately followed by an edge: F02", errors)
        self.assertIn("Mermaid edge is missing a preceding Flow ID comment: AI->MCP", errors)

    def test_forbidden_direct_ai_to_ops_mermaid_edge_is_invalid(self) -> None:
        changed = example().replace(
            "  HUMAN ==>|人間が既存手順で判断・実行| OPS",
            "  HUMAN ==>|人間が既存手順で判断・実行| OPS\n"
            "  %% F99\n"
            "  AI -->|既存運用を直接実行| OPS",
        )
        errors = VALIDATOR.validate_text(changed, fixture())
        self.assertIn("unknown Mermaid edge: F99", errors)
        self.assertIn("Mermaid AI must not connect directly to existing operations", errors)

    def test_missing_and_unknown_mermaid_nodes_and_edges_are_invalid(self) -> None:
        changed = example().replace('  CFG["AWS Config"]\n', '  OTHER["未知の情報源"]\n').replace(
            "  %% F06\n  IAM -->|構成履歴を参照| CFG\n", ""
        )
        errors = VALIDATOR.validate_text(changed, fixture())
        self.assertIn("missing Mermaid node: CFG", errors)
        self.assertIn("unknown Mermaid node: OTHER", errors)
        self.assertIn("missing Mermaid edge: F06", errors)


if __name__ == "__main__":
    unittest.main()

