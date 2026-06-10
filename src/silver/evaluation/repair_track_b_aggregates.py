# -*- coding: utf-8 -*-
"""Repair Track B aggregate files from per-case execution artifacts.

This script does not create experimental results. It reconstructs the resumable
CSV/JSONL/summary files from saved per-attempt `execution_result.json` files
after an interrupted writer left aggregate files corrupted.
"""

from __future__ import annotations

import json
import re
import shutil
import time
from collections import Counter
from pathlib import Path
from typing import Any

from silver.evaluation.track_b_full_official_eligibility import (
    FULL_MANIFEST,
    PHASE,
    PHASE_ROOT,
    classify_pair,
    read_jsonl,
    row_result,
    safe_rel,
    summarize_by_task,
    write_csv,
    write_json,
    write_jsonl,
)


RETRY_RE = re.compile(r"_retry(\d+)_")


def now_tag() -> str:
    return time.strftime("%Y%m%d_%H%M%S")


def is_valid_json_file(path: Path) -> bool:
    try:
        json.loads(path.read_text(encoding="utf-8-sig"))
        return True
    except Exception:
        return False


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def attempt_dirs(case_dir: Path, repeat_name: str) -> list[Path]:
    dirs = [case_dir / repeat_name]
    retry_dirs: list[tuple[int, Path]] = []
    if case_dir.exists():
        for path in case_dir.iterdir():
            if not path.is_dir() or not path.name.startswith(f"{repeat_name}_retry"):
                continue
            match = RETRY_RE.search(path.name)
            if match:
                retry_dirs.append((int(match.group(1)), path))
    dirs.extend(path for _, path in sorted(retry_dirs))
    return dirs


def final_attempt_result(case_dir: Path, repeat_name: str) -> dict[str, Any] | None:
    final: dict[str, Any] | None = None
    for attempt_dir in attempt_dirs(case_dir, repeat_name):
        result_path = attempt_dir / "execution_result.json"
        if not result_path.exists() or not is_valid_json_file(result_path):
            continue
        final = read_json(result_path)
    return final


def archive_if_present(path: Path, archive_root: Path) -> None:
    if not path.exists():
        return
    archive_root.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, archive_root / path.name)


def main() -> int:
    manifest = read_jsonl(FULL_MANIFEST)
    result_path = PHASE_ROOT / "metrics" / f"{PHASE}_official_results.csv"
    ledger_path = PHASE_ROOT / "manifest" / f"{PHASE}_official_eligibility_ledger.jsonl"
    summary_path = PHASE_ROOT / "metrics" / f"{PHASE}_official_summary.json"
    by_task_path = PHASE_ROOT / "metrics" / f"{PHASE}_summary_by_task.csv"

    archive_root = PHASE_ROOT / "archived_corrupted_aggregates" / now_tag()
    for path in [result_path, ledger_path, summary_path, by_task_path]:
        archive_if_present(path, archive_root)

    rows: list[dict[str, Any]] = []
    first_incomplete: dict[str, Any] | None = None
    for index, manifest_row in enumerate(manifest, start=1):
        case_dir = PHASE_ROOT / "data" / PHASE / safe_rel(manifest_row)
        rep1 = final_attempt_result(case_dir, "official_repeat_1")
        rep2 = final_attempt_result(case_dir, "official_repeat_2")
        if rep1 is None or rep2 is None:
            first_incomplete = {
                "sample_index": index,
                "sample_id": manifest_row["sample_id"],
                "case_dir": str(case_dir),
                "has_repeat_1": rep1 is not None,
                "has_repeat_2": rep2 is not None,
            }
            break
        rows.append(row_result(index, manifest_row, rep1, rep2, case_dir))

    counts = Counter(row["official_status"] for row in rows)
    summary = {
        "time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "phase": PHASE,
        "completed": len(rows) >= len(manifest),
        "recovered_from_case_artifacts": True,
        "archived_corrupted_aggregate_dir": str(archive_root),
        "total_manifest_rows": len(manifest),
        "processed_rows": len(rows),
        "remaining_rows": len(manifest) - len(rows),
        "official_eligible": sum(1 for row in rows if row.get("official_eligible") is True),
        "status_counts": dict(sorted(counts.items())),
        "first_incomplete": first_incomplete,
    }

    write_csv(result_path, rows)
    write_jsonl(ledger_path, rows)
    write_json(summary_path, summary)
    write_csv(by_task_path, summarize_by_task(rows))

    report_path = PHASE_ROOT / "metrics" / f"{PHASE}_aggregate_repair_report.json"
    write_json(report_path, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
