#!/usr/bin/env python3
"""Adaptive execution policy from hard evidence and soft progress scores."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ACTIONS = {"CONTINUE", "GATHER_EVIDENCE", "REPAIR", "REPLAN", "RESAMPLE", "DONE", "STOP"}


def decide(scores: list[float], hard_status: str = "UNKNOWN", repeated_failure_count: int = 0, budget_fraction: float = 0.0, done_threshold: float = 0.88) -> dict[str, Any]:
    scores = [max(0.0, min(1.0, float(s))) for s in scores]
    latest = scores[-1] if scores else None
    hard_status = hard_status.upper()

    if hard_status == "FAIL":
        action = "REPLAN" if repeated_failure_count >= 3 else "REPAIR"
        reason = "deterministic verification failed"
    elif hard_status in {"UNKNOWN", "NOT_CONFIGURED"} and budget_fraction < 0.9:
        action = "GATHER_EVIDENCE"
        reason = f"deterministic status is {hard_status}"
    elif hard_status == "PASS" and latest is not None and latest >= done_threshold:
        action = "DONE"
        reason = "hard gates passed and soft confidence cleared threshold"
    elif budget_fraction >= 0.95:
        action = "STOP"
        reason = "execution budget exhausted before acceptance"
    elif len(scores) >= 2 and scores[-1] <= scores[-2] - 0.12:
        action = "REPLAN"
        reason = "progress regressed materially"
    elif len(scores) >= 3 and max(scores[-3:]) - min(scores[-3:]) < 0.03 and (latest or 0.0) < 0.72:
        action = "RESAMPLE"
        reason = "progress plateaued below useful confidence"
    else:
        action = "CONTINUE"
        reason = "continue current trajectory"

    return {
        "schema_version": 2,
        "action": action,
        "reason": reason,
        "latest_score": latest,
        "scores": scores,
        "hard_status": hard_status,
        "repeated_failure_count": repeated_failure_count,
        "budget_fraction": round(max(0.0, min(1.0, budget_fraction)), 4),
        "done_threshold": done_threshold,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scores", default="", help="Comma-separated 0..1 scores")
    parser.add_argument("--hard-status", default="UNKNOWN")
    parser.add_argument("--repeated-failures", type=int, default=0)
    parser.add_argument("--budget-fraction", type=float, default=0.0)
    parser.add_argument("--done-threshold", type=float, default=0.88)
    parser.add_argument("--output")
    args = parser.parse_args()
    scores = [float(x) for x in args.scores.split(",") if x.strip()]
    result = decide(scores, args.hard_status, args.repeated_failures, args.budget_fraction, args.done_threshold)
    text = json.dumps(result, indent=2)
    if args.output:
        Path(args.output).write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
