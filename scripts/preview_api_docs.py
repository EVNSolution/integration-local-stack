#!/usr/bin/env python3

from __future__ import annotations

import argparse
import functools
import http.server
import socketserver
import subprocess
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
PLATFORM_ROOT = Path(__file__).resolve().parents[3]
API_DOCS_DIR = PLATFORM_ROOT / "development" / "integration-local-stack" / "compose" / "api-docs"
REFRESH_SCRIPT = SCRIPT_DIR / "refresh_api_docs.py"


def build_refresh_command(
    *,
    python_bin: str,
    services: list[str],
    strict: bool,
    build_only: bool,
    skip_verify: bool,
) -> list[str]:
    command = [python_bin, str(REFRESH_SCRIPT)]
    if strict:
        command.append("--strict")
    if build_only:
        command.append("--build-only")
    if skip_verify:
        command.append("--skip-verify")
    for service in services:
        command.extend(["--service", service])
    return command


def refresh_docs(
    *,
    python_bin: str,
    services: list[str],
    strict: bool,
    build_only: bool,
    skip_verify: bool,
) -> None:
    command = build_refresh_command(
        python_bin=python_bin,
        services=services,
        strict=strict,
        build_only=build_only,
        skip_verify=skip_verify,
    )
    print("[preview] refreshing API docs", flush=True)
    print(" ".join(command), flush=True)
    result = subprocess.run(command, cwd=PLATFORM_ROOT)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def serve_docs(*, host: str, port: int) -> None:
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(API_DOCS_DIR))
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer((host, port), handler) as httpd:
        print("[preview] serving API docs", flush=True)
        print(f"[preview] root=http://{host}:{port}/", flush=True)
        print(f"[preview] spec=http://{host}:{port}/clever-unified.openapi.yaml", flush=True)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n[preview] stopped", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Refresh and preview the CLEVER current MSA API docs locally."
    )
    parser.add_argument(
        "--python",
        default=sys.executable,
        help="Python executable to use for the refresh helper.",
    )
    parser.add_argument(
        "--service",
        action="append",
        dest="services",
        help="Repo name to limit the refresh set before starting the viewer.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail immediately if any service schema export fails during refresh.",
    )
    parser.add_argument(
        "--build-only",
        action="store_true",
        help="Skip schema export and rebuild from existing schema files before serving.",
    )
    parser.add_argument(
        "--skip-refresh",
        action="store_true",
        help="Serve the current api-docs directory without running refresh first.",
    )
    parser.add_argument(
        "--skip-verify",
        action="store_true",
        help="Skip unified OpenAPI verification during the refresh step.",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host interface for the local preview server.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8099,
        help="Port for the local preview server.",
    )
    args = parser.parse_args()

    services = list(dict.fromkeys(args.services or []))
    if args.skip_refresh and services:
        raise SystemExit("--service cannot be used together with --skip-refresh.")
    if args.skip_refresh and args.build_only:
        raise SystemExit("--build-only cannot be used together with --skip-refresh.")

    if not API_DOCS_DIR.exists():
        raise SystemExit(f"API docs directory not found: {API_DOCS_DIR}")

    if not args.skip_refresh:
        refresh_docs(
            python_bin=args.python,
            services=services,
            strict=args.strict,
            build_only=args.build_only,
            skip_verify=args.skip_verify,
        )

    serve_docs(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
