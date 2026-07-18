#!/usr/bin/env python3
"""Validate local AI execution-log fixtures without AWS or credentials."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
SCHEMA_PATH = ROOT / "ai-execution-log.schema.json"
CORRELATION_FIELDS = ("execution_id", "session_id", "ticket_id")
SENSITIVE_MARKERS = (
    re.compile(r"PLAINTEXT-SENSITIVE-VALUE", re.IGNORECASE),
    re.compile(r"BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY", re.IGNORECASE),
    re.compile(r"AKIA[0-9A-Z]{16}"),
)
MASKED_PATH = re.compile(r"^(input|output)(\.[A-Za-z_][A-Za-z0-9_]*)+$")
MASK_FORMATS = {
    "redact": re.compile(r"^\[REDACTED\]$"),
    "tokenize": re.compile(r"^token-[a-z0-9-]{3,64}$"),
    "hash": re.compile(r"^sha256:[0-9a-f]{64}$"),
}


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _matches_type(value: Any, expected: str) -> bool:
    return {
        "object": isinstance(value, dict),
        "array": isinstance(value, list),
        "string": isinstance(value, str),
        "integer": isinstance(value, int) and not isinstance(value, bool),
        "boolean": isinstance(value, bool),
        "null": value is None,
    }.get(expected, False)


def _is_datetime(value: str) -> bool:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None


def _parse_datetime(value: Any) -> datetime:
    if not isinstance(value, str):
        raise TypeError("date-time value must be a string")
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def validate_schema(value: Any, schema: dict[str, Any], path: str = "$") -> list[str]:
    """Evaluate the JSON Schema keywords used by this learner package."""
    errors: list[str] = []
    expected = schema.get("type")
    if isinstance(expected, str) and not _matches_type(value, expected):
        return [f"{path}: expected {expected}"]
    if isinstance(expected, list) and not any(_matches_type(value, item) for item in expected):
        return [f"{path}: expected one of {expected}"]
    if "const" in schema and value != schema["const"]:
        errors.append(f"{path}: value must equal {schema['const']!r}")
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: value is outside the allowed enum")
    if isinstance(value, dict):
        required = schema.get("required", [])
        for key in required:
            if key not in value:
                errors.append(f"{path}: missing required property {key}")
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            for key in value:
                if key not in properties:
                    errors.append(f"{path}: unexpected property {key}")
        for key, child_schema in properties.items():
            if key in value:
                errors.extend(validate_schema(value[key], child_schema, f"{path}.{key}"))
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            errors.append(f"{path}: too few items")
        if schema.get("uniqueItems") and len({json.dumps(item, sort_keys=True) for item in value}) != len(value):
            errors.append(f"{path}: items must be unique")
        if isinstance(schema.get("items"), dict):
            for index, item in enumerate(value):
                errors.extend(validate_schema(item, schema["items"], f"{path}[{index}]"))
    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0):
            errors.append(f"{path}: string is too short")
        if "pattern" in schema and re.fullmatch(schema["pattern"], value) is None:
            errors.append(f"{path}: string does not match the required pattern")
        if schema.get("format") == "date-time" and not _is_datetime(value):
            errors.append(f"{path}: invalid date-time")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"{path}: value is below minimum")
        if "maximum" in schema and value > schema["maximum"]:
            errors.append(f"{path}: value exceeds maximum")
    return errors


def _walk_strings(value: Any):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for child in value.values():
            yield from _walk_strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_strings(child)


def _validate_declared_masking(record: dict[str, Any], handling: dict[str, Any]) -> list[str]:
    """Resolve each declared path and verify its strategy-specific masked value."""
    fields = handling.get("masked_fields")
    strategy = handling.get("strategy")
    if handling.get("masking_applied") is not True or not isinstance(fields, list) or not fields:
        return ["masking_not_applied"]
    if strategy not in MASK_FORMATS:
        return ["masking_strategy_unsupported"]
    codes: list[str] = []
    for path in fields:
        if not isinstance(path, str) or MASKED_PATH.fullmatch(path) is None:
            codes.append("masking_path_unsupported")
            continue
        value: Any = record
        missing = False
        for segment in path.split("."):
            if not isinstance(value, dict) or segment not in value:
                missing = True
                break
            value = value[segment]
        if missing:
            codes.append("masking_path_missing")
        elif not isinstance(value, str):
            codes.append("masking_path_non_scalar")
        elif MASK_FORMATS[strategy].fullmatch(value) is None:
            codes.append("masking_value_invalid")
    return sorted(set(codes))


def policy_codes(record: Any) -> list[str]:
    if not isinstance(record, dict):
        return ["record_not_object"]
    codes: list[str] = []
    if any(not record.get(field) for field in CORRELATION_FIELDS):
        codes.append("missing_correlation_field")
    retention = record.get("retention", {})
    days = retention.get("retention_days") if isinstance(retention, dict) else None
    if not isinstance(days, int) or isinstance(days, bool) or not 1 <= days <= 365:
        codes.append("retention_out_of_range")
    else:
        try:
            occurred = _parse_datetime(record["occurred_at"])
            expires = _parse_datetime(retention["expires_at"])
            elapsed_days = (expires - occurred).total_seconds() / 86400
            if not 0 < elapsed_days <= days:
                codes.append("retention_window_mismatch")
        except (KeyError, TypeError, ValueError):
            codes.append("retention_window_mismatch")
    handling = record.get("data_handling", {})
    if not isinstance(handling, dict):
        codes.append("masking_not_applied")
    else:
        codes.extend(_validate_declared_masking(record, handling))
    outbound = record.get("external_send", {})
    if isinstance(outbound, dict):
        allowed = outbound.get("allowed")
        destination = outbound.get("destination")
        approval = outbound.get("approval_ticket")
        boundary_ok = (
            (allowed is False and destination == "none" and approval is None)
            or (allowed is True and destination == "approved-service" and isinstance(approval, str) and re.fullmatch(r"^[A-Z][A-Z0-9]+-[0-9]+$", approval))
        )
        if not boundary_ok:
            codes.append("external_send_unapproved")
    else:
        codes.append("external_send_unapproved")
    if any(pattern.search(text) for text in _walk_strings(record) for pattern in SENSITIVE_MARKERS):
        codes.append("sensitive_data_detected")
    return sorted(set(codes))


def validate_record(record: Any, schema: dict[str, Any]) -> dict[str, Any]:
    schema_errors = validate_schema(record, schema)
    codes = policy_codes(record)
    if schema_errors:
        codes.append("schema_validation_failed")
    codes = sorted(set(codes))
    return {"valid": not codes, "reason_codes": codes, "schema_error_count": len(schema_errors)}


def validate_population(fixtures_dir: Path, expected_path: Path) -> tuple[dict[str, Any], list[str]]:
    schema = load_json(SCHEMA_PATH)
    expected = load_json(expected_path)
    fixture_paths = sorted(fixtures_dir.glob("*.json"))
    actual = {path.name: validate_record(load_json(path), schema) for path in fixture_paths}
    errors: list[str] = []
    if set(actual) != set(expected):
        errors.append("fixture population does not exactly match expected-results.json")
    for name in sorted(set(actual) & set(expected)):
        for key in ("valid", "reason_codes"):
            if actual[name][key] != expected[name][key]:
                errors.append(f"{name}: {key} differs from expected")
    return actual, errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixtures", type=Path, default=ROOT / "fixtures")
    parser.add_argument("--expected", type=Path, default=ROOT / "expected-results.json")
    args = parser.parse_args()
    actual, errors = validate_population(args.fixtures.resolve(), args.expected.resolve())
    print(json.dumps(actual, ensure_ascii=False, indent=2, sort_keys=True))
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"PASS: {len(actual)} fixtures matched expected results", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
