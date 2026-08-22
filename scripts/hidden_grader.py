#!/usr/bin/env python3
"""Validate and run hidden future-test graders for Git-history evals.

The agent never sees oracle metadata or future tests. A history eval is considered
strictly gradable only when future tests fail on the base revision and pass on
the recorded target revision. Agent work is then graded by overlaying only those
validated hidden test files onto the ephemeral agent workspace and running the
repository's test command.
"""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import verify as hard_verify


def _git(root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    cp = subprocess.run(
        ["git", "-C", str(root), *args],
        text=True,
        capture_output=True,
        check=False,
    )
    if check and cp.returncode != 0:
        raise RuntimeError(cp.stderr.strip() or f"git {' '.join(args)} failed")
    return cp


def hidden_test_files(task: dict[str, Any]) -> list[str]:
    oracle = task.get("oracle", {}) if isinstance(task, dict) else {}
    grader = oracle.get("grader", {}) if isinstance(oracle, dict) else {}
    files = grader.get("hidden_test_files") or oracle.get("hidden_test_files") or []
    return [str(p) for p in files if isinstance(p, str) and p.strip()]


def _read_blob(repo: Path, ref: str, path: str) -> bytes:
    cp = subprocess.run(
        ["git", "-C", str(repo), "show", f"{ref}:{path}"],
        capture_output=True,
        check=False,
    )
    if cp.returncode != 0:
        raise RuntimeError(cp.stderr.decode("utf-8", errors="replace").strip() or f"missing {ref}:{path}")
    return cp.stdout


def overlay_hidden_tests(repo: Path, workspace: Path, target_ref: str, files: list[str]) -> list[str]:
    written: list[str] = []
    for rel in files:
        data = _read_blob(repo, target_ref, rel)
        dst = workspace / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists() and dst.is_dir():
            shutil.rmtree(dst)
        dst.write_bytes(data)
        written.append(rel)
    return written


def _test_status(workspace: Path, timeout: int) -> dict[str, Any]:
    verification = hard_verify.verify(workspace, timeout, {"test"})
    status = verification.get("overall_status", "UNKNOWN")
    return {"status": status, "verification": verification}


def _worktree(repo: Path, ref: str, prefix: str) -> tuple[tempfile.TemporaryDirectory[str], Path]:
    holder = tempfile.TemporaryDirectory(prefix=prefix)
    workspace = Path(holder.name) / "workspace"
    _git(repo, "worktree", "add", "--detach", str(workspace), ref)
    return holder, workspace


def _remove_worktree(repo: Path, holder: tempfile.TemporaryDirectory[str], workspace: Path) -> None:
    _git(repo, "worktree", "remove", "--force", str(workspace), check=False)
    _git(repo, "worktree", "prune", check=False)
    holder.cleanup()


def validate_oracle(repo: Path, task: dict[str, Any], timeout: int = 300) -> dict[str, Any]:
    """Prove that hidden future tests distinguish the base from the target.

    VALID means: future tests FAIL on base and PASS on target. Anything else is
    not eligible for strict benchmark success-rate statistics.
    """
    repo = repo.resolve()
    oracle = task.get("oracle", {}) if isinstance(task, dict) else {}
    base_ref = task.get("base_ref")
    target_ref = oracle.get("target_ref") if isinstance(oracle, dict) else None
    files = hidden_test_files(task)

    if not base_ref or not target_ref or not files:
        return {
            "status": "NOT_AVAILABLE",
            "valid": False,
            "hidden_test_files": files,
            "reason": "missing base_ref, target_ref, or hidden future tests",
        }

    base_holder = target_holder = None
    base_ws = target_ws = None
    try:
        base_holder, base_ws = _worktree(repo, str(base_ref), "codeamp-oracle-base-")
        overlay_hidden_tests(repo, base_ws, str(target_ref), files)
        base_result = _test_status(base_ws, timeout)

        target_holder, target_ws = _worktree(repo, str(target_ref), "codeamp-oracle-target-")
        target_result = _test_status(target_ws, timeout)
    except Exception as exc:
        return {
            "status": "UNKNOWN",
            "valid": False,
            "hidden_test_files": files,
            "reason": str(exc),
        }
    finally:
        if base_holder is not None and base_ws is not None:
            _remove_worktree(repo, base_holder, base_ws)
        if target_holder is not None and target_ws is not None:
            _remove_worktree(repo, target_holder, target_ws)

    base_status = base_result["status"]
    target_status = target_result["status"]
    valid = base_status == "FAIL" and target_status == "PASS"
    if valid:
        status = "VALID"
        reason = "future tests fail on base and pass on target"
    elif base_status in {"UNKNOWN", "NOT_CONFIGURED"} or target_status in {"UNKNOWN", "NOT_CONFIGURED"}:
        status = "UNKNOWN"
        reason = f"test command unavailable or inconclusive: base={base_status}, target={target_status}"
    else:
        status = "INVALID"
        reason = f"hidden tests are not discriminative: base={base_status}, target={target_status}"

    return {
        "status": status,
        "valid": valid,
        "reason": reason,
        "hidden_test_files": files,
        "base_status": base_status,
        "target_status": target_status,
        "base_verification": base_result["verification"],
        "target_verification": target_result["verification"],
    }


def grade_workspace(
    repo: Path,
    workspace: Path,
    task: dict[str, Any],
    oracle_validation: dict[str, Any],
    timeout: int = 300,
) -> dict[str, Any]:
    """Overlay validated hidden tests onto an ephemeral agent workspace."""
    if oracle_validation.get("status") != "VALID":
        return {
            "status": "NOT_RUN",
            "passed": False,
            "reason": "oracle validation is not VALID",
            "hidden_test_files": hidden_test_files(task),
        }

    oracle = task.get("oracle", {})
    target_ref = str(oracle.get("target_ref"))
    files = hidden_test_files(task)
    try:
        written = overlay_hidden_tests(repo.resolve(), workspace.resolve(), target_ref, files)
        result = _test_status(workspace, timeout)
    except Exception as exc:
        return {
            "status": "UNKNOWN",
            "passed": False,
            "reason": str(exc),
            "hidden_test_files": files,
        }

    return {
        "status": result["status"],
        "passed": result["status"] == "PASS",
        "hidden_test_files": written,
        "verification": result["verification"],
    }
