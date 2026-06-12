"""Compute the exact McNemar test for SR versus SILVER-R3."""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def exact_two_sided_binomial_pvalue(k: int, n: int, p: float = 0.5) -> float:
    """Two-sided exact binomial p-value for discordant McNemar pairs."""

    observed = math.comb(n, k) * (p**k) * ((1 - p) ** (n - k))
    total = 0.0
    for i in range(n + 1):
        prob = math.comb(n, i) * (p**i) * ((1 - p) ** (n - i))
        if prob <= observed:
            total += prob
    return min(1.0, total)


def main() -> int:
    path = ROOT / "data/records/stage4_sr_r3_paired_records.csv"
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    r3_only = sum(row["sr_success"] == "False" and row["r3_success"] == "True" for row in rows)
    sr_only = sum(row["sr_success"] == "True" and row["r3_success"] == "False" for row in rows)
    discordant = r3_only + sr_only
    p_value = exact_two_sided_binomial_pvalue(min(r3_only, sr_only), discordant)
    print(
        json.dumps(
            {
                "test": "McNemar exact binomial",
                "r3_only": r3_only,
                "sr_only": sr_only,
                "discordant_pairs": discordant,
                "p_value": p_value,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
