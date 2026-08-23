"""Adaptive task routing for CodeAmplifier.

Classifies coding tasks into FAST_PATH or FULL_PATH.
The classifier is intentionally conservative: uncertainty routes to FULL_PATH.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass


@dataclass
class RouteDecision:
    mode: str
    confidence: float
    reasons: list[str]


FULL_KEYWORDS = {
    "security": "security_sensitive",
    "permission": "security_sensitive",
    "authentication": "security_sensitive",
    "authorization": "security_sensitive",
    "refactor": "architecture_change",
    "migration": "architecture_change",
    "architecture": "architecture_change",
    "database": "data_change",
    "schema": "data_change",
    "root cause": "debugging",
    "regression": "regression_risk",
}

FAST_KEYWORDS = {
    "rename": "small_change",
    "typo": "small_change",
    "documentation": "docs_change",
    "docs": "docs_change",
    "getter": "small_change",
    "setter": "small_change",
}


def classify_task(task: str, changed_files: list[str] | None = None) -> RouteDecision:
    text = task.lower()
    reasons: list[str] = []
    files = changed_files or []

    for keyword, reason in FULL_KEYWORDS.items():
        if keyword in text:
            reasons.append(reason)

    if len(files) > 3:
        reasons.append("multi_file_change")

    if any(re.search(r"(^|/)(test|tests)/", f) for f in files):
        reasons.append("test_surface_change")

    if reasons:
        return RouteDecision("FULL_PATH", 0.9, sorted(set(reasons)))

    fast_reasons = []
    for keyword, reason in FAST_KEYWORDS.items():
        if keyword in text:
            fast_reasons.append(reason)

    if len(files) <= 1 and fast_reasons:
        return RouteDecision("FAST_PATH", 0.85, sorted(set(fast_reasons + ["small_scope"])))

    return RouteDecision("FULL_PATH", 0.6, ["insufficient_confidence"])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("task")
    parser.add_argument("--files", nargs="*", default=[])
    args = parser.parse_args()
    print(json.dumps(asdict(classify_task(args.task, args.files)), indent=2))


if __name__ == "__main__":
    main()
