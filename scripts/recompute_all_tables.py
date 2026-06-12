"""Recompute the core SILVER counts from released CSV ledgers."""

from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_csv(rel: str) -> list[dict[str, str]]:
    with (ROOT / rel).open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def count_true(rows: list[dict[str, str]], field: str) -> int:
    return sum(row.get(field) == "True" for row in rows)


def main() -> int:
    stage1 = read_csv("data/sample_ids/stage1_public_4500_ids.csv")
    stage2_candidates = read_csv("data/sample_ids/stage2_execution_candidate_4000_ids.csv")
    stage2_records = read_csv("data/records/stage2_official_expert_repeat_records.csv")
    stage3_records = read_csv("data/records/stage3_qwen_initial_execution_records.csv")
    stage4_records = read_csv("data/records/stage4_sr_r3_paired_records.csv")
    ablation_records = read_csv("data/records/ablation_300_records_long.csv")

    stage2_status = Counter(row["official_status"] for row in stage2_records)
    stage3_status = Counter(row["track_c_status"] for row in stage3_records)
    paired = Counter(row["paired_cell"] for row in stage4_records)
    ablation_success = Counter()
    for row in ablation_records:
        if row.get("success") == "True":
            ablation_success[row["variant"]] += 1

    summary = {
        "track_a_public_samples": len(stage1),
        "track_b_execution_candidates": len(stage2_candidates),
        "track_b_official_eligible": stage2_status["B0_official_eligible"],
        "track_c_initial_success": stage3_status["C0_qwen_guided_success"],
        "track_d_initial_failures": len(stage4_records),
        "track_d_same_plan_retry_recoveries": count_true(stage4_records, "sr_success"),
        "track_d_silver_r3_recoveries": count_true(stage4_records, "r3_success"),
        "track_d_paired_cells": dict(sorted(paired.items())),
        "ablation_success_counts": dict(sorted(ablation_success.items())),
    }

    expected = {
        "track_a_public_samples": 4500,
        "track_b_execution_candidates": 4000,
        "track_b_official_eligible": 2133,
        "track_c_initial_success": 1106,
        "track_d_initial_failures": 1027,
        "track_d_same_plan_retry_recoveries": 36,
        "track_d_silver_r3_recoveries": 326,
    }
    errors = [
        f"{key}: expected {value}, got {summary[key]}"
        for key, value in expected.items()
        if summary[key] != value
    ]
    print(json.dumps({"ok": not errors, "summary": summary, "errors": errors}, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
