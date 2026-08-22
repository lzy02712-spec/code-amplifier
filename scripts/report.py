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
        return {
            "runs": 0,
            "gradable_runs": 0,
            "ungradable_runs": 0,
            "successes": 0,
            "pass_rate": 0.0,
            "provisional_successes": 0,
            "provisional_pass_rate": 0.0,
            "avg_elapsed_seconds": 0.0,
            "avg_soft_score": 0.0,
        }
    gradable = [r for r in rows if bool(r.get("gradable")) and r.get("success") is not None]
    successes = sum(bool(r.get("success")) for r in gradable)
    provisional = sum(bool(r.get("provisional_success")) for r in rows)
    elapsed = [float(r.get("elapsed_seconds", 0.0)) for r in rows]
    scores = [float(r.get("soft_score", 0.0)) for r in rows]
    return {
        "runs": len(rows),
        "gradable_runs": len(gradable),
        "ungradable_runs": len(rows) - len(gradable),
        "successes": successes,
        "pass_rate": round(successes / len(gradable), 4) if gradable else 0.0,
        "provisional_successes": provisional,
        "provisional_pass_rate": round(provisional / len(rows), 4),
        "avg_elapsed_seconds": round(mean(elapsed), 3),
        "avg_soft_score": round(mean(scores), 4),
    }


def _paired(results: list[dict[str, Any]]) -> dict[str, int]:
    grouped: dict[str, dict[str, dict[str, Any]]] = {}
    for row in results:
        grouped.setdefault(str(row.get("task_id")), {})[str(row.get("mode"))] = row
    out = {"comparable_pairs": 0, "amplifier_wins": 0, "regressions": 0, "both_pass": 0, "both_fail": 0}
    for pair in grouped.values():
        d, a = pair.get("direct"), pair.get("amplified")
        if not d or not a or not d.get("gradable") or not a.get("gradable"):
            continue
        out["comparable_pairs"] += 1
        ds, aas = bool(d.get("success")), bool(a.get("success"))
        if not ds and aas:
            out["amplifier_wins"] += 1
        elif ds and not aas:
            out["regressions"] += 1
        elif ds and aas:
            out["both_pass"] += 1
        else:
            out["both_fail"] += 1
    return out


def summarize(results: list[dict[str, Any]]) -> dict[str, Any]:
    direct = [r for r in results if r.get("mode") == "direct"]
    amplified = [r for r in results if r.get("mode") == "amplified"]
    ds, amps = _summary(direct), _summary(amplified)
    return {
        "schema_version": 3,
        "tasks": len({r.get("task_id") for r in results}),
        "strict_gradable_tasks": len({r.get("task_id") for r in results if r.get("gradable")}),
        "direct": ds,
        "amplified": amps,
        "paired": _paired(results),
        "improvement": {
            "absolute_pass_rate": round(amps["pass_rate"] - ds["pass_rate"], 4),
            "relative_pass_rate": round(((amps["pass_rate"] / ds["pass_rate"]) - 1.0), 4) if ds["pass_rate"] else None,
        },
    }


def markdown(summary: dict[str, Any]) -> str:
    d, a = summary["direct"], summary["amplified"]
    p = summary.get("paired", {})
    delta = summary["improvement"]["absolute_pass_rate"]
    return f"""# CodeAmplifier Benchmark Report

## Strict hidden-test score

| Metric | Direct | Amplified |
|---|---:|---:|
| Total runs | {d['runs']} | {a['runs']} |
| Strict gradable runs | {d['gradable_runs']} | {a['gradable_runs']} |
| Ungradable runs | {d['ungradable_runs']} | {a['ungradable_runs']} |
| Strict successes | {d['successes']} | {a['successes']} |
| Strict pass rate | {d['pass_rate']:.1%} | {a['pass_rate']:.1%} |
| Provisional pass rate | {d['provisional_pass_rate']:.1%} | {a['provisional_pass_rate']:.1%} |
| Avg soft score | {d['avg_soft_score']:.3f} | {a['avg_soft_score']:.3f} |
| Avg elapsed | {d['avg_elapsed_seconds']:.1f}s | {a['avg_elapsed_seconds']:.1f}s |

**Absolute strict pass-rate change:** {delta:+.1%}

## Paired outcomes

| Outcome | Count |
|---|---:|
| Comparable pairs | {p.get('comparable_pairs', 0)} |
| Amplifier wins (Direct FAIL → Amplified PASS) | {p.get('amplifier_wins', 0)} |
| Regressions (Direct PASS → Amplified FAIL) | {p.get('regressions', 0)} |
| Both pass | {p.get('both_pass', 0)} |
| Both fail | {p.get('both_fail', 0)} |

Strict success is counted only when the future hidden tests are independently validated to **fail on the base revision and pass on the recorded target revision**, then also pass against the agent's final implementation. Public hard verification must pass too. Soft verification is diagnostic and cannot create a strict success.
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
