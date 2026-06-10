# -*- coding: utf-8 -*-
"""Rerun Track B cases whose previous artifacts show environment-level errors.

This is not a smoke test and does not fabricate any result. It archives the
previous per-case artifacts, removes the affected rows from the aggregate files,
and reruns the exact same samples with the repaired runtime.
"""

from __future__ import annotations

import argparse
import csv
import json
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
    read_existing_results,
    row_result,
    run_attempt_with_retry,
    summarize,
    summarize_by_task,
    write_progress_doc,
)
from silver.evaluation.vlabench_generic_official_phase import (
    read_jsonl,
    safe_rel,
    write_csv,
    write_json,
    write_jsonl,
)


TARGET_SAMPLE_IDS = [
    "CommenSence/add_condiment_common_sense/example20",
    "CommenSence/add_condiment_common_sense/example31",
    "CommenSence/add_condiment_common_sense/example38",
    "CommenSence/insert_flower_common_sense/example33",
    "CommenSence/insert_flower_common_sense/example45",
    "CommenSence/insert_flower_common_sense/example52",
    "CommenSence/insert_flower_common_sense/example82",
    "CommenSence/select_chemistry_tube_common_sense/example29",
    "CommenSence/select_chemistry_tube_common_sense/example37",
    "CommenSence/select_chemistry_tube_common_sense/example38",
    "CommenSence/select_chemistry_tube_common_sense/example8",
]


def now_iso() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def log(message: str) -> None:
    print(f"[{now_iso()}] {message}", flush=True)


def read_csv_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def sample_index(row: dict[str, Any]) -> int:
    return int(row["sample_index"])


def archive_case_dir(case_dir: Path, archive_root: Path) -> str | None:
    if not case_dir.exists():
        return None
    archive_target = archive_root / case_dir.relative_to(PHASE_ROOT / "data" / PHASE)
    archive_target.parent.mkdir(parents=True, exist_ok=True)
    if archive_target.exists():
        suffix = time.strftime("%H%M%S")
        archive_target = archive_target.with_name(f"{archive_target.name}_{suffix}")
    shutil.move(str(case_dir), str(archive_target))
    return str(archive_target)


def write_rerun_doc(report: dict[str, Any]) -> None:
    doc = PHASE_ROOT.parent / "TRACK_B_ENV_SUSPECT_RERUN_20260518.md"
    lines = [
        "# Track B 환경 의심 케이스 재실행 보고서 - 2026-05-18",
        "",
        "## 목적",
        "",
        "`orchestrator.log`에서 환경성 오류가 확인된 11개 sample의 기존 결과를 main eligibility 판단에서 제외하고, 수정된 런타임에서 동일 sample을 재실행했다.",
        "",
        "## 원칙",
        "",
        "- mock/synthetic result를 만들지 않는다.",
        "- 기존 데이터셋 파일은 수정하지 않는다.",
        "- 기존 실행 artifact는 삭제하지 않고 archive로 이동한다.",
        "- 재실행 결과만 aggregate CSV/JSONL에 반영한다.",
        "",
        "## 실행 요약",
        "",
        f"- 시작 시각: {report['started_at']}",
        f"- 종료 시각: {report['completed_at']}",
        f"- 대상 sample 수: {report['target_count']}",
        f"- 재실행 완료 sample 수: {report['rerun_count']}",
        "",
        "## 재실행 후 상태 분포",
        "",
    ]
    for key, value in report["rerun_status_counts"].items():
        lines.append(f"- {key}: {value}")
    lines.extend(
        [
            "",
            "## 대상별 결과",
            "",
            "| sample_index | sample_id | old_status | new_status | repeat_1 | repeat_2 | archive |",
            "|---:|---|---|---|---|---|---|",
        ]
    )
    for row in report["rerun_rows"]:
        lines.append(
            "| {sample_index} | `{sample_id}` | {old_status} | {official_status} | {repeat_1_status}/{repeat_1_success} | {repeat_2_status}/{repeat_2_success} | `{archive_path}` |".format(
                **row
            )
        )
    lines.extend(
        [
            "",
            "## 재집계 상태",
            "",
            f"- processed_rows: {report['summary']['processed_rows']} / {report['summary']['total_manifest_rows']}",
            f"- official_eligible: {report['summary']['official_eligible']}",
            f"- remaining_rows: {report['summary']['remaining_rows']}",
            "",
            "## Evidence",
            "",
            f"- results CSV: `{report['result_path']}`",
            f"- ledger JSONL: `{report['ledger_path']}`",
            f"- retry log: `{report['retry_path']}`",
            f"- archived old artifacts: `{report['archive_root']}`",
        ]
    )
    doc.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Rerun Track B environment-suspect cases.")
    parser.add_argument("--timeout-s", type=int, default=300)
    parser.add_argument("--max-retries", type=int, default=2)
    args = parser.parse_args()

    started_at = now_iso()
    result_path = PHASE_ROOT / "metrics" / f"{PHASE}_official_results.csv"
    ledger_path = PHASE_ROOT / "manifest" / f"{PHASE}_official_eligibility_ledger.jsonl"
    retry_path = PHASE_ROOT / "metrics" / f"{PHASE}_retry_log.jsonl"
    archive_root = PHASE_ROOT / "archived_invalid_runs" / ("env_suspect_rerun_" + time.strftime("%Y%m%d_%H%M%S"))

    manifest = read_jsonl(FULL_MANIFEST)
    manifest_by_id = {row["sample_id"]: (index, row) for index, row in enumerate(manifest, start=1)}
    missing = [sid for sid in TARGET_SAMPLE_IDS if sid not in manifest_by_id]
    if missing:
        raise SystemExit(f"Target samples not found in manifest: {missing}")

    existing = read_existing_results(result_path)
    old_rows_by_id = {row["sample_id"]: row for row in read_csv_rows(result_path)}
    retry_rows = [row for row in read_jsonl(retry_path) if row.get("sample_id") not in set(TARGET_SAMPLE_IDS)]

    for sid in TARGET_SAMPLE_IDS:
        existing.pop(sid, None)

    rerun_rows: list[dict[str, Any]] = []
    for sid in TARGET_SAMPLE_IDS:
        index, row = manifest_by_id[sid]
        case_dir = PHASE_ROOT / "data" / PHASE / safe_rel(row)
        archived = archive_case_dir(case_dir, archive_root)
        old_status = old_rows_by_id.get(sid, {}).get("official_status", "not_in_aggregate")

        log(f"RERUN sample_index={index} sample_id={sid} old_status={old_status}")
        log(f"  archived_old_case_dir={archived}")
        log(f"  repeat_1 start -> {case_dir / 'official_repeat_1'}")
        rep1, retries1 = run_attempt_with_retry(row, case_dir / "official_repeat_1", args.timeout_s, args.max_retries)
        log(f"  repeat_1 done status={rep1.get('execution_status')} success={rep1.get('condition_success')} retries={len(retries1)}")
        log(f"  repeat_2 start -> {case_dir / 'official_repeat_2'}")
        rep2, retries2 = run_attempt_with_retry(row, case_dir / "official_repeat_2", args.timeout_s, args.max_retries)
        log(f"  repeat_2 done status={rep2.get('execution_status')} success={rep2.get('condition_success')} retries={len(retries2)}")

        retry_rows.extend(retries1)
        retry_rows.extend(retries2)
        new_row = row_result(index, row, rep1, rep2, case_dir)
        existing[sid] = new_row
        rerun_rows.append(
            {
                **new_row,
                "old_status": old_status,
                "archive_path": archived or "",
            }
        )
        log(f"  rerun status={new_row['official_status']}")

    rows = list(existing.values())
    rows.sort(key=sample_index)
    summary = summarize(rows, len(manifest), started_at, completed=len(rows) >= len(manifest))
    write_csv(result_path, rows)
    write_jsonl(ledger_path, rows)
    write_jsonl(retry_path, retry_rows)
    write_json(PHASE_ROOT / "metrics" / f"{PHASE}_official_summary.json", summary)
    write_csv(PHASE_ROOT / "metrics" / f"{PHASE}_summary_by_task.csv", summarize_by_task(rows))
    write_progress_doc(summary, result_path, retry_path)

    report = {
        "started_at": started_at,
        "completed_at": now_iso(),
        "target_count": len(TARGET_SAMPLE_IDS),
        "rerun_count": len(rerun_rows),
        "rerun_status_counts": dict(Counter(row["official_status"] for row in rerun_rows)),
        "rerun_rows": rerun_rows,
        "summary": summary,
        "result_path": str(result_path),
        "ledger_path": str(ledger_path),
        "retry_path": str(retry_path),
        "archive_root": str(archive_root),
    }
    write_json(PHASE_ROOT / "metrics" / "env_suspect_rerun_20260518_summary.json", report)
    write_rerun_doc(report)
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
