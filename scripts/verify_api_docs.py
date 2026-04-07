#!/usr/bin/env python3

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
from typing import Any

import yaml

from build_unified_openapi import OUTPUT_PATH, load_active_services


def iter_operations(spec: dict[str, Any]):
    for path, path_item in (spec.get("paths") or {}).items():
        if not isinstance(path_item, dict):
            continue
        for method, operation in path_item.items():
            if method.startswith("x-") or method == "parameters":
                continue
            if not isinstance(operation, dict):
                continue
            yield path, method, operation


def walk_refs(value: Any):
    if isinstance(value, dict):
        ref = value.get("$ref")
        if isinstance(ref, str):
            yield ref
        for child in value.values():
            yield from walk_refs(child)
        return
    if isinstance(value, list):
        for item in value:
            yield from walk_refs(item)


def resolve_ref(spec: dict[str, Any], ref: str) -> bool:
    if not ref.startswith("#/"):
        return False
    current: Any = spec
    for segment in ref[2:].split("/"):
        if not isinstance(current, dict) or segment not in current:
            return False
        current = current[segment]
    return True


def verify_spec(path: Path) -> None:
    if not path.exists():
        raise SystemExit(f"Unified OpenAPI artifact not found: {path}")

    spec = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    active_services = load_active_services()
    active_repo_names = [service.repo_name for service in active_services]

    operations = list(iter_operations(spec))
    if not operations:
        raise SystemExit("Unified OpenAPI has no operations.")

    counts = Counter()
    service_operation_counts = Counter()
    missing_refs: set[str] = set()
    for _, _, operation in operations:
        source = operation.get("x-clever-schema-source", "missing")
        counts[source] += 1
        for tag in operation.get("tags", []):
            service_operation_counts[tag] += 1
        for ref in walk_refs(operation):
            if not resolve_ref(spec, ref):
                missing_refs.add(ref)

    for ref in walk_refs(spec.get("components", {})):
        if not resolve_ref(spec, ref):
            missing_refs.add(ref)

    components = spec.get("components") or {}
    schemas = components.get("schemas") or {}

    print(f"[verify] file={path}")
    print(f"[verify] active_services={len(active_repo_names)} operations={len(operations)}")
    print(f"[verify] source_counts={dict(counts)}")
    print(f"[verify] component_schemas={len(schemas)}")

    failures: list[str] = []

    if counts.get("route-inventory", 0) != 0:
        failures.append(f"route-inventory operations remain: {counts['route-inventory']}")
    if counts.get("missing", 0) != 0:
        failures.append(f"operations missing schema source metadata: {counts['missing']}")
    if len(service_operation_counts) != len(active_repo_names):
        missing_tags = sorted(set(active_repo_names) - set(service_operation_counts))
        failures.append(f"active services missing from unified spec tags: {', '.join(missing_tags)}")
    for repo_name in active_repo_names:
        if service_operation_counts.get(repo_name, 0) == 0:
            failures.append(f"service has no operations in unified spec: {repo_name}")
    if not schemas:
        failures.append("components.schemas is empty")
    if missing_refs:
        failures.append(f"unresolved refs: {', '.join(sorted(missing_refs))}")

    if failures:
        print("[verify] failed")
        for failure in failures:
            print(f"- {failure}")
        raise SystemExit(1)

    print("[verify] passed")


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify the generated CLEVER current MSA unified OpenAPI artifact.")
    parser.add_argument(
        "--input",
        default=str(OUTPUT_PATH),
        help="Path to the generated OpenAPI YAML to verify.",
    )
    args = parser.parse_args()
    verify_spec(Path(args.input))


if __name__ == "__main__":
    main()
