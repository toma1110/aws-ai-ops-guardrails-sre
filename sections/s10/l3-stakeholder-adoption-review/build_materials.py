import argparse
import json
from pathlib import Path


CONCERN_IDS = ("CHANGE", "LOG", "ACCOUNTABILITY", "API_CONNECTION")
OUTPUT_FILES = ("introduction.md", "faq.md", "security-review-checklist.md")
TOP_LEVEL_FIELDS = {"schema", "section_id", "scenario", "constraints", "concerns"}
SCENARIO_FIELDS = {"organization", "purpose", "pilot_scope", "decision_owner", "security_owner"}
CONSTRAINT_FIELDS = {
    "aws_connection",
    "credential_required",
    "production_change",
    "existing_approval_preserved",
    "incident_response_preserved",
    "release_process_preserved",
}
CONCERN_FIELDS = {
    "id",
    "question",
    "boundary",
    "owner_role",
    "evidence_required",
    "faq_answer",
    "review_check",
}
CANONICAL_CONTROLS = {
    "CHANGE": {
        "boundary": "AIは調査候補と根拠を整理するだけで、変更、復旧、release、削除を実行しない",
        "owner_role": "change approver",
        "faq_answer": "本番変更は行いません。提案は既存の変更承認へ渡し、人間が判断します。",
        "review_check": "AIの役割が調査補助に限定され、変更操作が既存承認を迂回しない",
    },
    "LOG": {
        "boundary": "synthetic dataで評価し、実運用では必要最小限の記録、masking、保持期間、外部送信境界を事前に決める",
        "owner_role": "security reviewer",
        "faq_answer": "ログは無制限に保存しません。記録目的、masking、保持期間、閲覧者、外部送信境界をsecurity reviewで決めます。",
        "review_check": "ログの目的、最小化、masking、保持、閲覧権限、外部送信境界が明記されている",
    },
    "ACCOUNTABILITY": {
        "boundary": "AI出力を確定事実や承認として扱わず、根拠と不明点を添えて人間のdecision ownerへ渡す",
        "owner_role": "incident commander",
        "faq_answer": "AIは判断主体ではありません。根拠と不明点を示し、incident commanderが既存手順で判断します。",
        "review_check": "誤回答時の判断者、検証方法、訂正、エスカレーションの責任分界が明記されている",
    },
    "API_CONNECTION": {
        "boundary": "この演習ではAWSへ接続せず、実運用のAPI接続前にReadOnly範囲、最小権限、監査、機密情報、prompt injection、費用をreviewする",
        "owner_role": "security reviewer",
        "faq_answer": "接続手段は安全性の保証ではありません。接続前に権限、監査、機密情報、prompt injection、費用、停止条件を確認します。",
        "review_check": "接続前reviewがあり、接続方法と権限・監査・承認が別の境界として扱われている",
    },
}


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def validate_input(data):
    errors = []
    if not isinstance(data, dict) or set(data) != TOP_LEVEL_FIELDS:
        return ["top_level_fields_invalid"]
    if data.get("schema") != "s10-introduction-input-v1" or data.get("section_id") != "s10":
        errors.append("identity_invalid")

    scenario = data.get("scenario")
    if not isinstance(scenario, dict) or set(scenario) != SCENARIO_FIELDS:
        errors.append("scenario_fields_invalid")
    elif any(not _nonempty(scenario[field]) for field in SCENARIO_FIELDS):
        errors.append("scenario_value_missing")

    constraints = data.get("constraints")
    if not isinstance(constraints, dict) or set(constraints) != CONSTRAINT_FIELDS:
        errors.append("constraint_fields_invalid")
    else:
        if any(type(constraints[field]) is not bool for field in CONSTRAINT_FIELDS):
            errors.append("constraint_type_invalid")
        if constraints.get("aws_connection") or constraints.get("credential_required") or constraints.get("production_change"):
            errors.append("unsafe_action_requested")
        if not all(
            constraints.get(field)
            for field in (
                "existing_approval_preserved",
                "incident_response_preserved",
                "release_process_preserved",
            )
        ):
            errors.append("existing_process_not_preserved")

    concerns = data.get("concerns")
    if not isinstance(concerns, list):
        errors.append("concerns_must_be_list")
    else:
        ids = [item.get("id") for item in concerns if isinstance(item, dict)]
        if ids != list(CONCERN_IDS):
            errors.append("concern_population_or_order_invalid")
        for item in concerns:
            if not isinstance(item, dict) or set(item) != CONCERN_FIELDS:
                errors.append("concern_fields_invalid")
                continue
            if any(not _nonempty(item[field]) for field in CONCERN_FIELDS):
                errors.append(f"concern_value_missing:{item.get('id', 'unknown')}")
            concern_id = item.get("id")
            canonical = CANONICAL_CONTROLS.get(concern_id)
            if canonical is not None and any(item.get(field) != value for field, value in canonical.items()):
                errors.append(f"safety_control_not_canonical:{concern_id}")
    return errors


def load_templates(template_dir):
    template_dir = Path(template_dir)
    return {
        "introduction": (template_dir / "introduction-template.md").read_text(encoding="utf-8"),
        "faq": (template_dir / "faq-template.md").read_text(encoding="utf-8"),
        "checklist": (template_dir / "security-review-checklist-template.md").read_text(encoding="utf-8"),
    }


def _render(template, replacements):
    rendered = template
    for key, value in replacements.items():
        rendered = rendered.replace("{{" + key + "}}", value)
    if "{{" in rendered or "}}" in rendered:
        raise ValueError("unresolved_template_placeholder")
    return rendered.rstrip() + "\n"


def build_documents(data, templates):
    errors = validate_input(data)
    if errors:
        raise ValueError(",".join(errors))
    scenario = data["scenario"]
    concerns = data["concerns"]
    preserved = "\n".join(
        (
            "- 変更は既存のchange approvalで判断します。",
            "- 障害対応は既存のincident responseとincident commanderの指揮を維持します。",
            "- releaseは既存のrelease processを維持し、AIは実行しません。",
        )
    )
    boundaries = "\n".join(
        f"- **{item['id']}** — {item['boundary']}（owner: {item['owner_role']}）" for item in concerns
    )
    faq_items = "\n\n".join(
        f"## {index}. [{item['id']}] {item['question']}\n\n{item['faq_answer']}"
        for index, item in enumerate(concerns, 1)
    )
    checklist_items = "\n".join(
        f"- [ ] **{item['id']}**: {item['review_check']}（owner: {item['owner_role']}）" for item in concerns
    )
    evidence_items = "\n".join(
        f"- [ ] **{item['id']}**: {item['evidence_required']}" for item in concerns
    )
    return {
        "introduction.md": _render(
            templates["introduction"],
            {
                "ORGANIZATION": scenario["organization"],
                "PURPOSE": scenario["purpose"],
                "PILOT_SCOPE": scenario["pilot_scope"],
                "PRESERVED_PROCESSES": preserved,
                "CONCERN_BOUNDARIES": boundaries,
                "DECISION_OWNER": scenario["decision_owner"],
                "SECURITY_OWNER": scenario["security_owner"],
            },
        ),
        "faq.md": _render(templates["faq"], {"FAQ_ITEMS": faq_items}),
        "security-review-checklist.md": _render(
            templates["checklist"],
            {"CHECKLIST_ITEMS": checklist_items, "EVIDENCE_ITEMS": evidence_items},
        ),
    }


def write_documents(documents, output_dir):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    for filename in OUTPUT_FILES:
        (output_dir / filename).write_text(documents[filename], encoding="utf-8", newline="\n")


def main():
    parser = argparse.ArgumentParser(description="Build the local S10 introduction package")
    parser.add_argument("--input", required=True)
    parser.add_argument("--templates", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        data = load_json(args.input)
        documents = build_documents(data, load_templates(args.templates))
        write_documents(documents, args.output)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        print(f"ERROR: {exc}")
        return 1
    print(f"PASS: generated {len(documents)} S10 learner documents")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
