import argparse
import json
import sys
from pathlib import Path


CONCERNS = {"change_control", "log_handling", "wrong_answer_accountability", "api_connectivity"}
PROCESSES = {"approval", "incident_response", "release"}
PROHIBITED = {"production_change", "release", "automatic_recovery", "iam_change", "delete"}
ROLES = {"ai_assistant", "operator", "security", "system_owner"}
REVIEW_CHECKS = {"scope", "identity_permission", "data_log", "prompt_injection", "auditability", "human_approval", "incident_exit"}
REVIEW_STATUSES = {"pass", "review", "fail"}
ROOT_FIELDS = {"package_id", "concerns", "adoption", "responsibilities", "introduction", "faq", "security_review"}
CANONICAL_CONCERN_CONTROLS = {
    "change_control": ("調査補助だけを許可し変更操作を禁止する", "許可・禁止操作一覧", "operations owner"),
    "log_handling": ("送信範囲、マスキング、保持、閲覧権限を事前reviewする", "data flowとlog handling設計", "security"),
    "wrong_answer_accountability": ("AI回答を判断材料に限定し最終判断者を人間に固定する", "責任分界表", "system owner"),
    "api_connectivity": ("identity、最小権限、監査、停止条件を別々にreviewする", "接続前review記録", "security"),
}
CANONICAL_RESPONSIBILITIES = {
    "ai_assistant": ("根拠付きの調査候補を提示する", "承認、変更、最終判断"),
    "operator": ("根拠を確認して既存手順で対応する", "security例外の単独承認"),
    "security": ("接続、権限、data、監査controlをreviewする", "incident command"),
    "system_owner": ("導入可否と業務上の最終判断を行う", "AI出力の無検証採用"),
}
CANONICAL_FAQ = {
    "change_control": ("変更は禁止し、人間の既存承認を維持する", "operations owner"),
    "log_handling": ("送信・保持・maskingをsecurityが事前reviewする", "security"),
    "wrong_answer_accountability": ("system ownerが根拠を確認して最終判断する", "system owner"),
    "api_connectivity": ("接続可否と安全性を分けてreviewする", "security"),
}
CANONICAL_REVIEW_EVIDENCE = {
    "scope": ("許可・禁止操作一覧", "operations owner"),
    "identity_permission": ("専用identityと最小権限の設計案", "security"),
    "data_log": ("data flowとmasking設計案", "security"),
    "prompt_injection": ("信頼しない入力と停止条件のtest計画", "security"),
    "auditability": ("AI実行IDとAPI監査の相関設計案", "operations owner"),
    "human_approval": ("既存承認processと責任分界表", "system owner"),
    "incident_exit": ("停止、連絡、無効化、既存運用への復帰手順案", "incident commander"),
}


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def exact_ids(items, expected):
    return isinstance(items, list) and len(items) == len(expected) and {item.get("id") for item in items if isinstance(item, dict)} == expected


def validate_package(package):
    errors = []
    if not isinstance(package, dict) or set(package) != ROOT_FIELDS:
        return ["package_fields_invalid"]
    if not nonempty(package.get("package_id")):
        errors.append("package_id_invalid")

    concerns = package.get("concerns")
    if not exact_ids(concerns, CONCERNS):
        errors.append("concern_ids_invalid")
    elif any(set(item) != {"id", "statement", "control", "evidence", "owner"} or any(not nonempty(item[key]) for key in ("statement", "control", "evidence", "owner")) for item in concerns):
        errors.append("concern_content_invalid")
    else:
        for item in concerns:
            if (item["control"], item["evidence"], item["owner"]) != CANONICAL_CONCERN_CONTROLS[item["id"]]:
                errors.append(f"concern_safety_control_invalid:{item['id']}")

    adoption = package.get("adoption")
    if not isinstance(adoption, dict):
        adoption = {}
    if adoption.get("role") != "readonly_investigation_assistance":
        errors.append("adoption_role_invalid")
    if adoption.get("preserved_processes") != ["approval", "incident_response", "release"]:
        errors.append("preserved_processes_invalid")
    if set(adoption.get("prohibited_actions", [])) != PROHIBITED or len(adoption.get("prohibited_actions", [])) != len(PROHIBITED):
        errors.append("prohibited_actions_invalid")
    if not nonempty(adoption.get("escalation_owner")):
        errors.append("escalation_owner_invalid")

    responsibilities = package.get("responsibilities")
    if not exact_ids([{"id": item.get("role")} for item in responsibilities] if isinstance(responsibilities, list) else None, ROLES):
        errors.append("responsibility_roles_invalid")
    elif any(set(item) != {"role", "accountable_for", "not_accountable_for"} or not nonempty(item["accountable_for"]) or not nonempty(item["not_accountable_for"]) for item in responsibilities):
        errors.append("responsibility_content_invalid")
    else:
        for item in responsibilities:
            if (item["accountable_for"], item["not_accountable_for"]) != CANONICAL_RESPONSIBILITIES[item["role"]]:
                errors.append(f"responsibility_assignment_invalid:{item['role']}")

    introduction = package.get("introduction")
    if not isinstance(introduction, dict) or set(introduction) != {"audience", "message", "limitations"} or any(not nonempty(introduction.get(key)) for key in ("audience", "message", "limitations")):
        errors.append("introduction_invalid")

    faq = package.get("faq")
    if not isinstance(faq, list) or len(faq) != len(CONCERNS) or {item.get("concern_id") for item in faq if isinstance(item, dict)} != CONCERNS:
        errors.append("faq_concern_ids_invalid")
    elif any(set(item) != {"concern_id", "answer", "owner"} or not nonempty(item["answer"]) or not nonempty(item["owner"]) for item in faq):
        errors.append("faq_content_invalid")
    else:
        for item in faq:
            if (item["answer"], item["owner"]) != CANONICAL_FAQ[item["concern_id"]]:
                errors.append(f"faq_safety_answer_invalid:{item['concern_id']}")

    reviews = package.get("security_review")
    if not exact_ids(reviews, REVIEW_CHECKS):
        errors.append("review_check_ids_invalid")
    elif any(set(item) != {"id", "status", "evidence", "owner"} or item["status"] not in REVIEW_STATUSES or not nonempty(item["evidence"]) or not nonempty(item["owner"]) for item in reviews):
        errors.append("review_content_invalid")
    else:
        for item in reviews:
            if (item["evidence"], item["owner"]) != CANONICAL_REVIEW_EVIDENCE[item["id"]]:
                errors.append(f"review_safety_evidence_invalid:{item['id']}")
    return errors


def evaluate_package(package):
    errors = validate_package(package)
    return {"decision": "INVALID_PACKAGE" if errors else "READY_FOR_STAKEHOLDER_REVIEW", "reason_codes": errors}


def validate_population(fixtures_dir, expected_path):
    expected_document = load_json(expected_path)
    expected = expected_document.get("fixture_expectations", expected_document)
    paths = sorted(Path(fixtures_dir).glob("*.json"))
    errors = []
    if {path.name for path in paths} != set(expected):
        errors.append("fixture population does not exactly match expected results")
    results = {}
    for path in paths:
        try:
            result = evaluate_package(load_json(path))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            result = {"decision": "INVALID_PACKAGE", "reason_codes": [f"json_read_error:{type(exc).__name__}"]}
        results[path.name] = result
        if expected.get(path.name) != result:
            errors.append(f"unexpected result: {path.name}")
    return results, errors


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    parser = argparse.ArgumentParser(description="Validate a local stakeholder adoption package")
    parser.add_argument("--fixtures", required=True)
    parser.add_argument("--expected", required=True)
    args = parser.parse_args()
    results, errors = validate_population(args.fixtures, args.expected)
    for name, result in sorted(results.items()):
        reasons = ",".join(result["reason_codes"]) or "none"
        print(f"{name}: {result['decision']} ({reasons})")
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(f"PASS: {len(results)} packages matched expected results")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
