from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "scripts" / "task_router.py"
SPEC = importlib.util.spec_from_file_location("task_router", PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(MODULE)


class TaskRouterTests(unittest.TestCase):
    def test_simple_change_uses_fast_path(self):
        result = MODULE.classify_task("add a getter method")
        self.assertEqual(result.mode, "FAST_PATH")

    def test_security_change_uses_full_path(self):
        result = MODULE.classify_task("add authorization permission checks")
        self.assertEqual(result.mode, "FULL_PATH")

    def test_multi_file_change_uses_full_path(self):
        result = MODULE.classify_task("implement a feature", ["a.py", "b.py", "c.py", "d.py"])
        self.assertEqual(result.mode, "FULL_PATH")

    def test_unknown_defaults_to_full_path(self):
        result = MODULE.classify_task("change something")
        self.assertEqual(result.mode, "FULL_PATH")


if __name__ == "__main__":
    unittest.main()
