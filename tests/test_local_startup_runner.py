from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "run_local_startup.py"
)


def load_module():
    spec = importlib.util.spec_from_file_location(
        "run_local_startup",
        SCRIPT_PATH,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load script module from {SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class LocalStartupRunnerTests(unittest.TestCase):
    def test_default_root_dir_points_to_platform_root(self) -> None:
        module = load_module()

        root_dir = module.default_root_dir()

        self.assertEqual(root_dir.name, "clever-msa-platform")
        self.assertTrue((root_dir / "development" / "integration-local-stack").exists())

    def test_build_steps_returns_stage_order_with_health_seed_and_smoke(self) -> None:
        module = load_module()

        with tempfile.TemporaryDirectory() as temp_dir:
            manifest_path = Path(temp_dir) / "local-startup-manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "stages": [
                            {
                                "name": "infra",
                                "services": ["redis", "account-db"],
                                "health_checks": [
                                    {
                                        "name": "account-db",
                                        "kind": "service_exec",
                                        "service": "account-db",
                                        "argv": ["pg_isready", "-U", "account_auth", "-d", "account_auth"]
                                    }
                                ]
                            },
                            {
                                "name": "core-auth",
                                "services": ["account-auth-api", "organization-master-api"],
                                "health_checks": [
                                    {
                                        "name": "account-auth",
                                        "kind": "service_http",
                                        "service": "account-auth-api",
                                        "url": "http://127.0.0.1:8000/health/",
                                    },
                                    {
                                        "name": "organization-master",
                                        "kind": "service_http",
                                        "service": "organization-master-api",
                                        "url": "http://127.0.0.1:8000/health/",
                                    },
                                ],
                            },
                            {
                                "name": "edge",
                                "services": ["web-console", "gateway"],
                                "health_checks": [
                                    {
                                        "name": "gateway",
                                        "kind": "host_http",
                                        "url": "http://127.0.0.1:8080/healthz",
                                    }
                                ],
                            },
                            {
                                "name": "seed",
                                "seed_runner": "seed-runner",
                            },
                            {
                                "name": "smoke",
                                "commands": [
                                    {
                                        "name": "gateway health",
                                        "argv": ["curl", "-fsS", "http://127.0.0.1:8080/healthz"],
                                    }
                                ],
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )

            steps = module.build_steps(
                root_dir=Path("/repo"),
                compose_path=Path("/repo/development/integration-local-stack/docker-compose.account-driver-settlement.yml"),
                manifest_path=manifest_path,
                rebuild_images=True,
                fresh_start=True,
            )

        self.assertEqual([step.name for step in steps], [
            "compose down fresh stack",
            "compose build local stack images",
            "compose up infra",
            "wait for infra health",
            "compose up core-auth",
            "wait for core-auth health",
            "compose up edge",
            "wait for edge health",
            "run seed stage",
            "smoke: gateway health",
        ])
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
        self.assertEqual(
            steps[1].argv,
            [
                "docker",
                "compose",
                "-f",
                "/repo/development/integration-local-stack/docker-compose.account-driver-settlement.yml",
                "build",
            ],
        )
        self.assertEqual(
            steps[2].argv,
            [
                "docker",
                "compose",
                "-f",
                "/repo/development/integration-local-stack/docker-compose.account-driver-settlement.yml",
                "up",
                "-d",
                "redis",
                "account-db",
            ],
        )
        self.assertEqual(
            steps[3].argv[:2],
            [sys.executable, str(SCRIPT_PATH)],
        )
        self.assertEqual(
            steps[3].argv[2:],
            [
                "wait-stage",
                "--compose-file",
                "/repo/development/integration-local-stack/docker-compose.account-driver-settlement.yml",
                "--manifest",
                str(manifest_path),
                "--stage",
                "infra",
            ],
        )
        self.assertEqual(
            steps[5].argv[2:],
            [
                "wait-stage",
                "--compose-file",
                "/repo/development/integration-local-stack/docker-compose.account-driver-settlement.yml",
                "--manifest",
                str(manifest_path),
                "--stage",
                "core-auth",
            ],
        )
        self.assertEqual(
            steps[8].argv,
            [
                "docker",
                "compose",
                "-f",
                "/repo/development/integration-local-stack/docker-compose.account-driver-settlement.yml",
                "run",
                "--rm",
                "seed-runner",
            ],
        )
        self.assertEqual(
            steps[9].argv,
            ["curl", "-fsS", "http://127.0.0.1:8080/healthz"],
        )

    def test_default_manifest_contains_expected_terminal_stages(self) -> None:
        module = load_module()

        manifest = module.load_manifest(module.default_manifest_path())

        self.assertEqual(
            [stage["name"] for stage in manifest["stages"][-3:]],
            ["edge", "seed", "smoke"],
        )
        self.assertEqual(manifest["stages"][-2]["seed_runner"], "seed-runner")
        self.assertTrue(manifest["stages"][-1]["commands"])

    def test_run_steps_executes_all_steps_in_order(self) -> None:
        module = load_module()
        seen: list[tuple[str, list[str], Path]] = []

        steps = (
            module.Step(name="one", argv=["echo", "1"]),
            module.Step(name="two", argv=["echo", "2"]),
        )

        def fake_runner(step: module.Step, cwd: Path) -> None:
            seen.append((step.name, step.argv, cwd))

        module.run_steps(
            steps=steps,
            cwd=Path("/repo"),
            runner=fake_runner,
        )

        self.assertEqual(
            seen,
            [
                ("one", ["echo", "1"], Path("/repo")),
                ("two", ["echo", "2"], Path("/repo")),
            ],
        )

    def test_resolve_docker_command_falls_back_to_docker_desktop_binary(self) -> None:
        module = load_module()

        with mock.patch.object(module.shutil, "which", return_value=None):
            command = module.resolve_docker_command()

        self.assertEqual(
            command,
            "/Applications/Docker.app/Contents/Resources/bin/docker",
        )

    def test_wait_for_stage_health_supports_service_exec_checks(self) -> None:
        module = load_module()

        with tempfile.TemporaryDirectory() as temp_dir:
            manifest_path = Path(temp_dir) / "local-startup-manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "stages": [
                            {
                                "name": "infra",
                                "health_checks": [
                                    {
                                        "name": "account-db",
                                        "kind": "service_exec",
                                        "service": "account-db",
                                        "argv": ["pg_isready", "-U", "account_auth", "-d", "account_auth"]
                                    }
                                ]
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            with mock.patch.object(
                module.subprocess,
                "run",
                return_value=module.subprocess.CompletedProcess(["docker"], 0),
            ) as run_mock:
                module.wait_for_stage_health(
                    manifest_path=manifest_path,
                    compose_path=Path("/repo/development/integration-local-stack/docker-compose.account-driver-settlement.yml"),
                    stage_name="infra",
                    cwd=Path("/repo"),
                    attempts=1,
                    interval_seconds=0,
                )

        self.assertEqual(run_mock.call_count, 1)

    def test_check_host_http_treats_connection_reset_as_retryable_failure(self) -> None:
        module = load_module()

        with mock.patch.object(module, "urlopen", side_effect=ConnectionResetError(54, "reset")):
            ok = module._check_host_http("http://127.0.0.1:8080/healthz")

        self.assertFalse(ok)

    def test_runtime_env_includes_docker_desktop_bin_when_using_fallback_docker(self) -> None:
        module = load_module()

        with mock.patch.object(module, "resolve_docker_command", return_value="/Applications/Docker.app/Contents/Resources/bin/docker"):
            env = module.runtime_env({})

        self.assertIn("/Applications/Docker.app/Contents/Resources/bin", env["PATH"])


if __name__ == "__main__":
    unittest.main()
