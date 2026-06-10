"""Track D 300-case feedback ablation pipeline.

This script follows silver/TRACK_D_ABLATION_300_GUIDELINE_20260529.md.
It creates a stratified 300-case subset from the completed Track D failure set,
runs NF/R1/R2/R4 replan variants, and reuses existing SR/R3 artifacts for
paired analysis. It does not synthesize results or expose GT plans.
"""

from __future__ import annotations

import argparse
import json
import random
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from silver.evaluation.track_c_official_guided_execution import (
    classify_track_c_status,
    run_native_qwen_guided,
    write_csv,
    write_json,
    write_jsonl,
)
from silver.evaluation.track_d_official_guided_replanning import (
    BASE_URL,
    MODEL,
    TRACK_D_ROOT,
    assistant_text,
    boolish,
    case_dir,
    chat_completion,
    image_to_data_url,
    read_csv,
    read_json,
    read_jsonl,
    stage_trace_summary,
    symptom_log,
    write_text,
)
from silver.evaluation.vlabench_executor_adapter import convert_sequence_to_executor_plan, sequence_from_parsed_output
from silver.evaluation.vlabench_plan_evaluator import extract_json, validate_prediction


ABLATION_ROOT = TRACK_D_ROOT / "ablation_300"
VARIANTS = {"NF", "R1", "R2", "R4"}
TARGET_COUNTS = {
    "C1_qwen_guided_condition_failure": 220,
    "C2_qwen_conversion_failure": 60,
    "C3_entity_mapping_failure": 19,
    "C4_unsupported_qwen_skill": 1,
}
SEED = 20260529


def now_iso() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def sample_rel(row: dict[str, Any]) -> Path:
    return Path(row["category"]) / row["task"] / row["example"]


def ablation_case_dir(row: dict[str, Any]) -> Path:
    return ABLATION_ROOT / "data" / sample_rel(row)


def load_manifest() -> list[dict[str, Any]]:
    return read_jsonl(ABLATION_ROOT / "manifest" / "track_d_ablation_300_manifest.jsonl")


def load_all_track_d_cases() -> list[dict[str, Any]]:
    return read_jsonl(TRACK_D_ROOT / "manifest" / "track_d_all_failure_cases.jsonl")


def prepare() -> dict[str, Any]:
    rows = load_all_track_d_cases()
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row["track_c_status"]].append(row)

    rng = random.Random(SEED)
    selected: list[dict[str, Any]] = []
    for status, count in TARGET_COUNTS.items():
        candidates = list(grouped.get(status, []))
        if len(candidates) < count:
            raise RuntimeError(f"Not enough cases for {status}: need {count}, found {len(candidates)}")
        candidates.sort(key=lambda item: item["sample_id"])
        if len(candidates) == count:
            chosen = candidates
        else:
            chosen = rng.sample(candidates, count)
            chosen.sort(key=lambda item: item["sample_id"])
        selected.extend(chosen)

    selected.sort(key=lambda item: (item["track_c_status"], item["sample_id"]))
    out_rows: list[dict[str, Any]] = []
    for idx, row in enumerate(selected, start=1):
        out = dict(row)
        out["ablation_index"] = idx
        out["ablation_seed"] = SEED
        out["ablation_case_dir"] = str(ablation_case_dir(out))
        out_rows.append(out)
        ablation_case_dir(out).mkdir(parents=True, exist_ok=True)
        write_json(ablation_case_dir(out) / "ablation_case_manifest.json", out)

    manifest_dir = ABLATION_ROOT / "manifest"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(manifest_dir / "track_d_ablation_300_manifest.jsonl", out_rows)
    by_status = Counter(row["track_c_status"] for row in out_rows)
    write_csv(
        manifest_dir / "track_d_ablation_300_summary_by_status.csv",
        [{"track_c_status": key, "count": value} for key, value in sorted(by_status.items())],
    )
    summary = {
        "time": now_iso(),
        "seed": SEED,
        "total": len(out_rows),
        "target_counts": TARGET_COUNTS,
        "actual_counts": dict(by_status),
        "source_manifest": str(TRACK_D_ROOT / "manifest" / "track_d_all_failure_cases.jsonl"),
    }
    write_json(ABLATION_ROOT / "manifest" / "track_d_ablation_300_prepare_summary.json", summary)
    update_progress("prepare", summary)
    return summary


def allowed_schema() -> dict[str, Any]:
    return {
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


def base_context(row: dict[str, Any]) -> tuple[str, dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    ddir = case_dir(TRACK_D_ROOT, row)
    instruction_path = Path(row["track_a_sample_dir"]) / "instruction.txt"
    instruction = instruction_path.read_text(encoding="utf-8-sig").strip() if instruction_path.exists() else ""
    initial_plan = read_json(ddir / "initial_qwen_plan.json")
    validation = read_json(ddir / "initial_adapter_validation.json")
    exec_result = read_json(ddir / "initial_failure_execution_result.json") if (ddir / "initial_failure_execution_result.json").exists() else {}
    registry = read_json(ddir / "entity_registry.json")
    return instruction, initial_plan, validation, exec_result, registry


def build_prompt(row: dict[str, Any], variant: str) -> str:
    instruction, initial_plan, validation, exec_result, _registry = base_context(row)
    symptom = symptom_log(row, exec_result, validation)
    trace = stage_trace_summary(exec_result)
    lines = [
        f"You are revising a robot manipulation plan. Variant={variant}.",
        "Return ONLY valid JSON. Do not include markdown.",
        "",
        "Rules:",
        "- Use only the allowed output schema.",
        "- Do not invent unsupported skills.",
        "- Do not reveal chain-of-thought; use only a short rationale_summary.",
        "- Do not use ground-truth actions, because they are not provided.",
        "",
        f"Instruction:\n{instruction}",
        "",
        f"Initial Qwen executor plan:\n{json.dumps(initial_plan, ensure_ascii=False)}",
        "",
    ]
    if variant == "NF":
        lines.extend(
            [
                "Failure feedback is intentionally hidden in this no-feedback ablation.",
                "Revise the plan only if the instruction and initial plan suggest a better executable plan.",
                "",
            ]
        )
    elif variant == "R1":
        lines.extend(
            [
                "Text failure observation:",
                symptom,
                "",
            ]
        )
    elif variant == "R2":
        lines.extend(
            [
                "A failure/final image is attached. No text failure symptom is provided in this image-only ablation.",
                "Use the image evidence only if it helps revise the plan.",
                "",
            ]
        )
    elif variant == "R4":
        lines.extend(
            [
                "Text failure observation:",
                symptom,
                "",
                "Executed trace summary:",
                trace,
                "",
                "A failure/final image is also attached.",
                "",
            ]
        )
    else:
        raise ValueError(f"Unsupported variant: {variant}")
    lines.append(f"Allowed output schema:\n{json.dumps(allowed_schema(), ensure_ascii=False, indent=2)}")
    return "\n".join(lines)


def image_path_for(row: dict[str, Any]) -> Path | None:
    image_path = Path(row["track_c_case_dir"]) / "qwen_guided_execution" / "final_mosaic.png"
    if image_path.exists():
        return image_path
    fallback = Path(row["track_a_sample_dir"]) / "input_mask.png"
    return fallback if fallback.exists() else None


def infer_variant(
    variant: str,
    *,
    start: int = 1,
    limit: int | None = None,
    base_url: str = BASE_URL,
    model: str = MODEL,
) -> dict[str, Any]:
    if variant not in VARIANTS:
        raise ValueError(f"variant must be one of {sorted(VARIANTS)}")
    rows = load_manifest()
    selected = rows[start - 1 :]
    if limit is not None:
        selected = selected[:limit]

    out_rows: list[dict[str, Any]] = []
    for idx, row in enumerate(selected, start=start):
        out_dir = ablation_case_dir(row) / variant
        raw_path = out_dir / "raw_output.json"
        parsed_path = out_dir / "parsed_output.json"
        validation_path = out_dir / "adapter_validation.json"
        plan_path = out_dir / "executor_plan.json"
        if raw_path.exists() and parsed_path.exists() and validation_path.exists() and plan_path.exists():
            validation = read_json(validation_path)
            out_rows.append(
                {
                    "ablation_index": row["ablation_index"],
                    "sample_id": row["sample_id"],
                    "track_c_status": row["track_c_status"],
                    "variant": variant,
                    "schema_valid": validation.get("schema_valid"),
                    "parse_error": validation.get("parse_error"),
                    "conversion_ok": validation.get("conversion_ok"),
                    "conversion_errors": ";".join(validation.get("conversion_errors", [])),
                    "skill_sequence": ">".join(str(x) for x in validation.get("skill_sequence", [])),
                    "status": "skipped_existing",
                    "updated_at": now_iso(),
                }
            )
            continue

        prompt = build_prompt(row, variant)
        write_text(out_dir / f"prompt_{variant}.txt", prompt)
        content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
        if variant in {"R2", "R4"}:
            image_path = image_path_for(row)
            if image_path:
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
            registry = read_json(case_dir(TRACK_D_ROOT, row) / "entity_registry.json")
            plan, adapter_validation = convert_sequence_to_executor_plan(row["sample_id"], sequence, registry, f"track_d_ablation_{variant}")
            adapter_validation["schema_valid"] = schema_valid
            adapter_validation["schema_errors"] = schema_errors
            adapter_validation["parse_error"] = parse_error
            adapter_validation["variant"] = variant
            write_json(validation_path, adapter_validation)
            write_json(plan_path, plan)
            out = {
                "ablation_index": row["ablation_index"],
                "sample_id": row["sample_id"],
                "track_c_status": row["track_c_status"],
                "variant": variant,
                "schema_valid": schema_valid,
                "parse_error": parse_error,
                "conversion_ok": adapter_validation.get("conversion_ok"),
                "conversion_errors": ";".join(adapter_validation.get("conversion_errors", [])),
                "skill_sequence": ">".join(str(x) for x in adapter_validation.get("skill_sequence", [])),
                "status": "completed",
                "updated_at": now_iso(),
            }
        except Exception as exc:
            out = {
                "ablation_index": row["ablation_index"],
                "sample_id": row["sample_id"],
                "track_c_status": row["track_c_status"],
                "variant": variant,
                "schema_valid": False,
                "parse_error": repr(exc),
                "conversion_ok": False,
                "conversion_errors": "inference_exception",
                "skill_sequence": "",
                "status": "inference_exception",
                "updated_at": now_iso(),
            }
            write_json(out_dir / "inference_error.json", out)
        out_rows.append(out)
        print(
            f"[{now_iso()}] Ablation infer {variant} {idx}/{len(rows)} {row['sample_id']} "
            f"conversion={out.get('conversion_ok')} status={out.get('status')}",
            flush=True,
        )

    result_path = ABLATION_ROOT / "metrics" / f"ablation_300_inference_{variant}_results.csv"
    existing = read_csv(result_path) if result_path.exists() else []
    by_id = {row["sample_id"]: row for row in existing}
    for row in out_rows:
        by_id[row["sample_id"]] = row
    merged = list(by_id.values())
    write_csv(result_path, merged)
    summary = {
        "time": now_iso(),
        "variant": variant,
        "completed_rows": len(merged),
        "conversion_ok": sum(1 for row in merged if boolish(row.get("conversion_ok")) is True),
        "status_counts": dict(Counter(row["status"] for row in merged)),
    }
    write_json(ABLATION_ROOT / "metrics" / f"ablation_300_inference_{variant}_summary.json", summary)
    update_progress(f"infer_{variant}", summary)
    return summary


def run_variant(variant: str, *, start: int = 1, limit: int | None = None, timeout_s: int = 300) -> dict[str, Any]:
    if variant not in VARIANTS:
        raise ValueError(f"variant must be one of {sorted(VARIANTS)}")
    rows = load_manifest()
    selected = rows[start - 1 :]
    if limit is not None:
        selected = selected[:limit]
    out_rows: list[dict[str, Any]] = []
    for idx, row in enumerate(selected, start=start):
        vdir = ablation_case_dir(row) / variant
        plan_path = vdir / "executor_plan.json"
        validation_path = vdir / "adapter_validation.json"
        if not plan_path.exists() or not validation_path.exists():
            validation = {"conversion_ok": False, "conversion_errors": ["missing_variant_plan"]}
            result = {"execution_status": "not_run_missing_variant_plan", "condition_success": None}
        else:
            validation = read_json(validation_path)
            if not validation.get("conversion_ok"):
                result = {
                    "sample_id": row["sample_id"],
                    "category": row["category"],
                    "task": row["task"],
                    "example": row["example"],
                    "mode": f"ablation_{variant}",
                    "execution_status": "not_run_conversion_failed",
                    "condition_success": None,
                    "failure_reason": ";".join(validation.get("conversion_errors", [])),
                    "completed_at": now_iso(),
                }
                write_json(ablation_case_dir(row) / f"{variant}_execution" / "execution_result.json", result)
            else:
                exec_row = {
                    "sample_id": row["sample_id"],
                    "category": row["category"],
                    "task": row["task"],
                    "example": row["example"],
                    "track_a_sample_dir": row["track_a_sample_dir"],
                }
                result = run_native_qwen_guided(exec_row, ablation_case_dir(row) / f"{variant}_execution", plan_path, timeout_s)
        status = classify_track_c_status(validation, result)
        out = {
            "ablation_index": row["ablation_index"],
            "sample_id": row["sample_id"],
            "track_c_status": row["track_c_status"],
            "variant": variant,
            "variant_status": status,
            "variant_execution_status": result.get("execution_status"),
            "variant_success": result.get("condition_success"),
            "variant_progress_score": result.get("progress_score"),
            "variant_elapsed_s": result.get("elapsed_s"),
            "case_dir": str(ablation_case_dir(row)),
            "updated_at": now_iso(),
        }
        out_rows.append(out)
        print(
            f"[{now_iso()}] Ablation exec {variant} {idx}/{len(rows)} {row['sample_id']} "
            f"status={status} success={out['variant_success']}",
            flush=True,
        )

    result_path = ABLATION_ROOT / "metrics" / f"ablation_300_execution_{variant}_results.csv"
    existing = read_csv(result_path) if result_path.exists() else []
    by_id = {row["sample_id"]: row for row in existing}
    for row in out_rows:
        by_id[row["sample_id"]] = row
    merged = list(by_id.values())
    write_csv(result_path, merged)
    summary = {
        "time": now_iso(),
        "variant": variant,
        "completed_rows": len(merged),
        "success": sum(1 for row in merged if boolish(row.get("variant_success")) is True),
        "status_counts": dict(Counter(row["variant_status"] for row in merged)),
    }
    write_json(ABLATION_ROOT / "metrics" / f"ablation_300_execution_{variant}_summary.json", summary)
    update_progress(f"run_{variant}", summary)
    return summary


def source_result_index(path: Path, success_col: str, status_col: str) -> dict[str, dict[str, Any]]:
    rows = read_csv(path) if path.exists() else []
    out = {}
    for row in rows:
        out[row["sample_id"]] = {
            "success": boolish(row.get(success_col)) is True,
            "status": row.get(status_col),
            "execution_status": row.get(status_col.replace("_status", "_execution_status"), ""),
        }
    return out


def summarize() -> dict[str, Any]:
    rows = load_manifest()
    variants = ["SR", "NF", "R1", "R2", "R3", "R4"]
    sr = source_result_index(
        TRACK_D_ROOT / "metrics" / "track_d_same_plan_retry_all_results.csv",
        "same_plan_success",
        "same_plan_status",
    )
    r3 = source_result_index(
        TRACK_D_ROOT / "metrics" / "track_d_replan_R3_execution_all_results.csv",
        "replan_R3_success",
        "replan_R3_status",
    )
    variant_results: dict[str, dict[str, dict[str, Any]]] = {"SR": sr, "R3": r3}
    for variant in ["NF", "R1", "R2", "R4"]:
        path = ABLATION_ROOT / "metrics" / f"ablation_300_execution_{variant}_results.csv"
        rows_v = read_csv(path) if path.exists() else []
        variant_results[variant] = {
            row["sample_id"]: {
                "success": boolish(row.get("variant_success")) is True,
                "status": row.get("variant_status"),
                "execution_status": row.get("variant_execution_status", ""),
            }
            for row in rows_v
        }

    paired_rows: list[dict[str, Any]] = []
    for row in rows:
        out = {
            "ablation_index": row["ablation_index"],
            "sample_id": row["sample_id"],
            "track_c_status": row["track_c_status"],
        }
        for variant in variants:
            item = variant_results.get(variant, {}).get(row["sample_id"], {})
            out[f"{variant}_success"] = item.get("success")
            out[f"{variant}_status"] = item.get("status")
        paired_rows.append(out)
    write_csv(ABLATION_ROOT / "metrics" / "ablation_300_pairwise_comparison.csv", paired_rows)

    condition_summary = []
    taxonomy_rows = []
    for variant in variants:
        completed = [row for row in paired_rows if row.get(f"{variant}_success") is not None]
        success = sum(1 for row in completed if row.get(f"{variant}_success") is True)
        statuses = Counter(str(row.get(f"{variant}_status")) for row in completed)
        condition_summary.append(
            {
                "variant": variant,
                "completed_rows": len(completed),
                "success": success,
                "success_rate": success / len(rows) if rows else None,
                "success_rate_completed": success / len(completed) if completed else None,
            }
        )
        for status, count in sorted(statuses.items()):
            taxonomy_rows.append({"variant": variant, "status": status, "count": count})

    write_csv(ABLATION_ROOT / "metrics" / "ablation_300_condition_success_by_variant.csv", condition_summary)
    write_csv(ABLATION_ROOT / "metrics" / "ablation_300_failure_taxonomy_by_variant.csv", taxonomy_rows)
    summary = {
        "time": now_iso(),
        "total_subset_cases": len(rows),
        "condition_summary": condition_summary,
        "status_counts": {
            variant: dict(Counter(str(row.get(f"{variant}_status")) for row in paired_rows if row.get(f"{variant}_success") is not None))
            for variant in variants
        },
    }
    write_json(ABLATION_ROOT / "metrics" / "ablation_300_summary.json", summary)
    update_progress("summarize", summary)
    return summary


def update_progress(step: str, payload: dict[str, Any]) -> None:
    ABLATION_ROOT.mkdir(parents=True, exist_ok=True)
    path = ABLATION_ROOT / "ABLATION_300_PROGRESS.md"
    existing = path.read_text(encoding="utf-8-sig") if path.exists() else "# Track D Ablation 300 Progress\n\n"
    entry = [
        f"## {now_iso()} - {step}",
        "",
        "```json",
        json.dumps(payload, ensure_ascii=False, indent=2),
        "```",
        "",
    ]
    write_text(path, existing + "\n".join(entry))


def main() -> int:
    parser = argparse.ArgumentParser(description="Track D 300-case feedback ablation")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("prepare")
    p_infer = sub.add_parser("infer")
    p_infer.add_argument("--variant", choices=sorted(VARIANTS), required=True)
    p_infer.add_argument("--start", type=int, default=1)
    p_infer.add_argument("--limit", type=int, default=None)
    p_infer.add_argument("--base-url", default=BASE_URL)
    p_infer.add_argument("--model", default=MODEL)
    p_run = sub.add_parser("run")
    p_run.add_argument("--variant", choices=sorted(VARIANTS), required=True)
    p_run.add_argument("--start", type=int, default=1)
    p_run.add_argument("--limit", type=int, default=None)
    p_run.add_argument("--timeout-s", type=int, default=300)
    sub.add_parser("summarize")
    args = parser.parse_args()

    if args.command == "prepare":
        print(json.dumps(prepare(), ensure_ascii=False, indent=2))
    elif args.command == "infer":
        print(
            json.dumps(
                infer_variant(args.variant, start=args.start, limit=args.limit, base_url=args.base_url, model=args.model),
                ensure_ascii=False,
                indent=2,
            )
        )
    elif args.command == "run":
        print(json.dumps(run_variant(args.variant, start=args.start, limit=args.limit, timeout_s=args.timeout_s), ensure_ascii=False, indent=2))
    elif args.command == "summarize":
        print(json.dumps(summarize(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
