# -*- coding: utf-8 -*-
"""Track C Qwen-guided official expert execution.

This runner uses the archived Track A/B artifacts as the only source of truth:

- Track A: Qwen P2 planning outputs and public VLABench sample files.
- Track B: official-expert eligibility ledger.

It does not read the old Dropbox `silver/results` Track B folder and it never
creates synthetic execution results.
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

from silver.evaluation.vlabench_entity_registry import build_entity_registry
from silver.evaluation.vlabench_executor_adapter import convert_sequence_to_executor_plan, sequence_from_parsed_output


CONFIG_PATH = Path(os.environ.get("SILVER_DATA_ROOTS_CONFIG", "config/data_roots.example.json"))
DEFAULT_RESULT_ROOT = Path(os.environ.get("SILVER_TRACK_C_ROOT", "data/track_c_rerun"))
VLABENCH_CONDA_ENV = os.environ.get("VLABENCH_CONDA_ENV", "vlabench310_repaired").strip()
VLABENCH_WSL_DISTRO = os.environ.get("VLABENCH_WSL_DISTRO", "Ubuntu").strip()
VLABENCH_WSL_USER = os.environ.get("VLABENCH_WSL_USER", "").strip()
VLABENCH_MUJOCO_GL = os.environ.get("VLABENCH_MUJOCO_GL", "egl").strip()


def now_iso() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


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


def read_text(path: Path) -> str:
    with open(native_path(path), "r", encoding="utf-8-sig", errors="replace") as f:
        return f.read()


def read_json(path: Path) -> Any:
    return json.loads(read_text(path))


def replace_with_retry(src: Path, dst: Path, *, attempts: int = 30, delay_s: float = 0.5) -> None:
    last_error: Exception | None = None
    for _ in range(attempts):
        try:
            os.replace(native_path(src), native_path(dst))
            return
        except PermissionError as exc:
            last_error = exc
            time.sleep(delay_s)
    raise PermissionError(f"Failed to replace {src} -> {dst} after {attempts} attempts: {last_error}")


def write_text(path: Path, text: str, encoding: str = "utf-8") -> None:
    os.makedirs(native_path(path.parent), exist_ok=True)
    tmp = path.with_name(f"{path.name}.tmp")
    with open(native_path(tmp), "w", encoding=encoding) as f:
        f.write(text)
    replace_with_retry(tmp, path)


def write_json(path: Path, obj: Any) -> None:
    write_text(path, json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path_exists(path):
        return rows
    with open(native_path(path), "r", encoding="utf-8-sig", errors="replace") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    write_text(path, "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    os.makedirs(native_path(path.parent), exist_ok=True)
    tmp = path.with_name(f"{path.name}.tmp")
    with open(native_path(tmp), "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    replace_with_retry(tmp, path)


def load_config() -> dict[str, Any]:
    cfg = read_json(CONFIG_PATH)
    return {
        **cfg,
        "track_a_root": Path(cfg["track_a_root"]),
        "track_b_root": Path(cfg["track_b_root"]),
        "track_b_final_data_root": Path(cfg["track_b_final_data_root"]),
    }


def boolish(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() == "true"


def sample_rel(row: dict[str, Any]) -> Path:
    return Path(row["category"]) / row["task"] / row["example"]


def sample_id_from_row(row: dict[str, Any]) -> str:
    return f"{row['category']}/{row['task']}/{row['example']}"


def archive_track_a_sample_dir(track_a_root: Path, row: dict[str, Any]) -> Path:
    return track_a_root / "data" / sample_rel(row)


def archive_track_b_case_dir(track_b_final_data_root: Path, row: dict[str, Any]) -> Path:
    return track_b_final_data_root / sample_rel(row)


def build_track_a_index(track_a_root: Path) -> dict[str, dict[str, Any]]:
    rows = read_jsonl(track_a_root / "manifest" / "vlabench_sample_manifest.jsonl")
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        sample_id = row.get("sample_id") or sample_id_from_row(row)
        sample_dir = archive_track_a_sample_dir(track_a_root, row)
        fixed = {
            **row,
            "sample_id": sample_id,
            "archive_sample_dir": str(sample_dir),
            "input.png": str(sample_dir / "input.png"),
            "input_mask.png": str(sample_dir / "input_mask.png"),
            "instruction.txt": str(sample_dir / "instruction.txt"),
            "operation_sequence.json": str(sample_dir / "operation_sequence.json"),
            "env_config.json": str(sample_dir / "env_config.json"),
        }
        out[sample_id] = fixed
    return out


def get_wsl_workspace() -> str:
    cwd = Path.cwd()
    if os.name != "nt":
        return cwd.as_posix()
    proc = subprocess.run(
        ["wsl", "-d", VLABENCH_WSL_DISTRO, "-u", VLABENCH_WSL_USER, "--", "wslpath", "-a", str(cwd)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode == 0 and proc.stdout.strip():
        return proc.stdout.strip()
    drive = cwd.drive.rstrip(":").lower()
    if drive and len(drive) == 1:
        return f"/mnt/{drive}/" + cwd.as_posix().split(":/", 1)[-1]
    raise RuntimeError((proc.stdout or "") + (proc.stderr or ""))


def to_wsl_path(path: Path) -> str:
    absolute = path if path.is_absolute() else Path.cwd() / path
    if os.name != "nt":
        return absolute.as_posix()
    proc = subprocess.run(
        ["wsl", "-d", VLABENCH_WSL_DISTRO, "-u", VLABENCH_WSL_USER, "--", "wslpath", "-a", str(absolute)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode == 0 and proc.stdout.strip():
        return proc.stdout.strip()
    drive = absolute.drive.rstrip(":").lower()
    if drive and len(drive) == 1:
        return f"/mnt/{drive}/" + absolute.as_posix().split(":/", 1)[-1]
    raise RuntimeError((proc.stdout or "") + (proc.stderr or ""))


def shell_quote(value: Any) -> str:
    return shlex.quote(str(value))


def native_subprocess_args(cmd: str) -> list[str]:
    if os.name != "nt":
        return ["bash", "-lc", cmd]
    return ["wsl", "-d", VLABENCH_WSL_DISTRO, "-u", VLABENCH_WSL_USER, "--", "bash", "-lc", cmd]


def init_docs(root: Path) -> None:
    (root / "manifest").mkdir(parents=True, exist_ok=True)
    (root / "metrics").mkdir(parents=True, exist_ok=True)
    (root / "data").mkdir(parents=True, exist_ok=True)
    (root / "report").mkdir(parents=True, exist_ok=True)
    write_text(
        root / "TRACK_C_PLAN.md",
        f"""# Track C 계획: Qwen-guided official expert execution

작성 시각: {now_iso()}

## 목표

Track B에서 official expert 2회 반복 실행을 모두 통과한 sample만 사용하여 Qwen P2 planning이 실제 VLABench 실행 성공으로 이어지는지 측정한다.

## 입력 원본

- Track A 기준 원본: `C:\\SILVER\\archive\\silver_track_ab_20260523\\track_a_vlabench_planning_20260510`
- Track B 기준 원본: `C:\\SILVER\\archive\\silver_track_ab_20260523\\silver-official-guided-evaluation-20260516\\track_b\\generic_compatible_official`

## 실행 방식

1. Track B `B0_official_eligible` sample만 Track C denominator로 사용한다.
2. Track A P2 parsed output에서 Qwen skill sequence를 읽는다.
3. VLABench env_config의 entity registry에 Qwen object/target을 매핑한다.
4. 변환 가능한 경우 `qwen_guided_expert` 모드로 VLABench official expert/task template에 Qwen target을 주입해 실행한다.
5. 변환 실패, entity mapping 실패, native exception, timeout, condition failure를 분리 기록한다.

## 금지

- GT operation sequence를 Qwen plan 보정에 사용하지 않는다.
- 변환 실패를 execution failure로 섞지 않는다.
- 실행하지 않은 sample을 성공으로 처리하지 않는다.
- 작업 폴더의 과거 `silver/results` Track B 부분본을 읽지 않는다.
""",
    )
    write_text(
        root / "TRACK_C_PROGRESS.md",
        f"""# Track C 진행 문서

작성 시각: {now_iso()}

아직 실행 전이다.
""",
    )


def runtime_preflight(root: Path) -> dict[str, Any]:
    workspace = get_wsl_workspace()
    code = (
        "import json, sys; "
        "mods=['numpy','mujoco','dm_control','open3d','VLABench']; "
        "out={'executable':sys.executable,'modules':{}}; "
        "\nfor m in mods:\n"
        "    try:\n"
        "        __import__(m); out['modules'][m]=True\n"
        "    except Exception as e:\n"
        "        out['modules'][m]=repr(e)\n"
        "print(json.dumps(out))\n"
    )
    cmd = (
        "source ~/miniforge3/etc/profile.d/conda.sh && "
        f"conda activate {shell_quote(VLABENCH_CONDA_ENV)} && "
        f"cd {shell_quote(workspace)} && "
        f"export MUJOCO_GL={shell_quote(VLABENCH_MUJOCO_GL)} && "
        "export PYOPENGL_PLATFORM=egl && "
        "export MESA_D3D12_DEFAULT_ADAPTER_NAME=NVIDIA && "
        "export GALLIUM_DRIVER=d3d12 && "
        "unset LIBGL_ALWAYS_SOFTWARE && "
        "export PYTHONDONTWRITEBYTECODE=1 && "
        f"python -B -c {shell_quote(code)}"
    )
    proc = subprocess.run(native_subprocess_args(cmd), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
    parsed = None
    for line in proc.stdout.splitlines():
        if line.strip().startswith("{"):
            parsed = json.loads(line)
    ok = proc.returncode == 0 and isinstance(parsed, dict) and all(value is True for value in parsed.get("modules", {}).values())
    payload = {
        "time": now_iso(),
        "ok": ok,
        "wsl_distro": VLABENCH_WSL_DISTRO,
        "wsl_user": VLABENCH_WSL_USER,
        "conda_env": VLABENCH_CONDA_ENV,
        "workspace": workspace,
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "parsed": parsed,
    }
    write_json(root / "metrics" / "runtime_preflight.json", payload)
    return payload


def prepare_manifest(root: Path) -> dict[str, Any]:
    cfg = load_config()
    track_a_index = build_track_a_index(cfg["track_a_root"])
    track_b_ledger = read_jsonl(cfg["track_b_root"] / "manifest" / "s0_full_4000_preload_target_official_eligibility_ledger.jsonl")
    eligible = [row for row in track_b_ledger if boolish(row.get("official_eligible"))]
    rows: list[dict[str, Any]] = []
    conversion_rows: list[dict[str, Any]] = []
    missing_rows: list[dict[str, Any]] = []
    required = [
        "input.png",
        "input_mask.png",
        "instruction.txt",
        "operation_sequence.json",
        "env_config.json",
        "raw_output_P2.json",
        "parsed_output_P2.json",
        "validation_P2.json",
    ]
    for row in eligible:
        sample_id = row["sample_id"]
        if sample_id not in track_a_index:
            missing_rows.append({"sample_id": sample_id, "reason": "missing_in_track_a_manifest"})
            continue
        arow = track_a_index[sample_id]
        sample_dir = Path(arow["archive_sample_dir"])
        missing = [name for name in required if not path_exists(sample_dir / name)]
        if missing:
            missing_rows.append({"sample_id": sample_id, "reason": "missing_track_a_files", "missing": missing})
            continue
        env_cfg = read_json(sample_dir / "env_config.json")
        registry = build_entity_registry(env_cfg)
        parsed = read_json(sample_dir / "parsed_output_P2.json")
        qwen_sequence = sequence_from_parsed_output(parsed)
        plan, validation = convert_sequence_to_executor_plan(sample_id, qwen_sequence, registry, "qwen_p2_track_c")
        out_row = {
            "sample_index": row.get("sample_index"),
            "sample_id": sample_id,
            "category": row["category"],
            "task": row["task"],
            "example": row["example"],
            "gt_skill_pattern": row.get("gt_skill_pattern", ""),
            "track_a_sample_dir": str(sample_dir),
            "track_b_case_dir": str(archive_track_b_case_dir(cfg["track_b_final_data_root"], row)),
            "qwen_conversion_ok": validation["conversion_ok"],
            "qwen_conversion_errors": ";".join(validation["conversion_errors"]),
            "qwen_skill_sequence": ">".join(str(x) for x in validation["skill_sequence"]),
            "planned_case_dir": str(root / "data" / sample_rel(row)),
        }
        rows.append(out_row)
        conversion_rows.append(
            {
                "sample_id": sample_id,
                "category": row["category"],
                "task": row["task"],
                "example": row["example"],
                "conversion_ok": validation["conversion_ok"],
                "conversion_errors": ";".join(validation["conversion_errors"]),
                "skill_sequence": ">".join(str(x) for x in validation["skill_sequence"]),
                "action_count": validation["action_count"],
            }
        )
        case_dir = root / "data" / sample_rel(row)
        write_json(case_dir / "qwen_p2_executor_plan.json", plan)
        write_json(case_dir / "qwen_p2_adapter_validation.json", validation)
        write_json(case_dir / "entity_registry.json", registry)
    write_jsonl(root / "manifest" / "qwen_guided_case_manifest.jsonl", rows)
    write_jsonl(root / "manifest" / "missing_track_c_inputs.jsonl", missing_rows)
    write_csv(root / "metrics" / "qwen_p2_conversion_by_case.csv", conversion_rows)
    summary = {
        "time": now_iso(),
        "track_b_eligible_rows": len(eligible),
        "track_c_manifest_rows": len(rows),
        "missing_input_rows": len(missing_rows),
        "qwen_conversion_ok": sum(1 for row in conversion_rows if row["conversion_ok"]),
        "qwen_conversion_failed": sum(1 for row in conversion_rows if not row["conversion_ok"]),
        "conversion_error_counts": dict(Counter(row["conversion_errors"] or "none" for row in conversion_rows)),
        "skill_sequence_counts": dict(Counter(row["skill_sequence"] for row in conversion_rows)),
    }
    write_json(root / "metrics" / "track_c_prepare_summary.json", summary)
    write_text(
        root / "TRACK_C_PROGRESS.md",
        f"""# Track C 진행 문서

## 준비 단계 완료

- 완료 시각: {now_iso()}
- Track B eligible rows: {summary['track_b_eligible_rows']}
- Track C manifest rows: {summary['track_c_manifest_rows']}
- Missing input rows: {summary['missing_input_rows']}
- Qwen P2 conversion OK: {summary['qwen_conversion_ok']}
- Qwen P2 conversion failed: {summary['qwen_conversion_failed']}

Evidence:

- `manifest/qwen_guided_case_manifest.jsonl`
- `metrics/qwen_p2_conversion_by_case.csv`
- `metrics/track_c_prepare_summary.json`
""",
    )
    return summary


def classify_track_c_status(validation: dict[str, Any], result: dict[str, Any]) -> str:
    if not validation.get("conversion_ok"):
        errors = ";".join(validation.get("conversion_errors", []))
        if "unsupported_skill" in errors:
            return "C4_unsupported_qwen_skill"
        if "unmapped_component" in errors or "ambiguous_component" in errors:
            return "C3_entity_mapping_failure"
        return "C2_qwen_conversion_failure"
    if result.get("execution_status") == "native_process_timeout":
        return "C6_timeout"
    if result.get("execution_status") in {"exception", "native_process_crash"}:
        return "C5_native_exception"
    if result.get("condition_success") is True:
        return "C0_qwen_guided_success"
    return "C1_qwen_guided_condition_failure"


def run_native_qwen_guided(row: dict[str, Any], out_dir: Path, plan_path: Path, timeout_s: int) -> dict[str, Any]:
    result_path = out_dir / "execution_result.json"
    log_path = out_dir / "orchestrator.log"
    os.makedirs(native_path(out_dir), exist_ok=True)
    if path_exists(result_path):
        result = read_json(result_path)
        result["orchestrator_status"] = "skipped_existing"
        return result
    workspace = get_wsl_workspace()
    sample_dir = Path(row["track_a_sample_dir"])
    cmd = (
        "source ~/miniforge3/etc/profile.d/conda.sh && "
        f"conda activate {shell_quote(VLABENCH_CONDA_ENV)} && "
        f"cd {shell_quote(workspace)} && "
        f"export MUJOCO_GL={shell_quote(VLABENCH_MUJOCO_GL)} && "
        "export PYOPENGL_PLATFORM=egl && "
        "export MESA_D3D12_DEFAULT_ADAPTER_NAME=NVIDIA && "
        "export GALLIUM_DRIVER=d3d12 && "
        "unset LIBGL_ALWAYS_SOFTWARE && "
        "export PYTHONDONTWRITEBYTECODE=1 && "
        "python -B silver/evaluation/vlabench_official_skill_executor.py "
        f"--sample-id {shell_quote(row['sample_id'])} "
        f"--category {shell_quote(row['category'])} "
        f"--task {shell_quote(row['task'])} "
        f"--example {shell_quote(row['example'])} "
        f"--sample-dir {shell_quote(to_wsl_path(sample_dir))} "
        f"--out-dir {shell_quote(to_wsl_path(out_dir))} "
        "--mode qwen_guided_expert "
        f"--plan-path {shell_quote(to_wsl_path(plan_path))}"
    )
    try:
        proc = subprocess.run(native_subprocess_args(cmd), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout_s)
    except subprocess.TimeoutExpired as exc:
        write_text(log_path, (exc.stdout or "") + (exc.stderr or "") + f"\nTIMEOUT: {timeout_s}s\n")
        result = {
            "sample_id": row["sample_id"],
            "category": row["category"],
            "task": row["task"],
            "example": row["example"],
            "mode": "qwen_guided_expert",
            "execution_status": "native_process_timeout",
            "condition_success": None,
            "failure_reason": f"Process exceeded {timeout_s} seconds.",
            "orchestrator_log": str(log_path),
            "completed_at": now_iso(),
        }
        write_json(result_path, result)
        return result
    write_text(log_path, (proc.stdout or "") + (proc.stderr or ""))
    if path_exists(result_path):
        result = read_json(result_path)
        result["orchestrator_returncode"] = proc.returncode
        result["orchestrator_log"] = str(log_path)
        write_json(result_path, result)
        return result
    result = {
        "sample_id": row["sample_id"],
        "category": row["category"],
        "task": row["task"],
        "example": row["example"],
        "mode": "qwen_guided_expert",
        "execution_status": "native_process_crash",
        "condition_success": None,
        "orchestrator_returncode": proc.returncode,
        "orchestrator_log": str(log_path),
        "failure_reason": "Process ended without execution_result.json.",
        "completed_at": now_iso(),
    }
    write_json(result_path, result)
    return result


def run_execution(root: Path, *, start_index: int, limit: int | None, timeout_s: int) -> dict[str, Any]:
    manifest = read_jsonl(root / "manifest" / "qwen_guided_case_manifest.jsonl")
    selected = manifest[start_index - 1 :]
    if limit is not None:
        selected = selected[:limit]
    results_path = root / "metrics" / "qwen_guided_execution_results.csv"
    existing: dict[str, dict[str, Any]] = {}
    if path_exists(results_path):
        with open(native_path(results_path), "r", encoding="utf-8-sig", newline="", errors="replace") as f:
            for row in csv.DictReader(f):
                existing[row["sample_id"]] = row
    results = list(existing.values())
    for pos, row in enumerate(selected, start=start_index):
        case_dir = root / "data" / sample_rel(row)
        validation_path = case_dir / "qwen_p2_adapter_validation.json"
        plan_path = case_dir / "qwen_p2_executor_plan.json"
        validation = read_json(validation_path)
        if not validation.get("conversion_ok"):
            out_dir = case_dir / "qwen_guided_execution"
            result = {
                "sample_id": row["sample_id"],
                "category": row["category"],
                "task": row["task"],
                "example": row["example"],
                "mode": "qwen_guided_expert",
                "execution_status": "not_run_conversion_failed",
                "condition_success": None,
                "failure_reason": ";".join(validation.get("conversion_errors", [])),
                "completed_at": now_iso(),
            }
            write_json(out_dir / "execution_result.json", result)
        else:
            result = run_native_qwen_guided(row, case_dir / "qwen_guided_execution", plan_path, timeout_s)
        status = classify_track_c_status(validation, result)
        result_row = {
            "run_position": pos,
            "sample_id": row["sample_id"],
            "category": row["category"],
            "task": row["task"],
            "example": row["example"],
            "gt_skill_pattern": row.get("gt_skill_pattern", ""),
            "qwen_skill_sequence": row.get("qwen_skill_sequence", ""),
            "qwen_conversion_ok": validation.get("conversion_ok"),
            "track_c_status": status,
            "execution_status": result.get("execution_status"),
            "condition_success": result.get("condition_success"),
            "progress_score": result.get("progress_score"),
            "intention_score": result.get("intention_score"),
            "elapsed_s": result.get("elapsed_s"),
            "case_dir": str(case_dir),
            "updated_at": now_iso(),
        }
        existing[row["sample_id"]] = result_row
        results = list(existing.values())
        write_csv(results_path, results)
        write_json(root / "metrics" / "qwen_guided_execution_checkpoint.json", summarize_results(results, root))
        print(
            f"[{now_iso()}] Track C {pos}/{len(manifest)} "
            f"{row['sample_id']} status={status} exec={result_row['execution_status']} success={result_row['condition_success']}",
            flush=True,
        )
    summary = summarize_results(results, root)
    write_json(root / "metrics" / "qwen_guided_execution_summary.json", summary)
    write_jsonl(root / "manifest" / "qwen_guided_execution_ledger.jsonl", results)
    write_csv(root / "metrics" / "qwen_guided_success_by_task.csv", summarize_by_task(results))
    write_csv(root / "metrics" / "qwen_guided_failure_taxonomy.csv", [{"status": k, "count": v} for k, v in summary["status_counts"].items()])
    update_completion_report(root, summary)
    return summary


def summarize_by_task(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    for row in rows:
        grouped[(row["category"], row["task"])]["rows"] += 1
        grouped[(row["category"], row["task"])][row["track_c_status"]] += 1
    return [{"category": key[0], "task": key[1], **dict(counts)} for key, counts in sorted(grouped.items())]


def summarize_results(rows: list[dict[str, Any]], root: Path) -> dict[str, Any]:
    status_counts = Counter(row["track_c_status"] for row in rows)
    return {
        "time": now_iso(),
        "result_root": str(root),
        "completed_rows": len(rows),
        "success": status_counts.get("C0_qwen_guided_success", 0),
        "status_counts": dict(status_counts),
    }


def update_completion_report(root: Path, summary: dict[str, Any]) -> None:
    write_text(
        root / "report" / "TRACK_C_COMPLETION_REPORT.md",
        f"""# Track C 완료/진행 보고

작성 시각: {now_iso()}

## 현재 집계

- Completed rows: {summary['completed_rows']}
- Qwen-guided success: {summary['success']}
- Status counts: `{json.dumps(summary['status_counts'], ensure_ascii=False)}`

## Evidence

- `manifest/qwen_guided_execution_ledger.jsonl`
- `metrics/qwen_guided_execution_results.csv`
- `metrics/qwen_guided_execution_summary.json`
- `metrics/qwen_guided_success_by_task.csv`
- `metrics/qwen_guided_failure_taxonomy.csv`
""",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Track C Qwen-guided official expert execution.")
    parser.add_argument("--root", type=Path, default=DEFAULT_RESULT_ROOT)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init")
    sub.add_parser("preflight")
    sub.add_parser("prepare")
    run_p = sub.add_parser("run")
    run_p.add_argument("--start-index", type=int, default=1)
    run_p.add_argument("--limit", type=int, default=None)
    run_p.add_argument("--timeout-s", type=int, default=300)
    sub.add_parser("summarize")
    args = parser.parse_args()
    root: Path = args.root
    if args.cmd == "init":
        init_docs(root)
        print(json.dumps({"root": str(root), "initialized": True}, ensure_ascii=False, indent=2))
    elif args.cmd == "preflight":
        payload = runtime_preflight(root)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0 if payload["ok"] else 1
    elif args.cmd == "prepare":
        init_docs(root)
        payload = prepare_manifest(root)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    elif args.cmd == "run":
        payload = run_execution(root, start_index=args.start_index, limit=args.limit, timeout_s=args.timeout_s)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    elif args.cmd == "summarize":
        rows = read_jsonl(root / "manifest" / "qwen_guided_execution_ledger.jsonl")
        payload = summarize_results(rows, root)
        write_json(root / "metrics" / "qwen_guided_execution_summary.json", payload)
        update_completion_report(root, payload)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
