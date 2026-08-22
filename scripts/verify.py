#!/usr/bin/env python3
"""Run conservative, discovered verification commands and emit evidence JSON."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from detect_project import CATEGORIES, detect

TAIL_LIMIT = 20000


def _run(command: list[str], root: Path, timeout: int) -> dict[str, Any]:
    start = time.monotonic()
    try:
        proc = subprocess.run(
            command,
            cwd=root,
            capture_output=True,
            text=True,
            timeout=timeout,
            env={**os.environ, "CI": os.environ.get("CI", "1")},
            check=False,
        )
        duration = round(time.monotonic() - start, 3)
        return {
            "command": command,
            "status": "PASS" if proc.returncode == 0 else "FAIL",
            "exit_code": proc.returncode,
            "duration_seconds": duration,
            "stdout_tail": proc.stdout[-TAIL_LIMIT:],
            "stderr_tail": proc.stderr[-TAIL_LIMIT:],
        }
    except FileNotFoundError as exc:
        return {
            "command": command,
            "status": "UNKNOWN",
            "exit_code": None,
            "duration_seconds": round(time.monotonic() - start, 3),
            "stdout_tail": "",
            "stderr_tail": f"Executable unavailable: {exc}",
        }
    except PermissionError as exc:
        return {
            "command": command,
            "status": "UNKNOWN",
            "exit_code": None,
            "duration_seconds": round(time.monotonic() - start, 3),
            "stdout_tail": "",
            "stderr_tail": f"Executable not runnable: {exc}",
        }
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        return {
            "command": command,
            "status": "UNKNOWN",
            "exit_code": None,
            "duration_seconds": round(time.monotonic() - start, 3),
            "stdout_tail": stdout[-TAIL_LIMIT:],
            "stderr_tail": (stderr + f"\nTimed out after {timeout}s")[-TAIL_LIMIT:],
        }


def _category_status(runs: list[dict[str, Any]]) -> str:
    if not runs:
        return "NOT_CONFIGURED"
    statuses = {run["status"] for run in runs}
    if "FAIL" in statuses:
        return "FAIL"
    if "UNKNOWN" in statuses:
        return "UNKNOWN"
    return "PASS"


def verify(root: Path, timeout: int, selected: set[str] | None = None) -> dict[str, Any]:
    discovery = detect(root)
    results: dict[str, Any] = {}

    for category in CATEGORIES:
        if selected and category not in selected:
            results[category] = {"status": "NOT_RUN", "runs": []}
            continue
        runs = [_run(cmd, root, timeout) for cmd in discovery["commands"].get(category, [])]
        results[category] = {"status": _category_status(runs), "runs": runs}

    material_statuses = [data["status"] for data in results.values() if data["status"] != "NOT_RUN"]
    if "FAIL" in material_statuses:
        overall = "FAIL"
    elif "UNKNOWN" in material_statuses:
        overall = "UNKNOWN"
    elif any(status == "PASS" for status in material_statuses):
        overall = "PASS"
    else:
        overall = "NOT_CONFIGURED"

    return {
        "schema_version": 1,
        "root": str(root.resolve()),
        "overall_status": overall,
        "discovery": discovery,
        "checks": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--output")
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument(
        "--checks",
        help="Comma-separated subset: compile,test,lint,typecheck",
    )
    args = parser.parse_args()

    selected = None
    if args.checks:
        selected = {x.strip() for x in args.checks.split(",") if x.strip()}
        invalid = selected.difference(CATEGORIES)
        if invalid:
            parser.error(f"unknown checks: {', '.join(sorted(invalid))}")

    result = verify(Path(args.root), args.timeout, selected)
    text = json.dumps(result, indent=2, ensure_ascii=False)
    if args.output:
        Path(args.output).write_text(text + "\n", encoding="utf-8")
    else:
        print(text)

    return 1 if result["overall_status"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
