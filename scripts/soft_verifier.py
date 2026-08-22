#!/usr/bin/env python3
"""Soft verification for requirements that deterministic checks cannot prove.

Backends:
- heuristic: zero-dependency evidence-aware scorer (always available)
- llm-verifier: optional adapter to the llm-verifier package's progress tracker
- openai-json: optional OpenAI-compatible structured reviewer

Soft scores never override a deterministic FAIL.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any


def _read_json(path: str | None) -> dict[str, Any] | None:
    if not path:
        return None
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _read_text(path: str | None) -> str:
    if not path:
        return ""
    return Path(path).read_text(encoding="utf-8", errors="replace")


def _clamp(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


def heuristic_score(task: str, trajectory: str, verification: dict[str, Any] | None = None, criteria: list[dict[str, str]] | None = None) -> dict[str, Any]:
    text = trajectory.lower()
    hard = (verification or {}).get("overall_status", "UNKNOWN")
    if hard == "FAIL":
        base = 0.2
    elif hard == "PASS":
        base = 0.78
    elif hard == "NOT_CONFIGURED":
        base = 0.45
    else:
        base = 0.4

    positives = ["test", "passed", "exit code 0", "verified", "compile", "lint", "typecheck", "git diff"]
    negatives = ["traceback", "failed", "error:", "not verified", "timeout", "cannot run"]
    base += min(0.12, sum(1 for p in positives if p in text) * 0.02)
    base -= min(0.18, sum(1 for n in negatives if n in text) * 0.03)
    if not trajectory.strip():
        base -= 0.15
    score = _clamp(base)

    crits = criteria or [
        {"id": "correctness", "name": "Task correctness"},
        {"id": "verification", "name": "Empirical verification"},
        {"id": "regression", "name": "Regression safety"},
    ]
    breakdown = {}
    for c in crits:
        cid = c.get("id", "criterion")
        cscore = score
        if cid == "verification":
            cscore = _clamp(score + (0.08 if hard == "PASS" else -0.08))
        elif cid == "security" and not any(k in text for k in ("security", "auth", "tenant", "permission", "isolation")):
            cscore = _clamp(score - 0.08)
        breakdown[cid] = round(cscore, 4)

    return {
        "schema_version": 2,
        "backend": "heuristic",
        "score": round(sum(breakdown.values()) / max(1, len(breakdown)), 4),
        "criteria": breakdown,
        "hard_status": hard,
        "notes": ["heuristic backend is a fallback signal, not a correctness oracle"],
    }


def llm_verifier_score(task: str, trajectory: str, verification: dict[str, Any] | None, criteria: list[dict[str, str]] | None, n_evaluations: int = 2) -> dict[str, Any]:
    try:
        import llm_verifier  # type: ignore
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("llm-verifier backend requested but package is not installed") from exc
    steps = [block.strip() for block in trajectory.split("\n\n") if block.strip()]
    if not steps:
        steps = ["No trajectory output was captured."]
    result = llm_verifier.track(problem=task, steps=steps, n_evaluations=n_evaluations)
    score = float(result.final)
    hard = (verification or {}).get("overall_status", "UNKNOWN")
    if hard == "FAIL":
        score = min(score, 0.49)
    return {
        "schema_version": 2,
        "backend": "llm-verifier",
        "score": round(_clamp(score), 4),
        "criteria": {},
        "hard_status": hard,
        "notes": ["final score adapted from llm_verifier.track; deterministic FAIL caps acceptance"],
    }


def openai_json_score(task: str, trajectory: str, verification: dict[str, Any] | None, criteria: list[dict[str, str]] | None, model: str | None = None, base_url: str | None = None) -> dict[str, Any]:
    try:
        from openai import OpenAI  # type: ignore
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("openai-json backend requested but openai package is not installed") from exc
    model = model or os.environ.get("CODE_AMPLIFIER_VERIFIER_MODEL") or "gpt-4.1-mini"
    base_url = base_url or os.environ.get("OPENAI_BASE_URL")
    client = OpenAI(base_url=base_url, api_key=os.environ.get("OPENAI_API_KEY", "EMPTY"))
    hard = (verification or {}).get("overall_status", "UNKNOWN")
    criteria_text = json.dumps(criteria or [], ensure_ascii=False)
    prompt = f"""You are a strict coding-task verifier. Trust observed command output more than agent narration.
Return JSON only with keys score (0..1), criteria (object of criterion id -> 0..1), notes (array of strings).
A deterministic FAIL cannot be considered successful.

Task:\n{task}\n
Criteria:\n{criteria_text}\n
Deterministic verification status: {hard}\n
Agent trajectory:\n{trajectory[-50000:]}\n"""
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        response_format={"type": "json_object"},
    )
    raw = resp.choices[0].message.content or "{}"
    data = json.loads(raw)
    score = _clamp(float(data.get("score", 0.5)))
    if hard == "FAIL":
        score = min(score, 0.49)
    return {
        "schema_version": 2,
        "backend": "openai-json",
        "model": model,
        "score": round(score, 4),
        "criteria": data.get("criteria", {}),
        "hard_status": hard,
        "notes": data.get("notes", []),
    }


def verify_soft(task: str, trajectory: str, verification: dict[str, Any] | None = None, criteria: list[dict[str, str]] | None = None, backend: str = "heuristic", n_evaluations: int = 2, model: str | None = None, base_url: str | None = None) -> dict[str, Any]:
    if backend == "heuristic":
        return heuristic_score(task, trajectory, verification, criteria)
    if backend == "llm-verifier":
        return llm_verifier_score(task, trajectory, verification, criteria, n_evaluations)
    if backend == "openai-json":
        return openai_json_score(task, trajectory, verification, criteria, model, base_url)
    raise ValueError(f"unknown backend: {backend}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", help="Task text; if omitted use --task-file")
    parser.add_argument("--task-file")
    parser.add_argument("--trajectory", required=True)
    parser.add_argument("--verification")
    parser.add_argument("--criteria")
    parser.add_argument("--backend", choices=("heuristic", "llm-verifier", "openai-json"), default="heuristic")
    parser.add_argument("--n-evaluations", type=int, default=2)
    parser.add_argument("--model")
    parser.add_argument("--base-url")
    parser.add_argument("--output")
    args = parser.parse_args()
    task = args.task or _read_text(args.task_file)
    criteria_obj = _read_json(args.criteria)
    criteria = None if criteria_obj is None else criteria_obj.get("criteria", criteria_obj if isinstance(criteria_obj, list) else [])
    result = verify_soft(task, _read_text(args.trajectory), _read_json(args.verification), criteria, args.backend, args.n_evaluations, args.model, args.base_url)
    text = json.dumps(result, indent=2, ensure_ascii=False)
    if args.output:
        Path(args.output).write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
