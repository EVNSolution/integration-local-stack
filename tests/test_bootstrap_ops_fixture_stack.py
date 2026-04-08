from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import sys
import unittest
from unittest import mock


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "bootstrap_ops_fixture_stack.py"
)


def load_module():
    spec = importlib.util.spec_from_file_location(
        "bootstrap_ops_fixture_stack",
        SCRIPT_PATH,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load script module from {SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class BootstrapOpsFixtureStackTests(unittest.TestCase):
    def test_build_steps_bootstraps_then_verifies(self) -> None:
        module = load_module()

        steps = module.build_steps(
            root_dir=Path("/repo"),
            compose_path=Path("/repo/development/integration-local-stack/docker-compose.account-driver-settlement.yml"),
            rebuild_images=False,
            fresh_start=False,
        )

        self.assertEqual([step.name for step in steps], [
            "compose up base stack",
            "seed stack with ops-derived fixture import",
            "full ops-derived fixture smoke",
        ])
        self.assertEqual(
            steps[0].argv,
            [
                "docker",
                "compose",
                "-f",
                "/repo/development/integration-local-stack/docker-compose.account-driver-settlement.yml",
                "up",
                "-d",
                "--scale",
                "telemetry-dead-letter-api=0",
                "--scale",
                "telemetry-hub-api=0",
                "--scale",
                "telemetry-listener=0",
            ],
        )
        self.assertEqual(steps[0].env, {})
        self.assertEqual(
            steps[1].argv,
            [
                "docker",
                "compose",
                "-f",
                "/repo/development/integration-local-stack/docker-compose.account-driver-settlement.yml",
                "run",
                "--rm",
                "-e",
                "ENABLE_OPS_DERIVED_FIXTURE_IMPORT=1",
                "-e",
                "OPS_FIXTURE_BOOTSTRAP_MODE=1",
                "seed-runner",
            ],
        )
        self.assertEqual(steps[2].argv[0], sys.executable)
        self.assertIn("verify_ops_fixture_stack.py", str(steps[2].argv[1]))
        self.assertIn("--skip-build", steps[2].argv)

    def test_build_steps_can_opt_into_image_rebuild(self) -> None:
        module = load_module()

        steps = module.build_steps(
            root_dir=Path("/repo"),
            compose_path=Path("/repo/development/integration-local-stack/docker-compose.account-driver-settlement.yml"),
            rebuild_images=True,
            fresh_start=False,
        )

        self.assertEqual(
            steps[0].argv,
            [
                "docker",
                "compose",
                "-f",
                "/repo/development/integration-local-stack/docker-compose.account-driver-settlement.yml",
                "up",
                "-d",
                "--scale",
                "telemetry-dead-letter-api=0",
                "--scale",
                "telemetry-hub-api=0",
                "--scale",
                "telemetry-listener=0",
                "--build",
            ],
        )

    def test_build_steps_can_reset_stack_before_bootstrap(self) -> None:
        module = load_module()

        steps = module.build_steps(
            root_dir=Path("/repo"),
            compose_path=Path("/repo/development/integration-local-stack/docker-compose.account-driver-settlement.yml"),
            rebuild_images=False,
            fresh_start=True,
        )

        self.assertEqual(steps[0].name, "compose down fresh stack")
        self.assertEqual(
            steps[0].argv,
            [
                "docker",
                "compose",
                "-f",
                "/repo/development/integration-local-stack/docker-compose.account-driver-settlement.yml",
                "down",
                "-v",
                "--remove-orphans",
            ],
        )
        self.assertEqual(steps[1].name, "compose up base stack")
        self.assertEqual(
            steps[1].argv,
            [
                "docker",
                "compose",
                "-f",
                "/repo/development/integration-local-stack/docker-compose.account-driver-settlement.yml",
                "up",
                "-d",
                "--scale",
                "telemetry-dead-letter-api=0",
                "--scale",
                "telemetry-hub-api=0",
                "--scale",
                "telemetry-listener=0",
            ],
        )

    def test_run_steps_passes_step_specific_environment(self) -> None:
        module = load_module()
        seen: list[tuple[str, list[str], dict[str, str]]] = []

        steps = (
            module.Step(name="one", argv=["echo", "1"], env={"A": "1"}),
            module.Step(name="two", argv=["echo", "2"], env={}),
        )

        def fake_runner(step: module.Step, cwd: Path) -> None:
            seen.append((step.name, step.argv, step.env))

        module.run_steps(
            steps=steps,
            cwd=Path("/repo"),
            runner=fake_runner,
        )

        self.assertEqual(
            seen,
            [
                ("one", ["echo", "1"], {"A": "1"}),
                ("two", ["echo", "2"], {}),
            ],
        )

    def test_run_command_retries_fresh_compose_down(self) -> None:
        module = load_module()
        step = module.Step(
            name="compose down fresh stack",
            argv=["docker", "compose", "-f", "/repo/development/integration-local-stack/docker-compose.account-driver-settlement.yml", "down"],
        )

        results = [
            subprocess.CompletedProcess(step.argv, 1),
            subprocess.CompletedProcess(step.argv, 0),
        ]

        with (
            mock.patch.object(module.subprocess, "run", side_effect=results) as run_mock,
            mock.patch.object(module.time, "sleep") as sleep_mock,
            mock.patch.object(
                module,
                "recover_compose_down_if_stack_is_already_stopped",
                side_effect=[False, False],
            ),
        ):
            module.run_command(step, Path("/repo"))

        self.assertEqual(run_mock.call_count, 2)
        self.assertEqual(sleep_mock.call_args_list, [mock.call(2), mock.call(2)])

    def test_run_command_recovers_compose_down_when_only_network_cleanup_races(self) -> None:
        module = load_module()
        step = module.Step(
            name="compose down fresh stack",
            argv=[
                "docker",
                "compose",
                "-f",
                "/repo/development/integration-local-stack/docker-compose.account-driver-settlement.yml",
                "down",
            ],
        )

        down_result = subprocess.CompletedProcess(step.argv, 1)
        ps_result = subprocess.CompletedProcess(
            ["docker", "compose", "-f", "/repo/development/integration-local-stack/docker-compose.account-driver-settlement.yml", "ps", "-q"],
            0,
            stdout="",
        )
        inspect_result = subprocess.CompletedProcess(
            ["docker", "network", "inspect", "integration-local-stack_default"],
            0,
            stdout='[{"Containers":{}}]',
        )

        with mock.patch.object(
            module.subprocess,
            "run",
            side_effect=[down_result, ps_result, inspect_result],
        ) as run_mock:
            module.run_command(step, Path("/repo"))

        self.assertEqual(run_mock.call_count, 3)


if __name__ == "__main__":
    unittest.main()
