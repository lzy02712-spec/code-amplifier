from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(name: str):
    path = ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


detect_project = load("detect_project")
evidence = load("evidence")


class DetectionTests(unittest.TestCase):
    def test_node_uses_only_declared_scripts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "package.json").write_text(
                json.dumps({"scripts": {"test": "vitest run", "lint": "eslint ."}}),
                encoding="utf-8",
            )
            result = detect_project.detect(root)
            self.assertIn("node", result["project_types"])
            self.assertEqual(result["commands"]["test"], [["npm", "run", "test"]])
            self.assertEqual(result["commands"]["lint"], [["npm", "run", "lint"]])
            self.assertEqual(result["commands"]["typecheck"], [])

    def test_explicit_config_overrides_discovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "package.json").write_text(
                json.dumps({"scripts": {"test": "vitest run"}}), encoding="utf-8"
            )
            (root / ".coding-amplifier.json").write_text(
                json.dumps({"commands": {"test": ["npm", "run", "test:unit"], "lint": None}}),
                encoding="utf-8",
            )
            result = detect_project.detect(root)
            self.assertEqual(result["commands"]["test"], [["npm", "run", "test:unit"]])
            self.assertEqual(result["commands"]["lint"], [])

    def test_python_detection_has_compile(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
            result = detect_project.detect(root)
            self.assertIn("python", result["project_types"])
            self.assertTrue(result["commands"]["compile"])


class EvidenceTests(unittest.TestCase):
    def test_verified_requires_clean_inputs(self):
        result = evidence.aggregate(
            {"overall_status": "PASS"},
            {"status": "PASS", "suspicious_paths": []},
            {"requirements": [{"id": "R1", "criterion": "x", "status": "PASS", "evidence": "test_x"}]},
        )
        self.assertEqual(result["status"], "VERIFIED")

    def test_unknown_requirement_is_partial(self):
        result = evidence.aggregate(
            {"overall_status": "PASS"},
            {"status": "PASS", "suspicious_paths": []},
            {"requirements": [{"id": "R1", "criterion": "x", "status": "UNKNOWN", "evidence": ""}]},
        )
        self.assertEqual(result["status"], "PARTIALLY_VERIFIED")

    def test_failed_check_is_not_verified(self):
        result = evidence.aggregate(
            {"overall_status": "FAIL"},
            {"status": "PASS", "suspicious_paths": []},
            {"requirements": [{"id": "R1", "criterion": "x", "status": "PASS", "evidence": "test_x"}]},
        )
        self.assertEqual(result["status"], "NOT_VERIFIED")


if __name__ == "__main__":
    unittest.main()
