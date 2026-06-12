"""Print Wilson confidence intervals for SR and SILVER-R3."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from silver.statistics import wilson_ci  # noqa: E402


def main() -> int:
    path = ROOT / "data/records/stage4_sr_r3_paired_records.csv"
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    n = len(rows)
    sr = sum(row["sr_success"] == "True" for row in rows)
    r3 = sum(row["r3_success"] == "True" for row in rows)
    result = {
        "SR": {"success": sr, "n": n, "ci": wilson_ci(sr, n)},
        "R3": {"success": r3, "n": n, "ci": wilson_ci(r3, n)},
    }
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
