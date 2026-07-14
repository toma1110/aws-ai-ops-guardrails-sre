#!/usr/bin/env python3
"""Validate a local AI work-classification Markdown document."""

from __future__ import annotations

import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any


DECISIONS = ("ALLOW", "HUMAN_REVIEW", "PROHIBIT")
PROHIBIT_FLAGS = (
    "mutating_action",
    "release_action",
    "iam_action",
    "delete_action",
    "recovery_execution",
)
REVIEW_FLAGS = (
    "production_impact_decision",
    "sensitive_data",
    "cost_exception",
    "insufficient_evidence",
)
REQUIRED_FLAGS = PROHIBIT_FLAGS + REVIEW_FLAGS + (
    "approved_read_only",
    "evidence_only_output",
)
PLACEHOLDER_PATTERN = re.compile(
    r"\[[^\]\n]*(?:記入|YYYY-MM-DD|未確認/承認/差戻し)[^\]\n]*\]"
    r"|\b(?:TBD|TODO)\b",
    re.IGNORECASE,
)
AUDIT_PATTERNS = {
    "分類担当role": re.compile(r"^-\s*分類担当role:\s*(.+?)\s*$", re.MULTILINE),
    "分類日": re.compile(r"^-\s*分類日:\s*(.+?)\s*$", re.MULTILINE),
    "使用fixture": re.compile(r"^-\s*使用fixture:\s*`?([^`\n]+)`?\s*$", re.MULTILINE),
    "承認状態": re.compile(r"^-\s*承認状態:\s*(.+?)\s*$", re.MULTILINE),
}


def derive_decision(flags: dict[str, bool]) -> str:
    """Apply precedence: prohibited execution, then human review, then allow."""
    if any(flags[name] for name in PROHIBIT_FLAGS):
        return "PROHIBIT"
    if any(flags[name] for name in REVIEW_FLAGS):
        return "HUMAN_REVIEW"
    if flags["approved_read_only"] and flags["evidence_only_output"]:
        return "ALLOW"
    return "HUMAN_REVIEW"


def validate_fixture(data: Any) -> tuple[dict[str, dict[str, Any]], list[str]]:
    errors: list[str] = []
    by_id: dict[str, dict[str, Any]] = {}
    if not isinstance(data, dict):
        return {}, ["fixture root must be an object"]
    for key, expected in (
        ("local_only", True),
        ("aws_connection", False),
        ("credentials_required", False),
    ):
        if data.get(key) is not expected:
            errors.append(f"fixture must declare {key}: {str(expected).lower()}")
    scenarios = data.get("scenarios")
    if not isinstance(scenarios, list):
        return {}, errors + ["fixture scenarios must be an array"]
    for index, scenario in enumerate(scenarios):
        if not isinstance(scenario, dict):
            errors.append(f"fixture scenario {index} must be an object")
            continue
        scenario_id = scenario.get("id")
        if not isinstance(scenario_id, str) or not re.fullmatch(r"[A-Z]+-\d{2}", scenario_id):
            errors.append(f"fixture scenario {index} has invalid id")
            continue
        if scenario_id in by_id:
            errors.append(f"duplicate fixture scenario id: {scenario_id}")
            continue
        flags = scenario.get("flags")
        if not isinstance(flags, dict):
            errors.append(f"fixture scenario {scenario_id} has invalid flags")
            continue
        for name in REQUIRED_FLAGS:
            if not isinstance(flags.get(name), bool):
                errors.append(f"fixture scenario {scenario_id} has invalid flag: {name}")
        if any(not isinstance(flags.get(name), bool) for name in REQUIRED_FLAGS):
            continue
        expected_decision = scenario.get("expected_decision")
        derived = derive_decision(flags)
        if expected_decision != derived:
            errors.append(
                f"fixture decision mismatch for {scenario_id}: "
                f"derived {derived}, got {expected_decision}"
            )
        if not isinstance(scenario.get("task"), str) or not scenario["task"].strip():
            errors.append(f"fixture scenario {scenario_id} has empty task")
        if not isinstance(scenario.get("observation"), str) or not scenario["observation"].strip():
            errors.append(f"fixture scenario {scenario_id} has empty observation")
        if not isinstance(scenario.get("boundary"), str) or not scenario["boundary"].strip():
            errors.append(f"fixture scenario {scenario_id} has empty boundary")
        by_id[scenario_id] = scenario
    present_decisions = {item.get("expected_decision") for item in by_id.values()}
    for decision in DECISIONS:
        if decision not in present_decisions:
            errors.append(f"fixture missing decision class: {decision}")
    return by_id, errors


def parse_rows(text: str) -> tuple[dict[str, list[str]], list[str]]:
    rows: dict[str, list[str]] = {}
    errors: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if not cells or not re.fullmatch(r"[A-Z]+-\d{2}", cells[0]):
            continue
        scenario_id = cells[0]
        if scenario_id in rows:
            errors.append(f"duplicate classification row: {scenario_id}")
            continue
        if len(cells) != 6:
            errors.append(f"classification row must have 6 columns: {scenario_id}")
            continue
        rows[scenario_id] = cells
    return rows, errors


def is_valid_date(value: str) -> bool:
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", value))


def validate_text(text: str, fixture: Any) -> list[str]:
    scenarios, errors = validate_fixture(fixture)
    rows, row_errors = parse_rows(text)
    errors.extend(row_errors)

    for scenario_id in rows:
        if scenario_id not in scenarios:
            errors.append(f"unknown scenario row: {scenario_id}")
    for scenario_id, scenario in scenarios.items():
        row = rows.get(scenario_id)
        if row is None:
            errors.append(f"missing classification row: {scenario_id}")
            continue
        _, task, decision, boundary, evidence, human_action = row
        if task != scenario["task"]:
            errors.append(f"task text mismatch: {scenario_id}")
        expected = scenario["expected_decision"]
        if decision != expected:
            errors.append(
                f"decision mismatch for {scenario_id}: expected {expected}, got {decision}"
            )
        if boundary != scenario["boundary"]:
            errors.append(
                f"boundary mismatch for {scenario_id}: "
                f"expected {scenario['boundary']}, got {boundary}"
            )
        if scenario_id not in evidence or len(evidence) < 20:
            errors.append(f"evidence must cite matching scenario id: {scenario_id}")
        if len(human_action) < 10:
            errors.append(f"human action is not specific: {scenario_id}")

    placeholders = PLACEHOLDER_PATTERN.findall(text)
    if placeholders:
        errors.append(f"unresolved placeholders: {len(placeholders)}")
    audit_values: dict[str, str] = {}
    for name, pattern in AUDIT_PATTERNS.items():
        match = pattern.search(text)
        if match is None:
            errors.append(f"missing audit field: {name}")
        else:
            audit_values[name] = match.group(1).strip()
    if "分類日" in audit_values and not is_valid_date(audit_values["分類日"]):
        errors.append("invalid classification date")
    if audit_values.get("使用fixture") != "fixtures/work-scenarios.json":
        errors.append("fixture reference must be fixtures/work-scenarios.json")
    if audit_values.get("承認状態") not in {"未確認", "承認", "差戻し"}:
        errors.append("invalid approval status")
    return errors


def display_path(path: Path) -> str:
    root = Path(__file__).resolve().parents[1]
    try:
        return path.resolve().relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def main(argv: list[str]) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    root = Path(__file__).resolve().parents[1]
    markdown_path = (
        Path(argv[1])
        if len(argv) > 1
        else root / "examples" / "completed-ai-work-classification.md"
    )
    fixture_path = (
        Path(argv[2])
        if len(argv) > 2
        else root / "fixtures" / "work-scenarios.json"
    )
    if len(argv) > 3:
        print("INVALID")
        print("- usage: validate_classification.py [markdown-path] [fixture-path]")
        return 1
    try:
        text = markdown_path.read_text(encoding="utf-8")
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
    rows, _ = parse_rows(text)
    counts = {
        decision: sum(row[2] == decision for row in rows.values())
        for decision in DECISIONS
    }
    print("VALID")
    print(f"classification: {display_path(markdown_path)}")
    print(f"fixture: {display_path(fixture_path)}")
    print(f"scenarios: {len(rows)}/{len(rows)}")
    print(
        "decisions: "
        f"ALLOW={counts['ALLOW']} "
        f"HUMAN_REVIEW={counts['HUMAN_REVIEW']} "
        f"PROHIBIT={counts['PROHIBIT']}"
    )
    print("aws_connection: false")
    print("placeholders: 0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
