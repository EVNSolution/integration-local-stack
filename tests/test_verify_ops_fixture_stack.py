from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "verify_ops_fixture_stack.py"
)


def load_module():
    spec = importlib.util.spec_from_file_location(
        "verify_ops_fixture_stack",
        SCRIPT_PATH,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load script module from {SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class VerifyOpsFixtureStackTests(unittest.TestCase):
    def test_default_root_dir_points_to_platform_root(self) -> None:
        module = load_module()

        root_dir = module.default_root_dir()

        self.assertEqual(root_dir.name, "clever-msa-platform")
        self.assertTrue((root_dir / "development" / "integration-local-stack").exists())

    def test_build_steps_returns_expected_smoke_sequence(self) -> None:
        module = load_module()

        steps = module.build_steps(
            root_dir=Path("/repo"),
            compose_path=Path("/repo/development/integration-local-stack/docker-compose.account-driver-settlement.yml"),
            playwright_spec="e2e/ops-fixture-console.spec.ts",
            rebuild_images=True,
        )

        self.assertEqual([step.name for step in steps], [
            "playwright image build",
            "refresh web console runtime",
            "core gateway smoke",
            "authenticated runtime smoke",
            "playwright web smoke",
        ])
        self.assertEqual(steps[0].argv[:4], [
            "docker",
            "compose",
            "-f",
            "/repo/development/integration-local-stack/docker-compose.account-driver-settlement.yml",
        ])
        self.assertEqual(
            steps[0].argv[4:],
            ["build", "web-console", "web-console-e2e"],
        )
        self.assertEqual(
            steps[1].argv[4:],
            ["up", "-d", "--force-recreate", "--no-deps", "web-console"],
        )
        self.assertEqual(steps[2].argv[0], sys.executable)
        self.assertIn("verify_core_gateway_routes.py", str(steps[2].argv[1]))
        self.assertEqual(steps[3].argv[0], sys.executable)
        self.assertIn("verify_ops_fixture_runtime.py", str(steps[3].argv[1]))
        self.assertEqual(
            steps[4].argv[-3:],
            ["sh", "-lc", "npx playwright test e2e/ops-fixture-console.spec.ts"],
        )

    def test_build_steps_can_skip_image_build(self) -> None:
        module = load_module()

        steps = module.build_steps(
            root_dir=Path("/repo"),
            compose_path=Path("/repo/development/integration-local-stack/docker-compose.account-driver-settlement.yml"),
            playwright_spec="e2e/ops-fixture-console.spec.ts",
            rebuild_images=False,
        )

        self.assertEqual([step.name for step in steps], [
            "refresh web console runtime",
            "core gateway smoke",
            "authenticated runtime smoke",
            "playwright web smoke",
        ])

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

    def test_run_steps_stops_on_failure(self) -> None:
        module = load_module()
        seen: list[str] = []

        steps = (
            module.Step(name="one", argv=["echo", "1"]),
            module.Step(name="two", argv=["echo", "2"]),
            module.Step(name="three", argv=["echo", "3"]),
        )

        def fake_runner(step: module.Step, cwd: Path) -> None:
            seen.append(step.name)
            if step.name == "two":
                raise RuntimeError("boom")

        with self.assertRaises(RuntimeError):
            module.run_steps(
                steps=steps,
                cwd=Path("/repo"),
                runner=fake_runner,
            )

        self.assertEqual(seen, ["one", "two"])


if __name__ == "__main__":
    unittest.main()
