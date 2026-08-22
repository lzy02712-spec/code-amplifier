#!/usr/bin/env python3
"""Detect repository project types and credible verification commands.

The script is intentionally conservative: repository-declared commands and
committed wrappers are preferred over guesses. Output is JSON for agent use.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any

try:
    import tomllib
except ImportError:  # pragma: no cover
    tomllib = None

CATEGORIES = ("compile", "test", "lint", "typecheck")


def _cmd(*parts: str) -> list[str]:
    return list(parts)


def _add(commands: dict[str, list[list[str]]], category: str, command: list[str]) -> None:
    if command and command not in commands[category]:
        commands[category].append(command)


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _pyproject_text(root: Path) -> str:
    path = root / "pyproject.toml"
    try:
        return path.read_text(encoding="utf-8").lower()
    except OSError:
        return ""


def _normalize_config_command(value: Any) -> list[list[str]] | None:
    """Return None for explicit null, else normalized list of argv arrays."""
    if value is None:
        return None
    if isinstance(value, list) and all(isinstance(x, str) for x in value):
        return [value]
    if (
        isinstance(value, list)
        and all(isinstance(item, list) for item in value)
        and all(all(isinstance(x, str) for x in item) for item in value)
    ):
        return value
    raise ValueError("command must be null, an argv array, or a list of argv arrays")


def detect(root: Path) -> dict[str, Any]:
    root = root.resolve()
    commands: dict[str, list[list[str]]] = {k: [] for k in CATEGORIES}
    project_types: list[str] = []
    markers: list[str] = []
    notes: list[str] = []

    def mark(project_type: str, *files: str) -> None:
        if project_type not in project_types:
            project_types.append(project_type)
        for file in files:
            if file not in markers:
                markers.append(file)

    if (root / "pom.xml").exists():
        mark("maven", "pom.xml")
        mvn = "./mvnw" if (root / "mvnw").exists() else "mvn"
        _add(commands, "compile", _cmd(mvn, "-q", "-DskipTests", "compile"))
        _add(commands, "test", _cmd(mvn, "-q", "test"))

    gradle_marker = None
    for name in ("build.gradle.kts", "build.gradle"):
        if (root / name).exists():
            gradle_marker = name
            break
    if gradle_marker:
        mark("gradle", gradle_marker)
        gradle = "./gradlew" if (root / "gradlew").exists() else "gradle"
        _add(commands, "compile", _cmd(gradle, "classes"))
        _add(commands, "test", _cmd(gradle, "test"))

    package_json = root / "package.json"
    if package_json.exists():
        mark("node", "package.json")
        package = _load_json(package_json) or {}
        scripts = package.get("scripts", {}) if isinstance(package, dict) else {}
        if isinstance(scripts, dict):
            mapping = {
                "test": "test",
                "lint": "lint",
                "typecheck": "typecheck",
                "compile": "build",
            }
            for category, script_name in mapping.items():
                script_value = scripts.get(script_name)
                if isinstance(script_value, str) and script_value.strip():
                    if script_name == "test" and "no test specified" in script_value.lower():
                        notes.append("Ignored package.json placeholder test script")
                        continue
                    _add(commands, category, _cmd("npm", "run", script_name))

    python_markers = [name for name in ("pyproject.toml", "setup.cfg", "pytest.ini", "tox.ini") if (root / name).exists()]
    has_python_files = any(root.glob("*.py")) or any((root / d).exists() for d in ("src", "tests"))
    if python_markers or has_python_files:
        mark("python", *python_markers)
        _add(commands, "compile", _cmd(sys.executable, "-m", "compileall", "-q", "."))
        pytext = _pyproject_text(root)
        if (root / "pytest.ini").exists() or (root / "tests").exists() or "pytest" in pytext:
            _add(commands, "test", _cmd(sys.executable, "-m", "pytest", "-q"))
        if "ruff" in pytext or (root / "ruff.toml").exists() or (root / ".ruff.toml").exists():
            _add(commands, "lint", _cmd(sys.executable, "-m", "ruff", "check", "."))
        if "mypy" in pytext or (root / "mypy.ini").exists() or (root / ".mypy.ini").exists():
            _add(commands, "typecheck", _cmd(sys.executable, "-m", "mypy", "."))

    if (root / "go.mod").exists():
        mark("go", "go.mod")
        _add(commands, "test", _cmd("go", "test", "./..."))

    if (root / "Cargo.toml").exists():
        mark("rust", "Cargo.toml")
        _add(commands, "compile", _cmd("cargo", "check"))
        _add(commands, "test", _cmd("cargo", "test"))
        _add(commands, "lint", _cmd("cargo", "clippy", "--", "-D", "warnings"))

    config_path = root / ".coding-amplifier.json"
    explicit: dict[str, Any] = {}
    if config_path.exists():
        mark("coding-amplifier-config", ".coding-amplifier.json")
        cfg = _load_json(config_path)
        if not isinstance(cfg, dict):
            notes.append("Invalid .coding-amplifier.json; ignored")
        else:
            cfg_commands = cfg.get("commands", {})
            if isinstance(cfg_commands, dict):
                for category in CATEGORIES:
                    if category in cfg_commands:
                        try:
                            normalized = _normalize_config_command(cfg_commands[category])
                        except ValueError as exc:
                            notes.append(f"Invalid configured {category} command: {exc}")
                            continue
                        explicit[category] = cfg_commands[category]
                        commands[category] = [] if normalized is None else normalized

    availability: dict[str, bool] = {}
    for category_commands in commands.values():
        for command in category_commands:
            exe = command[0]
            if exe.startswith("./"):
                availability[exe] = (root / exe[2:]).exists()
            elif os.path.isabs(exe):
                availability[exe] = Path(exe).exists()
            else:
                availability[exe] = shutil.which(exe) is not None

    return {
        "root": str(root),
        "project_types": project_types,
        "markers": markers,
        "commands": commands,
        "explicit_overrides": explicit,
        "executable_availability": availability,
        "notes": notes,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--output")
    args = parser.parse_args()

    result = detect(Path(args.root))
    text = json.dumps(result, indent=2, ensure_ascii=False)
    if args.output:
        Path(args.output).write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
