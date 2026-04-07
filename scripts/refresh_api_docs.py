#!/usr/bin/env python3

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
PLATFORM_ROOT = Path(__file__).resolve().parents[3]
EXPORT_SCRIPT = SCRIPT_DIR / "export_service_openapi.py"
BUILD_SCRIPT = SCRIPT_DIR / "build_unified_openapi.py"
VERIFY_SCRIPT = SCRIPT_DIR / "verify_api_docs.py"


def build_export_command(*, python_bin: str, services: list[str], strict: bool) -> list[str]:
    command = [python_bin, str(EXPORT_SCRIPT)]
    if not strict:
        command.append("--keep-going")
    for service in services:
        command.extend(["--service", service])
    return command


def build_unified_command(*, python_bin: str) -> list[str]:
    return [python_bin, str(BUILD_SCRIPT)]


def build_verify_command(*, python_bin: str) -> list[str]:
    return [python_bin, str(VERIFY_SCRIPT)]


def run_command(command: list[str], *, description: str, allow_failure: bool) -> int:
    print(f"[run] {description}", flush=True)
    print(" ".join(command), flush=True)
    result = subprocess.run(command, cwd=PLATFORM_ROOT)
    if result.returncode == 0:
        return 0
    if allow_failure:
        print(
            f"[warn] {description} failed with exit code {result.returncode}. Continuing with route fallback.",
            flush=True,
        )
        return result.returncode
    raise SystemExit(result.returncode)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Refresh the CLEVER current MSA API docs by exporting service schemas and rebuilding the unified OpenAPI."
    )
    parser.add_argument(
        "--service",
        action="append",
        dest="services",
        help="Repo name to export. Repeat to limit the refresh set.",
    )
    parser.add_argument(
        "--python",
        default=sys.executable,
        help="Python executable to use for export/build scripts.",
    )
    parser.add_argument(
        "--build-only",
        action="store_true",
        help="Skip service schema export and rebuild the unified artifact from existing schema files only.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail immediately if any service schema export fails.",
    )
    parser.add_argument(
        "--skip-verify",
        action="store_true",
        help="Skip unified OpenAPI verification after the build step.",
    )
    args = parser.parse_args()

    services = list(dict.fromkeys(args.services or []))
    if args.build_only and services:
        raise SystemExit("--service cannot be used together with --build-only.")

    export_exit_code = 0
    if not args.build_only:
        export_exit_code = run_command(
            build_export_command(
                python_bin=args.python,
                services=services,
                strict=args.strict,
            ),
            description="export service-owned OpenAPI schemas",
            allow_failure=not args.strict,
        )

    run_command(
        build_unified_command(python_bin=args.python),
        description="build unified OpenAPI artifact",
        allow_failure=False,
    )

    if not args.skip_verify:
        run_command(
            build_verify_command(python_bin=args.python),
            description="verify unified OpenAPI artifact",
            allow_failure=False,
        )

    if export_exit_code != 0:
        raise SystemExit(export_exit_code)


if __name__ == "__main__":
    main()
