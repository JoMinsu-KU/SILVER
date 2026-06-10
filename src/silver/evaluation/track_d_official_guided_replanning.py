"""Track D official-guided failure-aware replanning pipeline.

This script uses only saved Track C artifacts. It does not synthesize results,
does not read GT operation sequences for replanning, and records every result as
an artifact. The main Track D condition is R3: failure image + symptom log.
"""

from __future__ import annotations

import argparse
import base64
import csv
import json
import os
import time
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from silver.evaluation.track_c_official_guided_execution import (
    classify_track_c_status,
    run_native_qwen_guided,
    summarize_results,
    write_csv,
    write_json,
    write_jsonl,
)
from silver.evaluation.vlabench_executor_adapter import convert_sequence_to_executor_plan, sequence_from_parsed_output
from silver.evaluation.vlabench_plan_evaluator import extract_json, validate_prediction


TRACK_C_ROOT = Path(os.environ.get("SILVER_TRACK_C_ROOT", "data/track_c_rerun"))
TRACK_D_ROOT = Path(os.environ.get("SILVER_TRACK_D_ROOT", "data/track_d_rerun"))
BASE_URL = os.environ.get("QWEN_BASE_URL", "http://127.0.0.1:8000/v1")
MODEL = os.environ.get("QWEN_MODEL", "Qwen/Qwen3-VL-8B-Instruct")


def now_iso() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def read_csv(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", newline="", errors="replace") as f:
        return list(csv.DictReader(f))


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8-sig")


def image_to_data_url(path: Path) -> str:
    b64 = base64.b64encode(path.read_bytes()).decode("utf-8")
    return f"data:image/png;base64,{b64}"


def sample_rel(row: dict[str, Any]) -> Path:
    return Path(row["category"]) / row["task"] / row["example"]


def case_dir(root: Path, row: dict[str, Any]) -> Path:
    return root / "data" / sample_rel(row)


def boolish(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text == "true":
        return True
    if text == "false":
        return False
    return None


def model_preflight(base_url: str = BASE_URL) -> dict[str, Any]:
    req = urllib.request.Request(base_url.rstrip("/") + "/models", method="GET")
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def chat_completion(base_url: str, model: str, messages: list[dict[str, Any]], max_tokens: int = 1024) -> dict[str, Any]:
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0,
        "max_tokens": max_tokens,
    }
    req = urllib.request.Request(
        base_url.rstrip("/") + "/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=240) as resp:
        return json.loads(resp.read().decode("utf-8"))


def assistant_text(raw: dict[str, Any]) -> str:
    try:
        return raw["choices"][0]["message"]["content"]
    except Exception:
        return ""


def track_c_indices() -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    result_rows = read_csv(TRACK_C_ROOT / "metrics" / "qwen_guided_execution_results.csv")
    manifest_rows = read_jsonl(TRACK_C_ROOT / "manifest" / "qwen_guided_case_manifest.jsonl")
    return {row["sample_id"]: row for row in result_rows}, {row["sample_id"]: row for row in manifest_rows}


def status_set(status: str) -> str:
    if status == "C1_qwen_guided_condition_failure":
        return "primary_c1_condition_failure"
    if status in {"C2_qwen_conversion_failure", "C3_entity_mapping_failure", "C4_unsupported_qwen_skill"}:
        return "secondary_diagnostic"
    return "not_track_d_failure"


def prepare(root: Path = TRACK_D_ROOT) -> dict[str, Any]:
    root.mkdir(parents=True, exist_ok=True)
    (root / "manifest").mkdir(parents=True, exist_ok=True)
    (root / "metrics").mkdir(parents=True, exist_ok=True)
    (root / "report").mkdir(parents=True, exist_ok=True)

    results_by_id, manifest_by_id = track_c_indices()
    rows: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []
    for sample_id, result in sorted(results_by_id.items(), key=lambda kv: int(kv[1]["run_position"])):
        status = result["track_c_status"]
        dset = status_set(status)
        if dset == "not_track_d_failure":
            continue
        mrow = manifest_by_id.get(sample_id)
        if not mrow:
            missing.append({"sample_id": sample_id, "reason": "missing_track_c_manifest"})
            continue
        cdir = Path(result["case_dir"])
        required = ["qwen_p2_executor_plan.json", "qwen_p2_adapter_validation.json", "entity_registry.json"]
        missing_files = [name for name in required if not (cdir / name).exists()]
        if status == "C1_qwen_guided_condition_failure":
            for name in ["qwen_guided_execution/execution_result.json", "qwen_guided_execution/final_mosaic.png", "qwen_guided_execution/orchestrator.log"]:
                if not (cdir / name).exists():
                    missing_files.append(name)
        if missing_files:
            missing.append({"sample_id": sample_id, "reason": "missing_track_c_files", "missing": missing_files})
            continue
        out = {
            "run_position": result["run_position"],
            "sample_id": sample_id,
            "category": result["category"],
            "task": result["task"],
            "example": result["example"],
            "track_c_status": status,
            "track_d_set": dset,
            "gt_skill_pattern": result.get("gt_skill_pattern", ""),
            "qwen_skill_sequence": result.get("qwen_skill_sequence", ""),
            "track_a_sample_dir": mrow["track_a_sample_dir"],
            "track_c_case_dir": result["case_dir"],
            "track_d_case_dir": str(case_dir(root, result)),
            "initial_execution_status": result.get("execution_status", ""),
            "initial_condition_success": result.get("condition_success", ""),
            "initial_progress_score": result.get("progress_score", ""),
            "initial_intention_score": result.get("intention_score", ""),
        }
        rows.append(out)

        out_dir = case_dir(root, result)
        out_dir.mkdir(parents=True, exist_ok=True)
        write_json(out_dir / "track_d_case_manifest.json", out)
        write_json(out_dir / "initial_qwen_plan.json", read_json(cdir / "qwen_p2_executor_plan.json"))
        write_json(out_dir / "initial_adapter_validation.json", read_json(cdir / "qwen_p2_adapter_validation.json"))
        write_json(out_dir / "entity_registry.json", read_json(cdir / "entity_registry.json"))
        if (cdir / "qwen_guided_execution" / "execution_result.json").exists():
            write_json(out_dir / "initial_failure_execution_result.json", read_json(cdir / "qwen_guided_execution" / "execution_result.json"))

    primary = [row for row in rows if row["track_d_set"] == "primary_c1_condition_failure"]
    secondary = [row for row in rows if row["track_d_set"] == "secondary_diagnostic"]
    write_jsonl(root / "manifest" / "track_d_all_failure_cases.jsonl", rows)
    write_jsonl(root / "manifest" / "track_d_primary_c1_cases.jsonl", primary)
    write_jsonl(root / "manifest" / "track_d_secondary_diagnostic_cases.jsonl", secondary)
    write_jsonl(root / "manifest" / "track_d_missing_inputs.jsonl", missing)
    write_csv(root / "metrics" / "track_d_manifest_summary_by_status.csv", [{"track_c_status": k, "count": v} for k, v in Counter(row["track_c_status"] for row in rows).items()])

    summary = {
        "time": now_iso(),
        "track_c_root": str(TRACK_C_ROOT),
        "track_d_root": str(root),
        "all_failure_cases": len(rows),
        "primary_c1_cases": len(primary),
        "secondary_diagnostic_cases": len(secondary),
        "missing_input_cases": len(missing),
        "status_counts": dict(Counter(row["track_c_status"] for row in rows)),
    }
    write_json(root / "metrics" / "track_d_prepare_summary.json", summary)
    write_text(
        root / "TRACK_D_PROGRESS.md",
        f"""# Track D 진행 문서

## Step 0. 준비 완료

- 완료 시각: {now_iso()}
- 전체 실패 후보: {summary['all_failure_cases']}
- Primary C1 대상: {summary['primary_c1_cases']}
- Secondary diagnostic 대상: {summary['secondary_diagnostic_cases']}
- 누락 입력: {summary['missing_input_cases']}

Evidence:

- `manifest/track_d_all_failure_cases.jsonl`
- `manifest/track_d_primary_c1_cases.jsonl`
- `manifest/track_d_secondary_diagnostic_cases.jsonl`
- `metrics/track_d_prepare_summary.json`

Main comparison은 Primary C1 set에서 Same-plan Retry와 SILVER R3 Replan을 paired design으로 비교한다.
""",
    )
    return summary


def load_manifest(root: Path, set_name: str) -> list[dict[str, Any]]:
    if set_name == "primary":
        return read_jsonl(root / "manifest" / "track_d_primary_c1_cases.jsonl")
    if set_name == "secondary":
        return read_jsonl(root / "manifest" / "track_d_secondary_diagnostic_cases.jsonl")
    return read_jsonl(root / "manifest" / "track_d_all_failure_cases.jsonl")


def execution_status_from_result(validation: dict[str, Any], result: dict[str, Any]) -> str:
    return classify_track_c_status(validation, result)


def run_same_plan(root: Path = TRACK_D_ROOT, *, set_name: str = "primary", start: int = 1, limit: int | None = None, timeout_s: int = 300) -> dict[str, Any]:
    rows = load_manifest(root, set_name)
    selected = rows[start - 1 :]
    if limit is not None:
        selected = selected[:limit]
    out_rows: list[dict[str, Any]] = []
    for idx, row in enumerate(selected, start=start):
        ddir = case_dir(root, row)
        plan_path = ddir / "initial_qwen_plan.json"
        validation = read_json(ddir / "initial_adapter_validation.json")
        if not validation.get("conversion_ok"):
            out_dir = ddir / "same_plan_retry"
            result = {
                "sample_id": row["sample_id"],
                "category": row["category"],
                "task": row["task"],
                "example": row["example"],
                "mode": "same_plan_retry",
                "execution_status": "not_run_conversion_failed",
                "condition_success": None,
                "failure_reason": ";".join(validation.get("conversion_errors", [])),
                "completed_at": now_iso(),
            }
            write_json(out_dir / "execution_result.json", result)
        else:
            exec_row = {
                "sample_id": row["sample_id"],
                "category": row["category"],
                "task": row["task"],
                "example": row["example"],
                "track_a_sample_dir": row["track_a_sample_dir"],
            }
            result = run_native_qwen_guided(exec_row, ddir / "same_plan_retry", plan_path, timeout_s)
        status = execution_status_from_result(validation, result)
        out = {
            "run_position": row["run_position"],
            "sample_id": row["sample_id"],
            "track_c_status": row["track_c_status"],
            "track_d_set": row["track_d_set"],
            "same_plan_status": status,
            "same_plan_execution_status": result.get("execution_status"),
            "same_plan_success": result.get("condition_success"),
            "same_plan_progress_score": result.get("progress_score"),
            "same_plan_elapsed_s": result.get("elapsed_s"),
            "case_dir": str(ddir),
            "updated_at": now_iso(),
        }
        out_rows.append(out)
        print(f"[{now_iso()}] Same-plan {idx}/{len(rows)} {row['sample_id']} status={status} success={out['same_plan_success']}", flush=True)
    result_path = root / "metrics" / f"track_d_same_plan_retry_{set_name}_results.csv"
    existing = []
    if result_path.exists():
        existing = read_csv(result_path)
    by_id = {row["sample_id"]: row for row in existing}
    for row in out_rows:
        by_id[row["sample_id"]] = row
    merged = list(by_id.values())
    write_csv(result_path, merged)
    summary = {
        "time": now_iso(),
        "set": set_name,
        "completed_rows": len(merged),
        "success": sum(1 for row in merged if boolish(row.get("same_plan_success")) is True),
        "status_counts": dict(Counter(row["same_plan_status"] for row in merged)),
    }
    write_json(root / "metrics" / f"track_d_same_plan_retry_{set_name}_summary.json", summary)
    return summary


def stage_trace_summary(exec_result: dict[str, Any]) -> str:
    stages = exec_result.get("stage_results")
    if not isinstance(stages, list):
        return "No stage trace was available."
    parts = []
    for stage in stages[:8]:
        parts.append(
            f"stage {stage.get('stage_index')}: skill={stage.get('skill_name')}, "
            f"stage_success={stage.get('stage_success')}, task_success={stage.get('task_success')}, "
            f"error={stage.get('error')}"
        )
    return "\n".join(parts)


def symptom_log(row: dict[str, Any], exec_result: dict[str, Any], validation: dict[str, Any]) -> str:
    status = row["track_c_status"]
    if status == "C1_qwen_guided_condition_failure":
        return (
            "The initial Qwen plan was executed, but the task condition was not satisfied. "
            f"execution_status={exec_result.get('execution_status')}; "
            f"condition_success={exec_result.get('condition_success')}; "
            f"progress_score={exec_result.get('progress_score')}; "
            f"intention_score={exec_result.get('intention_score')}."
        )
    if status == "C2_qwen_conversion_failure":
        return "The initial Qwen output could not be converted into an executable plan: " + ";".join(validation.get("conversion_errors", []))
    if status == "C3_entity_mapping_failure":
        return "The initial Qwen output referenced an object or target that could not be mapped to the scene registry: " + ";".join(validation.get("conversion_errors", []))
    if status == "C4_unsupported_qwen_skill":
        return "The initial Qwen output proposed an unsupported skill: " + ";".join(validation.get("conversion_errors", []))
    return "The initial attempt failed."


def make_r3_prompt(row: dict[str, Any], ddir: Path) -> str:
    instruction_path = Path(row["track_a_sample_dir"]) / "instruction.txt"
    instruction = instruction_path.read_text(encoding="utf-8-sig").strip() if instruction_path.exists() else ""
    initial_plan = read_json(ddir / "initial_qwen_plan.json")
    validation = read_json(ddir / "initial_adapter_validation.json")
    exec_result = read_json(ddir / "initial_failure_execution_result.json") if (ddir / "initial_failure_execution_result.json").exists() else {}
    symptom = symptom_log(row, exec_result, validation)
    trace = stage_trace_summary(exec_result)
    allowed_schema = {
        "skill_sequence": [
            {
                "name": "pick | place | lift | pull | press | push | pour | insert",
                "params": {
                    "target_entity_name": "object name or numeric visible component id for pick/press",
                    "target_container_name": "container/target name or numeric visible component id for place/pull/push/pour/insert",
                },
            }
        ],
        "rationale_summary": "brief non-chain-of-thought explanation",
    }
    return (
        "You are revising a robot manipulation plan after a failed simulator execution.\n"
        "Return ONLY valid JSON. Do not include markdown.\n\n"
        "Rules:\n"
        "- Use only the allowed output schema.\n"
        "- Do not invent unsupported skills.\n"
        "- Do not copy the failed plan if the failure suggests a wrong object, target, or sequence.\n"
        "- Do not reveal chain-of-thought; use only a short rationale_summary.\n\n"
        f"Instruction:\n{instruction}\n\n"
        f"Initial Qwen executor plan:\n{json.dumps(initial_plan, ensure_ascii=False)}\n\n"
        f"Failure observation:\n{symptom}\n\n"
        f"Executed trace summary:\n{trace}\n\n"
        f"Allowed output schema:\n{json.dumps(allowed_schema, ensure_ascii=False, indent=2)}\n"
    )


def infer_r3(root: Path = TRACK_D_ROOT, *, set_name: str = "primary", start: int = 1, limit: int | None = None, base_url: str = BASE_URL, model: str = MODEL) -> dict[str, Any]:
    rows = load_manifest(root, set_name)
    selected = rows[start - 1 :]
    if limit is not None:
        selected = selected[:limit]
    out_rows: list[dict[str, Any]] = []
    for idx, row in enumerate(selected, start=start):
        ddir = case_dir(root, row)
        out_dir = ddir / "replan_R3"
        raw_path = out_dir / "raw_output.json"
        parsed_path = out_dir / "parsed_output.json"
        validation_path = out_dir / "adapter_validation.json"
        plan_path = out_dir / "executor_plan.json"
        if raw_path.exists() and parsed_path.exists() and validation_path.exists() and plan_path.exists():
            val = read_json(validation_path)
            out_rows.append({"sample_id": row["sample_id"], "replan_conversion_ok": val.get("conversion_ok"), "status": "skipped_existing"})
            continue
        prompt = make_r3_prompt(row, ddir)
        write_text(out_dir / "prompt_R3.txt", prompt)
        image_path = Path(row["track_c_case_dir"]) / "qwen_guided_execution" / "final_mosaic.png"
        if not image_path.exists():
            image_path = Path(row["track_a_sample_dir"]) / "input_mask.png"
        content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
        if image_path.exists():
            content.insert(0, {"type": "image_url", "image_url": {"url": image_to_data_url(image_path)}})
        try:
            raw = chat_completion(base_url, model, [{"role": "user", "content": content}])
            write_json(raw_path, raw)
            text = assistant_text(raw)
            parsed_json, parse_error = extract_json(text)
            parsed_payload = {"assistant_text": text, "parsed_json": parsed_json, "parse_error": parse_error}
            write_json(parsed_path, parsed_payload)
            schema_valid, schema_errors = validate_prediction(parsed_json)
            sequence = sequence_from_parsed_output(parsed_payload)
            registry = read_json(ddir / "entity_registry.json")
            plan, adapter_validation = convert_sequence_to_executor_plan(row["sample_id"], sequence, registry, "track_d_replan_R3")
            adapter_validation["schema_valid"] = schema_valid
            adapter_validation["schema_errors"] = schema_errors
            adapter_validation["parse_error"] = parse_error
            write_json(validation_path, adapter_validation)
            write_json(plan_path, plan)
            out = {
                "run_position": row["run_position"],
                "sample_id": row["sample_id"],
                "track_c_status": row["track_c_status"],
                "schema_valid": schema_valid,
                "parse_error": parse_error,
                "replan_conversion_ok": adapter_validation.get("conversion_ok"),
                "conversion_errors": ";".join(adapter_validation.get("conversion_errors", [])),
                "skill_sequence": ">".join(str(x) for x in adapter_validation.get("skill_sequence", [])),
                "status": "completed",
                "updated_at": now_iso(),
            }
        except Exception as exc:
            out = {
                "run_position": row["run_position"],
                "sample_id": row["sample_id"],
                "track_c_status": row["track_c_status"],
                "schema_valid": False,
                "parse_error": repr(exc),
                "replan_conversion_ok": False,
                "conversion_errors": "inference_exception",
                "skill_sequence": "",
                "status": "inference_exception",
                "updated_at": now_iso(),
            }
            write_json(out_dir / "inference_error.json", out)
        out_rows.append(out)
        print(f"[{now_iso()}] Replan R3 infer {idx}/{len(rows)} {row['sample_id']} conversion={out.get('replan_conversion_ok')} status={out.get('status')}", flush=True)
    result_path = root / "metrics" / f"track_d_replan_R3_inference_{set_name}_results.csv"
    existing = read_csv(result_path) if result_path.exists() else []
    by_id = {row["sample_id"]: row for row in existing}
    for row in out_rows:
        by_id[row["sample_id"]] = row
    merged = list(by_id.values())
    write_csv(result_path, merged)
    summary = {
        "time": now_iso(),
        "set": set_name,
        "completed_rows": len(merged),
        "conversion_ok": sum(1 for row in merged if boolish(row.get("replan_conversion_ok")) is True),
        "status_counts": dict(Counter(row["status"] for row in merged)),
    }
    write_json(root / "metrics" / f"track_d_replan_R3_inference_{set_name}_summary.json", summary)
    return summary


def run_replan_r3(root: Path = TRACK_D_ROOT, *, set_name: str = "primary", start: int = 1, limit: int | None = None, timeout_s: int = 300) -> dict[str, Any]:
    rows = load_manifest(root, set_name)
    selected = rows[start - 1 :]
    if limit is not None:
        selected = selected[:limit]
    out_rows: list[dict[str, Any]] = []
    for idx, row in enumerate(selected, start=start):
        ddir = case_dir(root, row)
        plan_path = ddir / "replan_R3" / "executor_plan.json"
        validation_path = ddir / "replan_R3" / "adapter_validation.json"
        if not plan_path.exists() or not validation_path.exists():
            result = {"execution_status": "not_run_missing_replan_plan", "condition_success": None}
            validation = {"conversion_ok": False, "conversion_errors": ["missing_replan_plan"]}
        else:
            validation = read_json(validation_path)
            if not validation.get("conversion_ok"):
                result = {
                    "sample_id": row["sample_id"],
                    "category": row["category"],
                    "task": row["task"],
                    "example": row["example"],
                    "mode": "replan_R3",
                    "execution_status": "not_run_conversion_failed",
                    "condition_success": None,
                    "failure_reason": ";".join(validation.get("conversion_errors", [])),
                    "completed_at": now_iso(),
                }
                write_json(ddir / "replan_R3_execution" / "execution_result.json", result)
            else:
                exec_row = {
                    "sample_id": row["sample_id"],
                    "category": row["category"],
                    "task": row["task"],
                    "example": row["example"],
                    "track_a_sample_dir": row["track_a_sample_dir"],
                }
                result = run_native_qwen_guided(exec_row, ddir / "replan_R3_execution", plan_path, timeout_s)
        status = execution_status_from_result(validation, result)
        out = {
            "run_position": row["run_position"],
            "sample_id": row["sample_id"],
            "track_c_status": row["track_c_status"],
            "track_d_set": row["track_d_set"],
            "replan_R3_status": status,
            "replan_R3_execution_status": result.get("execution_status"),
            "replan_R3_success": result.get("condition_success"),
            "replan_R3_progress_score": result.get("progress_score"),
            "replan_R3_elapsed_s": result.get("elapsed_s"),
            "case_dir": str(ddir),
            "updated_at": now_iso(),
        }
        out_rows.append(out)
        print(f"[{now_iso()}] Replan R3 exec {idx}/{len(rows)} {row['sample_id']} status={status} success={out['replan_R3_success']}", flush=True)
    result_path = root / "metrics" / f"track_d_replan_R3_execution_{set_name}_results.csv"
    existing = read_csv(result_path) if result_path.exists() else []
    by_id = {row["sample_id"]: row for row in existing}
    for row in out_rows:
        by_id[row["sample_id"]] = row
    merged = list(by_id.values())
    write_csv(result_path, merged)
    summary = {
        "time": now_iso(),
        "set": set_name,
        "completed_rows": len(merged),
        "success": sum(1 for row in merged if boolish(row.get("replan_R3_success")) is True),
        "status_counts": dict(Counter(row["replan_R3_status"] for row in merged)),
    }
    write_json(root / "metrics" / f"track_d_replan_R3_execution_{set_name}_summary.json", summary)
    return summary


def summarize(root: Path = TRACK_D_ROOT, *, set_name: str = "primary") -> dict[str, Any]:
    manifest = load_manifest(root, set_name)
    same_path = root / "metrics" / f"track_d_same_plan_retry_{set_name}_results.csv"
    replan_path = root / "metrics" / f"track_d_replan_R3_execution_{set_name}_results.csv"
    same = {row["sample_id"]: row for row in (read_csv(same_path) if same_path.exists() else [])}
    replan = {row["sample_id"]: row for row in (read_csv(replan_path) if replan_path.exists() else [])}
    rows = []
    for row in manifest:
        sid = row["sample_id"]
        srow = same.get(sid, {})
        rrow = replan.get(sid, {})
        same_success = boolish(srow.get("same_plan_success")) is True
        replan_success = boolish(rrow.get("replan_R3_success")) is True
        if replan_success and not same_success:
            attribution = "A3_or_A4_replan_recovered"
        elif same_success:
            attribution = "A1_same_plan_retry_recovered"
        else:
            attribution = "A0_no_recovery"
        rows.append(
            {
                "sample_id": sid,
                "track_c_status": row["track_c_status"],
                "same_plan_success": same_success,
                "replan_R3_success": replan_success,
                "same_plan_execution_status": srow.get("same_plan_execution_status"),
                "replan_R3_execution_status": rrow.get("replan_R3_execution_status"),
                "attribution": attribution,
                "case_dir": row["track_d_case_dir"],
            }
        )
    completed = [row for row in rows if row["sample_id"] in same and row["sample_id"] in replan]
    same_success_n = sum(1 for row in completed if row["same_plan_success"])
    replan_success_n = sum(1 for row in completed if row["replan_R3_success"])
    gain = None
    if completed:
        gain = replan_success_n / len(completed) - same_success_n / len(completed)
    write_csv(root / "metrics" / f"track_d_same_plan_vs_replan_R3_{set_name}.csv", rows)
    summary = {
        "time": now_iso(),
        "set": set_name,
        "manifest_cases": len(manifest),
        "paired_completed_cases": len(completed),
        "same_plan_success": same_success_n,
        "replan_R3_success": replan_success_n,
        "attributed_recovery_gain": gain,
        "attribution_counts": dict(Counter(row["attribution"] for row in completed)),
    }
    write_json(root / "metrics" / f"track_d_R3_summary_{set_name}.json", summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Track D official-guided replanning pipeline")
    parser.add_argument("--root", type=Path, default=TRACK_D_ROOT)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("prepare")
    p_same = sub.add_parser("run-same")
    p_same.add_argument("--set", choices=["primary", "secondary", "all"], default="primary")
    p_same.add_argument("--start", type=int, default=1)
    p_same.add_argument("--limit", type=int, default=None)
    p_same.add_argument("--timeout-s", type=int, default=300)
    p_infer = sub.add_parser("infer-r3")
    p_infer.add_argument("--set", choices=["primary", "secondary", "all"], default="primary")
    p_infer.add_argument("--start", type=int, default=1)
    p_infer.add_argument("--limit", type=int, default=None)
    p_infer.add_argument("--base-url", default=BASE_URL)
    p_infer.add_argument("--model", default=MODEL)
    p_exec = sub.add_parser("run-r3")
    p_exec.add_argument("--set", choices=["primary", "secondary", "all"], default="primary")
    p_exec.add_argument("--start", type=int, default=1)
    p_exec.add_argument("--limit", type=int, default=None)
    p_exec.add_argument("--timeout-s", type=int, default=300)
    p_sum = sub.add_parser("summarize")
    p_sum.add_argument("--set", choices=["primary", "secondary", "all"], default="primary")
    args = parser.parse_args()
    if args.command == "prepare":
        print(json.dumps(prepare(args.root), ensure_ascii=False, indent=2))
    elif args.command == "run-same":
        print(json.dumps(run_same_plan(args.root, set_name=args.set, start=args.start, limit=args.limit, timeout_s=args.timeout_s), ensure_ascii=False, indent=2))
    elif args.command == "infer-r3":
        print(json.dumps(infer_r3(args.root, set_name=args.set, start=args.start, limit=args.limit, base_url=args.base_url, model=args.model), ensure_ascii=False, indent=2))
    elif args.command == "run-r3":
        print(json.dumps(run_replan_r3(args.root, set_name=args.set, start=args.start, limit=args.limit, timeout_s=args.timeout_s), ensure_ascii=False, indent=2))
    elif args.command == "summarize":
        print(json.dumps(summarize(args.root, set_name=args.set), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
