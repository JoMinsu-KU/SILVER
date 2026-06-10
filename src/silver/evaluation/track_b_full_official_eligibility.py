# -*- coding: utf-8 -*-
"""Full Track B official expert eligibility runner.

This runner is for the real Track B full pass, not smoke/probe. It processes
the S0 generic-compatible manifest, runs VLABench official expert twice per
sample, retries only native crash/timeout/exception attempts, and writes a
resumable artifact ledger.
"""

from __future__ import annotations

import argparse
import csv
import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from silver.evaluation.vlabench_generic_official_phase import (
    ROOT,
    classify_pair,
    prepare,
    read_jsonl,
    run_native,
    safe_rel,
    write_csv,
    write_json,
    write_jsonl,
)


PHASE = "s0_full_4000_preload_target"
PHASE_ROOT = ROOT / "track_b" / "generic_compatible_official"
FULL_MANIFEST = PHASE_ROOT / "manifest" / "s0_generic_compatible_manifest.jsonl"


def now_iso() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def log(message: str) -> None:
    print(f"[{now_iso()}] {message}", flush=True)


def native_retryable(result: dict[str, Any]) -> bool:
    return result.get("execution_status") in {"native_process_crash", "exception", "native_process_timeout"}


def run_attempt_with_retry(
    row: dict[str, Any],
    attempt_dir: Path,
    timeout_s: int,
    max_retries: int,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    retry_rows: list[dict[str, Any]] = []
    result = run_native(row, attempt_dir, timeout_s)
    retry_index = 0
    while native_retryable(result) and retry_index < max_retries:
        retry_index += 1
        reason = str(result.get("execution_status") or "unknown")
        retry_dir = attempt_dir.with_name(f"{attempt_dir.name}_retry{retry_index}_{reason}")
        retry_rows.append(
            {
                "time": now_iso(),
                "sample_id": row["sample_id"],
                "attempt_dir": str(attempt_dir),
                "retry_dir": str(retry_dir),
                "retry_index": retry_index,
                "reason": reason,
            }
        )
        log(f"    retry {retry_index}/{max_retries} reason={reason} -> {retry_dir}")
        result = run_native(row, retry_dir, timeout_s)
    return result, retry_rows


def row_result(
    index: int,
    row: dict[str, Any],
    rep1: dict[str, Any],
    rep2: dict[str, Any],
    case_dir: Path,
) -> dict[str, Any]:
    status = classify_pair(rep1, rep2)
    return {
        "sample_index": index,
        "sample_id": row["sample_id"],
        "category": row["category"],
        "task": row["task"],
        "example": row["example"],
        "gt_skill_pattern": row.get("gt_skill_pattern", ""),
        "official_status": status,
        "official_eligible": status == "B0_official_eligible",
        "repeat_1_status": rep1.get("execution_status"),
        "repeat_1_success": rep1.get("condition_success"),
        "repeat_2_status": rep2.get("execution_status"),
        "repeat_2_success": rep2.get("condition_success"),
        "case_dir": str(case_dir),
        "updated_at": now_iso(),
    }


def read_existing_results(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    rows: dict[str, dict[str, Any]] = {}
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            rows[row["sample_id"]] = row
    return rows


def summarize(results: list[dict[str, Any]], total_manifest_rows: int, started_at: str, completed: bool) -> dict[str, Any]:
    counts = Counter(row["official_status"] for row in results)
    return {
        "time": now_iso(),
        "started_at": started_at,
        "phase": PHASE,
        "completed": completed,
        "total_manifest_rows": total_manifest_rows,
        "processed_rows": len(results),
        "remaining_rows": total_manifest_rows - len(results),
        "official_eligible": sum(
            1
            for row in results
            if str(row.get("official_eligible")).lower() == "true" or row.get("official_eligible") is True
        ),
        "status_counts": dict(sorted(counts.items())),
    }


def summarize_by_task(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in results:
        grouped[(str(row["category"]), str(row["task"]))].append(row)
    out: list[dict[str, Any]] = []
    for (category, task), group in sorted(grouped.items()):
        counts = Counter(str(row["official_status"]) for row in group)
        out.append({"category": category, "task": task, "rows": len(group), **dict(sorted(counts.items()))})
    return out


def write_progress_doc(summary: dict[str, Any], result_path: Path, retry_path: Path) -> None:
    doc = PHASE_ROOT / "TRACK_B_FULL_PROGRESS.md"
    lines = [
        "# Track B Full Official Expert 진행 문서",
        "",
        f"최근 갱신: {now_iso()} KST",
        "",
        "## 목적",
        "",
        "S0_static_generic_compatible 4,000개 sample에 대해 VLABench official expert 2-repeat 실행을 수행하고, Track C/D main denominator로 사용할 official eligible sample을 확정한다.",
        "",
        "## 실행 원칙",
        "",
        "- mock/synthetic 결과를 만들지 않는다.",
        "- 원본 VLABench public dataset 파일을 수정하지 않는다.",
        "- native crash/exception/timeout은 성공으로 처리하지 않는다.",
        "- retry는 별도 attempt artifact로 보존하고 retry 이력은 JSONL로 남긴다.",
        "- 완료 metric은 저장된 CSV/JSON artifact에서만 계산한다.",
        "",
        "## 현재 집계",
        "",
        f"- 전체 S0 manifest rows: {summary['total_manifest_rows']}",
        f"- 처리 완료 rows: {summary['processed_rows']}",
        f"- 남은 rows: {summary['remaining_rows']}",
        f"- official eligible rows: {summary['official_eligible']}",
        f"- completed: {summary['completed']}",
        "",
        "## 상태별 count",
        "",
    ]
    for key, value in summary["status_counts"].items():
        lines.append(f"- {key}: {value}")
    lines.extend(
        [
            "",
            "## Evidence",
            "",
            f"- full results CSV: `{result_path}`",
            f"- full ledger JSONL: `{PHASE_ROOT / 'manifest' / (PHASE + '_official_eligibility_ledger.jsonl')}`",
            f"- summary JSON: `{PHASE_ROOT / 'metrics' / (PHASE + '_official_summary.json')}`",
            f"- retry log: `{retry_path}`",
            f"- per-case data: `{PHASE_ROOT / 'data' / PHASE}`",
        ]
    )
    doc.write_text("\n".join(lines) + "\n", encoding="utf-8")


def estimate_eta(start_time: float, processed_this_run: int, remaining_rows: int) -> str:
    if processed_this_run <= 0:
        return "unknown"
    avg_s = (time.time() - start_time) / processed_this_run
    eta_s = avg_s * remaining_rows
    eta_h = eta_s / 3600
    return f"{eta_h:.1f}h at current average ({avg_s:.1f}s/sample)"


def run_full(
    timeout_s: int,
    max_retries: int,
    max_runtime_s: int | None,
    start_index: int,
    limit: int | None,
    log_every: int,
) -> dict[str, Any]:
    if not FULL_MANIFEST.exists():
        log(f"Manifest not found. Preparing Track B manifest: {FULL_MANIFEST}")
        prepare(ROOT)
    manifest = read_jsonl(FULL_MANIFEST)
    total = len(manifest)
    if start_index < 1:
        raise SystemExit("--start-index is 1-based and must be >= 1")
    selected = manifest[start_index - 1 :]
    if limit is not None:
        selected = selected[:limit]

    result_path = PHASE_ROOT / "metrics" / f"{PHASE}_official_results.csv"
    ledger_path = PHASE_ROOT / "manifest" / f"{PHASE}_official_eligibility_ledger.jsonl"
    retry_path = PHASE_ROOT / "metrics" / f"{PHASE}_retry_log.jsonl"
    existing = read_existing_results(result_path)
    initial_existing_count = len(existing)
    try:
        retry_rows: list[dict[str, Any]] = read_jsonl(retry_path)
    except Exception as exc:
        archive_dir = PHASE_ROOT / "archived_corrupted_aggregates" / time.strftime("%Y%m%d_%H%M%S")
        archive_dir.mkdir(parents=True, exist_ok=True)
        if retry_path.exists():
            retry_path.replace(archive_dir / retry_path.name)
        retry_rows = []
        log(f"Archived unreadable retry log and continuing with an empty retry ledger: {exc}")
    started_at = now_iso()
    t0 = time.time()

    log(
        "Track B full run started "
        f"(phase={PHASE}, total_manifest_rows={total}, already_completed={len(existing)}, "
        f"timeout_s={timeout_s}, max_retries={max_retries}, start_index={start_index}, limit={limit})"
    )
    log(f"Results CSV: {result_path}")
    log(f"Summary JSON: {PHASE_ROOT / 'metrics' / f'{PHASE}_official_summary.json'}")

    skipped_since_log = 0
    for offset, row in enumerate(selected, start=start_index):
        if row["sample_id"] in existing:
            skipped_since_log += 1
            if log_every > 0 and skipped_since_log >= log_every:
                log(f"SKIP existing rows={skipped_since_log}; latest sample_index={offset}/{total}")
                skipped_since_log = 0
            continue
        if max_runtime_s is not None and time.time() - t0 >= max_runtime_s:
            log(f"Max runtime reached after {time.time() - t0:.1f}s. Checkpointing and exiting cleanly.")
            break

        case_dir = PHASE_ROOT / "data" / PHASE / safe_rel(row)
        sample_t0 = time.time()
        processed_before = len(existing)
        log(
            f"START sample_index={offset}/{total} processed={processed_before}/{total} "
            f"sample_id={row['sample_id']} task={row.get('task')} pattern={row.get('gt_skill_pattern', '')}"
        )

        log(f"  repeat_1 start -> {case_dir / 'official_repeat_1'}")
        rep1, retries1 = run_attempt_with_retry(row, case_dir / "official_repeat_1", timeout_s, max_retries)
        log(
            f"  repeat_1 done status={rep1.get('execution_status')} "
            f"condition_success={rep1.get('condition_success')} retries={len(retries1)}"
        )

        log(f"  repeat_2 start -> {case_dir / 'official_repeat_2'}")
        rep2, retries2 = run_attempt_with_retry(row, case_dir / "official_repeat_2", timeout_s, max_retries)
        log(
            f"  repeat_2 done status={rep2.get('execution_status')} "
            f"condition_success={rep2.get('condition_success')} retries={len(retries2)}"
        )

        retry_rows.extend(retries1)
        retry_rows.extend(retries2)
        existing[row["sample_id"]] = row_result(offset, row, rep1, rep2, case_dir)

        rows = list(existing.values())
        rows.sort(key=lambda r: int(r["sample_index"]))
        write_csv(result_path, rows)
        write_jsonl(ledger_path, rows)
        write_jsonl(retry_path, retry_rows)
        summary = summarize(rows, total, started_at, completed=len(rows) >= total)
        write_json(PHASE_ROOT / "metrics" / f"{PHASE}_official_summary.json", summary)
        write_csv(PHASE_ROOT / "metrics" / f"{PHASE}_summary_by_task.csv", summarize_by_task(rows))
        write_progress_doc(summary, result_path, retry_path)

        processed_this_run = len(existing) - initial_existing_count
        log(
            f"DONE sample_index={offset}/{total} status={existing[row['sample_id']]['official_status']} "
            f"elapsed_s={time.time() - sample_t0:.1f} processed={summary['processed_rows']}/{total} "
            f"eligible={summary['official_eligible']} remaining={summary['remaining_rows']} "
            f"eta={estimate_eta(t0, processed_this_run, summary['remaining_rows'])}"
        )

    rows = list(existing.values())
    rows.sort(key=lambda r: int(r["sample_index"]))
    summary = summarize(rows, total, started_at, completed=len(rows) >= total)
    write_csv(result_path, rows)
    write_jsonl(ledger_path, rows)
    write_jsonl(retry_path, retry_rows)
    write_json(PHASE_ROOT / "metrics" / f"{PHASE}_official_summary.json", summary)
    write_csv(PHASE_ROOT / "metrics" / f"{PHASE}_summary_by_task.csv", summarize_by_task(rows))
    write_progress_doc(summary, result_path, retry_path)
    log(
        "Track B full run checkpoint complete "
        f"(processed={summary['processed_rows']}/{summary['total_manifest_rows']}, "
        f"eligible={summary['official_eligible']}, completed={summary['completed']})"
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Run full Track B official expert eligibility for S0 4,000 samples.")
    parser.add_argument("--timeout-s", type=int, default=300)
    parser.add_argument("--max-retries", type=int, default=2)
    parser.add_argument("--max-runtime-s", type=int, default=None)
    parser.add_argument("--start-index", type=int, default=1)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument(
        "--log-every",
        type=int,
        default=100,
        help="Print one skip message after this many already-completed rows. Active samples always log.",
    )
    args = parser.parse_args()
    payload = run_full(
        args.timeout_s,
        args.max_retries,
        args.max_runtime_s,
        args.start_index,
        args.limit,
        args.log_every,
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
