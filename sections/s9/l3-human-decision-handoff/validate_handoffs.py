import argparse
import json
import sys
from pathlib import Path


PRODUCTION_VALUES = {"none", "possible", "confirmed"}
COST_VALUES = {"none", "known_within_approved_limit", "unknown", "exceeds_approved_limit"}
ROLLBACK_VALUES = {"not_required", "ready", "missing", "unverified"}


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def validate_structure(scenario):
    errors = []
    required = {"scenario_id", "summary", "conditions", "evidence", "unknowns", "options", "next_actor"}
    if not isinstance(scenario, dict):
        return ["scenario_must_be_object"]
    if set(scenario) != required:
        errors.append("scenario_fields_invalid")
    if not _nonempty(scenario.get("scenario_id")) or not _nonempty(scenario.get("summary")):
        errors.append("identity_or_summary_missing")

    conditions = scenario.get("conditions")
    condition_fields = {"production_impact", "cost_impact", "exception_required", "permission_change_required", "rollback"}
    if not isinstance(conditions, dict) or set(conditions) != condition_fields:
        errors.append("condition_fields_invalid")
    else:
        if conditions["production_impact"] not in PRODUCTION_VALUES:
            errors.append("production_impact_invalid")
        if conditions["cost_impact"] not in COST_VALUES:
            errors.append("cost_impact_invalid")
        if type(conditions["exception_required"]) is not bool:
            errors.append("exception_required_invalid")
        if type(conditions["permission_change_required"]) is not bool:
            errors.append("permission_change_required_invalid")
        if conditions["rollback"] not in ROLLBACK_VALUES:
            errors.append("rollback_invalid")

    evidence = scenario.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        errors.append("evidence_missing")
    elif any(not isinstance(item, dict) or set(item) != {"source", "observation"} or not _nonempty(item.get("source")) or not _nonempty(item.get("observation")) for item in evidence):
        errors.append("evidence_invalid")

    unknowns = scenario.get("unknowns")
    if not isinstance(unknowns, list) or any(not _nonempty(item) for item in unknowns):
        errors.append("unknowns_invalid")

    options = scenario.get("options")
    if not isinstance(options, list) or len(options) < 2:
        errors.append("options_insufficient")
    elif any(not isinstance(item, dict) or set(item) != {"id", "description", "tradeoff"} or any(not _nonempty(item.get(key)) for key in ("id", "description", "tradeoff")) for item in options):
        errors.append("options_invalid")
    elif len({item["id"] for item in options}) != len(options):
        errors.append("option_ids_not_unique")

    next_actor = scenario.get("next_actor")
    if not isinstance(next_actor, dict) or set(next_actor) != {"role", "action"} or not _nonempty(next_actor.get("role")) or not _nonempty(next_actor.get("action")):
        errors.append("next_actor_invalid")
    return errors


def decision_reasons(conditions):
    reasons = []
    if conditions["production_impact"] in {"possible", "confirmed"}:
        reasons.append(f"production_impact_{conditions['production_impact']}")
    if conditions["cost_impact"] == "unknown":
        reasons.append("cost_impact_unknown")
    elif conditions["cost_impact"] == "exceeds_approved_limit":
        reasons.append("cost_exceeds_approved_limit")
    if conditions["exception_required"]:
        reasons.append("exception_requires_approval")
    if conditions["permission_change_required"]:
        reasons.append("permission_change_requires_approval")
    if conditions["rollback"] in {"missing", "unverified"}:
        reasons.append(f"rollback_{conditions['rollback']}")
    return reasons


def evaluate_scenario(scenario):
    errors = validate_structure(scenario)
    if errors:
        return {"decision": "INVALID_INPUT", "reason_codes": errors}
    reasons = decision_reasons(scenario["conditions"])
    if reasons and not scenario["unknowns"]:
        return {"decision": "INVALID_INPUT", "reason_codes": ["stopped_scenario_unknowns_missing"]}
    result = {
        "decision": "NEED_HUMAN_DECISION" if reasons else "CONTINUE_READONLY",
        "reason_codes": reasons,
    }
    if reasons:
        result["handoff"] = {
            "evidence": scenario["evidence"],
            "unknowns": scenario["unknowns"],
            "choices": scenario["options"],
            "next_actor": scenario["next_actor"],
        }
    return result


def validate_population(fixtures_dir, expected_path):
    fixtures_dir = Path(fixtures_dir)
    expected = load_json(expected_path)
    files = sorted(fixtures_dir.glob("*.json"))
    actual_names = {path.name for path in files}
    expected_names = set(expected)
    errors = []
    if actual_names != expected_names:
        errors.append("fixture population does not exactly match expected-results.json")
    results = {}
    for path in files:
        try:
            result = evaluate_scenario(load_json(path))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            result = {"decision": "INVALID_INPUT", "reason_codes": [f"json_read_error:{type(exc).__name__}"]}
        results[path.name] = result
        comparable = {"decision": result["decision"], "reason_codes": result["reason_codes"]}
        if path.name not in expected or comparable != expected[path.name]:
            errors.append(f"unexpected result: {path.name}")
    return results, errors


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    parser = argparse.ArgumentParser(description="Validate local human-decision stop-condition scenarios")
    parser.add_argument("--fixtures", required=True)
    parser.add_argument("--expected", required=True)
    args = parser.parse_args()
    results, errors = validate_population(args.fixtures, args.expected)
    for name, result in sorted(results.items()):
        reasons = ",".join(result["reason_codes"]) or "none"
        print(f"{name}: {result['decision']} ({reasons})")
        if result["decision"] == "NEED_HUMAN_DECISION":
            print(json.dumps(result["handoff"], ensure_ascii=False, sort_keys=True))
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(f"PASS: {len(results)} scenarios matched expected results")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
