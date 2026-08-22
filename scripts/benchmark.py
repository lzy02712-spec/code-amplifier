#!/usr/bin/env python3
"""Run paired Direct vs CodeAmplifier coding-agent benchmarks.

The same agent command is run in two isolated Git worktrees. Amplified mode
installs this Agent Skill into `.agents/skills/coding-amplifier`; direct mode
does not. Hidden oracle metadata and future tests are never passed to the agent.

V2.1 strict grading only counts tasks whose future tests are independently
validated to FAIL on the base revision and PASS on the recorded target commit.
"""
from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_ROOT = SCRIPT_DIR.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import hidden_grader  # noqa: E402
import report as report_mod  # noqa: E402
import soft_verifier  # noqa: E402
import verify as hard_verify  # noqa: E402

SKILL_RUNTIME_FILES = [
    "SKILL.md",
    "references",
    "scripts/detect_project.py",
    "scripts/verify.py",
    "scripts/inspect_diff.py",
    "scripts/evidence.py",
    "scripts/soft_verifier.py",
    "scripts/progress.py",
]


def _git(root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    cp = subprocess.run(["git", "-C", str(root), *args], text=True, capture_output=True, check=False)
    if check and cp.returncode != 0:
        raise RuntimeError(cp.stderr.strip() or f"git {' '.join(args)} failed")
    return cp


def _install_skill(workspace: Path) -> Path:
    dst = workspace / ".agents" / "skills" / "coding-amplifier"
    dst.mkdir(parents=True, exist_ok=True)
    for rel in SKILL_RUNTIME_FILES:
        src = SKILL_ROOT / rel
        target = dst / rel
        if src.is_dir():
            shutil.copytree(src, target, dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, target)
    return dst


def _render_command(template: list[str], workspace: Path, prompt: str, task_file: Path, mode: str) -> list[str]:
    mapping = {
        "workspace": str(workspace),
        "prompt": prompt,
        "task_file": str(task_file),
        "mode": mode,
    }
    return [part.format(**mapping) for part in template]


def _run_agent(template: list[str], workspace: Path, prompt: str, mode: str, timeout: int) -> dict[str, Any]:
    task_file = workspace.parent / f"task-{mode}.txt"
    task_file.write_text(prompt + "\n", encoding="utf-8")
    env = os.environ.copy()
    env.update({
        "CODE_AMPLIFIER_MODE": mode,
        "CODE_AMPLIFIER_TASK_FILE": str(task_file),
        "CODE_AMPLIFIER_WORKSPACE": str(workspace),
    })
    if mode == "amplified":
        skill_dir = _install_skill(workspace)
        env["CODE_AMPLIFIER_SKILL_DIR"] = str(skill_dir)
    cmd = _render_command(template, workspace, prompt, task_file, mode)
    start = time.monotonic()
    try:
        cp = subprocess.run(cmd, cwd=workspace, env=env, text=True, capture_output=True, timeout=timeout, check=False)
        return {
            "command": cmd,
            "exit_code": cp.returncode,
            "elapsed_seconds": round(time.monotonic() - start, 3),
            "stdout": cp.stdout[-100000:],
            "stderr": cp.stderr[-50000:],
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "command": cmd,
            "exit_code": None,
            "elapsed_seconds": round(time.monotonic() - start, 3),
            "stdout": (exc.stdout or "")[-100000:] if isinstance(exc.stdout, str) else "",
            "stderr": ((exc.stderr or "") + f"\nTimed out after {timeout}s")[-50000:] if isinstance(exc.stderr, str) else f"Timed out after {timeout}s",
        }


def _changed_files(workspace: Path, base_ref: str) -> list[str]:
    tracked = _git(workspace, "diff", "--name-only", base_ref, check=False).stdout.splitlines()
    untracked = _git(workspace, "ls-files", "--others", "--exclude-standard", check=False).stdout.splitlines()
    files = sorted({p for p in tracked + untracked if p and not p.startswith(".agents/skills/coding-amplifier/")})
    return files


def _file_overlap(actual: list[str], expected: list[str]) -> float:
    a, e = set(actual), set(expected)
    if not e:
        return 1.0 if not a else 0.0
    return round(len(a & e) / len(e), 4)


def _run_one(
    repo: Path,
    task: dict[str, Any],
    mode: str,
    command: list[str],
    timeout: int,
    verify_timeout: int,
    soft_backend: str,
    soft_threshold: float,
    oracle_validation: dict[str, Any],
) -> dict[str, Any]:
    base_ref = task["base_ref"]
    with tempfile.TemporaryDirectory(prefix=f"codeamp-{mode}-") as tmp:
        workspace = Path(tmp) / "workspace"
        _git(repo, "worktree", "add", "--detach", str(workspace), base_ref)
        try:
            agent = _run_agent(command, workspace, task["prompt"], mode, timeout)
            hard = hard_verify.verify(workspace, verify_timeout)
            trajectory = (agent.get("stdout", "") + "\n" + agent.get("stderr", "")).strip()
            soft = soft_verifier.verify_soft(task["prompt"], trajectory, hard, task.get("criteria"), backend=soft_backend)

            # Capture the agent's own diff before hidden tests are overlaid.
            changed = _changed_files(workspace, base_ref)
            expected = task.get("oracle", {}).get("changed_files", [])
            overlap = _file_overlap(changed, expected)

            hidden = hidden_grader.grade_workspace(repo, workspace, task, oracle_validation, verify_timeout)
            gradable = oracle_validation.get("status") == "VALID"
            provisional_success = (
                hard.get("overall_status") == "PASS"
                and float(soft.get("score", 0.0)) >= soft_threshold
                and bool(changed)
            )
            strict_success = (
                hard.get("overall_status") == "PASS"
                and hidden.get("status") == "PASS"
                and bool(changed)
            ) if gradable else None

            return {
                "task_id": task.get("id"),
                "mode": mode,
                "gradable": gradable,
                "success": strict_success,
                "provisional_success": provisional_success,
                "agent_exit_code": agent.get("exit_code"),
                "elapsed_seconds": agent.get("elapsed_seconds", 0.0),
                "hard_status": hard.get("overall_status"),
                "hidden_status": hidden.get("status"),
                "soft_score": soft.get("score", 0.0),
                "soft_backend": soft.get("backend"),
                "changed_files": changed,
                "oracle_file_overlap": overlap,
                "oracle_validation": oracle_validation,
                "hidden_grader": hidden,
                "verification": hard,
                "soft_verification": soft,
                "trajectory_tail": trajectory[-20000:],
            }
        finally:
            _git(repo, "worktree", "remove", "--force", str(workspace), check=False)
            _git(repo, "worktree", "prune", check=False)


def run_benchmark(
    repo: Path,
    evals: list[dict[str, Any]],
    command: list[str],
    timeout: int = 1800,
    verify_timeout: int = 300,
    soft_backend: str = "heuristic",
    soft_threshold: float = 0.72,
    modes: tuple[str, ...] = ("direct", "amplified"),
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    oracle_validations: dict[str, dict[str, Any]] = {}
    for task in evals:
        task_id = str(task.get("id"))
        validation = hidden_grader.validate_oracle(repo, task, verify_timeout)
        oracle_validations[task_id] = validation
        for mode in modes:
            rows.append(_run_one(
                repo,
                task,
                mode,
                command,
                timeout,
                verify_timeout,
                soft_backend,
                soft_threshold,
                validation,
            ))
    return {
        "schema_version": 3,
        "repository": str(repo.resolve()),
        "oracle_validations": oracle_validations,
        "runs": rows,
        "summary": report_mod.summarize(rows),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Paired Direct vs CodeAmplifier benchmark")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--evals", required=True)
    parser.add_argument("--agent-command", required=True, help="Shell-like argv template; supports {prompt}, {task_file}, {workspace}, {mode}")
    parser.add_argument("--timeout", type=int, default=1800)
    parser.add_argument("--verify-timeout", type=int, default=300)
    parser.add_argument("--soft-backend", choices=("heuristic", "llm-verifier", "openai-json"), default="heuristic")
    parser.add_argument("--soft-threshold", type=float, default=0.72, help="Diagnostic/provisional threshold only; strict success is determined by validated hidden tests")
    parser.add_argument("--mode", choices=("both", "direct", "amplified"), default="both")
    parser.add_argument("--output", default="results/benchmark.json")
    parser.add_argument("--report", default="results/report.md")
    args = parser.parse_args()

    repo = Path(args.repo).resolve()
    eval_doc = json.loads(Path(args.evals).read_text(encoding="utf-8"))
    evals = eval_doc.get("evals", [])
    if not evals:
        raise SystemExit("no evals found")
    command = shlex.split(args.agent_command)
    modes = ("direct", "amplified") if args.mode == "both" else (args.mode,)
    result = run_benchmark(repo, evals, command, args.timeout, args.verify_timeout, args.soft_backend, args.soft_threshold, modes)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    rp = Path(args.report)
    rp.parent.mkdir(parents=True, exist_ok=True)
    rp.write_text(report_mod.markdown(result["summary"]), encoding="utf-8")
    print(rp)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
