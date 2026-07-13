#!/usr/bin/env python3
"""Validate a completed adoption-scope Markdown file without modifying it."""

from __future__ import annotations

import re
import sys
from pathlib import Path


REQUIRED_HEADINGS = (
    "目的",
    "対象環境",
    "事実",
    "仮説",
    "ReadOnly境界",
    "作業分類",
    "AIが作業を中断して人間に確認する条件",
    "承認",
)
DECISION_CLASSES = ("ALLOW", "HUMAN_REVIEW", "PROHIBIT")
TRACEABILITY_FIELDS = (
    "actor/identity",
    "timestamp",
    "source",
    "session/correlation ID",
)
PLACEHOLDER_PATTERNS = (
    re.compile(r"\[[^\]\n]*(?:記入|判断区分|未確認/承認/差戻し)[^\]\n]*\]"),
    re.compile(r"<[^>\n]+>"),
    re.compile(r"\b(?:TBD|TODO)\b", re.IGNORECASE),
)


def validate_text(text: str) -> list[str]:
    """Return deterministic validation errors for Markdown text."""
    errors: list[str] = []
    headings = set(re.findall(r"^##\s+(.+?)\s*$", text, flags=re.MULTILINE))
    for heading in REQUIRED_HEADINGS:
        if heading not in headings:
            errors.append(f"missing required heading: {heading}")

    for decision in DECISION_CLASSES:
        rows = re.findall(
            rf"^\|[^\n]*\|\s*{re.escape(decision)}\s*\|[^\n]*$",
            text,
            flags=re.MULTILINE,
        )
        if not rows:
            errors.append(f"missing classified work row: {decision}")

    lower_text = text.lower()
    for field in TRACEABILITY_FIELDS:
        if field.lower() not in lower_text:
            errors.append(f"missing auditability traceability field: {field}")

    placeholder_count = sum(
        len(pattern.findall(text)) for pattern in PLACEHOLDER_PATTERNS
    )
    if placeholder_count:
        errors.append(f"unresolved placeholders: {placeholder_count}")
    return errors


def display_path(path: Path) -> str:
    learner_root = Path(__file__).resolve().parents[1]
    resolved = path.resolve()
    try:
        return resolved.relative_to(learner_root).as_posix()
    except ValueError:
        return path.as_posix()


def main(argv: list[str]) -> int:
    default = Path(__file__).resolve().parents[1] / "examples" / "completed-adoption-scope.md"
    path = Path(argv[1]) if len(argv) > 1 else default
    if len(argv) > 2:
        print("INVALID")
        print("- usage: validate_scope.py [markdown-path]")
        return 1
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        print("INVALID")
        print(f"- cannot read file: {exc}")
        return 1

    errors = validate_text(text)
    if errors:
        print("INVALID")
        for error in errors:
            print(f"- {error}")
        return 1

    counts = {
        decision: len(
            re.findall(
                rf"^\|[^\n]*\|\s*{re.escape(decision)}\s*\|[^\n]*$",
                text,
                flags=re.MULTILINE,
            )
        )
        for decision in DECISION_CLASSES
    }
    print("VALID")
    print(f"file: {display_path(path)}")
    print(
        "decisions: "
        f"ALLOW={counts['ALLOW']} "
        f"HUMAN_REVIEW={counts['HUMAN_REVIEW']} "
        f"PROHIBIT={counts['PROHIBIT']}"
    )
    print(f"headings: {len(REQUIRED_HEADINGS)}/{len(REQUIRED_HEADINGS)}")
    print("placeholders: 0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
