#!/usr/bin/env python3
from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import subprocess
import sys
from typing import Callable, Sequence


DEFAULT_PLAYWRIGHT_SPEC = "e2e/ops-fixture-console.spec.ts"


@dataclass(frozen=True)
class Step:
    name: str
    argv: list[str]


Runner = Callable[[Step, Path], None]


def default_root_dir() -> Path:
    return Path(__file__).resolve().parents[3]


def build_steps(
    *,
    root_dir: Path,
    compose_path: Path,
    playwright_spec: str,
    rebuild_images: bool,
) -> tuple[Step, ...]:
    scripts_dir = root_dir / "development" / "integration-local-stack" / "scripts"
    steps: list[Step] = []
    if rebuild_images:
        steps.append(
            Step(
                name="playwright image build",
                argv=[
                    "docker",
                    "compose",
                    "-f",
                    str(compose_path),
                    "build",
                    "web-console",
                    "web-console-e2e",
                ],
            )
        )
    steps.extend(
        (
        Step(
            name="refresh web console runtime",
            argv=[
                "docker",
                "compose",
                "-f",
                str(compose_path),
                "up",
                "-d",
                "--force-recreate",
                "--no-deps",
                "web-console",
            ],
        ),
        Step(
            name="core gateway smoke",
            argv=[
                sys.executable,
                str(scripts_dir / "verify_core_gateway_routes.py"),
            ],
        ),
        Step(
            name="authenticated runtime smoke",
            argv=[
                sys.executable,
                str(scripts_dir / "verify_ops_fixture_runtime.py"),
            ],
        ),
        Step(
            name="playwright web smoke",
            argv=[
                "docker",
                "compose",
                "-f",
                str(compose_path),
                "run",
                "--rm",
                "web-console-e2e",
                "sh",
                "-lc",
                f"npx playwright test {playwright_spec}",
            ],
        ),
        )
    )
    return tuple(steps)


def run_command(step: Step, cwd: Path) -> None:
    subprocess.run(step.argv, cwd=cwd, check=True)


def run_steps(*, steps: Sequence[Step], cwd: Path, runner: Runner) -> None:
    for step in steps:
        print(f"==> {step.name}", flush=True)
        runner(step, cwd)


def parse_args() -> argparse.Namespace:
    root_dir = default_root_dir()
    parser = argparse.ArgumentParser(
        description="Run the full ops-derived local fixture smoke sequence.",
    )
    parser.add_argument(
        "--compose-file",
        type=Path,
        default=root_dir / "development" / "integration-local-stack" / "docker-compose.account-driver-settlement.yml",
    )
    parser.add_argument(
        "--playwright-spec",
        default=DEFAULT_PLAYWRIGHT_SPEC,
    )
    parser.add_argument(
        "--skip-build",
        action="store_true",
        help="Reuse existing web-console and web-console-e2e images without rebuilding them.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root_dir = default_root_dir()
    steps = build_steps(
        root_dir=root_dir,
        compose_path=args.compose_file.resolve(),
        playwright_spec=args.playwright_spec,
        rebuild_images=not args.skip_build,
    )
    run_steps(steps=steps, cwd=root_dir, runner=run_command)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
