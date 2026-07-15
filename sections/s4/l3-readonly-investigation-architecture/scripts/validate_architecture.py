#!/usr/bin/env python3
"""Validate the deterministic local ReadOnly investigation architecture."""

from __future__ import annotations

import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any


PLACEHOLDER = re.compile(r"\[[^\]\n]*(?:記入|YYYY-MM-DD|From|To|Kind|Label|未確認/承認/差戻し)[^\]\n]*\]|\b(?:TODO|TBD)\b", re.IGNORECASE)
FLOW_KINDS = {"request", "readonly_query", "authorize", "evidence", "audit", "recommendation", "human_decision"}
REQUIRED_EXPLANATIONS = ("人間判断:", "既存運用:", "監査:")
MERMAID_NODE = re.compile(r'^\s*([A-Z][A-Z0-9]*)\["([^"]+)"\]\s*$')
MERMAID_EDGE = re.compile(
    r"^\s*([A-Z][A-Z0-9]*)\s*(-->|-\.->|==>)\|([^|]+)\|\s*"
    r"([A-Z][A-Z0-9]*)\s*$"
)
MERMAID_FLOW_ID = re.compile(r"^\s*%%\s*(F\d{2})\s*$")
EDGE_STYLE = {"audit": "-.->", "human_decision": "==>"}


def table_rows(text: str, id_pattern: str, columns: int) -> tuple[dict[str, list[str]], list[str]]:
    rows: dict[str, list[str]] = {}
    errors: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if not cells or not re.fullmatch(id_pattern, cells[0]):
            continue
        row_id = cells[0]
        if row_id in rows:
            errors.append(f"duplicate row: {row_id}")
        elif len(cells) != columns:
            errors.append(f"row must have {columns} columns: {row_id}")
        else:
            rows[row_id] = cells
    return rows, errors


def validate_requirements(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["requirements root must be an object"]
    for key, expected in (("local_only", True), ("aws_connection", False), ("credentials_required", False)):
        if data.get(key) is not expected:
            errors.append(f"requirements must declare {key}: {str(expected).lower()}")
    nodes = data.get("required_nodes")
    flows = data.get("required_flows")
    scope = data.get("required_scope")
    if not isinstance(nodes, dict) or not nodes:
        errors.append("required_nodes must be a non-empty object")
    if not isinstance(scope, dict) or not scope:
        errors.append("required_scope must be a non-empty object")
    if not isinstance(flows, list):
        return errors + ["required_flows must be an array"]
    seen: set[str] = set()
    for flow in flows:
        if not isinstance(flow, dict) or not all(isinstance(flow.get(k), str) and flow[k] for k in ("id", "from", "to", "kind", "label")):
            errors.append("each required flow must contain non-empty id/from/to/kind/label")
            continue
        if flow["id"] in seen:
            errors.append(f"duplicate required flow: {flow['id']}")
        seen.add(flow["id"])
        if isinstance(nodes, dict) and (flow["from"] not in nodes or flow["to"] not in nodes):
            errors.append(f"required flow references unknown node: {flow['id']}")
        if flow["kind"] not in FLOW_KINDS:
            errors.append(f"unknown required flow kind: {flow['id']}")
    return errors


def validate_mermaid(text: str, requirements: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    blocks = re.findall(r"```mermaid\s*\n(.*?)```", text, re.DOTALL)
    if len(blocks) != 1:
        return [f"expected exactly one Mermaid architecture diagram, found {len(blocks)}"]
    lines = blocks[0].splitlines()
    if not lines or lines[0].strip() != "flowchart LR":
        errors.append("Mermaid diagram must start with flowchart LR")
    nodes: dict[str, str] = {}
    edges: dict[str, tuple[str, str, str, str]] = {}
    pending_flow_id: str | None = None
    seen_flow_ids: set[str] = set()
    for line in lines[1:]:
        if not line.strip():
            if pending_flow_id is not None:
                errors.append(f"Flow ID comment must be immediately followed by an edge: {pending_flow_id}")
                pending_flow_id = None
            continue
        flow_id_match = MERMAID_FLOW_ID.fullmatch(line)
        if flow_id_match:
            flow_id = flow_id_match.group(1)
            if pending_flow_id is not None:
                errors.append(f"Flow ID comment is not bound to an edge: {pending_flow_id}")
            if flow_id in seen_flow_ids:
                errors.append(f"duplicate Mermaid Flow ID comment: {flow_id}")
            seen_flow_ids.add(flow_id)
            pending_flow_id = flow_id
            continue
        node_match = MERMAID_NODE.fullmatch(line)
        if node_match:
            if pending_flow_id is not None:
                errors.append(f"Flow ID comment must be followed by an edge, found node: {pending_flow_id}")
                pending_flow_id = None
            node_id, name = node_match.groups()
            if node_id in nodes:
                errors.append(f"duplicate Mermaid node: {node_id}")
            else:
                nodes[node_id] = name
            continue
        edge_match = MERMAID_EDGE.fullmatch(line)
        if edge_match:
            source, style, label, target = edge_match.groups()
            if pending_flow_id is None:
                errors.append(f"Mermaid edge is missing a preceding Flow ID comment: {source}->{target}")
                continue
            flow_id = pending_flow_id
            pending_flow_id = None
            if flow_id in edges:
                errors.append(f"duplicate Mermaid edge: {flow_id}")
            else:
                edges[flow_id] = (source, target, style, label.strip())
            continue
        if pending_flow_id is not None:
            errors.append(f"Flow ID comment must be immediately followed by a recognized edge: {pending_flow_id}")
            pending_flow_id = None
        errors.append(f"unrecognized Mermaid line: {line.strip()}")

    if pending_flow_id is not None:
        errors.append(f"Flow ID comment is not followed by an edge: {pending_flow_id}")

    expected_nodes = requirements["required_nodes"]
    for node_id, name in expected_nodes.items():
        if node_id not in nodes:
            errors.append(f"missing Mermaid node: {node_id}")
        elif nodes[node_id] != name:
            errors.append(f"Mermaid node name mismatch: {node_id}")
    for node_id in nodes.keys() - expected_nodes.keys():
        errors.append(f"unknown Mermaid node: {node_id}")

    expected_edges = {flow["id"]: flow for flow in requirements["required_flows"]}
    for flow_id, flow in expected_edges.items():
        edge = edges.get(flow_id)
        if edge is None:
            errors.append(f"missing Mermaid edge: {flow_id}")
            continue
        source, target, style, label = edge
        expected_style = EDGE_STYLE.get(flow["kind"], "-->")
        if source != flow["from"]:
            errors.append(f"Mermaid edge from mismatch: {flow_id}")
        if target != flow["to"]:
            errors.append(f"Mermaid edge to mismatch: {flow_id}")
        if style != expected_style:
            errors.append(f"Mermaid edge style mismatch: {flow_id}")
        if label != flow["label"]:
            errors.append(f"Mermaid edge label mismatch: {flow_id}")
    for flow_id in edges.keys() - expected_edges.keys():
        errors.append(f"unknown Mermaid edge: {flow_id}")
    if any(source == "AI" and target in requirements["forbidden_ai_targets"] for source, target, _, _ in edges.values()):
        errors.append("Mermaid AI must not connect directly to existing operations")
    return errors


def validate_text(text: str, requirements: Any) -> list[str]:
    errors = validate_requirements(requirements)
    if errors:
        return errors
    scope_rows, scope_errors = table_rows(text, r"SC-\d{2}", 2)
    node_rows, node_errors = table_rows(text, r"(?:HUMAN|AI|MCP|IAM|CW|CT|CFG|AILOG|OPS)", 3)
    flow_rows, flow_errors = table_rows(text, r"F\d{2}", 5)
    errors.extend(scope_errors + node_errors + flow_errors)

    for scope_id, declaration in requirements["required_scope"].items():
        row = scope_rows.get(scope_id)
        if row is None:
            errors.append(f"missing scope row: {scope_id}")
        elif row[1] != declaration:
            errors.append(f"scope mismatch: {scope_id}")
    for extra in scope_rows.keys() - requirements["required_scope"].keys():
        errors.append(f"unknown scope row: {extra}")

    for node_id, name in requirements["required_nodes"].items():
        row = node_rows.get(node_id)
        if row is None:
            errors.append(f"missing node row: {node_id}")
        else:
            if row[1] != name:
                errors.append(f"node name mismatch: {node_id}")
            if len(row[2]) < 15:
                errors.append(f"node boundary is not specific: {node_id}")

    expected_flows = {flow["id"]: flow for flow in requirements["required_flows"]}
    for flow_id, expected in expected_flows.items():
        row = flow_rows.get(flow_id)
        if row is None:
            errors.append(f"missing flow row: {flow_id}")
            continue
        actual = dict(zip(("id", "from", "to", "kind", "label"), row))
        for key in ("from", "to", "kind", "label"):
            if actual[key] != expected[key]:
                errors.append(f"flow {key} mismatch: {flow_id}")
    for extra in flow_rows.keys() - expected_flows.keys():
        errors.append(f"unknown flow row: {extra}")

    forbidden = set(requirements["forbidden_ai_targets"])
    if any(row[1] == "AI" and row[2] in forbidden for row in flow_rows.values()):
        errors.append("AI must not connect directly to existing operations")
    if not any(row[1:4] == ["HUMAN", "OPS", "human_decision"] for row in flow_rows.values()):
        errors.append("existing operations must be reached through human_decision")
    kinds = {row[3] for row in flow_rows.values()}
    for kind in requirements["required_kinds"]:
        if kind not in kinds:
            errors.append(f"missing flow kind: {kind}")
    for label in REQUIRED_EXPLANATIONS:
        match = re.search(rf"^-\s*{re.escape(label)}\s*(.+)$", text, re.MULTILINE)
        if match is None or len(match.group(1).strip()) < 25:
            errors.append(f"missing or weak explanation: {label[:-1]}")
    errors.extend(validate_mermaid(text, requirements))
    placeholders = PLACEHOLDER.findall(text)
    if placeholders:
        errors.append(f"unresolved placeholders: {len(placeholders)}")
    fixture_match = re.search(r"^-\s*使用fixture:\s*`([^`]+)`", text, re.MULTILINE)
    if fixture_match is None or fixture_match.group(1) != "fixtures/architecture-requirements.json":
        errors.append("fixture reference must be fixtures/architecture-requirements.json")
    date_match = re.search(r"^-\s*作成日:\s*(\S+)", text, re.MULTILINE)
    try:
        if date_match is None:
            raise ValueError
        date.fromisoformat(date_match.group(1))
    except ValueError:
        errors.append("invalid creation date")
    return errors


def display(path: Path) -> str:
    root = Path(__file__).resolve().parents[1]
    try:
        return path.resolve().relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def main(argv: list[str]) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    root = Path(__file__).resolve().parents[1]
    document = Path(argv[1]) if len(argv) > 1 else root / "examples" / "completed-readonly-investigation-architecture.md"
    fixture = Path(argv[2]) if len(argv) > 2 else root / "fixtures" / "architecture-requirements.json"
    if len(argv) > 3:
        print("INVALID\n- usage: validate_architecture.py [markdown-path] [fixture-path]")
        return 1
    try:
        text = document.read_text(encoding="utf-8")
        requirements = json.loads(fixture.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"INVALID\n- cannot read input: {exc}")
        return 1
    errors = validate_text(text, requirements)
    if errors:
        print("INVALID")
        for error in errors:
            print(f"- {error}")
        return 1
    print("VALID")
    print(f"architecture: {display(document)}")
    print(f"fixture: {display(fixture)}")
    print(f"scope: {len(requirements['required_scope'])}/{len(requirements['required_scope'])}")
    print(f"nodes: {len(requirements['required_nodes'])}/{len(requirements['required_nodes'])}")
    print(f"flows: {len(requirements['required_flows'])}/{len(requirements['required_flows'])}")
    print("flow_id_binding: standalone_preceding_comment")
    print("permission_boundary: readonly")
    print("audit_paths: cloudtrail+ai_execution_log")
    print("existing_operations: human_decision_only")
    print("aws_connection: false")
    print("placeholders: 0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

