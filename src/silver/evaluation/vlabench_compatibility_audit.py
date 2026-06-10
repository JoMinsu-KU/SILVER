# -*- coding: utf-8 -*-
"""Audit alignment between VLABench public samples and native runtime needs.

This script is intentionally read-only with respect to the dataset. It does
not execute robot skills, synthesize missing fields, or mark any sample as a
successful execution. It builds a ledger that explains what each public VLM
sample would require before native official-expert replay can be trusted.
"""

from __future__ import annotations

import argparse
import csv
import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


TRACK_A_ROOT = Path("silver/results/track_a_vlabench_planning_20260510")
DEFAULT_ROOT = Path("silver/results/silver-official-guided-evaluation-20260516")
REQUIRED_FILES = ("env_config.json", "operation_sequence.json", "instruction.txt", "input.png", "input_mask.png")


def now_iso() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def task_components(env_cfg: dict[str, Any]) -> list[dict[str, Any]]:
    task = env_cfg.get("task", {}) if isinstance(env_cfg, dict) else {}
    comps = task.get("components", []) if isinstance(task, dict) else []
    return [comp for comp in comps if isinstance(comp, dict)]


def operation_steps(op_seq: dict[str, Any]) -> list[dict[str, Any]]:
    seq = op_seq.get("skill_sequence", []) if isinstance(op_seq, dict) else []
    return [step for step in seq if isinstance(step, dict)]


def build_component_maps(env_cfg: dict[str, Any]) -> tuple[dict[int, dict[str, Any]], dict[str, dict[str, Any]]]:
    by_id: dict[int, dict[str, Any]] = {}
    by_name: dict[str, dict[str, Any]] = {}
    for idx, comp in enumerate(task_components(env_cfg)):
        by_id[idx] = comp
        name = comp.get("name")
        if name is not None:
            by_name[str(name)] = comp
    return by_id, by_name


def resolve_component(value: Any, by_id: dict[int, dict[str, Any]], by_name: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    if isinstance(value, int):
        return by_id.get(value)
    if isinstance(value, str) and value.strip().isdigit():
        return by_id.get(int(value.strip()))
    if isinstance(value, str):
        return by_name.get(value)
    return None


def unique_keep_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            out.append(value)
    return out


def extract_sequence_targets(env_cfg: dict[str, Any], op_seq: dict[str, Any]) -> dict[str, Any]:
    by_id, by_name = build_component_maps(env_cfg)
    entities: list[str] = []
    containers: list[str] = []
    unmapped: list[dict[str, Any]] = []
    mapped_params: list[dict[str, Any]] = []
    for idx, step in enumerate(operation_steps(op_seq)):
        params = step.get("params", {}) if isinstance(step.get("params", {}), dict) else {}
        for key, value in params.items():
            comp = resolve_component(value, by_id, by_name)
            if comp is None:
                unmapped.append({"step_index": idx, "skill": step.get("name"), "param": key, "value": value})
                mapped_params.append({"step_index": idx, "skill": step.get("name"), "param": key, "value": value, "mapped_name": None})
                continue
            name = str(comp.get("name"))
            mapped_params.append({"step_index": idx, "skill": step.get("name"), "param": key, "value": value, "mapped_name": name})
            if key == "target_entity_name":
                entities.append(name)
            elif key == "target_container_name":
                containers.append(name)
    return {
        "sequence_entities": unique_keep_order(entities),
        "sequence_containers": unique_keep_order(containers),
        "mapped_params": mapped_params,
        "unmapped_params": unmapped,
    }


def walk_condition_refs(obj: Any, refs: dict[str, list[str]]) -> None:
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key in {"target_entity", "entity", "entities"}:
                if isinstance(value, str):
                    refs["condition_entities"].append(value)
                elif isinstance(value, list):
                    refs["condition_entities"].extend(str(item) for item in value if isinstance(item, str))
            elif key in {"target_container", "container", "platform", "target_platform"}:
                if isinstance(value, str):
                    refs["condition_containers"].append(value)
                elif isinstance(value, list):
                    refs["condition_containers"].extend(str(item) for item in value if isinstance(item, str))
            walk_condition_refs(value, refs)
    elif isinstance(obj, list):
        for item in obj:
            walk_condition_refs(item, refs)


def extract_condition_targets(env_cfg: dict[str, Any]) -> dict[str, Any]:
    task = env_cfg.get("task", {}) if isinstance(env_cfg, dict) else {}
    conditions = task.get("conditions", {}) if isinstance(task, dict) else {}
    refs = {"condition_entities": [], "condition_containers": []}
    walk_condition_refs(conditions, refs)
    refs["condition_entities"] = unique_keep_order(refs["condition_entities"])
    refs["condition_containers"] = unique_keep_order(refs["condition_containers"])
    return refs


def infer_target_contract(task: str, category: str, seq_targets: dict[str, Any], condition_targets: dict[str, Any]) -> dict[str, Any]:
    entities = seq_targets["sequence_entities"]
    containers = seq_targets["sequence_containers"]
    skills = seq_targets.get("skills", [])
    if task == "take_chemistry_experiment":
        return {
            "target_entity_contract": "list[str]",
            "target_container_contract": "str",
            "adapter_requirement": "task_specific_multi_solution_adapter",
            "runtime_target_entity": condition_targets["condition_entities"] or entities,
            "runtime_target_container": (condition_targets["condition_containers"] or containers)[:1],
        }
    if task in {"book_rearrange", "cook_dishes", "texas_holdem"} or category == "Complex" or len(entities) > 1:
        return {
            "target_entity_contract": "task_specific",
            "target_container_contract": "task_specific",
            "adapter_requirement": "task_specific_sequence_adapter",
            "runtime_target_entity": condition_targets["condition_entities"] or entities,
            "runtime_target_container": condition_targets["condition_containers"] or containers,
        }
    return {
        "target_entity_contract": "str",
        "target_container_contract": "str",
        "adapter_requirement": "generic_single_target_adapter",
        "runtime_target_entity": entities[:1],
        "runtime_target_container": containers[:1],
    }


def detect_env_config_issues(env_cfg: dict[str, Any]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    for idx, comp in enumerate(task_components(env_cfg)):
        cls = comp.get("class")
        if cls == "Painting" and not comp.get("style") and not comp.get("specific_painting"):
            issues.append(
                {
                    "issue_code": "missing_painting_texture_key",
                    "component_index": str(idx),
                    "component_name": str(comp.get("name")),
                    "detail": "Painting component has neither style nor specific_painting; current VLABench Painting loader calls style.lower().",
                }
            )
    return issues


def classify_static(row: dict[str, Any], op_seq: dict[str, Any], env_cfg: dict[str, Any], seq_targets: dict[str, Any], env_issues: list[dict[str, str]], contract: dict[str, Any]) -> str:
    if env_issues:
        return "S4_env_config_runtime_incompatible"
    if seq_targets["unmapped_params"]:
        return "S3_operation_param_unmapped"
    if contract["adapter_requirement"] != "generic_single_target_adapter":
        return "S5_task_specific_adapter_required"
    return "S0_static_generic_compatible"


def audit_one(row: dict[str, Any]) -> dict[str, Any]:
    local_dir = Path(row["local_dir"])
    missing = [name for name in REQUIRED_FILES if not (local_dir / name).exists()]
    base = {
        "sample_id": row["sample_id"],
        "category": row["category"],
        "task": row["task"],
        "example": row["example"],
        "local_dir": str(local_dir),
        "missing_files": missing,
    }
    if missing:
        return {**base, "static_status": "S1_missing_required_file", "static_ok": False}
    try:
        env_cfg = read_json(local_dir / "env_config.json")
        op_seq = read_json(local_dir / "operation_sequence.json")
    except Exception as exc:  # noqa: BLE001
        return {**base, "static_status": "S2_invalid_json", "static_ok": False, "error": repr(exc)}

    seq_targets = extract_sequence_targets(env_cfg, op_seq)
    seq_targets["skills"] = [str(step.get("name")) for step in operation_steps(op_seq)]
    condition_targets = extract_condition_targets(env_cfg)
    env_issues = detect_env_config_issues(env_cfg)
    contract = infer_target_contract(row["task"], row["category"], seq_targets, condition_targets)
    status = classify_static(row, op_seq, env_cfg, seq_targets, env_issues, contract)
    return {
        **base,
        "static_status": status,
        "static_ok": status == "S0_static_generic_compatible",
        "gt_skill_pattern": ">".join(seq_targets["skills"]),
        "sequence_length": len(seq_targets["skills"]),
        "sequence_entities": seq_targets["sequence_entities"],
        "sequence_containers": seq_targets["sequence_containers"],
        "condition_entities": condition_targets["condition_entities"],
        "condition_containers": condition_targets["condition_containers"],
        "unmapped_params": seq_targets["unmapped_params"],
        "env_config_issues": env_issues,
        "target_entity_contract": contract["target_entity_contract"],
        "target_container_contract": contract["target_container_contract"],
        "adapter_requirement": contract["adapter_requirement"],
        "runtime_target_entity": contract["runtime_target_entity"],
        "runtime_target_container": contract["runtime_target_container"],
    }


def flatten_for_csv(row: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in row.items():
        if isinstance(value, (dict, list)):
            out[key] = json.dumps(value, ensure_ascii=False)
        else:
            out[key] = value
    return out


def summarize_by(rows: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get(key, ""))].append(row)
    out: list[dict[str, Any]] = []
    for name, group in sorted(grouped.items()):
        statuses = Counter(row.get("static_status") for row in group)
        out.append({key: name, "rows": len(group), **{str(k): v for k, v in sorted(statuses.items())}})
    return out


def write_report(root: Path, summary: dict[str, Any]) -> None:
    path = root / "track_b" / "compatibility_audit" / "TRACK_B_COMPATIBILITY_AUDIT_REPORT.md"
    lines = [
        "# Track B Compatibility Audit 보고서",
        "",
        f"작성 시각: {now_iso()} KST",
        "",
        "## 목적",
        "",
        "VLABench public VLM dataset 4,500개를 native official expert 실행으로 넘기기 전에, 데이터셋의 `env_config.json`, `operation_sequence.json`, 현재 VLABench runtime, 그리고 우리 wrapper 사이의 정렬 상태를 점검했다.",
        "",
        "이 단계는 실제 실행 성공률을 보고하지 않는다. 실행하지 않은 sample을 성공으로 처리하지 않으며, 데이터셋 파일도 수정하지 않는다.",
        "",
        "## 전체 결과",
        "",
        f"- 전체 sample: {summary['total_rows']}",
        f"- 정적 generic 호환 sample: {summary['status_counts'].get('S0_static_generic_compatible', 0)}",
        f"- task-specific adapter 필요 sample: {summary['status_counts'].get('S5_task_specific_adapter_required', 0)}",
        f"- env_config/runtime 호환성 이슈 sample: {summary['status_counts'].get('S4_env_config_runtime_incompatible', 0)}",
        f"- operation parameter unmapped sample: {summary['status_counts'].get('S3_operation_param_unmapped', 0)}",
        f"- missing/invalid file sample: {summary['status_counts'].get('S1_missing_required_file', 0) + summary['status_counts'].get('S2_invalid_json', 0)}",
        "",
        "## 상태 코드",
        "",
        "| 코드 | 의미 |",
        "|---|---|",
        "| `S0_static_generic_compatible` | 단일 target string 기반 generic adapter로 정적 호환 가능 |",
        "| `S3_operation_param_unmapped` | operation sequence의 id/name이 env_config component로 매핑되지 않음 |",
        "| `S4_env_config_runtime_incompatible` | env_config가 현재 VLABench loader 요구 필드를 충족하지 못할 가능성이 큼 |",
        "| `S5_task_specific_adapter_required` | 복수 object, 복합 순서, task-specific target contract가 필요함 |",
        "",
        "## 핵심 해석",
        "",
        "- `KeyError('N')` 계열은 `take_chemistry_experiment`처럼 `target_entity`가 리스트여야 하는 task에 문자열을 넣을 때 발생할 수 있다. 이 경우 데이터셋 오류가 아니라 wrapper target contract 오류다.",
        "- `NoneType.lower` 계열은 Painting component가 현재 VLABench loader가 기대하는 `style` 또는 `specific_painting` 필드를 갖지 않는 경우에 발생한다. 이 경우는 sample config와 runtime loader의 호환성 이슈로 분리해야 한다.",
        "- 따라서 Track B full native execution 전에 task별 compatibility adapter를 먼저 작성해야 한다.",
        "",
        "## Evidence",
        "",
        "- Ledger: `track_b/compatibility_audit/manifest/vlabench_compatibility_ledger.jsonl`",
        "- CSV ledger: `track_b/compatibility_audit/metrics/vlabench_compatibility_ledger.csv`",
        "- Status summary: `track_b/compatibility_audit/metrics/compatibility_status_counts.csv`",
        "- Task summary: `track_b/compatibility_audit/metrics/compatibility_summary_by_task.csv`",
        "- Adapter summary: `track_b/compatibility_audit/metrics/adapter_requirement_counts.csv`",
        "- Env issue cases: `track_b/compatibility_audit/failures/env_config_runtime_incompatible.jsonl`",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(track_a_root: Path, root: Path) -> dict[str, Any]:
    out_root = root / "track_b" / "compatibility_audit"
    manifest = read_jsonl(track_a_root / "manifest" / "vlabench_sample_manifest.jsonl")
    rows = [audit_one(row) for row in manifest]

    status_counts = Counter(row.get("static_status") for row in rows)
    adapter_counts = Counter(row.get("adapter_requirement", "none") for row in rows)
    contract_counts = Counter(f"{row.get('target_entity_contract')}->{row.get('target_container_contract')}" for row in rows)
    env_issue_rows = [row for row in rows if row.get("env_config_issues")]
    unmapped_rows = [row for row in rows if row.get("unmapped_params")]

    write_jsonl(out_root / "manifest" / "vlabench_compatibility_ledger.jsonl", rows)
    write_csv(out_root / "metrics" / "vlabench_compatibility_ledger.csv", [flatten_for_csv(row) for row in rows])
    write_csv(out_root / "metrics" / "compatibility_status_counts.csv", [{"static_status": k, "count": v} for k, v in sorted(status_counts.items())])
    write_csv(out_root / "metrics" / "adapter_requirement_counts.csv", [{"adapter_requirement": k, "count": v} for k, v in sorted(adapter_counts.items())])
    write_csv(out_root / "metrics" / "target_contract_counts.csv", [{"target_contract": k, "count": v} for k, v in sorted(contract_counts.items())])
    write_csv(out_root / "metrics" / "compatibility_summary_by_task.csv", summarize_by(rows, "task"))
    write_csv(out_root / "metrics" / "compatibility_summary_by_category.csv", summarize_by(rows, "category"))
    write_jsonl(out_root / "failures" / "env_config_runtime_incompatible.jsonl", env_issue_rows)
    write_jsonl(out_root / "failures" / "operation_param_unmapped.jsonl", unmapped_rows)

    summary = {
        "time": now_iso(),
        "total_rows": len(rows),
        "status_counts": dict(sorted(status_counts.items())),
        "adapter_requirement_counts": dict(sorted(adapter_counts.items())),
        "target_contract_counts": dict(sorted(contract_counts.items())),
        "env_config_issue_rows": len(env_issue_rows),
        "unmapped_param_rows": len(unmapped_rows),
    }
    write_json(out_root / "metrics" / "compatibility_audit_summary.json", summary)
    write_report(root, summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit VLABench public sample compatibility with native official replay.")
    parser.add_argument("--track-a-root", type=Path, default=TRACK_A_ROOT)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    args = parser.parse_args()
    print(json.dumps(run(args.track_a_root, args.root), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
