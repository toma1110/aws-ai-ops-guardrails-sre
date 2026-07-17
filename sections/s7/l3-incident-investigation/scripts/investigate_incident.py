#!/usr/bin/env python3
"""Correlate synthetic operations observations without connecting to AWS."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


def load(path: Path, label: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot load {label}: {exc}") from exc


def timestamp(value: Any, label: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be an ISO-8601 string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{label} must be ISO-8601") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{label} must include a timezone")
    return parsed


def validate_fixture(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        raise ValueError("fixture schema_version must be 1")
    if data.get("local_only") is not True or data.get("aws_connection") is not False or data.get("credentials_required") is not False:
        raise ValueError("fixture must declare local_only=true, aws_connection=false, credentials_required=false")
    start = timestamp(data.get("window_start"), "window_start")
    end = timestamp(data.get("window_end"), "window_end")
    if start > end:
        raise ValueError("window_start must not be after window_end")
    collections = ("metrics", "logs", "cloudtrail_events", "config_changes", "resource_states")
    seen: set[str] = set()
    for collection in collections:
        items = data.get(collection)
        if not isinstance(items, list) or not items:
            raise ValueError(f"{collection} must be a non-empty list")
        time_key = {"cloudtrail_events": "event_time", "config_changes": "capture_time"}.get(collection, "timestamp")
        for item in items:
            if not isinstance(item, dict):
                raise ValueError(f"{collection} entries must be objects")
            evidence_id = item.get("evidence_id")
            if not isinstance(evidence_id, str) or not evidence_id or evidence_id in seen:
                raise ValueError("evidence_id must be non-empty and globally unique")
            seen.add(evidence_id)
            observed = timestamp(item.get(time_key), f"{evidence_id}.{time_key}")
            if not start <= observed <= end:
                raise ValueError(f"{evidence_id} is outside the incident window")
    return data


def find_one(items: list[dict[str, Any]], evidence_id: str) -> dict[str, Any]:
    matches = [item for item in items if item["evidence_id"] == evidence_id]
    if len(matches) != 1:
        raise ValueError(f"required evidence {evidence_id} must exist exactly once")
    return matches[0]


def validate_metric_state_pair(
    metric: dict[str, Any],
    state: dict[str, Any],
    *,
    expected_namespace: str,
    expected_metric: str,
    expected_service: str,
) -> None:
    evidence_id = metric.get("evidence_id", "metric")
    state_id = state.get("evidence_id", "state")
    if metric.get("namespace") != expected_namespace:
        raise ValueError(f"{evidence_id} namespace must be {expected_namespace}")
    if metric.get("metric") != expected_metric:
        raise ValueError(f"{evidence_id} metric must be {expected_metric}")
    if state.get("service") != expected_service:
        raise ValueError(f"{state_id} service must be {expected_service}")
    if metric.get("resource") != state.get("resource"):
        raise ValueError(f"{evidence_id} and {state_id} must reference the same resource")
    metric_time = timestamp(metric.get("timestamp"), f"{evidence_id}.timestamp")
    state_time = timestamp(state.get("timestamp"), f"{state_id}.timestamp")
    if metric_time != state_time:
        raise ValueError(f"{evidence_id} and {state_id} must have the same timestamp")


def build_report(data: dict[str, Any]) -> dict[str, Any]:
    metrics = data["metrics"]
    logs = data["logs"]
    events = data["cloudtrail_events"]
    changes = data["config_changes"]
    states = data["resource_states"]
    event = find_one(events, "CT-001")
    change = find_one(changes, "CFG-001")
    error = find_one(logs, "LOG-001")
    five_xx = find_one(metrics, "MET-002")
    unhealthy = find_one(metrics, "MET-003")
    cpu = find_one(metrics, "MET-004")
    connections = find_one(metrics, "MET-005")
    alb_state = find_one(states, "ALB-001")
    ec2_state = find_one(states, "EC2-001")
    rds_state = find_one(states, "RDS-001")
    validate_metric_state_pair(
        five_xx,
        alb_state,
        expected_namespace="AWS/ApplicationELB",
        expected_metric="HTTPCode_Target_5XX_Count",
        expected_service="ALB",
    )
    validate_metric_state_pair(
        unhealthy,
        alb_state,
        expected_namespace="AWS/ApplicationELB",
        expected_metric="UnHealthyHostCount",
        expected_service="ALB",
    )
    validate_metric_state_pair(
        cpu,
        ec2_state,
        expected_namespace="AWS/EC2",
        expected_metric="CPUUtilization",
        expected_service="EC2",
    )
    validate_metric_state_pair(
        connections,
        rds_state,
        expected_namespace="AWS/RDS",
        expected_metric="DatabaseConnections",
        expected_service="RDS",
    )
    thresholds = data.get("metric_thresholds")
    if not isinstance(thresholds, dict):
        raise ValueError("metric_thresholds must be an object")
    five_key = f"{five_xx.get('namespace')}:{five_xx.get('metric')}"
    unhealthy_key = f"{unhealthy.get('namespace')}:{unhealthy.get('metric')}"
    five_limit = thresholds.get(five_key)
    unhealthy_limit = thresholds.get(unhealthy_key)
    if not isinstance(five_limit, (int, float)) or five_xx.get("value", -1) < five_limit:
        raise ValueError("MET-002 must cross its declared threshold")
    if not isinstance(unhealthy_limit, (int, float)) or unhealthy.get("value", -1) < unhealthy_limit:
        raise ValueError("MET-003 must cross its declared threshold")
    if change.get("related_event_id") != event.get("event_id") or change.get("resource") != event.get("resource"):
        raise ValueError("Config change must correlate to the CloudTrail event and resource")
    if error.get("level") != "ERROR":
        raise ValueError("LOG-001 must be an ERROR observation")
    anomaly_start = min(error["timestamp"], five_xx["timestamp"], unhealthy["timestamp"])
    return {
        "schema_version": 1,
        "incident_id": data["incident_id"],
        "anomaly_start": anomaly_start,
        "facts": [
            {"id":"FACT-001","time":event["event_time"],"statement":f"ALB target group attribute change was recorded for ticket {event['ticket_id']}.","evidence_ids":["CT-001"]},
            {"id":"FACT-002","time":change["capture_time"],"statement":f"Config history records {change['changed_field']} changing from {change['before']} to {change['after']}.","evidence_ids":["CFG-001"]},
            {"id":"FACT-003","time":error["timestamp"],"statement":"Application log recorded an ERROR for a database-response timeout.","evidence_ids":["LOG-001"]},
            {"id":"FACT-004","time":five_xx["timestamp"],"statement":f"ALB target 5XX count crossed its local threshold: {five_xx['value']} >= {five_limit}.","evidence_ids":["MET-002"]},
            {"id":"FACT-005","time":unhealthy["timestamp"],"statement":f"ALB unhealthy-host count crossed its local threshold: {unhealthy['value']} >= {unhealthy_limit}.","evidence_ids":["MET-003",alb_state["evidence_id"]]},
            {"id":"FACT-006","time":cpu["timestamp"],"statement":f"EC2 status checks passed and CPUUtilization was {cpu['value']} {cpu['unit']}.","evidence_ids":[ec2_state["evidence_id"],"MET-004"]},
            {"id":"FACT-007","time":connections["timestamp"],"statement":f"RDS state was available and DatabaseConnections was {connections['value']} {connections['unit']}.","evidence_ids":[rds_state["evidence_id"],"MET-005"]}
        ],
        "hypotheses": [
            {"id":"HYP-001","statement":"The target-group attribute change may have contributed to the unhealthy target and 5XX increase.","supporting_evidence_ids":["CT-001","CFG-001","MET-002","MET-003","ALB-001"],"disconfirming_evidence_needed":"Compare request/target traces and test the previous value in an approved non-production environment."},
            {"id":"HYP-002","statement":"A transient database-response delay may have contributed to the application error, but current RDS state and connection count do not establish a database fault.","supporting_evidence_ids":["LOG-001","RDS-001","MET-005"],"disconfirming_evidence_needed":"Review approved RDS latency, load, and database logs for the same request window."}
        ],
        "unknowns": [
            {"id":"UNK-001","question":"Did the attribute change cause the unhealthy target and 5XX increase?","needed_evidence":"Request/target traces or an approved reproduction."},
            {"id":"UNK-002","question":"Was there a database latency or query event during req-synthetic-77?","needed_evidence":"RDS latency/load metrics and database logs that are not present in this fixture."}
        ],
        "human_decisions": [
            {"id":"HUM-001","decision":"Decide whether to roll back the target-group attribute after change-owner and impact review.","reason":"Rollback changes production state and cannot be authorized by this local investigation."},
            {"id":"HUM-002","decision":"Approve access to additional request traces or database logs if needed.","reason":"The fixture does not establish authorization, sensitivity, or retention boundaries for production data."}
        ]
    }


def validate_report(report: Any, evidence_ids: set[str]) -> None:
    if not isinstance(report, dict) or report.get("schema_version") != 1:
        raise ValueError("report schema_version must be 1")
    groups = {"facts":"evidence_ids", "hypotheses":"supporting_evidence_ids", "unknowns":None, "human_decisions":None}
    seen: set[str] = set()
    for group, evidence_key in groups.items():
        entries = report.get(group)
        if not isinstance(entries, list) or not entries:
            raise ValueError(f"report {group} must be a non-empty list")
        for entry in entries:
            entry_id = entry.get("id") if isinstance(entry, dict) else None
            if not isinstance(entry_id, str) or not entry_id or entry_id in seen:
                raise ValueError("report IDs must be non-empty and globally unique")
            seen.add(entry_id)
            if evidence_key:
                refs = entry.get(evidence_key)
                if not isinstance(refs, list) or not refs or any(ref not in evidence_ids for ref in refs):
                    raise ValueError(f"{entry_id} has missing or unknown evidence references")
    if any("cause" in fact.get("statement", "").lower() for fact in report["facts"]):
        raise ValueError("facts must not assert causality")


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", newline="\n")
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=root / "fixtures" / "incident-observations.json")
    parser.add_argument("--expected", type=Path, default=root / "fixtures" / "expected-investigation.json")
    parser.add_argument("--write-report", type=Path)
    args = parser.parse_args(argv)
    try:
        data = validate_fixture(load(args.input, "incident observations"))
        report = build_report(data)
        all_ids = {item["evidence_id"] for key in ("metrics","logs","cloudtrail_events","config_changes","resource_states") for item in data[key]}
        validate_report(report, all_ids)
        expected = load(args.expected, "expected investigation")
        validate_report(expected, all_ids)
        if report != expected:
            raise ValueError("generated report does not exactly match expected investigation")
        if args.write_report:
            args.write_report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except (ValueError, OSError) as exc:
        print("INVALID")
        print(f"- {exc}")
        return 1
    print("VALID")
    print(f"incident_id: {report['incident_id']}")
    print(f"anomaly_start: {report['anomaly_start']}")
    print(f"facts: {len(report['facts'])}")
    print(f"hypotheses: {len(report['hypotheses'])}")
    print(f"unknowns: {len(report['unknowns'])}")
    print(f"human_decisions: {len(report['human_decisions'])}")
    print("expected_comparison: PASS")
    print("aws_connection: false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
