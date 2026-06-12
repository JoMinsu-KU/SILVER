"""Recompute the 300-case ablation success counts."""

from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    path = ROOT / "data/records/ablation_300_records_long.csv"
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    counts = Counter()
    totals = Counter()
    for row in rows:
        totals[row["variant"]] += 1
        if row["success"] == "True":
            counts[row["variant"]] += 1
    print(json.dumps({"rows": len(rows), "totals": dict(sorted(totals.items())), "success_counts": dict(sorted(counts.items()))}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
