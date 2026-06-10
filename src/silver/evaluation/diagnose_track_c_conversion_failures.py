# -*- coding: utf-8 -*-
"""Diagnose Track C conversion failures from saved artifacts.

This script does not run VLABench. It reads Track C CSV/artifacts and reports
why cases were marked not_run_conversion_failed.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
from collections import Counter
from pathlib import Path
from typing import Any


DEFAULT_ROOT = Path(os.environ.get("SILVER_TRACK_C_ROOT", "data/track_c"))


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig", errors="replace") as f:
        return json.load(f)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="", errors="replace") as f:
        return list(csv.DictReader(f))


def sample_dir(root: Path, row: dict[str, str]) -> Path:
    return root / "data" / row["category"] / row["task"] / row["example"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--task", default="select_poker")
    parser.add_argument("--limit-examples", type=int, default=8)
    args = parser.parse_args()

    root = args.root
    rows = read_csv(root / "metrics" / "qwen_guided_execution_results.csv")
    c2_rows = [r for r in rows if r.get("track_c_status") == "C2_qwen_conversion_failure"]
    task_rows = [r for r in rows if r.get("task") == args.task]
    task_c2_rows = [r for r in task_rows if r.get("track_c_status") == "C2_qwen_conversion_failure"]

    error_counter: Counter[str] = Counter()
    task_error_counter: Counter[str] = Counter()
    examples: list[dict[str, Any]] = []

    for row in c2_rows:
        validation_path = sample_dir(root, row) / "qwen_p2_adapter_validation.json"
        errors = ["missing_validation"]
        if validation_path.exists():
            validation = read_json(validation_path)
            errors = validation.get("conversion_errors") or ["conversion_error_empty"]
        for error in errors:
            error_counter[str(error)] += 1
            if row.get("task") == args.task:
                task_error_counter[str(error)] += 1

    for row in task_c2_rows[: args.limit_examples]:
        case_dir = sample_dir(root, row)
        validation = read_json(case_dir / "qwen_p2_adapter_validation.json")
        plan_path = case_dir / "qwen_p2_executor_plan.json"
        plan = read_json(plan_path) if plan_path.exists() else None
        examples.append(
            {
                "run_position": row.get("run_position"),
                "sample_id": row.get("sample_id"),
                "execution_status": row.get("execution_status"),
                "failure_reason_in_csv": row.get("failure_reason", ""),
                "conversion_errors": validation.get("conversion_errors", []),
                "skill_sequence": validation.get("skill_sequence", []),
                "plan_conversion_ok": None if plan is None else plan.get("conversion_ok"),
                "plan_actions": None if plan is None else plan.get("actions", []),
            }
        )

    summary = {
        "root": str(root),
        "total_completed_rows": len(rows),
        "total_c2_conversion_failures": len(c2_rows),
        "task": args.task,
        "task_rows_completed": len(task_rows),
        "task_c2_conversion_failures": len(task_c2_rows),
        "all_c2_error_counts": dict(error_counter.most_common()),
        "task_c2_error_counts": dict(task_error_counter.most_common()),
        "task_c2_examples": examples,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
