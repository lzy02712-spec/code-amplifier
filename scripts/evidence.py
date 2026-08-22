#!/usr/bin/env python3
"""Aggregate verification, diff, and requirement-ledger evidence."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

VALID_REQ = {"PENDING", "PASS", "FAIL", "UNKNOWN"}


def _read(path: str | None) -> dict[str, Any] | None:
    if not path:
        return None
    return json.loads(Path(path).read_text(encoding="utf-8"))


def aggregate(
    verification: dict[str, Any] | None,
    diff: dict[str, Any] | None,
    requirements: dict[str, Any] | None,
) -> dict[str, Any]:
    blockers: list[str] = []
    limitations: list[str] = []

    verification_status = "UNKNOWN" if verification is None else verification.get("overall_status", "UNKNOWN")
    if verification_status == "FAIL":
        blockers.append("deterministic verification failed")
    elif verification_status in {"UNKNOWN", "NOT_CONFIGURED"}:
        limitations.append(f"verification status is {verification_status}")

    diff_status = "UNKNOWN" if diff is None else diff.get("status", "UNKNOWN")
    if diff_status != "PASS":
        limitations.append("final Git diff was not confirmed")
    elif diff and diff.get("suspicious_paths"):
        blockers.append("final diff contains suspicious secret-like or temporary paths")

    req_items = []
    if requirements is None:
        limitations.append("requirement ledger was not provided")
    else:
        raw = requirements.get("requirements", [])
        if not isinstance(raw, list):
            blockers.append("requirement ledger has invalid schema")
        else:
            for item in raw:
                if not isinstance(item, dict):
                    blockers.append("requirement ledger contains a non-object entry")
                    continue
                status = str(item.get("status", "UNKNOWN")).upper()
                if status not in VALID_REQ:
                    status = "UNKNOWN"
                normalized = {
                    "id": item.get("id"),
                    "criterion": item.get("criterion"),
                    "status": status,
                    "evidence": item.get("evidence", ""),
                }
                req_items.append(normalized)
                if status == "FAIL":
                    blockers.append(f"requirement {normalized['id']} failed")
                elif status in {"UNKNOWN", "PENDING"}:
                    limitations.append(f"requirement {normalized['id']} is {status}")

    if blockers:
        overall = "NOT_VERIFIED"
    elif limitations:
        overall = "PARTIALLY_VERIFIED"
    else:
        overall = "VERIFIED"

    return {
        "schema_version": 1,
        "status": overall,
        "verification_status": verification_status,
        "diff_status": diff_status,
        "requirements": req_items,
        "blockers": blockers,
        "limitations": limitations,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verification")
    parser.add_argument("--diff")
    parser.add_argument("--requirements")
    parser.add_argument("--output")
    args = parser.parse_args()

    result = aggregate(_read(args.verification), _read(args.diff), _read(args.requirements))
    text = json.dumps(result, indent=2, ensure_ascii=False)
    if args.output:
        Path(args.output).write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0 if result["status"] == "VERIFIED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
