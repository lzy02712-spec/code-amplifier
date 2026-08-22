#!/usr/bin/env python3
"""Aggregate paired benchmark runs and render JSON/Markdown reports."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import mean
from typing import Any


def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"runs": 0, "successes": 0, "pass_rate": 0.0, "avg_elapsed_seconds": 0.0, "avg_soft_score": 0.0}
    successes = sum(bool(r.get("success")) for r in rows)
    elapsed = [float(r.get("elapsed_seconds", 0.0)) for r in rows]
    scores = [float(r.get("soft_score", 0.0)) for r in rows]
    return {
        "runs": len(rows),
        "successes": successes,
        "pass_rate": round(successes / len(rows), 4),
        "avg_elapsed_seconds": round(mean(elapsed), 3),
        "avg_soft_score": round(mean(scores), 4),
    }


def summarize(results: list[dict[str, Any]]) -> dict[str, Any]:
    direct = [r for r in results if r.get("mode") == "direct"]
    amplified = [r for r in results if r.get("mode") == "amplified"]
    ds, amps = _summary(direct), _summary(amplified)
    return {
        "schema_version": 2,
        "tasks": len({r.get("task_id") for r in results}),
        "direct": ds,
        "amplified": amps,
        "improvement": {
            "absolute_pass_rate": round(amps["pass_rate"] - ds["pass_rate"], 4),
            "relative_pass_rate": round(((amps["pass_rate"] / ds["pass_rate"]) - 1.0), 4) if ds["pass_rate"] else None,
        },
    }


def markdown(summary: dict[str, Any]) -> str:
    d, a = summary["direct"], summary["amplified"]
    delta = summary["improvement"]["absolute_pass_rate"]
    return f"""# CodeAmplifier Benchmark Report

| Metric | Direct | Amplified |
|---|---:|---:|
| Runs | {d['runs']} | {a['runs']} |
| Successes | {d['successes']} | {a['successes']} |
| Pass rate | {d['pass_rate']:.1%} | {a['pass_rate']:.1%} |
| Avg soft score | {d['avg_soft_score']:.3f} | {a['avg_soft_score']:.3f} |
| Avg elapsed | {d['avg_elapsed_seconds']:.1f}s | {a['avg_elapsed_seconds']:.1f}s |

**Absolute pass-rate change:** {delta:+.1%}

Success requires deterministic verification to pass and the configured soft-verification threshold to be met. Soft scores never override a hard failure.
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", required=True)
    parser.add_argument("--json-output", default="results/summary.json")
    parser.add_argument("--markdown-output", default="results/report.md")
    args = parser.parse_args()
    raw = json.loads(Path(args.results).read_text(encoding="utf-8"))
    rows = raw.get("runs", raw if isinstance(raw, list) else [])
    summary = summarize(rows)
    jp, mp = Path(args.json_output), Path(args.markdown_output)
    jp.parent.mkdir(parents=True, exist_ok=True)
    mp.parent.mkdir(parents=True, exist_ok=True)
    jp.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    mp.write_text(markdown(summary), encoding="utf-8")
    print(mp)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
