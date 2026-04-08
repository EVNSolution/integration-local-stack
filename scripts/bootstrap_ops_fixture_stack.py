#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
import subprocess
import sys
import time
from typing import Callable, Sequence


@dataclass(frozen=True)
class Step:
    name: str
    argv: list[str]
    env: dict[str, str] = field(default_factory=dict)


Runner = Callable[[Step, Path], None]


def default_root_dir() -> Path:
    return Path(__file__).resolve().parents[3]


def build_steps(
    *,
    root_dir: Path,
    compose_path: Path,
    rebuild_images: bool,
    fresh_start: bool,
) -> tuple[Step, ...]:
    scripts_dir = root_dir / "development" / "integration-local-stack" / "scripts"
    steps: list[Step] = []
    if fresh_start:
        steps.append(
            Step(
                name="compose down fresh stack",
                argv=[
                    "docker",
                    "compose",
                    "-f",
                    str(compose_path),
                    "down",
                    "-v",
                    "--remove-orphans",
                ],
            )
        )
    compose_up_argv = [
        "docker",
        "compose",
        "-f",
        str(compose_path),
        "up",
        "-d",
        "--scale",
        "telemetry-dead-letter-api=0",
        "--scale",
        "telemetry-hub-api=0",
        "--scale",
        "telemetry-listener=0",
    ]
    if rebuild_images:
        compose_up_argv.append("--build")
    steps.extend(
        (
            Step(
                name="compose up base stack",
                argv=compose_up_argv,
            ),
            Step(
                name="seed stack with ops-derived fixture import",
                argv=[
                    "docker",
                    "compose",
                    "-f",
                    str(compose_path),
                    "run",
                    "--rm",
                    "-e",
                    "ENABLE_OPS_DERIVED_FIXTURE_IMPORT=1",
                    "-e",
                    "OPS_FIXTURE_BOOTSTRAP_MODE=1",
                    "seed-runner",
                ],
            ),
            Step(
                name="full ops-derived fixture smoke",
                argv=[
                    sys.executable,
                    str(scripts_dir / "verify_ops_fixture_stack.py"),
                    "--skip-build",
                ],
            ),
        )
    )
    return tuple(steps)


def _compose_file_from_step(step: Step) -> Path:
    compose_index = step.argv.index("-f") + 1
    return Path(step.argv[compose_index])


def recover_compose_down_if_stack_is_already_stopped(step: Step, cwd: Path) -> bool:
    compose_file = _compose_file_from_step(step)
    project_name = compose_file.parent.name
    ps_result = subprocess.run(
        ["docker", "compose", "-f", str(compose_file), "ps", "-q"],
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
    )
    if ps_result.returncode != 0 or (ps_result.stdout or "").strip():
        return False

    network_name = f"{project_name}_default"
    inspect_result = subprocess.run(
        ["docker", "network", "inspect", network_name],
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
    )
    if inspect_result.returncode != 0:
        return True

    network_payload = json.loads(inspect_result.stdout)
    if network_payload and network_payload[0].get("Containers"):
        return False
    return True


def run_command(step: Step, cwd: Path) -> None:
    env = os.environ.copy()
    env.update(step.env)
    attempts = 3 if step.name == "compose down fresh stack" else 1
    for attempt in range(1, attempts + 1):
        result = subprocess.run(step.argv, cwd=cwd, check=False, env=env)
        if result.returncode == 0:
            return
        is_fresh_compose_down = step.name == "compose down fresh stack"
        if is_fresh_compose_down and recover_compose_down_if_stack_is_already_stopped(step, cwd):
            print(
                "Recovered compose down fresh stack after network cleanup race; stack is already stopped.",
                flush=True,
            )
            return
        if is_fresh_compose_down:
            time.sleep(2)
            if recover_compose_down_if_stack_is_already_stopped(step, cwd):
                print(
                    "Recovered compose down fresh stack after delayed network cleanup race; stack is already stopped.",
                    flush=True,
                )
                return
        if attempt == attempts:
            raise subprocess.CalledProcessError(result.returncode, step.argv)
        print(
            f"Retrying {step.name} after non-zero exit ({result.returncode}), attempt {attempt + 1}/{attempts}...",
            flush=True,
        )
        time.sleep(2)


def run_steps(*, steps: Sequence[Step], cwd: Path, runner: Runner) -> None:
    for step in steps:
        print(f"==> {step.name}", flush=True)
        runner(step, cwd)


def parse_args() -> argparse.Namespace:
    root_dir = default_root_dir()
    parser = argparse.ArgumentParser(
        description="Boot the local stack with ops-derived fixture import enabled, then run the full smoke sequence.",
    )
    parser.add_argument(
        "--compose-file",
        type=Path,
        default=root_dir / "development" / "integration-local-stack" / "docker-compose.account-driver-settlement.yml",
    )
    parser.add_argument(
        "--build",
        action="store_true",
        help="Rebuild images before bringing the base stack up.",
    )
    parser.add_argument(
        "--fresh",
        action="store_true",
        help="Drop stack containers and volumes before bootstrapping.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root_dir = default_root_dir()
    steps = build_steps(
        root_dir=root_dir,
        compose_path=args.compose_file.resolve(),
        rebuild_images=args.build,
        fresh_start=args.fresh,
    )
    run_steps(steps=steps, cwd=root_dir, runner=run_command)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
