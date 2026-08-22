#!/usr/bin/env python3
"""Generate hidden-oracle coding evals from repository Git history.

The generated task prompt is safe to give to the agent. Oracle fields (target
commit, patch hash, expected changed files, hidden future tests) are retained
only for grading and are never included in the public prompt.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any

DOC_SUFFIXES = {".md", ".rst", ".txt", ".adoc"}
TEST_MARKERS = ("test", "tests", "spec", "specs", "__tests__")
SECURITY_MARKERS = ("auth", "tenant", "permission", "security", "token", "secret", "acl", "rbac")


def _git(root: Path, *args: str, check: bool = True) -> str:
    cp = subprocess.run(
        ["git", "-C", str(root), *args],
        text=True,
        capture_output=True,
        check=False,
    )
    if check and cp.returncode != 0:
        raise RuntimeError(cp.stderr.strip() or f"git {' '.join(args)} failed")
    return cp.stdout


def _clean_subject(subject: str) -> str:
    subject = re.sub(r"^(feat|fix|refactor|perf|test|chore|build|ci|docs)(\([^)]*\))?!?:\s*", "", subject, flags=re.I)
    return subject.strip().rstrip(".")


def _is_test_path(path: str) -> bool:
    parts = [p.lower() for p in Path(path).parts]
    stem = Path(path).stem.lower()
    return any(any(marker in part for marker in TEST_MARKERS) for part in parts) or stem.startswith(("test_", "spec_")) or stem.endswith(("_test", "_spec"))


def _exists_at_ref(root: Path, ref: str, path: str) -> bool:
    cp = subprocess.run(
        ["git", "-C", str(root), "cat-file", "-e", f"{ref}:{path}"],
        capture_output=True,
        check=False,
    )
    return cp.returncode == 0


def _criteria(subject: str, changed_files: list[str]) -> list[dict[str, str]]:
    text = (subject + " " + " ".join(changed_files)).lower()
    criteria = [
        {"id": "correctness", "name": "Task correctness", "description": "Does the final repository state satisfy the requested behavior?"},
        {"id": "regression", "name": "Regression safety", "description": "Does the change preserve unrelated existing behavior and contracts?"},
        {"id": "verification", "name": "Empirical verification", "description": "Did the agent run relevant checks and ground completion in observed output?"},
    ]
    if any(marker in text for marker in SECURITY_MARKERS):
        criteria.append({"id": "security", "name": "Security boundary", "description": "Does the change preserve authentication, authorization, isolation, and secret-handling constraints?"})
    return criteria


def history_evals(
    root: Path,
    limit: int = 20,
    scan: int | None = None,
    max_files: int = 12,
    require_hidden_tests: bool = False,
) -> list[dict[str, Any]]:
    root = root.resolve()
    if _git(root, "rev-parse", "--is-inside-work-tree").strip() != "true":
        raise RuntimeError(f"not a Git repository: {root}")
    scan = scan or max(limit * 8, 80)
    lines = _git(root, "log", "--no-merges", f"-n{scan}", "--format=%H%x09%P%x09%s").splitlines()
    evals: list[dict[str, Any]] = []
    for line in lines:
        parts = line.split("\t", 2)
        if len(parts) != 3:
            continue
        commit, parents, subject = parts
        parent_list = parents.split()
        if len(parent_list) != 1:
            continue
        parent = parent_list[0]
        files = [p for p in _git(root, "diff", "--name-only", parent, commit).splitlines() if p.strip()]
        if not files or len(files) > max_files:
            continue
        if all(Path(p).suffix.lower() in DOC_SUFFIXES for p in files):
            continue
        patch = _git(root, "diff", "--binary", parent, commit)
        if not patch.strip():
            continue
        cleaned = _clean_subject(subject)
        if not cleaned:
            continue

        hidden_tests = [p for p in files if _is_test_path(p) and _exists_at_ref(root, commit, p)]
        if require_hidden_tests and not hidden_tests:
            continue

        task_id = f"hist-{commit[:12]}"
        evals.append({
            "id": task_id,
            "source": "git-history",
            "prompt": f"Implement this repository task: {cleaned}. Preserve behavior outside the requested scope and verify the final result.",
            "base_ref": parent,
            "criteria": _criteria(subject, files),
            "oracle": {
                "target_ref": commit,
                "patch_sha256": hashlib.sha256(patch.encode("utf-8")).hexdigest(),
                "changed_files": files,
                "includes_tests": bool(hidden_tests),
                "grader": {
                    "kind": "future-tests" if hidden_tests else "none",
                    "hidden_test_files": hidden_tests,
                    "strict_eligible": bool(hidden_tests),
                },
            },
        })
        if len(evals) >= limit:
            break
    return evals


def generate(root: Path, limit: int = 20, max_files: int = 12, require_hidden_tests: bool = False) -> dict[str, Any]:
    evals = history_evals(root, limit=limit, max_files=max_files, require_hidden_tests=require_hidden_tests)
    strict = sum(bool(e.get("oracle", {}).get("grader", {}).get("strict_eligible")) for e in evals)
    return {
        "schema_version": 3,
        "generator": "git-history",
        "repository": str(root.resolve()),
        "eval_count": len(evals),
        "strict_candidate_count": strict,
        "require_hidden_tests": require_hidden_tests,
        "evals": evals,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate CodeAmplifier evals from Git history")
    parser.add_argument("--root", default=".")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--max-files", type=int, default=12)
    parser.add_argument("--require-hidden-tests", action="store_true", help="Only emit commits that changed at least one test/spec file present in the target revision")
    parser.add_argument("--output", default="evals/generated.json")
    args = parser.parse_args()
    result = generate(Path(args.root), args.limit, args.max_files, args.require_hidden_tests)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"generated {result['eval_count']} evals ({result['strict_candidate_count']} with hidden tests) -> {out}")
    return 0 if result["eval_count"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
