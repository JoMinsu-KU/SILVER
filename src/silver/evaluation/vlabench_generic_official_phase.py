# -*- coding: utf-8 -*-
"""Track B-2 runner for S0 generic-compatible VLABench samples.

This phase uses only samples that passed the static compatibility audit as
`S0_static_generic_compatible`. It still does not assume execution success:
each sample must pass two independent VLABench official-expert runs to become
eligible for Track C.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import shlex
import subprocess
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path("silver/results/silver-official-guided-evaluation-20260516")
TRACK_A_ROOT = Path("silver/results/track_a_vlabench_planning_20260510")
AUDIT_LEDGER = ROOT / "track_b" / "compatibility_audit" / "manifest" / "vlabench_compatibility_ledger.jsonl"
PHASE_ROOT = ROOT / "track_b" / "generic_compatible_official"
VLABENCH_CONDA_ENV = os.environ.get("VLABENCH_CONDA_ENV", "vlabench310")
VLABENCH_WSL_DISTRO = os.environ.get("VLABENCH_WSL_DISTRO", "Ubuntu")
VLABENCH_WSL_USER = os.environ.get("VLABENCH_WSL_USER", "")


def now_iso() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def read_json(path: Path) -> Any:
    with open(native_path(path), "r", encoding="utf-8-sig") as f:
        return json.load(f)


def native_path(path: Path) -> str:
    if os.name != "nt":
        return str(path)
    absolute = path if path.is_absolute() else Path.cwd() / path
    text = str(absolute)
    if text.startswith("\\\\?\\"):
        return text
    return "\\\\?\\" + text


def path_exists(path: Path) -> bool:
    return os.path.exists(native_path(path))


def write_text_atomic(path: Path, text: str, encoding: str = "utf-8") -> None:
    os.makedirs(native_path(path.parent), exist_ok=True)
    tmp = path.with_name(f"{path.name}.tmp")
    with open(native_path(tmp), "w", encoding=encoding) as f:
        f.write(text)
    os.replace(native_path(tmp), native_path(path))


def write_json(path: Path, obj: Any) -> None:
    write_text_atomic(path, json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def write_log(path: Path, text: str) -> None:
    write_text_atomic(path, text, encoding="utf-8")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path_exists(path):
        return rows
    with open(native_path(path), "r", encoding="utf-8-sig") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    text = "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows)
    write_text_atomic(path, text, encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    tmp = path.with_name(f"{path.name}.tmp")
    os.makedirs(native_path(path.parent), exist_ok=True)
    with open(native_path(tmp), "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    os.replace(native_path(tmp), native_path(path))


def get_wsl_workspace() -> str:
    cwd = Path.cwd()
    if os.name != "nt":
        return cwd.as_posix()
    last_error = ""
    for attempt in range(3):
        proc = subprocess.run(
            ["wsl", "-d", VLABENCH_WSL_DISTRO, "-u", VLABENCH_WSL_USER, "--", "wslpath", "-a", str(cwd)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if proc.returncode == 0 and proc.stdout.strip():
            return proc.stdout.strip()
        last_error = (proc.stdout or "") + (proc.stderr or "")
        time.sleep(1 + attempt)
    drive = cwd.drive.rstrip(":").lower()
    if drive and len(drive) == 1:
        manual = f"/mnt/{drive}/" + cwd.as_posix().split(":/", 1)[-1]
        return manual
    raise RuntimeError(f"wslpath failed and manual fallback is unavailable: {last_error}")


def shell_quote(value: Any) -> str:
    return shlex.quote(str(value))


def normalize_posix_path(path: str | Path) -> str:
    return Path(str(path).replace("\\", "/")).as_posix()


def native_subprocess_args(cmd: str) -> list[str]:
    if os.name != "nt":
        return ["bash", "-lc", cmd]
    return ["wsl", "-d", VLABENCH_WSL_DISTRO, "-u", VLABENCH_WSL_USER, "--", "bash", "-lc", cmd]


def archive_corrupt_result(result_path: Path, log_path: Path) -> None:
    tag = time.strftime("%Y%m%d_%H%M%S")
    if path_exists(result_path):
        corrupt_path = result_path.with_name(f"{result_path.name}.corrupt_{tag}")
        try:
            os.replace(native_path(result_path), native_path(corrupt_path))
        except FileNotFoundError:
            pass
    if path_exists(log_path):
        log_archive = log_path.with_name(f"{log_path.name}.with_corrupt_result_{tag}")
        try:
            os.replace(native_path(log_path), native_path(log_archive))
        except FileNotFoundError:
            pass


def safe_rel(row: dict[str, Any]) -> Path:
    return Path(row["category"]) / row["task"] / row["example"]


def result_status(result: dict[str, Any]) -> str:
    status = result.get("execution_status")
    if status == "completed" and result.get("condition_success") is True:
        return "success"
    if status == "native_process_timeout":
        return "timeout"
    if status in {"exception", "native_process_crash"}:
        return "native_exception"
    if status == "expert_sequence_error":
        return "expert_sequence_error"
    if status == "completed" and result.get("condition_success") is False:
        return "condition_failure"
    return str(status or "unknown")


def classify_pair(rep1: dict[str, Any], rep2: dict[str, Any]) -> str:
    s1 = result_status(rep1)
    s2 = result_status(rep2)
    if s1 == "success" and s2 == "success":
        return "B0_official_eligible"
    if "timeout" in {s1, s2}:
        return "B4_timeout"
    if "native_exception" in {s1, s2}:
        return "B3_native_exception"
    if "expert_sequence_error" in {s1, s2}:
        return "B2_expert_sequence_error"
    if s1 != s2:
        return "B5_nondeterministic_mismatch"
    return "B1_condition_failure"


def run_native(row: dict[str, Any], out_dir: Path, timeout_s: int) -> dict[str, Any]:
    result_path = out_dir / "execution_result.json"
    log_path = out_dir / "orchestrator.log"
    os.makedirs(native_path(out_dir), exist_ok=True)
    if path_exists(result_path):
        try:
            result = read_json(result_path)
            result["orchestrator_status"] = "skipped_existing"
            return result
        except Exception:
            archive_corrupt_result(result_path, log_path)

    workspace = get_wsl_workspace()
    sample_dir = normalize_posix_path(row["local_dir"])
    out_dir_arg = normalize_posix_path(out_dir)
    cmd = (
        "source ~/miniforge3/etc/profile.d/conda.sh && "
        f"conda activate {shell_quote(VLABENCH_CONDA_ENV)} && "
        f"cd {shell_quote(workspace)} && "
        "export MUJOCO_GL=egl && "
        "export PYTHONDONTWRITEBYTECODE=1 && "
        f"(find ~/miniforge3/envs/{shell_quote(VLABENCH_CONDA_ENV)}/lib/python3.10 -name '*.pyc' -delete 2>/dev/null || true) && "
        "python -B silver/evaluation/vlabench_official_skill_executor.py "
        f"--sample-id {shell_quote(row['sample_id'])} "
        f"--category {shell_quote(row['category'])} "
        f"--task {shell_quote(row['task'])} "
        f"--example {shell_quote(row['example'])} "
        f"--sample-dir {shell_quote(sample_dir)} "
        f"--out-dir {shell_quote(out_dir_arg)} "
        "--mode 'official_expert'"
    )
    try:
        proc = subprocess.run(
            native_subprocess_args(cmd),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired as exc:
        write_log(log_path, (exc.stdout or "") + (exc.stderr or "") + f"\nTIMEOUT: {timeout_s}s\n")
        result = {
            "sample_id": row["sample_id"],
            "category": row["category"],
            "task": row["task"],
            "example": row["example"],
            "mode": "official_expert",
            "execution_status": "native_process_timeout",
            "condition_success": None,
            "failure_reason": f"Process exceeded {timeout_s} seconds.",
            "orchestrator_log": str(log_path),
            "completed_at": now_iso(),
        }
        write_json(result_path, result)
        return result

    write_log(log_path, (proc.stdout or "") + (proc.stderr or ""))
    if path_exists(result_path):
        try:
            result = read_json(result_path)
        except Exception as exc:
            archive_corrupt_result(result_path, log_path)
            result = {
                "sample_id": row["sample_id"],
                "category": row["category"],
                "task": row["task"],
                "example": row["example"],
                "mode": "official_expert",
                "execution_status": "native_process_crash",
                "condition_success": None,
                "orchestrator_returncode": proc.returncode,
                "orchestrator_log": str(log_path),
                "failure_reason": f"Corrupt execution_result.json could not be parsed: {exc}",
                "completed_at": now_iso(),
            }
            write_json(result_path, result)
            return result
        result["orchestrator_returncode"] = proc.returncode
        result["orchestrator_log"] = str(log_path)
        write_json(result_path, result)
        return result

    result = {
        "sample_id": row["sample_id"],
        "category": row["category"],
        "task": row["task"],
        "example": row["example"],
        "mode": "official_expert",
        "execution_status": "native_process_crash",
        "condition_success": None,
        "orchestrator_returncode": proc.returncode,
        "orchestrator_log": str(log_path),
        "failure_reason": "Process ended without execution_result.json.",
        "completed_at": now_iso(),
    }
    write_json(result_path, result)
    return result


def prepare(root: Path = ROOT) -> dict[str, Any]:
    ledger = read_jsonl(root / "track_b" / "compatibility_audit" / "manifest" / "vlabench_compatibility_ledger.jsonl")
    s0_rows = [row for row in ledger if row.get("static_status") == "S0_static_generic_compatible"]
    rows_by_task: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in s0_rows:
        rows_by_task[(row["category"], row["task"])].append(row)

    sanity_rows: list[dict[str, Any]] = []
    for (_, _), group in sorted(rows_by_task.items()):
        sanity_rows.extend(sorted(group, key=lambda r: r["example"])[:2])

    phase = root / "track_b" / "generic_compatible_official"
    write_jsonl(phase / "manifest" / "s0_generic_compatible_manifest.jsonl", s0_rows)
    write_jsonl(phase / "manifest" / "s0_task2_sanity_manifest.jsonl", sanity_rows)
    task_rows = [
        {"category": category, "task": task, "rows": len(group), "sanity_rows": min(2, len(group))}
        for (category, task), group in sorted(rows_by_task.items())
    ]
    write_csv(phase / "metrics" / "s0_task_counts.csv", task_rows)
    summary = {
        "time": now_iso(),
        "s0_rows": len(s0_rows),
        "s0_tasks": len(rows_by_task),
        "sanity_rows": len(sanity_rows),
        "manifest": str(phase / "manifest" / "s0_generic_compatible_manifest.jsonl"),
        "sanity_manifest": str(phase / "manifest" / "s0_task2_sanity_manifest.jsonl"),
    }
    write_json(phase / "metrics" / "prepare_summary.json", summary)
    return summary


def prepare_stable_from_sanity(root: Path = ROOT) -> dict[str, Any]:
    phase = root / "track_b" / "generic_compatible_official"
    stable_csv = phase / "metrics" / "s0_sanity_stable_tasks.csv"
    if not stable_csv.exists():
        raise SystemExit(f"stable task CSV missing: {stable_csv}")
    stable_tasks: set[tuple[str, str]] = set()
    with stable_csv.open("r", newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            stable_tasks.add((row["category"], row["task"]))
    s0_path = phase / "manifest" / "s0_generic_compatible_manifest.jsonl"
    if not s0_path.exists():
        prepare(root)
    s0_rows = read_jsonl(s0_path)
    stable_rows = [row for row in s0_rows if (row["category"], row["task"]) in stable_tasks]
    write_jsonl(phase / "manifest" / "s0_sanity_stable_task_manifest.jsonl", stable_rows)
    task_counts = Counter((row["category"], row["task"]) for row in stable_rows)
    write_csv(
        phase / "metrics" / "s0_sanity_stable_task_full_counts.csv",
        [{"category": k[0], "task": k[1], "rows": v} for k, v in sorted(task_counts.items())],
    )
    summary = {
        "time": now_iso(),
        "stable_tasks": len(stable_tasks),
        "stable_rows": len(stable_rows),
        "manifest": str(phase / "manifest" / "s0_sanity_stable_task_manifest.jsonl"),
    }
    write_json(phase / "metrics" / "stable_prepare_summary.json", summary)
    return summary


def run_rows(root: Path, rows: list[dict[str, Any]], phase_name: str, timeout_s: int, max_rows: int | None = None) -> dict[str, Any]:
    phase = root / "track_b" / "generic_compatible_official"
    selected = rows if max_rows is None else rows[:max_rows]
    results: list[dict[str, Any]] = []
    partial_path = phase / "metrics" / f"{phase_name}_official_results_partial.csv"
    for index, row in enumerate(selected, start=1):
        case_dir = phase / "data" / phase_name / safe_rel(row)
        rep1 = run_native(row, case_dir / "official_repeat_1", timeout_s)
        rep2 = run_native(row, case_dir / "official_repeat_2", timeout_s)
        status = classify_pair(rep1, rep2)
        result_row = {
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
        }
        results.append(result_row)
        write_csv(partial_path, results)

    result_path = phase / "metrics" / f"{phase_name}_official_results.csv"
    ledger_path = phase / "manifest" / f"{phase_name}_official_eligibility_ledger.jsonl"
    write_csv(result_path, results)
    write_jsonl(ledger_path, results)
    summary = summarize_results(results, phase_name)
    write_json(phase / "metrics" / f"{phase_name}_official_summary.json", summary)
    write_csv(phase / "metrics" / f"{phase_name}_summary_by_task.csv", summarize_by_task(results))
    return summary


def summarize_results(results: list[dict[str, Any]], phase_name: str) -> dict[str, Any]:
    counts = Counter(row["official_status"] for row in results)
    return {
        "time": now_iso(),
        "phase": phase_name,
        "rows": len(results),
        "official_eligible": sum(1 for row in results if row["official_eligible"]),
        "status_counts": dict(sorted(counts.items())),
    }


def summarize_by_task(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in results:
        grouped[(row["category"], row["task"])].append(row)
    out: list[dict[str, Any]] = []
    for (category, task), group in sorted(grouped.items()):
        counts = Counter(row["official_status"] for row in group)
        out.append({"category": category, "task": task, "rows": len(group), **dict(sorted(counts.items()))})
    return out


def run_sanity(root: Path, timeout_s: int, max_rows: int | None) -> dict[str, Any]:
    sanity_path = root / "track_b" / "generic_compatible_official" / "manifest" / "s0_task2_sanity_manifest.jsonl"
    if not sanity_path.exists():
        prepare(root)
    return run_rows(root, read_jsonl(sanity_path), "s0_task2_sanity", timeout_s, max_rows)


def run_full(root: Path, timeout_s: int, max_rows: int | None) -> dict[str, Any]:
    manifest_path = root / "track_b" / "generic_compatible_official" / "manifest" / "s0_generic_compatible_manifest.jsonl"
    if not manifest_path.exists():
        prepare(root)
    return run_rows(root, read_jsonl(manifest_path), "s0_full_4000", timeout_s, max_rows)


def run_stable_full(root: Path, timeout_s: int, max_rows: int | None) -> dict[str, Any]:
    manifest_path = root / "track_b" / "generic_compatible_official" / "manifest" / "s0_sanity_stable_task_manifest.jsonl"
    if not manifest_path.exists():
        prepare_stable_from_sanity(root)
    return run_rows(root, read_jsonl(manifest_path), "s0_stable_task_full", timeout_s, max_rows)


def run_aligned_reset_probe(root: Path, timeout_s: int, max_rows: int | None) -> dict[str, Any]:
    manifest_path = root / "track_b" / "generic_compatible_official" / "manifest" / "s0_sanity_stable_task_manifest.jsonl"
    if not manifest_path.exists():
        prepare_stable_from_sanity(root)
    return run_rows(root, read_jsonl(manifest_path), "s0_stable_task_full_aligned_reset", timeout_s, max_rows)


def run_aligned_reset_full(root: Path, timeout_s: int, max_rows: int | None) -> dict[str, Any]:
    manifest_path = root / "track_b" / "generic_compatible_official" / "manifest" / "s0_generic_compatible_manifest.jsonl"
    if not manifest_path.exists():
        prepare(root)
    return run_rows(root, read_jsonl(manifest_path), "s0_full_4000_aligned_reset", timeout_s, max_rows)


def run_preload_target_probe(root: Path, timeout_s: int, max_rows: int | None) -> dict[str, Any]:
    manifest_path = root / "track_b" / "generic_compatible_official" / "manifest" / "s0_sanity_stable_task_manifest.jsonl"
    if not manifest_path.exists():
        prepare_stable_from_sanity(root)
    return run_rows(root, read_jsonl(manifest_path), "s0_stable_task_full_preload_target", timeout_s, max_rows)


def run_preload_target_full(root: Path, timeout_s: int, max_rows: int | None) -> dict[str, Any]:
    manifest_path = root / "track_b" / "generic_compatible_official" / "manifest" / "s0_generic_compatible_manifest.jsonl"
    if not manifest_path.exists():
        prepare(root)
    return run_rows(root, read_jsonl(manifest_path), "s0_full_4000_preload_target", timeout_s, max_rows)


def run_balanced_preload_probe(root: Path, timeout_s: int, examples_per_task: int, max_rows: int | None) -> dict[str, Any]:
    manifest_path = root / "track_b" / "generic_compatible_official" / "manifest" / "s0_generic_compatible_manifest.jsonl"
    if not manifest_path.exists():
        prepare(root)
    rows = read_jsonl(manifest_path)
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[(row["category"], row["task"])].append(row)
    selected: list[dict[str, Any]] = []
    for key in sorted(grouped):
        selected.extend(sorted(grouped[key], key=lambda r: r["example"])[:examples_per_task])
    write_jsonl(
        root / "track_b" / "generic_compatible_official" / "manifest" / f"s0_balanced_task{examples_per_task}_manifest.jsonl",
        selected,
    )
    return run_rows(root, selected, f"s0_balanced_task{examples_per_task}_preload_target", timeout_s, max_rows)


def write_plan_docs(root: Path) -> dict[str, Any]:
    phase = root / "track_b" / "generic_compatible_official"
    phase.mkdir(parents=True, exist_ok=True)
    doc = phase / "TRACK_B2_GENERIC_OFFICIAL_PLAN.md"
    doc.write_text(
        """# Track B-2 Generic-Compatible Official Execution 계획

## 현재 상황

Track B compatibility audit 결과, 전체 4,500개 중 4,000개가 `S0_static_generic_compatible`로 분류되었다. 이 그룹은 `operation_sequence.json`의 object/container id가 `env_config.json` component로 정적으로 매핑되며, target contract가 기본적으로 `str -> str` 구조다.

반면 400개는 task-specific adapter가 필요하고, 100개는 현재 VLABench loader와 env_config의 호환성 문제가 있다. 따라서 4,500개 전체를 무조건 같은 wrapper로 실행하지 않는다.

## 목표

1. 4,000개 S0 sample을 별도 manifest로 고정한다.
2. task별 2개 sanity set을 먼저 2-repeat 실행한다.
3. sanity set에서 발견되는 wrapper/runtime 문제를 안정화한다.
4. 안정화 이후 S0 4,000개 전체 official expert 2-repeat를 resume 가능하게 실행한다.
5. 2회 모두 성공한 sample만 Track C denominator 후보로 넘긴다.

## 금지 사항

- 데이터셋 원본 수정 금지
- mock success 금지
- 실행하지 않은 sample 성공 처리 금지
- timeout/crash를 Qwen planning 실패로 합산 금지

## 상태 taxonomy

- `B0_official_eligible`: 2회 모두 official expert condition success
- `B1_condition_failure`: 실행은 완료됐지만 condition 실패
- `B2_expert_sequence_error`: expert sequence 생성 실패
- `B3_native_exception`: native exception 또는 crash
- `B4_timeout`: timeout
- `B5_nondeterministic_mismatch`: repeat 간 결과 불일치

## Evidence

- S0 manifest: `manifest/s0_generic_compatible_manifest.jsonl`
- sanity manifest: `manifest/s0_task2_sanity_manifest.jsonl`
- sanity results: `metrics/s0_task2_sanity_official_results.csv`
- full results: `metrics/s0_full_4000_official_results.csv`
""",
        encoding="utf-8",
    )
    return {"time": now_iso(), "plan": str(doc)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Track B-2 generic-compatible official execution phase.")
    parser.add_argument(
        "command",
        choices=[
            "plan",
            "prepare",
            "sanity",
            "stable-prepare",
            "stable-full",
            "aligned-reset-probe",
            "aligned-reset-full",
            "preload-target-probe",
            "preload-target-full",
            "balanced-preload-probe",
            "full",
        ],
    )
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--timeout-s", type=int, default=300)
    parser.add_argument("--max-rows", type=int, default=None)
    parser.add_argument("--examples-per-task", type=int, default=5)
    args = parser.parse_args()

    if args.command == "plan":
        payload = write_plan_docs(args.root)
    elif args.command == "prepare":
        write_plan_docs(args.root)
        payload = prepare(args.root)
    elif args.command == "sanity":
        payload = run_sanity(args.root, args.timeout_s, args.max_rows)
    elif args.command == "stable-prepare":
        payload = prepare_stable_from_sanity(args.root)
    elif args.command == "stable-full":
        payload = run_stable_full(args.root, args.timeout_s, args.max_rows)
    elif args.command == "aligned-reset-probe":
        payload = run_aligned_reset_probe(args.root, args.timeout_s, args.max_rows)
    elif args.command == "aligned-reset-full":
        payload = run_aligned_reset_full(args.root, args.timeout_s, args.max_rows)
    elif args.command == "preload-target-probe":
        payload = run_preload_target_probe(args.root, args.timeout_s, args.max_rows)
    elif args.command == "preload-target-full":
        payload = run_preload_target_full(args.root, args.timeout_s, args.max_rows)
    elif args.command == "balanced-preload-probe":
        payload = run_balanced_preload_probe(args.root, args.timeout_s, args.examples_per_task, args.max_rows)
    elif args.command == "full":
        payload = run_full(args.root, args.timeout_s, args.max_rows)
    else:
        raise AssertionError(args.command)

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
