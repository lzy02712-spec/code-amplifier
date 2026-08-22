#!/usr/bin/env python3
"""Inspect Git working-tree changes without modifying the repository."""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any


def _git(root: Path, *args: str) -> tuple[int, str, str]:
    proc = subprocess.run(
        ["git", *args], cwd=root, capture_output=True, text=True, check=False
    )
    return proc.returncode, proc.stdout, proc.stderr


def inspect(root: Path) -> dict[str, Any]:
    root = root.resolve()
    rc, top, err = _git(root, "rev-parse", "--show-toplevel")
    if rc != 0:
        return {
            "root": str(root),
            "status": "UNKNOWN",
            "reason": f"Not a readable Git worktree: {err.strip()}",
            "changed_files": [],
        }

    _, porcelain, _ = _git(root, "status", "--porcelain=v1")
    _, stat, _ = _git(root, "diff", "--stat")
    _, cached_stat, _ = _git(root, "diff", "--cached", "--stat")
    _, names, _ = _git(root, "diff", "--name-status")
    _, cached_names, _ = _git(root, "diff", "--cached", "--name-status")

    status_lines = [line for line in porcelain.splitlines() if line.strip()]
    changed_files = []
    for line in status_lines:
        code = line[:2]
        path = line[3:] if len(line) > 3 else ""
        changed_files.append({"status": code, "path": path})

    suspicious = []
    for item in changed_files:
        lower = item["path"].lower()
        if any(token in lower for token in (".env", "secret", "credential", "private_key", "id_rsa")):
            suspicious.append({"path": item["path"], "reason": "secret-like filename"})
        if lower.endswith((".log", ".tmp", ".swp")):
            suspicious.append({"path": item["path"], "reason": "temporary/debug artifact"})

    return {
        "root": str(root),
        "git_toplevel": top.strip(),
        "status": "PASS",
        "working_tree_porcelain": status_lines,
        "changed_files": changed_files,
        "unstaged_name_status": names.splitlines(),
        "staged_name_status": cached_names.splitlines(),
        "unstaged_stat": stat.strip(),
        "staged_stat": cached_stat.strip(),
        "suspicious_paths": suspicious,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--output")
    args = parser.parse_args()

    result = inspect(Path(args.root))
    text = json.dumps(result, indent=2, ensure_ascii=False)
    if args.output:
        Path(args.output).write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
