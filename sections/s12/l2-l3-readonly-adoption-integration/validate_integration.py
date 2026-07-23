import argparse
import json
import re
import sys
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = PACKAGE_ROOT.parents[2]

IDS = [f"D{number:02d}" for number in range(1, 13)]
DEPENDENCIES = {
    "D01": [],
    "D02": ["D01"],
    "D03": ["D01"],
    "D04": ["D01", "D02", "D03"],
    "D05": ["D03", "D04"],
    "D06": ["D04", "D05"],
    "D07": ["D01", "D06"],
    "D08": ["D06", "D07"],
    "D09": ["D03", "D07", "D08"],
    "D10": ["D01", "D05", "D09"],
    "D11": ["D02", "D03", "D05", "D06", "D07", "D08", "D09"],
    "D12": IDS[:11],
}
NAMES = [
    "導入スコープ",
    "MCP接続前確認",
    "AI作業分類",
    "IAM設計",
    "禁止操作",
    "監査観点",
    "調査観点",
    "AI実行ログ",
    "人間判断",
    "現場説明",
    "評価テスト",
    "ReadOnly導入チェックリスト",
]
SECTIONS = ["s1", "s2", "s3", "s5", "s5", "s6", "s7", "s8", "s9", "s10", "s11", "s12"]
PATHS = [
    ["sections/s1/l3-readonly-adoption-scope/examples/completed-adoption-scope.md"],
    ["sections/s2/l3-mcp-preconnection-checklist/examples/completed-mcp-preconnection-checklist.md"],
    ["sections/s3/l3-ai-work-classification/examples/completed-ai-work-classification.md"],
    ["sections/s5/l3-readonly-iam-guardrails/examples/iam-guardrail-package/role-session-boundary.json"],
    ["sections/s5/l3-readonly-iam-guardrails/examples/iam-guardrail-package/iam-policy.json"],
    [
        "sections/s6/l3-cloudtrail-audit/audit-checklist.md",
        "sections/s6/l3-cloudtrail-audit/fixtures/expected-audit.json",
    ],
    ["sections/s7/l3-incident-investigation/fixtures/expected-investigation.json"],
    [
        "sections/s8/l3-ai-execution-log-validation/ai-execution-log.schema.json",
        "sections/s8/l3-ai-execution-log-validation/fixtures/valid-local.json",
    ],
    [
        "sections/s9/l3-human-decision-handoff/expected-results.json",
        "sections/s9/l3-human-decision-handoff/handoff-template.json",
    ],
    [
        "sections/s10/l3-stakeholder-adoption-review/generated/introduction.md",
        "sections/s10/l3-stakeholder-adoption-review/generated/faq.md",
        "sections/s10/l3-stakeholder-adoption-review/generated/security-review-checklist.md",
    ],
    [
        "sections/s11/l3-pre-deployment-test-pack/evaluation-cases.json",
        "sections/s11/l3-pre-deployment-test-pack/decision-table.md",
    ],
    ["sections/s12/l2-l3-readonly-adoption-integration/readonly-adoption-checklist.md"],
]
CANONICAL_INDEX = {
    "schema": "s12-deliverable-index-v1",
    "deliverables": [
        {
            "id": artifact_id,
            "name": name,
            "section": section,
            "artifact_paths": paths,
            "depends_on": DEPENDENCIES[artifact_id],
        }
        for artifact_id, name, section, paths in zip(IDS, NAMES, SECTIONS, PATHS)
    ],
}

MARKDOWN_LINK = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")
ACCOUNT_ID = re.compile(r"(?<!\d)\d{12}(?!\d)")
PRIVATE_KEY = re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")
AWS_ACCESS_KEY = re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")
EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def is_nonempty_string(value):
    return isinstance(value, str) and bool(value.strip())


def validate_schema_contract(schema):
    errors = []
    required = {"schema", "case_id", "environment", "safety_boundary", "artifacts", "decision"}
    if not isinstance(schema, dict) or schema.get("type") != "object":
        return ["schema_contract_invalid"]
    if set(schema.get("required", [])) != required or schema.get("additionalProperties") is not False:
        errors.append("schema_contract_invalid")
    properties = schema.get("properties", {})
    if properties.get("schema", {}).get("const") != "s12-integration-package-v1":
        errors.append("schema_contract_invalid")
    safety = properties.get("safety_boundary", {}).get("properties", {})
    for key in ("aws_connection", "iam_policy_application", "resource_change", "external_send"):
        if safety.get(key, {}).get("const") is not False:
            errors.append("schema_contract_invalid")
    artifacts = properties.get("artifacts", {})
    if artifacts.get("minItems") != 12 or artifacts.get("maxItems") != 12:
        errors.append("schema_contract_invalid")
    decision = properties.get("decision", {}).get("properties", {})
    if decision.get("production_change_authorized", {}).get("const") is not False:
        errors.append("schema_contract_invalid")
    basis = decision.get("basis_ids", {})
    if basis.get("minItems") != 12 or basis.get("maxItems") != 12 or basis.get("uniqueItems") is not True:
        errors.append("schema_contract_invalid")
    return sorted(set(errors))


def validate_package_structure(package):
    errors = []
    if not isinstance(package, dict):
        return ["package_must_be_object"]
    if set(package) != {"schema", "case_id", "environment", "safety_boundary", "artifacts", "decision"}:
        errors.append("package_fields_invalid")
    if package.get("schema") != "s12-integration-package-v1":
        errors.append("package_schema_invalid")
    if not is_nonempty_string(package.get("case_id")):
        errors.append("case_id_invalid")

    environment = package.get("environment")
    if not isinstance(environment, dict) or set(environment) != {
        "kind", "data_source", "aws_account_id", "credentials"
    }:
        errors.append("environment_fields_invalid")
    else:
        if environment.get("kind") != "synthetic-local":
            errors.append("environment_must_be_synthetic_local")
        if environment.get("data_source") != "course-fixtures-only":
            errors.append("data_source_must_be_course_fixtures_only")
        if environment.get("aws_account_id") is not None:
            errors.append("aws_account_id_must_be_null")
        if environment.get("credentials") is not False:
            errors.append("credentials_must_be_false")

    safety = package.get("safety_boundary")
    if not isinstance(safety, dict) or set(safety) != {
        "aws_connection", "iam_policy_application", "resource_change", "external_send"
    }:
        errors.append("safety_boundary_fields_invalid")
    else:
        for key, error in (
            ("aws_connection", "aws_connection_must_be_false"),
            ("iam_policy_application", "iam_policy_application_must_be_false"),
            ("resource_change", "resource_change_must_be_false"),
            ("external_send", "external_send_must_be_false"),
        ):
            if safety.get(key) is not False:
                errors.append(error)

    artifacts = package.get("artifacts")
    if not isinstance(artifacts, list) or len(artifacts) != 12:
        errors.append("artifact_population_invalid")
    else:
        actual_ids = []
        for item in artifacts:
            if not isinstance(item, dict) or set(item) != {
                "id", "status", "evidence_path", "depends_on", "result"
            }:
                errors.append("artifact_fields_invalid")
                continue
            actual_ids.append(item.get("id"))
            if item.get("status") != "ready" or item.get("result") != "pass":
                errors.append("artifact_not_ready")
            if not is_nonempty_string(item.get("evidence_path")):
                errors.append("artifact_evidence_path_invalid")
            dependencies = item.get("depends_on")
            if not isinstance(dependencies, list) or len(set(dependencies)) != len(dependencies):
                errors.append("artifact_dependency_type_invalid")
        if actual_ids != IDS:
            errors.append("artifact_order_or_identity_invalid")

    decision = package.get("decision")
    if not isinstance(decision, dict) or set(decision) != {
        "outcome", "production_change_authorized", "next_actor", "basis_ids"
    }:
        errors.append("decision_fields_invalid")
    else:
        if decision.get("outcome") != "READY_FOR_READONLY_PILOT_REVIEW":
            errors.append("decision_outcome_invalid")
        if decision.get("production_change_authorized") is not False:
            errors.append("production_change_must_not_be_authorized")
        if decision.get("next_actor") != "change owner and security owner":
            errors.append("decision_next_actor_invalid")
        if decision.get("basis_ids") != IDS:
            errors.append("decision_basis_invalid")
    return sorted(set(errors))


def validate_index(index):
    if index != CANONICAL_INDEX:
        return ["deliverable_index_not_canonical"]
    errors = []
    repository = REPOSITORY_ROOT.resolve()
    for item in index["deliverables"]:
        for relative in item["artifact_paths"]:
            path = (REPOSITORY_ROOT / relative).resolve()
            try:
                path.relative_to(repository)
            except ValueError:
                errors.append(f"artifact_outside_repository:{item['id']}")
                continue
            if not path.is_file() or path.is_symlink():
                errors.append(f"artifact_missing:{item['id']}:{relative}")
    return errors


def validate_artifact_semantics():
    errors = []
    role = load_json(REPOSITORY_ROOT / PATHS[3][0])
    if (
        role.get("local_only") is not True
        or role.get("aws_connection") is not False
        or role.get("credentials_required") is not False
        or role.get("policy_application") is not False
    ):
        errors.append("iam_design_safety_boundary_invalid")

    policy = load_json(REPOSITORY_ROOT / PATHS[4][0])
    statements = policy.get("Statement", [])
    allows = [item for item in statements if item.get("Effect") == "Allow"]
    denies = [item for item in statements if item.get("Effect") == "Deny"]
    allowed_actions = [action for item in allows for action in item.get("Action", [])]
    denied_actions = [action for item in denies for action in item.get("Action", [])]
    if not allowed_actions or any(action == "*" or action.endswith(":*") for action in allowed_actions):
        errors.append("iam_allow_boundary_invalid")
    if "iam:*" not in denied_actions or not any(
        "Delete" in action or "Terminate" in action for action in denied_actions
    ):
        errors.append("explicit_deny_missing")

    audit_checklist = (REPOSITORY_ROOT / PATHS[5][0]).read_text(encoding="utf-8")
    if audit_checklist.count("- [ ]") < 10 or "AWSへ接続" not in audit_checklist:
        errors.append("audit_checklist_incomplete")

    investigation = load_json(REPOSITORY_ROOT / PATHS[6][0])
    for key in ("facts", "hypotheses", "unknowns", "human_decisions"):
        if not isinstance(investigation.get(key), list) or not investigation[key]:
            errors.append("investigation_separation_invalid")

    ai_log = load_json(REPOSITORY_ROOT / PATHS[7][1])
    if (
        ai_log.get("external_send", {}).get("allowed") is not False
        or ai_log.get("data_handling", {}).get("masking_applied") is not True
        or not ai_log.get("cloudtrail_correlation", {}).get("event_ids")
    ):
        errors.append("ai_execution_log_boundary_invalid")

    decisions = load_json(REPOSITORY_ROOT / PATHS[8][0])
    if (
        not decisions
        or any(
            result.get("decision") not in {"NEED_HUMAN_DECISION", "CONTINUE_READONLY"}
            for result in decisions.values()
        )
        or not any(result.get("decision") == "NEED_HUMAN_DECISION" for result in decisions.values())
    ):
        errors.append("human_decision_results_invalid")

    introduction = (REPOSITORY_ROOT / PATHS[9][0]).read_text(encoding="utf-8")
    if not all(token in introduction for token in ("既存運用", "変更", "release", "AIは実行しません")):
        errors.append("stakeholder_explanation_incomplete")

    evaluation = load_json(REPOSITORY_ROOT / PATHS[10][0])
    if evaluation.get("expected_summary") != {"PASS": 1, "REVIEW": 2, "FAIL": 3}:
        errors.append("evaluation_summary_invalid")

    checklist = (REPOSITORY_ROOT / PATHS[11][0]).read_text(encoding="utf-8")
    checked = re.findall(r"^- \[x\] (D\d{2})\b", checklist, flags=re.MULTILINE)
    if checked != IDS:
        errors.append("readonly_checklist_population_invalid")
    return sorted(set(errors))


def validate_markdown_links(paths=None):
    errors = []
    paths = paths or [PACKAGE_ROOT / "README.md", PACKAGE_ROOT / "readonly-adoption-checklist.md"]
    repository = REPOSITORY_ROOT.resolve()
    for markdown in paths:
        text = Path(markdown).read_text(encoding="utf-8")
        for target in MARKDOWN_LINK.findall(text):
            target = target.strip().split("#", 1)[0]
            if not target or target.startswith(("https://", "http://", "mailto:")):
                continue
            linked = (Path(markdown).parent / target).resolve()
            try:
                linked.relative_to(repository)
            except ValueError:
                errors.append(f"markdown_link_outside_repository:{Path(markdown).name}:{target}")
                continue
            if not linked.exists():
                errors.append(f"markdown_link_missing:{Path(markdown).name}:{target}")
    return errors


def validate_package(package, index):
    errors = validate_package_structure(package)
    if index != CANONICAL_INDEX:
        return sorted(set(errors + ["deliverable_index_not_canonical"]))
    artifacts = package.get("artifacts")
    if not isinstance(artifacts, list) or len(artifacts) != 12:
        return sorted(set(errors))
    for expected, actual in zip(index["deliverables"], artifacts):
        if not isinstance(actual, dict):
            continue
        if actual.get("depends_on") != expected["depends_on"]:
            errors.append("dependency_graph_invalid")
        if actual.get("evidence_path") != expected["artifact_paths"][0]:
            errors.append("evidence_path_mismatch")
    return sorted(set(errors))


def audit_package_files():
    errors = []
    for path in PACKAGE_ROOT.rglob("*"):
        if not path.is_file() or "__pycache__" in path.parts:
            continue
        relative = path.relative_to(PACKAGE_ROOT)
        if path.stat().st_size > 1024 * 1024:
            errors.append(f"large_file:{relative}")
        if path.suffix.lower() not in {".md", ".json", ".py"}:
            continue
        text = path.read_text(encoding="utf-8")
        if PRIVATE_KEY.search(text) or AWS_ACCESS_KEY.search(text):
            errors.append(f"secret_pattern:{relative}")
        if ACCOUNT_ID.search(text):
            errors.append(f"aws_account_id_pattern:{relative}")
        if EMAIL.search(text):
            errors.append(f"pii_email_pattern:{relative}")
        if re.search(r"\b[A-Za-z]:\\Users\\", text, flags=re.IGNORECASE):
            errors.append(f"local_absolute_path:{relative}")
    return errors


def run_validation(package_path):
    try:
        index = load_json(PACKAGE_ROOT / "deliverable-index.json")
        schema = load_json(PACKAGE_ROOT / "integration-package.schema.json")
        package = load_json(package_path)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return [f"package_read_error:{type(exc).__name__}"]
    errors = []
    errors.extend(validate_schema_contract(schema))
    errors.extend(validate_index(index))
    errors.extend(validate_artifact_semantics())
    errors.extend(validate_markdown_links())
    errors.extend(validate_package(package, index))
    errors.extend(audit_package_files())
    return sorted(set(errors))


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    parser = argparse.ArgumentParser(description="Validate the local S12 integration package")
    parser.add_argument(
        "--package",
        default=PACKAGE_ROOT / "fixtures" / "sample-integration-package.json",
    )
    args = parser.parse_args()
    expected = load_json(PACKAGE_ROOT / "expected-results.json")["fixtures"]
    sample_path = Path(args.package)
    errors = run_validation(sample_path)
    if errors:
        print(f"{sample_path.name}: FAIL")
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(f"{sample_path.name}: PASS")

    invalid_path = PACKAGE_ROOT / "fixtures" / "invalid-write-enabled.json"
    invalid = load_json(invalid_path)
    index = load_json(PACKAGE_ROOT / "deliverable-index.json")
    invalid_errors = validate_package(invalid, index)
    required = expected["invalid-write-enabled.json"]["required_errors"]
    if not all(error in invalid_errors for error in required):
        print("invalid-write-enabled.json: UNEXPECTED_RESULT")
        for error in invalid_errors:
            print(f"ERROR: {error}")
        return 1
    print("invalid-write-enabled.json: EXPECTED_FAIL")
    print("PASS: 12 deliverables, checklist, links, schema, and sample tests are consistent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
