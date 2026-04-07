#!/usr/bin/env python3

from __future__ import annotations

import argparse
import os
import subprocess
import sys

from build_unified_openapi import SCHEMA_ENABLED_SERVICES, load_active_services, service_schema_path


def enabled_services(selected_services: set[str] | None) -> list:
    services = [
        service
        for service in load_active_services()
        if service.repo_name in SCHEMA_ENABLED_SERVICES
    ]
    if not selected_services:
        return services
    return [service for service in services if service.repo_name in selected_services]


def ensure_drf_spectacular(python_bin: str) -> None:
    result = subprocess.run(
        [python_bin, "-c", "import drf_spectacular"],
        text=True,
        capture_output=True,
    )
    if result.returncode == 0:
        return
    message = "drf-spectacular is not installed in the selected Python environment."
    if result.stderr.strip():
        message = f"{message}\n{result.stderr.strip()}"
    raise SystemExit(message)


def export_service_schema(service, *, python_bin: str, keep_going: bool) -> bool:
    output_path = service_schema_path(service)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        output_path.unlink()

    env = os.environ.copy()
    env.setdefault("DJANGO_SECRET_KEY", "openapi-export-secret-key")
    env.setdefault("JWT_SECRET_KEY", "openapi-export-jwt-secret-key-32chars")
    env.setdefault("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,testserver")
    if service.repo_name == "service-personnel-document-registry":
        env.setdefault("PERSONNEL_DOCUMENT_TEST_MODE", "1")

    command = [python_bin, "manage.py", "spectacular", "--file", str(output_path)]
    print(f"[export] {service.repo_name} -> {output_path}")
    result = subprocess.run(
        command,
        cwd=service.repo_path,
        env=env,
        text=True,
        capture_output=True,
    )
    if result.returncode == 0:
        if result.stdout.strip():
            print(result.stdout.strip())
        return True

    print(result.stdout.strip())
    print(result.stderr.strip(), file=sys.stderr)
    if keep_going:
        return False
    raise SystemExit(result.returncode)


def main() -> None:
    parser = argparse.ArgumentParser(description="Export service-owned OpenAPI files for current CLEVER MSA services.")
    parser.add_argument(
        "--service",
        action="append",
        dest="services",
        help="Repo name to export. Repeat to limit the export set.",
    )
    parser.add_argument(
        "--python",
        default=sys.executable,
        help="Python executable to use for each service manage.py command.",
    )
    parser.add_argument(
        "--keep-going",
        action="store_true",
        help="Continue exporting remaining services even if one export fails.",
    )
    args = parser.parse_args()

    selected_services = set(args.services or [])
    services = enabled_services(selected_services)
    if not services:
        raise SystemExit("No schema-enabled services matched the requested export set.")

    ensure_drf_spectacular(args.python)

    exported = 0
    failed: list[str] = []
    for service in services:
        success = export_service_schema(
            service,
            python_bin=args.python,
            keep_going=args.keep_going,
        )
        if success:
            exported += 1
        else:
            failed.append(service.repo_name)

    print(f"[summary] exported={exported} failed={len(failed)}")
    if failed:
        print(f"[summary] failed services: {', '.join(failed)}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
