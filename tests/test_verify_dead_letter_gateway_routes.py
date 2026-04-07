from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "verify_dead_letter_gateway_routes.py"
)


def load_module():
    spec = importlib.util.spec_from_file_location(
        "verify_dead_letter_gateway_routes",
        SCRIPT_PATH,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load script module from {SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class VerifyDeadLetterGatewayRoutesTests(unittest.TestCase):
    def test_run_route_checks_accepts_expected_gateway_matrix(self) -> None:
        module = load_module()
        calls: list[tuple[str, str]] = []

        def fake_fetch(url: str, method: str):
            calls.append((method, url))
            if url.endswith("/api/telemetry-dead-letters"):
                return module.FetchResult(status_code=301, location="/api/telemetry-dead-letters/")
            if url.endswith("/api/telemetry-dead-letters/health"):
                return module.FetchResult(status_code=301, location="/api/telemetry-dead-letters/health/")
            if url.endswith("/api/telemetry-dead-letters/health/"):
                return module.FetchResult(status_code=200)
            if url.endswith("/api/telemetry-dead-letters/00000000-0000-0000-0000-000000000000"):
                return module.FetchResult(
                    status_code=301,
                    location="/api/telemetry-dead-letters/00000000-0000-0000-0000-000000000000/",
                )
            if url.endswith("/api/telemetry-dead-letters/00000000-0000-0000-0000-000000000000/"):
                return module.FetchResult(status_code=401)
            if url.endswith("/api/telemetry-dead-letters/"):
                return module.FetchResult(status_code=401)
            if url.endswith("/api/telemetry-dead-letters/ingest"):
                return module.FetchResult(status_code=404)
            if url.endswith("/api/telemetry-dead-letters/ingest/"):
                return module.FetchResult(status_code=404)
            raise AssertionError(f"unexpected url: {url}")

        results = module.run_route_checks(
            base_url="http://localhost:8080",
            fetch=fake_fetch,
        )

        self.assertEqual(len(results), 8)
        self.assertEqual(calls[0], ("GET", "http://localhost:8080/api/telemetry-dead-letters"))
        self.assertEqual(calls[-1], ("POST", "http://localhost:8080/api/telemetry-dead-letters/ingest/"))

    def test_run_route_checks_rejects_exposed_ingest_route(self) -> None:
        module = load_module()

        def fake_fetch(url: str, method: str):
            if url.endswith("/api/telemetry-dead-letters/ingest"):
                return module.FetchResult(status_code=200)
            if url.endswith("/api/telemetry-dead-letters/ingest/"):
                return module.FetchResult(status_code=404)
            if url.endswith("/api/telemetry-dead-letters"):
                return module.FetchResult(status_code=301, location="/api/telemetry-dead-letters/")
            if url.endswith("/api/telemetry-dead-letters/health"):
                return module.FetchResult(status_code=301, location="/api/telemetry-dead-letters/health/")
            if url.endswith("/api/telemetry-dead-letters/health/"):
                return module.FetchResult(status_code=200)
            if url.endswith("/api/telemetry-dead-letters/00000000-0000-0000-0000-000000000000"):
                return module.FetchResult(
                    status_code=301,
                    location="/api/telemetry-dead-letters/00000000-0000-0000-0000-000000000000/",
                )
            if url.endswith("/api/telemetry-dead-letters/00000000-0000-0000-0000-000000000000/"):
                return module.FetchResult(status_code=401)
            if url.endswith("/api/telemetry-dead-letters/"):
                return module.FetchResult(status_code=401)
            raise AssertionError(f"unexpected url: {url}")

        with self.assertRaises(module.RouteVerificationError) as ctx:
            module.run_route_checks(base_url="http://localhost:8080", fetch=fake_fetch)

        self.assertIn("dead-letter ingest without trailing slash", str(ctx.exception))
        self.assertIn("expected 404", str(ctx.exception))

    def test_run_route_checks_accepts_absolute_redirect_locations(self) -> None:
        module = load_module()

        def fake_fetch(url: str, method: str):
            if url.endswith("/api/telemetry-dead-letters"):
                return module.FetchResult(
                    status_code=301,
                    location="http://localhost:8080/api/telemetry-dead-letters/",
                )
            if url.endswith("/api/telemetry-dead-letters/health"):
                return module.FetchResult(
                    status_code=301,
                    location="http://localhost:8080/api/telemetry-dead-letters/health/",
                )
            if url.endswith("/api/telemetry-dead-letters/health/"):
                return module.FetchResult(status_code=200)
            if url.endswith("/api/telemetry-dead-letters/00000000-0000-0000-0000-000000000000"):
                return module.FetchResult(
                    status_code=301,
                    location="http://localhost:8080/api/telemetry-dead-letters/00000000-0000-0000-0000-000000000000/",
                )
            if url.endswith("/api/telemetry-dead-letters/00000000-0000-0000-0000-000000000000/"):
                return module.FetchResult(status_code=401)
            if url.endswith("/api/telemetry-dead-letters/"):
                return module.FetchResult(status_code=401)
            if url.endswith("/api/telemetry-dead-letters/ingest"):
                return module.FetchResult(status_code=404)
            if url.endswith("/api/telemetry-dead-letters/ingest/"):
                return module.FetchResult(status_code=404)
            raise AssertionError(f"unexpected url: {url}")

        results = module.run_route_checks(
            base_url="http://localhost:8080",
            fetch=fake_fetch,
        )

        self.assertEqual(len(results), 8)

    def test_run_route_checks_rejects_wrong_redirect_target(self) -> None:
        module = load_module()

        def fake_fetch(url: str, method: str):
            if url.endswith("/api/telemetry-dead-letters"):
                return module.FetchResult(status_code=301, location="/wrong-target/")
            if url.endswith("/api/telemetry-dead-letters/health"):
                return module.FetchResult(status_code=301, location="/api/telemetry-dead-letters/health/")
            if url.endswith("/api/telemetry-dead-letters/health/"):
                return module.FetchResult(status_code=200)
            if url.endswith("/api/telemetry-dead-letters/00000000-0000-0000-0000-000000000000"):
                return module.FetchResult(
                    status_code=301,
                    location="/api/telemetry-dead-letters/00000000-0000-0000-0000-000000000000/",
                )
            if url.endswith("/api/telemetry-dead-letters/00000000-0000-0000-0000-000000000000/"):
                return module.FetchResult(status_code=401)
            if url.endswith("/api/telemetry-dead-letters/"):
                return module.FetchResult(status_code=401)
            if url.endswith("/api/telemetry-dead-letters/ingest"):
                return module.FetchResult(status_code=404)
            if url.endswith("/api/telemetry-dead-letters/ingest/"):
                return module.FetchResult(status_code=404)
            raise AssertionError(f"unexpected url: {url}")

        with self.assertRaises(module.RouteVerificationError) as ctx:
            module.run_route_checks(base_url="http://localhost:8080", fetch=fake_fetch)

        self.assertIn("dead-letter list no-slash redirect", str(ctx.exception))
        self.assertIn("/api/telemetry-dead-letters/", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
