#!/usr/bin/env python3
"""Validate a local MCP pre-connection checklist and scenario fixture."""

from __future__ import annotations

import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any


REQUIRED_CATEGORIES = (
    "CONNECTION",
    "PERMISSIONS",
    "AUDIT",
    "SENSITIVE_DATA",
    "PROMPT_INJECTION",
    "COST",
)
VALID_DECISIONS = {"PASS", "REVIEW", "BLOCK"}
REQUIRED_TRACE_FIELDS = (
    "actor/identity",
    "timestamp",
    "API operation",
    "session/correlation ID",
)
PLACEHOLDER_PATTERN = re.compile(
    r"\[[^\]\n]*(?:記入|PASS/REVIEW/BLOCK|YYYY-MM-DD|担当role|未確認/承認/差戻し|https://\.\.\.)[^\]\n]*\]"
    r"|\b(?:TBD|TODO)\b",
    re.IGNORECASE,
)
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
OVERALL_PATTERN = re.compile(
    r"^-\s*接続前判定:\s*(READY_FOR_APPROVAL|NEEDS_REVIEW|DO_NOT_CONNECT)\s*$",
    re.MULTILINE,
)


def parse_risk_rows(text: str) -> tuple[dict[str, list[str]], list[str]]:
    """Return category rows and table-structure errors."""
    rows: dict[str, list[str]] = {}
    errors: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if not cells or cells[0] not in REQUIRED_CATEGORIES:
            continue
        category = cells[0]
        if category in rows:
            errors.append(f"duplicate risk category: {category}")
            continue
        if len(cells) != 6:
            errors.append(f"risk row must have 6 columns: {category}")
            continue
        rows[category] = cells
    return rows, errors


def expected_overall(decisions: list[str]) -> str:
    if "BLOCK" in decisions:
        return "DO_NOT_CONNECT"
    if "REVIEW" in decisions:
        return "NEEDS_REVIEW"
    return "READY_FOR_APPROVAL"


def is_valid_date(value: str) -> bool:
    if not DATE_PATTERN.fullmatch(value):
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def validate_fixture(data: Any) -> tuple[dict[str, dict[str, str]], list[str]]:
    errors: list[str] = []
    scenarios_by_category: dict[str, dict[str, str]] = {}
    if not isinstance(data, dict):
        return {}, ["fixture root must be an object"]
    if data.get("local_only") is not True:
        errors.append("fixture must declare local_only: true")
    scenarios = data.get("scenarios")
    if not isinstance(scenarios, list):
        return {}, errors + ["fixture scenarios must be an array"]
    seen_ids: set[str] = set()
    for index, item in enumerate(scenarios):
        if not isinstance(item, dict):
            errors.append(f"fixture scenario {index} must be an object")
            continue
        scenario_id = item.get("id")
        category = item.get("category")
        observation = item.get("observation")
        decision = item.get("expected_decision")
        if not isinstance(scenario_id, str) or not scenario_id:
            errors.append(f"fixture scenario {index} has invalid id")
        elif scenario_id in seen_ids:
            errors.append(f"duplicate fixture scenario id: {scenario_id}")
        else:
            seen_ids.add(scenario_id)
        if category not in REQUIRED_CATEGORIES:
            errors.append(f"fixture scenario {index} has invalid category: {category}")
            continue
        if category in scenarios_by_category:
            errors.append(f"duplicate fixture category: {category}")
            continue
        if not isinstance(observation, str) or not observation.strip():
            errors.append(f"fixture scenario has empty observation: {category}")
        if decision not in VALID_DECISIONS:
            errors.append(f"fixture scenario has invalid expected_decision: {category}")
        scenarios_by_category[category] = item
    for category in REQUIRED_CATEGORIES:
        if category not in scenarios_by_category:
            errors.append(f"missing fixture category: {category}")
    return scenarios_by_category, errors


def validate_text(text: str, fixture: Any) -> list[str]:
    errors: list[str] = []
    scenarios, fixture_errors = validate_fixture(fixture)
    errors.extend(fixture_errors)
    rows, row_errors = parse_risk_rows(text)
    errors.extend(row_errors)

    for category in REQUIRED_CATEGORIES:
        row = rows.get(category)
        if row is None:
            errors.append(f"missing risk category: {category}")
            continue
        _, decision, evidence, owner, recheck_date, stop_condition = row
        if decision not in VALID_DECISIONS:
            errors.append(f"invalid decision for {category}: {decision}")
        scenario = scenarios.get(category)
        if scenario:
            scenario_id = scenario.get("id")
            if scenario_id not in evidence:
                errors.append(f"evidence must cite matching scenario id: {category}")
            expected_decision = scenario.get("expected_decision")
            if decision in VALID_DECISIONS and decision != expected_decision:
                errors.append(
                    f"decision contradicts fixture for {category}: "
                    f"expected {expected_decision}, got {decision}"
                )
        if not owner or owner in {"-", "N/A"}:
            errors.append(f"missing owner: {category}")
        if not is_valid_date(recheck_date):
            errors.append(f"invalid recheck date: {category}")
        if len(stop_condition) < 10:
            errors.append(f"stop condition is not specific: {category}")

    lower_text = text.lower()
    for field in REQUIRED_TRACE_FIELDS:
        if field.lower() not in lower_text:
            errors.append(f"missing audit trace field: {field}")

    placeholders = PLACEHOLDER_PATTERN.findall(text)
    if placeholders:
        errors.append(f"unresolved placeholders: {len(placeholders)}")

    overall_match = OVERALL_PATTERN.search(text)
    if overall_match is None:
        errors.append("missing or invalid overall decision")
    elif len(rows) == len(REQUIRED_CATEGORIES):
        decisions = [rows[category][1] for category in REQUIRED_CATEGORIES]
        if all(decision in VALID_DECISIONS for decision in decisions):
            expected = expected_overall(decisions)
            if overall_match.group(1) != expected:
                errors.append(
                    f"overall decision mismatch: expected {expected}, "
                    f"got {overall_match.group(1)}"
                )
    return errors


def display_path(path: Path) -> str:
    learner_root = Path(__file__).resolve().parents[1]
    try:
        return path.resolve().relative_to(learner_root).as_posix()
    except ValueError:
        return path.as_posix()


def main(argv: list[str]) -> int:
    learner_root = Path(__file__).resolve().parents[1]
    checklist_path = (
        Path(argv[1])
        if len(argv) > 1
        else learner_root / "examples" / "completed-mcp-preconnection-checklist.md"
    )
    fixture_path = (
        Path(argv[2])
        if len(argv) > 2
        else learner_root / "fixtures" / "risk-scenarios.json"
    )
    if len(argv) > 3:
        print("INVALID")
        print("- usage: validate_checklist.py [checklist-path] [fixture-path]")
        return 1
    try:
        text = checklist_path.read_text(encoding="utf-8")
        fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print("INVALID")
        print(f"- cannot read input: {exc}")
        return 1

    errors = validate_text(text, fixture)
    if errors:
        print("INVALID")
        for error in errors:
            print(f"- {error}")
        return 1

    rows, _ = parse_risk_rows(text)
    counts = {
        decision: sum(row[1] == decision for row in rows.values())
        for decision in ("PASS", "REVIEW", "BLOCK")
    }
    decisions = [rows[category][1] for category in REQUIRED_CATEGORIES]
    print("VALID")
    print(f"checklist: {display_path(checklist_path)}")
    print(f"fixture: {display_path(fixture_path)}")
    print(f"categories: {len(rows)}/{len(REQUIRED_CATEGORIES)}")
    print(
        "decisions: "
        f"PASS={counts['PASS']} REVIEW={counts['REVIEW']} BLOCK={counts['BLOCK']}"
    )
    print(f"overall: {expected_overall(decisions)}")
    print("placeholders: 0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
