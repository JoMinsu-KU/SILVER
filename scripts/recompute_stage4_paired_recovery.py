"""Recompute Track D same-plan retry versus SILVER-R3 paired counts."""

from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    path = ROOT / "data/records/stage4_sr_r3_paired_records.csv"
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    paired = Counter(row["paired_cell"] for row in rows)
    summary = {
        "rows": len(rows),
        "same_plan_retry_success": sum(row["sr_success"] == "True" for row in rows),
        "silver_r3_success": sum(row["r3_success"] == "True" for row in rows),
        "paired_cells": dict(sorted(paired.items())),
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
