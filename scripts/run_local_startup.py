#!/usr/bin/env python3
from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from typing import Any, Callable, Mapping, Sequence
from urllib.error import URLError
from urllib.request import urlopen


@dataclass(frozen=True)
class Step:
    name: str
    argv: list[str]
    env: dict[str, str] = field(default_factory=dict)


Runner = Callable[[Step, Path], None]


def default_root_dir() -> Path:
    return Path(__file__).resolve().parents[3]


def default_compose_path() -> Path:
    return (
        default_root_dir()
        / "development"
        / "integration-local-stack"
        / "docker-compose.account-driver-settlement.yml"
    )


def default_manifest_path() -> Path:
    return (
        default_root_dir()
        / "development"
        / "integration-local-stack"
        / "compose"
        / "local-startup-manifest.json"
    )


def resolve_docker_command() -> str:
    if os.environ.get("DOCKER_BIN"):
        return os.environ["DOCKER_BIN"]
    docker_on_path = shutil.which("docker")
    if docker_on_path:
        return docker_on_path
    docker_desktop_binary = "/Applications/Docker.app/Contents/Resources/bin/docker"
    if Path(docker_desktop_binary).exists():
        return docker_desktop_binary
    return "docker"


def _runtime_argv(argv: Sequence[str]) -> list[str]:
    if argv and argv[0] == "docker":
        return [resolve_docker_command(), *argv[1:]]
    return list(argv)


def runtime_env(overrides: Mapping[str, str]) -> dict[str, str]:
    env = os.environ.copy()
    env.update(overrides)
    docker_bin_dir = str(Path(resolve_docker_command()).parent)
    current_path = env.get("PATH", "")
    path_parts = current_path.split(os.pathsep) if current_path else []
    if docker_bin_dir not in path_parts:
        env["PATH"] = os.pathsep.join([docker_bin_dir, *path_parts]) if path_parts else docker_bin_dir
    return env


def load_manifest(manifest_path: Path) -> dict[str, Any]:
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("stages"), list):
        raise ValueError(f"invalid startup manifest: {manifest_path}")
    return payload


def build_steps(
    *,
    root_dir: Path,
    compose_path: Path,
    manifest_path: Path,
    rebuild_images: bool,
    fresh_start: bool,
) -> tuple[Step, ...]:
    manifest = load_manifest(manifest_path)
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
    if rebuild_images:
        steps.append(
            Step(
                name="compose build local stack images",
                argv=[
                    "docker",
                    "compose",
                    "-f",
                    str(compose_path),
                    "build",
                ],
            )
        )

    for stage in manifest["stages"]:
        stage_name = stage["name"]
        services = stage.get("services", [])
        if services:
            steps.append(
                Step(
                    name=f"compose up {stage_name}",
                    argv=[
                        "docker",
                        "compose",
                        "-f",
                        str(compose_path),
                        "up",
                        "-d",
                        *services,
                    ],
                )
            )
        if stage.get("health_checks"):
            steps.append(
                Step(
                    name=f"wait for {stage_name} health",
                    argv=[
                        sys.executable,
                        str(Path(__file__).resolve()),
                        "wait-stage",
                        "--compose-file",
                        str(compose_path),
                        "--manifest",
                        str(manifest_path),
                        "--stage",
                        stage_name,
                    ],
                )
            )
        if stage.get("seed_runner"):
            steps.append(
                Step(
                    name="run seed stage",
                    argv=[
                        "docker",
                        "compose",
                        "-f",
                        str(compose_path),
                        "run",
                        "--rm",
                        stage["seed_runner"],
                    ],
                )
            )
        for command in stage.get("commands", []):
            steps.append(
                Step(
                    name=f"smoke: {command['name']}",
                    argv=list(command["argv"]),
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
        _runtime_argv(["docker", "compose", "-f", str(compose_file), "ps", "-q"]),
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
    )
    if ps_result.returncode != 0 or (ps_result.stdout or "").strip():
        return False

    network_name = f"{project_name}_default"
    inspect_result = subprocess.run(
        _runtime_argv(["docker", "network", "inspect", network_name]),
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
    env = runtime_env(step.env)
    attempts = 3 if step.name == "compose down fresh stack" else 1
    for attempt in range(1, attempts + 1):
        result = subprocess.run(_runtime_argv(step.argv), cwd=cwd, check=False, env=env)
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
        time.sleep(2)


def run_steps(*, steps: Sequence[Step], cwd: Path, runner: Runner) -> None:
    for step in steps:
        print(f"==> {step.name}", flush=True)
        runner(step, cwd)


def _find_stage(manifest: dict[str, Any], stage_name: str) -> dict[str, Any]:
    for stage in manifest["stages"]:
        if stage["name"] == stage_name:
            return stage
    raise KeyError(f"stage not found: {stage_name}")


def _check_host_http(url: str) -> bool:
    try:
        with urlopen(url, timeout=2) as response:
            return response.status == 200
    except (URLError, TimeoutError, OSError):
        return False


def _check_service_http(*, compose_path: Path, service: str, url: str, cwd: Path) -> bool:
    probe = (
        "import sys\n"
        "from urllib.error import URLError\n"
        "from urllib.request import urlopen\n"
        "url = sys.argv[1]\n"
        "try:\n"
        "    with urlopen(url, timeout=2) as response:\n"
        "        raise SystemExit(0 if response.status == 200 else 1)\n"
        "except (URLError, TimeoutError, OSError):\n"
        "    raise SystemExit(1)\n"
    )
    result = subprocess.run(
        [
            resolve_docker_command(),
            "compose",
            "-f",
            str(compose_path),
            "exec",
            "-T",
            service,
            "python",
            "-c",
            probe,
            url,
        ],
        cwd=cwd,
        check=False,
        env=runtime_env({}),
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def _check_service_exec(*, compose_path: Path, service: str, argv: Sequence[str], cwd: Path) -> bool:
    result = subprocess.run(
        _runtime_argv(
            [
                "docker",
                "compose",
                "-f",
                str(compose_path),
                "exec",
                "-T",
                service,
                *argv,
            ]
        ),
        cwd=cwd,
        check=False,
        env=runtime_env({}),
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def wait_for_stage_health(
    *,
    manifest_path: Path,
    compose_path: Path,
    stage_name: str,
    cwd: Path,
    attempts: int = 60,
    interval_seconds: int = 2,
) -> None:
    manifest = load_manifest(manifest_path)
    stage = _find_stage(manifest, stage_name)
    checks = stage.get("health_checks", [])
    if not checks:
        return

    for _ in range(attempts):
        all_ok = True
        for check in checks:
            kind = check["kind"]
            if kind == "host_http":
                ok = _check_host_http(check["url"])
            elif kind == "service_http":
                ok = _check_service_http(
                    compose_path=compose_path,
                    service=check["service"],
                    url=check["url"],
                    cwd=cwd,
                )
            elif kind == "service_exec":
                ok = _check_service_exec(
                    compose_path=compose_path,
                    service=check["service"],
                    argv=check["argv"],
                    cwd=cwd,
                )
            else:
                raise ValueError(f"unsupported health check kind: {kind}")

            if not ok:
                all_ok = False
                break
        if all_ok:
            return
        time.sleep(interval_seconds)
    raise RuntimeError(f"stage did not become healthy: {stage_name}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sequential local startup runner for integration-local-stack.",
    )
    subparsers = parser.add_subparsers(dest="command")

    wait_stage = subparsers.add_parser("wait-stage", help="Wait for one manifest stage to become healthy.")
    wait_stage.add_argument("--compose-file", type=Path, required=True)
    wait_stage.add_argument("--manifest", type=Path, required=True)
    wait_stage.add_argument("--stage", required=True)

    parser.add_argument(
        "--compose-file",
        type=Path,
        default=default_compose_path(),
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=default_manifest_path(),
    )
    parser.add_argument(
        "--build",
        action="store_true",
        help="Build compose images before startup.",
    )
    parser.add_argument(
        "--fresh",
        action="store_true",
        help="Run compose down -v before staged startup.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root_dir = default_root_dir()
    if args.command == "wait-stage":
        wait_for_stage_health(
            manifest_path=args.manifest.resolve(),
            compose_path=args.compose_file.resolve(),
            stage_name=args.stage,
            cwd=root_dir,
        )
        return 0

    steps = build_steps(
        root_dir=root_dir,
        compose_path=args.compose_file.resolve(),
        manifest_path=args.manifest.resolve(),
        rebuild_images=args.build,
        fresh_start=args.fresh,
    )
    run_steps(steps=steps, cwd=root_dir, runner=run_command)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
