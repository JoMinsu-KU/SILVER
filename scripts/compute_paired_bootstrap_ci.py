"""Compute a deterministic paired bootstrap CI for the SR-vs-R3 gain."""

from __future__ import annotations

import csv
import json
import random
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    path = ROOT / "data/records/stage4_sr_r3_paired_records.csv"
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    diffs = [(1 if row["r3_success"] == "True" else 0) - (1 if row["sr_success"] == "True" else 0) for row in rows]
    rng = random.Random(20260612)
    estimates = []
    n = len(diffs)
    for _ in range(10000):
        sample = [diffs[rng.randrange(n)] for _ in range(n)]
        estimates.append(sum(sample) / n)
    estimates.sort()
    result = {
        "n": n,
        "gain": sum(diffs) / n,
        "ci_low": estimates[int(0.025 * len(estimates))],
        "ci_high": estimates[int(0.975 * len(estimates))],
        "bootstrap_replicates": len(estimates),
        "seed": 20260612,
    }
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
