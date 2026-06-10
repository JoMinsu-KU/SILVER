"""Skill taxonomy reports for VLABench Track A."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


TRACK_ROOT = Path("silver/results/track_a_vlabench_planning_20260510")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def build_taxonomy(track_root: Path) -> dict[str, Any]:
    manifest_path = track_root / "manifest" / "vlabench_sample_manifest.jsonl"
    rows = read_jsonl(manifest_path)
    skill_counts: Counter[str] = Counter()
    sequence_counts: Counter[int] = Counter()
    category_counts: Counter[str] = Counter()
    task_counts: Counter[tuple[str, str]] = Counter()
    skill_by_category: dict[str, Counter[str]] = defaultdict(Counter)
    param_key_counts: Counter[str] = Counter()

    for row in rows:
        if not row.get("download_ok"):
            continue
        category = row["category"]
        task = row["task"]
        category_counts[category] += 1
        task_counts[(category, task)] += 1
        gt_path = Path(row["operation_sequence.json"])
        gt = json.loads(gt_path.read_text(encoding="utf-8-sig"))
        seq = gt.get("skill_sequence", []) if isinstance(gt, dict) else []
        sequence_counts[len(seq)] += 1
        for step in seq:
            if not isinstance(step, dict):
                continue
            skill = str(step.get("name"))
            skill_counts[skill] += 1
            skill_by_category[category][skill] += 1
            params = step.get("params", {})
            if isinstance(params, dict):
                for key in params:
                    param_key_counts[key] += 1

    metrics_dir = track_root / "metrics"
    write_csv(
        metrics_dir / "skill_taxonomy_report.csv",
        ["skill", "count"],
        [{"skill": k, "count": v} for k, v in skill_counts.most_common()],
    )
    write_csv(
        metrics_dir / "sequence_length_distribution.csv",
        ["sequence_length", "count"],
        [{"sequence_length": k, "count": v} for k, v in sorted(sequence_counts.items())],
    )
    write_csv(
        metrics_dir / "category_distribution.csv",
        ["category", "sample_count"],
        [{"category": k, "sample_count": v} for k, v in sorted(category_counts.items())],
    )
    write_csv(
        metrics_dir / "task_distribution.csv",
        ["category", "task", "sample_count"],
        [{"category": k[0], "task": k[1], "sample_count": v} for k, v in sorted(task_counts.items())],
    )
    write_csv(
        metrics_dir / "skill_by_category.csv",
        ["category", "skill", "count"],
        [
            {"category": category, "skill": skill, "count": count}
            for category in sorted(skill_by_category)
            for skill, count in skill_by_category[category].most_common()
        ],
    )
    write_csv(
        metrics_dir / "parameter_key_distribution.csv",
        ["parameter_key", "count"],
        [{"parameter_key": k, "count": v} for k, v in param_key_counts.most_common()],
    )
    summary = {
        "manifest_rows": len(rows),
        "download_ok_rows": sum(1 for r in rows if r.get("download_ok")),
        "skill_counts": dict(skill_counts),
        "sequence_length_distribution": dict(sequence_counts),
        "category_counts": dict(category_counts),
        "parameter_key_counts": dict(param_key_counts),
    }
    (metrics_dir / "skill_taxonomy_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Build VLABench skill taxonomy reports.")
    parser.add_argument("--track_root", type=Path, default=TRACK_ROOT)
    args = parser.parse_args()
    print(json.dumps(build_taxonomy(args.track_root), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
