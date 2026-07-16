#!/usr/bin/env python3
"""Correlate synthetic CloudTrail events with a local AI execution record."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

LOCAL = {"local_only": True, "aws_connection": False, "credentials_required": False}


def load(path: Path, label: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read {label}: {exc}") from exc


def check_local(data: Any, label: str) -> None:
    if not isinstance(data, dict):
        raise ValueError(f"{label} root must be an object")
    for key, expected in LOCAL.items():
        if data.get(key) is not expected:
            raise ValueError(f"{label} must declare {key}: {str(expected).lower()}")


def parse_time(value: Any, label: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError(f"{label} must be an ISO-8601 UTC timestamp ending in Z")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{label} has an invalid timestamp") from exc


def select_execution(data: Any, execution_id: str) -> dict[str, Any]:
    check_local(data, "executions")
    if data.get("schema_version") != 1 or not isinstance(data.get("executions"), list):
        raise ValueError("executions schema is invalid")
    matches = [item for item in data["executions"] if isinstance(item, dict) and item.get("execution_id") == execution_id]
    if len(matches) != 1:
        raise ValueError(f"execution_id must match exactly one record: {execution_id}")
    record = matches[0]
    for key in ("session", "ticket_id"):
        if not isinstance(record.get(key), str) or not record[key]:
            raise ValueError(f"execution {key} must be a non-empty string")
    start = parse_time(record.get("window_start"), "window_start")
    end = parse_time(record.get("window_end"), "window_end")
    if start >= end:
        raise ValueError("execution window_start must be before window_end")
    for other in data["executions"]:
        if other is record or not isinstance(other, dict) or other.get("session") != record["session"]:
            continue
        other_start = parse_time(other.get("window_start"), "other window_start")
        other_end = parse_time(other.get("window_end"), "other window_end")
        if max(start, other_start) <= min(end, other_end):
            raise ValueError("ambiguous correlation: the same session has overlapping execution windows")
    return record


def identity(event: dict[str, Any], session: str) -> str:
    user = event.get("userIdentity")
    if not isinstance(user, dict) or user.get("type") != "AssumedRole":
        raise ValueError(f"event {event.get('eventID')} identity must be AssumedRole")
    principal = user.get("principalId")
    arn = user.get("arn")
    context = user.get("sessionContext")
    issuer = context.get("sessionIssuer") if isinstance(context, dict) else None
    role = issuer.get("userName") if isinstance(issuer, dict) else None
    if not all(isinstance(value, str) and value for value in (principal, arn, role)):
        raise ValueError(f"event {event.get('eventID')} identity fields are incomplete")
    if principal.rsplit(":", 1)[-1] != session or arn.rsplit("/", 1)[-1] != session:
        raise ValueError(f"event {event.get('eventID')} has inconsistent session identity")
    return f"AssumedRole/{role}/{session}"


def correlate(events_data: Any, execution: dict[str, Any]) -> list[dict[str, Any]]:
    check_local(events_data, "events")
    if events_data.get("schema_version") != 1 or not isinstance(events_data.get("events"), list):
        raise ValueError("events schema is invalid")
    start = parse_time(execution["window_start"], "window_start")
    end = parse_time(execution["window_end"], "window_end")
    session = execution["session"]
    matched: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in events_data["events"]:
        if not isinstance(raw, dict):
            raise ValueError("each event must be an object")
        event_id = raw.get("eventID")
        event_time = parse_time(raw.get("eventTime"), f"event {event_id} eventTime")
        principal = raw.get("userIdentity", {}).get("principalId") if isinstance(raw.get("userIdentity"), dict) else None
        if not isinstance(principal, str) or principal.rsplit(":", 1)[-1] != session or not start <= event_time <= end:
            continue
        if not isinstance(event_id, str) or not event_id or event_id in seen:
            raise ValueError("matched eventID must be non-empty and unique")
        seen.add(event_id)
        for key in ("eventName", "eventSource", "requestParameters"):
            if key not in raw:
                raise ValueError(f"event {event_id} missing {key}")
        if not isinstance(raw["eventName"], str) or not isinstance(raw["eventSource"], str) or not isinstance(raw["requestParameters"], dict):
            raise ValueError(f"event {event_id} has invalid audit fields")
        error_code, error_message = raw.get("errorCode"), raw.get("errorMessage")
        if (error_code is None) != (error_message is None):
            raise ValueError(f"event {event_id} errorCode and errorMessage must appear together")
        error = None if error_code is None else {"code": error_code, "message": error_message}
        matched.append({
            "event_id": event_id,
            "event_time": raw["eventTime"],
            "identity": identity(raw, session),
            "event": raw["eventName"],
            "source": raw["eventSource"],
            "parameters": raw["requestParameters"],
            "error": error,
        })
    matched.sort(key=lambda item: (item["event_time"], item["event_id"]))
    if not matched:
        raise ValueError("no CloudTrail events matched the execution session and time window")
    return matched


def compare_expected(expected: Any, execution: dict[str, Any], events: list[dict[str, Any]]) -> None:
    if not isinstance(expected, dict) or expected.get("schema_version") != 1:
        raise ValueError("expected audit schema is invalid")
    for key in ("execution_id", "session", "ticket_id"):
        if expected.get(key) != execution.get(key):
            raise ValueError(f"expected {key} does not match correlated execution")
    if expected.get("event_ids") != [event["event_id"] for event in events]:
        raise ValueError("expected event_ids do not exactly match correlated events")
    actual = [{key: event[key] for key in ("identity", "event", "source", "parameters", "error")} for event in events]
    if expected.get("events") != actual:
        raise ValueError("expected audit fields do not exactly match extracted events")


def compact(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execution-id", default="AI-EXEC-006")
    parser.add_argument("--executions", type=Path, default=root / "fixtures" / "ai-executions.json")
    parser.add_argument("--events", type=Path, default=root / "fixtures" / "cloudtrail-events.json")
    parser.add_argument("--expected", type=Path, default=root / "fixtures" / "expected-audit.json")
    args = parser.parse_args(argv)
    try:
        execution = select_execution(load(args.executions, "executions"), args.execution_id)
        events = correlate(load(args.events, "events"), execution)
        compare_expected(load(args.expected, "expected audit"), execution, events)
    except ValueError as exc:
        print("INVALID")
        print(f"- {exc}")
        return 1
    print("VALID")
    print(f"execution_id: {execution['execution_id']}")
    print(f"session: {execution['session']}")
    print(f"ticket_id: {execution['ticket_id']}")
    print(f"matched_events: {len(events)}")
    for index, event in enumerate(events, 1):
        print(f"event[{index}]: id={event['event_id']} time={event['event_time']}")
        print(f"  identity={event['identity']}")
        print(f"  event={event['event']} source={event['source']}")
        print(f"  parameters={compact(event['parameters'])}")
        print(f"  error={compact(event['error'])}")
    print("expected_comparison: PASS")
    print("aws_connection: false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
