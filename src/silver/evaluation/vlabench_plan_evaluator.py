"""Qwen inference and operation-sequence evaluation for VLABench Track A."""

from __future__ import annotations

import argparse
import base64
import csv
import json
import re
import time
import urllib.request
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any


TRACK_ROOT = Path("silver/results/track_a_vlabench_planning_20260510")
BASE_URL = "http://127.0.0.1:8000/v1"
MODEL = "Qwen/Qwen3-VL-8B-Instruct"
CONDITIONS = ("P1", "P2", "P3")


BASIC_SCHEMA_TEXT = """Return ONLY valid JSON with this shape:
{
  "skill_sequence": [
    {"name": "pick", "params": {"target_entity_name": 2}},
    {"name": "place", "params": {"target_container_name": 1}}
  ],
  "uncertainty": [],
  "rationale_summary": "short non-chain-of-thought explanation"
}
Use the operation names and parameter keys that best match the instruction and image. Do not include markdown.
"""

EXPLICIT_SCHEMA_TEXT = """Return ONLY valid JSON with this shape:
{
  "skill_sequence": [
    {"name": "<skill>", "params": {"<argument_key>": <integer_or_string>}}
  ],
  "uncertainty": [],
  "rationale_summary": "short non-chain-of-thought explanation"
}
Allowed skills include: pick, place, open, close, pour, insert, press, push, wait, move.
Common parameter keys include:
- target_entity_name
- target_container_name
- target_entity_from_instruction
- target_object_name
- target_button_name
- target_flower_name
- target_region_name
- target_position_name
Preserve integer entity identifiers if the visual prompt uses numeric labels. Do not include markdown.
"""


def now_iso() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def image_to_data_url(path: Path) -> str:
    b64 = base64.b64encode(path.read_bytes()).decode("utf-8")
    return f"data:image/png;base64,{b64}"


def extract_json(text: str) -> tuple[Any | None, str | None]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text, flags=re.IGNORECASE).strip()
        text = re.sub(r"```$", "", text).strip()
    try:
        return json.loads(text), None
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            return None, "no_json_object_found"
        try:
            return json.loads(match.group(0)), None
        except json.JSONDecodeError as exc:
            return None, f"json_decode_error:{exc}"


def normalize_sequence(obj: Any) -> list[dict[str, Any]]:
    if not isinstance(obj, dict):
        return []
    seq = obj.get("skill_sequence", [])
    if not isinstance(seq, list):
        return []
    out: list[dict[str, Any]] = []
    for step in seq:
        if not isinstance(step, dict):
            continue
        name = step.get("name")
        params = step.get("params", {})
        if not isinstance(params, dict):
            params = {}
        out.append({"name": name, "params": params})
    return out


def validate_prediction(obj: Any) -> tuple[bool, list[str]]:
    errors: list[str] = []
    if not isinstance(obj, dict):
        return False, ["root_not_object"]
    seq = obj.get("skill_sequence")
    if not isinstance(seq, list) or not seq:
        errors.append("skill_sequence_missing_or_empty")
        return False, errors
    for idx, step in enumerate(seq, start=1):
        if not isinstance(step, dict):
            errors.append(f"step_{idx}_not_object")
            continue
        if not isinstance(step.get("name"), str) or not step.get("name"):
            errors.append(f"step_{idx}_name_invalid")
        if not isinstance(step.get("params", {}), dict):
            errors.append(f"step_{idx}_params_invalid")
    return not errors, errors


def step_signature(step: dict[str, Any]) -> tuple[Any, tuple[tuple[str, str], ...]]:
    params = step.get("params", {})
    if not isinstance(params, dict):
        params = {}
    return step.get("name"), tuple(sorted((str(k), str(v)) for k, v in params.items()))


def levenshtein(a: list[Any], b: list[Any]) -> int:
    prev = list(range(len(b) + 1))
    for i, x in enumerate(a, start=1):
        cur = [i]
        for j, y in enumerate(b, start=1):
            cur.append(min(cur[-1] + 1, prev[j] + 1, prev[j - 1] + (0 if x == y else 1)))
        prev = cur
    return prev[-1]


def evaluate_one(gt_obj: Any, pred_obj: Any, schema_valid: bool) -> dict[str, Any]:
    gt_seq = normalize_sequence(gt_obj)
    pred_seq = normalize_sequence(pred_obj)
    gt_names = [s.get("name") for s in gt_seq]
    pred_names = [s.get("name") for s in pred_seq]
    gt_sigs = [step_signature(s) for s in gt_seq]
    pred_sigs = [step_signature(s) for s in pred_seq]

    exact = gt_sigs == pred_sigs and bool(gt_sigs)
    max_len = max(len(gt_seq), len(pred_seq), 1)
    aligned = min(len(gt_seq), len(pred_seq))
    skill_name_matches = sum(1 for i in range(aligned) if gt_names[i] == pred_names[i])
    skill_name_accuracy = skill_name_matches / max_len

    gt_name_counter = Counter(gt_names)
    pred_name_counter = Counter(pred_names)
    overlap_actions = sum((gt_name_counter & pred_name_counter).values())
    action_recall = overlap_actions / len(gt_names) if gt_names else 0.0
    action_order_accuracy = 1.0 if gt_names == pred_names and bool(gt_names) else 0.0

    object_matches = 0
    object_total = 0
    target_matches = 0
    target_total = 0
    for i in range(aligned):
        gt_params = gt_seq[i].get("params", {})
        pred_params = pred_seq[i].get("params", {})
        for key, value in gt_params.items():
            key_l = str(key).lower()
            is_target_key = any(token in key_l for token in ("container", "support", "region", "position", "button"))
            is_object_key = any(token in key_l for token in ("entity", "object", "flower", "fruit")) and not is_target_key
            if is_object_key:
                object_total += 1
                if str(pred_params.get(key)) == str(value):
                    object_matches += 1
            if is_target_key:
                target_total += 1
                if str(pred_params.get(key)) == str(value):
                    target_matches += 1
    object_arg_accuracy = object_matches / object_total if object_total else None
    target_arg_accuracy = target_matches / target_total if target_total else None

    gt_set = Counter(gt_sigs)
    pred_set = Counter(pred_sigs)
    step_overlap = sum((gt_set & pred_set).values())
    precision = step_overlap / len(pred_sigs) if pred_sigs else 0.0
    recall = step_overlap / len(gt_sigs) if gt_sigs else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if precision + recall else 0.0

    return {
        "schema_valid": bool(schema_valid),
        "operation_sequence_exact_match": bool(exact),
        "skill_name_accuracy": skill_name_accuracy,
        "action_recall_rate": action_recall,
        "action_order_accuracy": action_order_accuracy,
        "object_argument_accuracy": object_arg_accuracy,
        "target_argument_accuracy": target_arg_accuracy,
        "step_level_f1": f1,
        "sequence_edit_distance": levenshtein(gt_sigs, pred_sigs),
        "gt_steps": len(gt_sigs),
        "pred_steps": len(pred_sigs),
    }


def make_prompt(instruction: str, condition: str) -> str:
    if condition in ("P1", "P2"):
        schema = BASIC_SCHEMA_TEXT
    elif condition == "P3":
        schema = EXPLICIT_SCHEMA_TEXT
    else:
        raise ValueError(f"Unknown condition: {condition}")
    return (
        "You are evaluating an embodied manipulation planning dataset.\n"
        "Infer the operation-level skill sequence needed to satisfy the instruction from the image.\n\n"
        f"Instruction:\n{instruction}\n\n"
        f"{schema}\n"
    )


def write_prompts(track_root: Path) -> dict[str, int]:
    rows = read_jsonl(track_root / "manifest" / "vlabench_sample_manifest.jsonl")
    count = 0
    for row in rows:
        if not row.get("download_ok"):
            continue
        local_dir = Path(row["local_dir"])
        instruction = Path(row["instruction.txt"]).read_text(encoding="utf-8-sig").strip()
        for condition in CONDITIONS:
            (local_dir / f"prompt_{condition}.txt").write_text(
                make_prompt(instruction, condition), encoding="utf-8"
            )
            count += 1
    return {"prompt_files_written": count}


def chat_completion(base_url: str, model: str, messages: list[dict[str, Any]], timeout_s: int) -> dict[str, Any]:
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0,
        "max_tokens": 1024,
    }
    req = urllib.request.Request(
        base_url.rstrip("/") + "/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        return json.loads(resp.read().decode("utf-8"))


def output_complete(local_dir: Path, condition: str) -> bool:
    for name in (
        f"raw_output_{condition}.json",
        f"parsed_output_{condition}.json",
        f"validation_{condition}.json",
    ):
        path = local_dir / name
        if not path.exists():
            return False
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            return False
    return True


def infer_one_call(
    row: dict[str, Any],
    condition: str,
    base_url: str,
    model: str,
    timeout_s: int,
) -> dict[str, Any]:
    local_dir = Path(row["local_dir"])
    image_path = Path(row["input_mask.png"] if condition == "P2" else row["input.png"])
    prompt_path = local_dir / f"prompt_{condition}.txt"
    if not prompt_path.exists():
        prompt_path.write_text(make_prompt(row["instruction"], condition), encoding="utf-8")
    prompt = prompt_path.read_text(encoding="utf-8")
    content = [
        {"type": "image_url", "image_url": {"url": image_to_data_url(image_path)}},
        {"type": "text", "text": prompt},
    ]
    t0 = time.time()
    raw = chat_completion(
        base_url,
        model,
        [{"role": "user", "content": content}],
        timeout_s=timeout_s,
    )
    latency_s = time.time() - t0
    assistant_text = raw.get("choices", [{}])[0].get("message", {}).get("content", "")
    parsed, parse_error = extract_json(assistant_text)
    schema_valid, schema_errors = validate_prediction(parsed)
    gt = json.loads(Path(row["operation_sequence.json"]).read_text(encoding="utf-8-sig"))
    metrics = evaluate_one(gt, parsed, schema_valid)
    raw["_track_a_metadata"] = {
        "sample_id": row["sample_id"],
        "condition": condition,
        "latency_s": latency_s,
        "model": model,
        "time": now_iso(),
    }
    (local_dir / f"raw_output_{condition}.json").write_text(
        json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (local_dir / f"parsed_output_{condition}.json").write_text(
        json.dumps(
            {
                "assistant_text": assistant_text,
                "parsed_json": parsed,
                "parse_error": parse_error,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (local_dir / f"validation_{condition}.json").write_text(
        json.dumps(
            {
                "schema_valid": schema_valid,
                "schema_errors": schema_errors,
                "metrics": metrics,
                "latency_s": latency_s,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return {
        "stage": "inference",
        "sample_id": row["sample_id"],
        "condition": condition,
        "attempt": 1,
        "status": "success",
        "latency_s": latency_s,
        "time": now_iso(),
    }


def run_inference(
    track_root: Path,
    base_url: str,
    model: str,
    conditions: list[str],
    limit_calls: int | None,
    timeout_s: int,
    workers: int = 1,
) -> dict[str, Any]:
    rows = read_jsonl(track_root / "manifest" / "vlabench_sample_manifest.jsonl")
    retry_log = track_root / "metrics" / "retry_log.jsonl"
    failed_log = track_root / "metrics" / "failed_samples.jsonl"
    attempted = 0
    skipped = 0
    succeeded = 0
    failed = 0

    pending: list[tuple[dict[str, Any], str]] = []
    for row in rows:
        if not row.get("download_ok"):
            continue
        local_dir = Path(row["local_dir"])
        for condition in conditions:
            if output_complete(local_dir, condition):
                skipped += 1
                continue
            pending.append((row, condition))
            if limit_calls is not None and len(pending) >= limit_calls:
                break
        if limit_calls is not None and len(pending) >= limit_calls:
            break

    attempted = len(pending)
    completed = 0
    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        futures = {
            executor.submit(infer_one_call, row, condition, base_url, model, timeout_s): (row, condition)
            for row, condition in pending
        }
        for future in as_completed(futures):
            row, condition = futures[future]
            try:
                success_log = future.result()
                succeeded += 1
                append_jsonl(retry_log, success_log)
            except Exception as exc:  # noqa: BLE001
                failed += 1
                append_jsonl(
                    failed_log,
                    {
                        "stage": "inference",
                        "sample_id": row["sample_id"],
                        "condition": condition,
                        "error": f"{type(exc).__name__}:{exc}",
                        "time": now_iso(),
                    },
                )
            completed += 1
            if completed % 25 == 0:
                print(f"[inference] attempted={attempted} succeeded={succeeded} failed={failed} skipped={skipped}")

    return {
        "attempted": attempted,
        "skipped": skipped,
        "succeeded": succeeded,
        "failed": failed,
        "stopped_by_limit": False,
    }


def aggregate_metrics(track_root: Path, conditions: list[str]) -> dict[str, Any]:
    rows = read_jsonl(track_root / "manifest" / "vlabench_sample_manifest.jsonl")
    eval_rows: list[dict[str, Any]] = []
    for row in rows:
        if not row.get("download_ok"):
            continue
        local_dir = Path(row["local_dir"])
        for condition in conditions:
            validation_path = local_dir / f"validation_{condition}.json"
            if not validation_path.exists():
                continue
            validation = json.loads(validation_path.read_text(encoding="utf-8"))
            metric = validation.get("metrics", {})
            eval_rows.append(
                {
                    "sample_id": row["sample_id"],
                    "category": row["category"],
                    "task": row["task"],
                    "condition": condition,
                    "schema_valid": int(bool(metric.get("schema_valid"))),
                    "operation_sequence_exact_match": int(bool(metric.get("operation_sequence_exact_match"))),
                    "skill_name_accuracy": float(metric.get("skill_name_accuracy", 0.0)),
                    "action_recall_rate": float(metric.get("action_recall_rate", 0.0)),
                    "action_order_accuracy": float(metric.get("action_order_accuracy", 0.0)),
                    "object_argument_accuracy": metric.get("object_argument_accuracy"),
                    "target_argument_accuracy": metric.get("target_argument_accuracy"),
                    "step_level_f1": float(metric.get("step_level_f1", 0.0)),
                    "sequence_edit_distance": int(metric.get("sequence_edit_distance", 0)),
                    "latency_s": float(validation.get("latency_s", 0.0)),
                }
            )

    metrics_dir = track_root / "metrics"
    write_csv(
        metrics_dir / "vlabench_planning_metrics_per_sample.csv",
        [
            "sample_id",
            "category",
            "task",
            "condition",
            "schema_valid",
            "operation_sequence_exact_match",
            "skill_name_accuracy",
            "action_recall_rate",
            "action_order_accuracy",
            "object_argument_accuracy",
            "target_argument_accuracy",
            "step_level_f1",
            "sequence_edit_distance",
            "latency_s",
        ],
        eval_rows,
    )

    def summarize(group_keys: list[str]) -> list[dict[str, Any]]:
        groups: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
        for r in eval_rows:
            groups[tuple(r[k] for k in group_keys)].append(r)
        out: list[dict[str, Any]] = []
        for key, group in sorted(groups.items()):
            row = {k: v for k, v in zip(group_keys, key)}
            n = len(group)
            row["n"] = n
            for metric in (
                "schema_valid",
                "operation_sequence_exact_match",
                "skill_name_accuracy",
                "action_recall_rate",
                "action_order_accuracy",
                "step_level_f1",
                "sequence_edit_distance",
                "latency_s",
            ):
                row[metric] = sum(float(g[metric]) for g in group) / n if n else 0.0
            for metric in ("object_argument_accuracy", "target_argument_accuracy"):
                vals = [float(g[metric]) for g in group if g[metric] is not None]
                row[metric] = sum(vals) / len(vals) if vals else None
            out.append(row)
        return out

    by_condition = summarize(["condition"])
    by_category = summarize(["category", "condition"])
    by_task = summarize(["category", "task", "condition"])
    write_csv(metrics_dir / "vlabench_planning_metrics_by_condition.csv", list(by_condition[0]) if by_condition else [], by_condition)
    write_csv(metrics_dir / "vlabench_planning_metrics_by_category.csv", list(by_category[0]) if by_category else [], by_category)
    write_csv(metrics_dir / "vlabench_planning_metrics_by_task.csv", list(by_task[0]) if by_task else [], by_task)

    gains: list[dict[str, Any]] = []
    condition_map = {r["condition"]: r for r in by_condition}
    if "P1" in condition_map and "P2" in condition_map:
        gains.append(
            {
                "gain": "visual_prompt_gain_P2_minus_P1",
                "operation_sequence_exact_match": condition_map["P2"]["operation_sequence_exact_match"]
                - condition_map["P1"]["operation_sequence_exact_match"],
                "step_level_f1": condition_map["P2"]["step_level_f1"] - condition_map["P1"]["step_level_f1"],
            }
        )
    if "P1" in condition_map and "P3" in condition_map:
        gains.append(
            {
                "gain": "schema_guidance_gain_P3_minus_P1",
                "operation_sequence_exact_match": condition_map["P3"]["operation_sequence_exact_match"]
                - condition_map["P1"]["operation_sequence_exact_match"],
                "step_level_f1": condition_map["P3"]["step_level_f1"] - condition_map["P1"]["step_level_f1"],
            }
        )
    if gains:
        write_csv(metrics_dir / "vlabench_planning_condition_gains.csv", list(gains[0]), gains)
    summary = {
        "evaluated_outputs": len(eval_rows),
        "by_condition": by_condition,
        "gains": gains,
    }
    (metrics_dir / "vlabench_planning_metrics_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return summary


def self_test() -> dict[str, Any]:
    gt = {"skill_sequence": [{"name": "pick", "params": {"target_entity_name": 2}}]}
    same = {"skill_sequence": [{"name": "pick", "params": {"target_entity_name": 2}}]}
    skill_mismatch = {"skill_sequence": [{"name": "place", "params": {"target_entity_name": 2}}]}
    arg_mismatch = {"skill_sequence": [{"name": "pick", "params": {"target_entity_name": 3}}]}
    missing = {"skill_sequence": []}
    tests = {
        "gt_vs_gt": evaluate_one(gt, same, True),
        "skill_mismatch": evaluate_one(gt, skill_mismatch, True),
        "arg_mismatch": evaluate_one(gt, arg_mismatch, True),
        "missing_step": evaluate_one(gt, missing, False),
        "invalid_json": validate_prediction(None),
    }
    assert tests["gt_vs_gt"]["operation_sequence_exact_match"] is True
    assert tests["gt_vs_gt"]["step_level_f1"] == 1.0
    assert tests["skill_mismatch"]["skill_name_accuracy"] == 0.0
    assert tests["arg_mismatch"]["object_argument_accuracy"] == 0.0
    assert tests["missing_step"]["schema_valid"] is False
    assert tests["invalid_json"][0] is False
    return tests


def main() -> None:
    parser = argparse.ArgumentParser(description="VLABench Track A inference/evaluation.")
    sub = parser.add_subparsers(dest="command", required=True)
    p_prompts = sub.add_parser("prompts")
    p_prompts.add_argument("--track_root", type=Path, default=TRACK_ROOT)
    p_infer = sub.add_parser("infer")
    p_infer.add_argument("--track_root", type=Path, default=TRACK_ROOT)
    p_infer.add_argument("--base_url", default=BASE_URL)
    p_infer.add_argument("--model", default=MODEL)
    p_infer.add_argument("--conditions", default="P1,P2,P3")
    p_infer.add_argument("--limit_calls", type=int, default=None)
    p_infer.add_argument("--timeout_s", type=int, default=180)
    p_infer.add_argument("--workers", type=int, default=1)
    p_eval = sub.add_parser("evaluate")
    p_eval.add_argument("--track_root", type=Path, default=TRACK_ROOT)
    p_eval.add_argument("--conditions", default="P1,P2,P3")
    sub.add_parser("self-test")
    args = parser.parse_args()

    if args.command == "prompts":
        print(json.dumps(write_prompts(args.track_root), ensure_ascii=False, indent=2))
    elif args.command == "infer":
        conditions = [c.strip() for c in args.conditions.split(",") if c.strip()]
        print(
            json.dumps(
                run_inference(
                    args.track_root,
                    args.base_url,
                    args.model,
                    conditions,
                    args.limit_calls,
                    args.timeout_s,
                    args.workers,
                ),
                ensure_ascii=False,
                indent=2,
            )
        )
    elif args.command == "evaluate":
        conditions = [c.strip() for c in args.conditions.split(",") if c.strip()]
        print(json.dumps(aggregate_metrics(args.track_root, conditions), ensure_ascii=False, indent=2))
    elif args.command == "self-test":
        print(json.dumps(self_test(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
