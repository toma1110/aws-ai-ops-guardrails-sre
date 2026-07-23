import argparse
import hashlib
import json
from pathlib import Path

import build_materials


def validate_package(input_path, template_dir, output_dir, expected_path):
    errors = []
    try:
        data = build_materials.load_json(input_path)
        templates = build_materials.load_templates(template_dir)
        expected_document = build_materials.load_json(expected_path)
        expected = expected_document.get("generated_package", expected_document)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return {}, [f"input_read_error:{type(exc).__name__}"]

    errors.extend(build_materials.validate_input(data))
    if errors:
        return {}, errors
    if set(expected) != {"schema", "concern_ids", "output_files", "required_preserved_processes", "result"}:
        errors.append("expected_result_fields_invalid")
    if expected.get("schema") != "s10-expected-results-v1" or expected.get("result") != "pass":
        errors.append("expected_result_identity_invalid")
    if expected.get("concern_ids") != list(build_materials.CONCERN_IDS):
        errors.append("expected_concern_population_invalid")
    if expected.get("output_files") != list(build_materials.OUTPUT_FILES):
        errors.append("expected_output_population_invalid")

    try:
        canonical = build_materials.build_documents(data, templates)
    except ValueError as exc:
        return {}, errors + [str(exc)]
    output_dir = Path(output_dir)
    actual_names = sorted(path.name for path in output_dir.glob("*.md")) if output_dir.is_dir() else []
    if actual_names != sorted(build_materials.OUTPUT_FILES):
        errors.append("output_population_invalid")

    hashes = {}
    combined = ""
    for filename in build_materials.OUTPUT_FILES:
        path = output_dir / filename
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            errors.append(f"output_unreadable:{filename}")
            continue
        if content != canonical[filename]:
            errors.append(f"output_not_deterministic:{filename}")
        if "{{" in content or "}}" in content:
            errors.append(f"placeholder_remaining:{filename}")
        hashes[filename] = hashlib.sha256(path.read_bytes()).hexdigest()
        combined += content

    for concern_id in build_materials.CONCERN_IDS:
        if combined.count(concern_id) < 3:
            errors.append(f"concern_not_covered_in_all_documents:{concern_id}")
    for process in expected.get("required_preserved_processes", []):
        if process not in canonical["introduction.md"]:
            errors.append(f"preserved_process_missing:{process}")
    if "AWSへ接続" not in combined or "接続せず" not in combined:
        errors.append("api_connection_boundary_missing")
    if "AIは判断主体ではありません" not in canonical["faq.md"]:
        errors.append("accountability_boundary_missing")
    return hashes, errors


def main():
    parser = argparse.ArgumentParser(description="Validate the complete local S10 learner package")
    parser.add_argument("--input", required=True)
    parser.add_argument("--templates", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--expected", required=True)
    args = parser.parse_args()
    hashes, errors = validate_package(args.input, args.templates, args.output, args.expected)
    for filename, digest in sorted(hashes.items()):
        print(f"{filename}: sha256={digest}")
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("PASS: S10 package preserves four concern boundaries and three existing processes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
