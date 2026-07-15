#!/usr/bin/env python3
"""Validate a local IAM guardrail example without AWS access."""

from __future__ import annotations

import fnmatch
import json
import re
import sys
from pathlib import Path
from typing import Any


DECISIONS = ("ALLOW", "EXPLICIT_DENY", "IMPLICIT_DENY")
LOCAL_DECLARATIONS = {
    "local_only": True,
    "aws_connection": False,
    "credentials_required": False,
    "policy_application": False,
}
ALLOWED_STATEMENT_KEYS = {"Sid", "Effect", "Action", "Resource"}
REQUIRED_PROHIBITIONS = {
    "share a human operator role",
    "use an untracked session",
    "store credentials in learner files",
    "apply this policy to AWS",
}
PLACEHOLDER = re.compile(r"REPLACE_|\b(?:TBD|TODO)\b", re.IGNORECASE)


def string_list(value: Any) -> list[str] | None:
    if isinstance(value, str) and value.strip():
        return [value]
    if isinstance(value, list) and value and all(
        isinstance(item, str) and item.strip() for item in value
    ):
        return value
    return None


def duplicates(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen and value not in result:
            result.append(value)
        seen.add(value)
    return result


def validate_local_declarations(data: Any, label: str) -> list[str]:
    if not isinstance(data, dict):
        return [f"{label} root must be an object"]
    return [
        f"{label} must declare {key}: {str(expected).lower()}"
        for key, expected in LOCAL_DECLARATIONS.items()
        if data.get(key) is not expected
    ]


def validate_requirements(data: Any) -> list[str]:
    errors = validate_local_declarations(data, "requirements")
    if not isinstance(data, dict):
        return errors
    if data.get("schema_version") != 1:
        errors.append("requirements schema_version must be 1")
    if data.get("required_policy_version") != "2012-10-17":
        errors.append("requirements policy version must be 2012-10-17")
    for key in ("required_allow_actions", "required_explicit_deny_actions"):
        values = string_list(data.get(key))
        if values is None:
            errors.append(f"requirements {key} must be a non-empty string list")
        elif duplicates(values):
            errors.append(f"requirements {key} contains duplicates")
    fields = string_list(data.get("required_session_fields"))
    if fields != ["actor", "ticket", "run"]:
        errors.append("requirements session fields must be actor, ticket, run in order")
    pattern = data.get("session_name_pattern")
    if not isinstance(pattern, str):
        errors.append("requirements session_name_pattern is required")
    else:
        try:
            re.compile(pattern)
        except re.error:
            errors.append("requirements session_name_pattern is invalid")
    return errors


def policy_actions(policy: Any) -> tuple[list[str], list[str], list[str]]:
    errors: list[str] = []
    if not isinstance(policy, dict):
        return [], [], ["policy root must be an object"]
    if set(policy) != {"Version", "Statement"}:
        errors.append("policy root must contain only Version and Statement")
    statements = policy.get("Statement")
    if not isinstance(statements, list):
        return [], [], errors + ["policy Statement must be an array"]
    by_sid: dict[str, dict[str, Any]] = {}
    for index, statement in enumerate(statements):
        if not isinstance(statement, dict):
            errors.append(f"statement {index} must be an object")
            continue
        unknown = sorted(set(statement) - ALLOWED_STATEMENT_KEYS)
        if unknown:
            errors.append(f"statement {index} has prohibited or unknown keys: {unknown}")
        sid = statement.get("Sid")
        if not isinstance(sid, str) or not sid:
            errors.append(f"statement {index} requires Sid")
            continue
        if sid in by_sid:
            errors.append(f"duplicate statement Sid: {sid}")
        by_sid[sid] = statement
    expected_sids = {"AllowApprovedInvestigationReads", "DenyProhibitedMutations"}
    if set(by_sid) != expected_sids:
        errors.append("policy must contain exactly the approved Allow and explicit Deny statements")

    def extract(sid: str, effect: str) -> list[str]:
        statement = by_sid.get(sid)
        if statement is None:
            return []
        if statement.get("Effect") != effect:
            errors.append(f"{sid} Effect must be {effect}")
        if statement.get("Resource") != "*":
            errors.append(f"{sid} Resource must be * for this fixture")
        actions = string_list(statement.get("Action"))
        if actions is None:
            errors.append(f"{sid} Action must be a non-empty string list")
            return []
        if duplicates(actions):
            errors.append(f"{sid} contains duplicate actions")
        return actions

    return (
        extract("AllowApprovedInvestigationReads", "Allow"),
        extract("DenyProhibitedMutations", "Deny"),
        errors,
    )


def validate_policy(policy: Any, requirements: dict[str, Any]) -> tuple[list[str], list[str], list[str]]:
    allow, deny, errors = policy_actions(policy)
    if not isinstance(policy, dict):
        return allow, deny, errors
    if policy.get("Version") != requirements.get("required_policy_version"):
        errors.append("policy Version does not match requirements")
    wildcard_allow = [action for action in allow if "*" in action or "?" in action]
    if wildcard_allow:
        errors.append(f"Allow actions must not use wildcards: {wildcard_allow}")
    required_allow = requirements.get("required_allow_actions", [])
    required_deny = requirements.get("required_explicit_deny_actions", [])
    if allow != required_allow:
        errors.append("Allow actions must exactly match the ordered least-privilege list")
    if deny != required_deny:
        errors.append("Deny actions must exactly match the ordered prohibited-action list")
    serialized = json.dumps(policy, ensure_ascii=False)
    if PLACEHOLDER.search(serialized):
        errors.append("policy contains unresolved placeholders")
    return allow, deny, errors


def validate_profile(profile: Any, requirements: dict[str, Any]) -> list[str]:
    errors = validate_local_declarations(profile, "profile")
    if not isinstance(profile, dict):
        return errors
    if profile.get("schema_version") != 1:
        errors.append("profile schema_version must be 1")
    ai_role = profile.get("ai_role")
    human_role = profile.get("human_role")
    names: list[str] = []
    for label, role in (("ai_role", ai_role), ("human_role", human_role)):
        if not isinstance(role, dict):
            errors.append(f"profile {label} must be an object")
            continue
        name = role.get("name")
        responsibilities = string_list(role.get("responsibilities"))
        if not isinstance(name, str) or not name.strip() or PLACEHOLDER.search(name):
            errors.append(f"profile {label} requires a concrete name")
        else:
            names.append(name)
        if responsibilities is None or len(responsibilities) < 2:
            errors.append(f"profile {label} requires at least two responsibilities")
    if len(names) == 2 and names[0] == names[1]:
        errors.append("AI and human roles must be distinct")

    session = profile.get("session")
    if not isinstance(session, dict):
        errors.append("profile session must be an object")
    else:
        if session.get("required") is not True:
            errors.append("tracked session must be required")
        if session.get("name_format") != "ai-{actor}-{ticket}-{run}":
            errors.append("session name format must expose actor, ticket, and run")
        if session.get("trace_fields") != requirements.get("required_session_fields"):
            errors.append("session trace fields do not match requirements")
        example = session.get("example")
        pattern = requirements.get("session_name_pattern", "(?!)")
        if not isinstance(example, str) or not re.fullmatch(pattern, example):
            errors.append("session example is not traceable or does not match the required pattern")
    prohibited = profile.get("prohibited_for_ai")
    if not isinstance(prohibited, list) or set(prohibited) != REQUIRED_PROHIBITIONS:
        errors.append("profile must record the complete AI prohibition boundary")
    serialized = json.dumps(profile, ensure_ascii=False)
    if PLACEHOLDER.search(serialized):
        errors.append("profile contains unresolved placeholders")
    return errors


def matches(action: str, pattern: str) -> bool:
    return fnmatch.fnmatchcase(action.lower(), pattern.lower())


def evaluate_action(action: str, allow: list[str], deny: list[str]) -> str:
    if any(matches(action, pattern) for pattern in deny):
        return "EXPLICIT_DENY"
    if any(matches(action, pattern) for pattern in allow):
        return "ALLOW"
    return "IMPLICIT_DENY"


def validate_cases(data: Any, allow: list[str], deny: list[str]) -> tuple[dict[str, int], list[str]]:
    errors = validate_local_declarations(data, "cases")
    counts = {decision: 0 for decision in DECISIONS}
    if not isinstance(data, dict):
        return counts, errors
    if data.get("schema_version") != 1:
        errors.append("cases schema_version must be 1")
    cases = data.get("cases")
    if not isinstance(cases, list) or not cases:
        return counts, errors + ["cases must be a non-empty array"]
    seen: set[str] = set()
    for index, case in enumerate(cases):
        if not isinstance(case, dict):
            errors.append(f"case {index} must be an object")
            continue
        case_id = case.get("id")
        action = case.get("action")
        expected = case.get("expected")
        reason = case.get("reason")
        if not isinstance(case_id, str) or not re.fullmatch(r"[A-Z]+-\d{2}", case_id):
            errors.append(f"case {index} has invalid id")
            continue
        if case_id in seen:
            errors.append(f"duplicate case id: {case_id}")
        seen.add(case_id)
        if not isinstance(action, str) or not re.fullmatch(r"[a-z0-9-]+:[A-Za-z0-9*?]+", action):
            errors.append(f"case {case_id} has invalid action")
            continue
        if expected not in DECISIONS:
            errors.append(f"case {case_id} has invalid expected decision")
            continue
        if not isinstance(reason, str) or len(reason) < 15:
            errors.append(f"case {case_id} requires a specific reason")
        actual = evaluate_action(action, allow, deny)
        if actual != expected:
            errors.append(f"case {case_id} decision mismatch: expected {expected}, got {actual}")
        counts[expected] += 1
    for decision, count in counts.items():
        if count == 0:
            errors.append(f"cases missing decision class: {decision}")
    return counts, errors


def display_path(path: Path) -> str:
    root = Path(__file__).resolve().parents[1]
    try:
        return path.resolve().relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def load_json(path: Path, label: str) -> tuple[Any, list[str]]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), []
    except (OSError, json.JSONDecodeError) as exc:
        return None, [f"cannot read {label}: {exc}"]


def main(argv: list[str]) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    root = Path(__file__).resolve().parents[1]
    policy_path = Path(argv[1]) if len(argv) > 1 else root / "examples" / "iam-guardrail-package" / "iam-policy.json"
    profile_path = Path(argv[2]) if len(argv) > 2 else root / "examples" / "iam-guardrail-package" / "role-session-boundary.json"
    cases_path = Path(argv[3]) if len(argv) > 3 else root / "fixtures" / "evaluation-cases.json"
    requirements_path = Path(argv[4]) if len(argv) > 4 else root / "fixtures" / "guardrail-requirements.json"
    if len(argv) > 5:
        print("INVALID")
        print("- usage: validate_iam_guardrails.py [policy] [profile] [cases] [requirements]")
        return 1
    requirements, errors = load_json(requirements_path, "requirements")
    policy, read_errors = load_json(policy_path, "policy")
    errors.extend(read_errors)
    profile, read_errors = load_json(profile_path, "profile")
    errors.extend(read_errors)
    cases, read_errors = load_json(cases_path, "cases")
    errors.extend(read_errors)
    if requirements is not None:
        errors.extend(validate_requirements(requirements))
    if not isinstance(requirements, dict):
        requirements = {}
    allow, deny, policy_errors = validate_policy(policy, requirements)
    errors.extend(policy_errors)
    errors.extend(validate_profile(profile, requirements))
    counts, case_errors = validate_cases(cases, allow, deny)
    errors.extend(case_errors)
    if errors:
        print("INVALID")
        for error in errors:
            print(f"- {error}")
        return 1
    case_total = sum(counts.values())
    print("VALID")
    print(f"policy: {display_path(policy_path)}")
    print(f"profile: {display_path(profile_path)}")
    print(f"cases: {display_path(cases_path)}")
    print(f"allow_actions: {len(allow)}/{len(requirements['required_allow_actions'])}")
    print(f"explicit_deny_actions: {len(deny)}/{len(requirements['required_explicit_deny_actions'])}")
    print(f"evaluation: {case_total}/{case_total}")
    print("decisions: " + " ".join(f"{name}={counts[name]}" for name in DECISIONS))
    print("role_separation: true")
    print("tracked_session: true")
    print("aws_connection: false")
    print("policy_application: false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
