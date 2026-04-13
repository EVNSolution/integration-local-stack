from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import types
import unittest


BUILD_SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "build_unified_openapi.py"
)


def load_module(script_name: str, script_path: Path):
    spec = importlib.util.spec_from_file_location(script_name, script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load script module from {script_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    sys.modules.setdefault("yaml", types.ModuleType("yaml"))
    spec.loader.exec_module(module)
    return module


class ApiDocsScriptTests(unittest.TestCase):
    def test_schema_enabled_services_include_attendance_registry(self) -> None:
        module = load_module("build_unified_openapi", BUILD_SCRIPT_PATH)

        self.assertIn("service-attendance-registry", module.SCHEMA_ENABLED_SERVICES)


if __name__ == "__main__":
    unittest.main()
