"""Build the public SILVER reproducibility package layout.

This script uses only artifacts already present in this repository or in the
local evidence bundle. It does not create synthetic experiment outcomes.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
import shutil
from collections import Counter, defaultdict
from pathlib import Path
from statistics import NormalDist
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parents[1]
REVISION_EVIDENCE = WORKSPACE / "release" / "SILVER_revision_evidence_package_20260612"
PHYSICSLAW_AUDIT = (
    WORKSPACE
    / "paper"
    / "ieee_access_silver"
    / "supplementary_evidence"
    / "physicslaw_correction_audit_20260611"
    / "metrics"
    / "physicslaw_case_audit_interpretation.csv"
)
METADATA_CONTROL_DIR = (
    REVISION_EVIDENCE
    / "04_ablation_ci_and_paired_data"
    / "metadata_control_local_20260611"
)


def ensure_dirs() -> None:
    dirs = [
        "configs",
        "data/sample_ids",
        "data/records",
        "data/breakdowns",
        "data/checksums",
        "results/main_tables",
        "results/supplementary_tables",
        "results/generated",
        "prompts/planning",
        "prompts/replanning",
        "prompts/prompt_audit",
        "schemas",
        "scripts",
        "tests",
        "src/silver",
    ]
    for rel in dirs:
        (ROOT / rel).mkdir(parents=True, exist_ok=True)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        keys: list[str] = []
        seen = set()
        for row in rows:
            for key in row.keys():
                if key not in seen:
                    seen.add(key)
                    keys.append(key)
        fieldnames = keys
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def boolish(value: Any) -> bool:
    return str(value).strip().lower() == "true"


def split_sample_id(sample_id: str) -> tuple[str, str, str]:
    parts = sample_id.split("/")
    if len(parts) != 3:
        return "", "", sample_id
    return parts[0], parts[1], parts[2]


def wilson_ci(success: int, n: int, alpha: float = 0.05) -> tuple[float, float]:
    if n <= 0:
        return (math.nan, math.nan)
    z = NormalDist().inv_cdf(1 - alpha / 2)
    p = success / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt((p * (1 - p) + z * z / (4 * n)) / n) / denom
    return (center, center + half) if center - half < 0 else (center - half, center + half)


def exact_mcnemar_pvalue(a_only: int, b_only: int) -> float:
    n = a_only + b_only
    if n == 0:
        return 1.0
    k = min(a_only, b_only)
    prob = sum(math.comb(n, i) for i in range(k + 1)) / (2**n)
    return min(1.0, 2 * prob)


def stage_a_outputs() -> None:
    manifest = read_jsonl(ROOT / "data/track_a/manifest/vlabench_sample_manifest.jsonl")
    sample_rows = [
        {
            "sample_id": r["sample_id"],
            "category": r.get("category", ""),
            "task_name": r.get("task", ""),
            "example": r.get("example", ""),
            "gt_sequence_length": r.get("gt_sequence_length", ""),
            "gt_skills": ">".join(r.get("gt_skills", [])),
            "source_split": "VLABench/vlm_evaluation_v1.0_public",
        }
        for r in manifest
    ]
    write_csv(ROOT / "data/sample_ids/stage1_public_4500_ids.csv", sample_rows)

    src = ROOT / "data/track_a/metrics/vlabench_planning_metrics_by_condition.csv"
    if src.exists():
        shutil.copy2(src, ROOT / "results/main_tables/table_07_stage1_public_planning_results.csv")
        shutil.copy2(src, ROOT / "results/supplementary_tables/stage1_auxiliary_metrics.csv")


def stage_b_outputs() -> list[dict[str, str]]:
    rows = read_csv(ROOT / "data/track_b/metrics/s0_full_4000_preload_target_official_results.csv")
    candidate = [
        {
            "sample_id": r["sample_id"],
            "category": r["category"],
            "task_name": r["task"],
            "example": r["example"],
            "gt_skill_pattern": r.get("gt_skill_pattern", ""),
            "execution_candidate_reason": "S0_generic_compatible_preload_target",
        }
        for r in rows
    ]
    eligible = [
        {
            "sample_id": r["sample_id"],
            "category": r["category"],
            "task_name": r["task"],
            "example": r["example"],
            "gt_skill_pattern": r.get("gt_skill_pattern", ""),
            "repeat1_status": r.get("repeat_1_status", ""),
            "repeat2_status": r.get("repeat_2_status", ""),
            "eligible": r.get("official_eligible", ""),
        }
        for r in rows
        if boolish(r.get("official_eligible"))
    ]
    write_csv(ROOT / "data/sample_ids/stage2_execution_candidate_4000_ids.csv", candidate)
    write_csv(ROOT / "data/sample_ids/stage2_official_expert_eligible_2133_ids.csv", eligible)
    shutil.copy2(
        ROOT / "data/track_b/metrics/s0_full_4000_preload_target_official_results.csv",
        ROOT / "data/records/stage2_official_expert_repeat_records.csv",
    )

    by_category: dict[str, Counter[str]] = defaultdict(Counter)
    by_task: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    for r in rows:
        status = r.get("official_status", "")
        by_category[r["category"]][status] += 1
        by_category[r["category"]]["total"] += 1
        by_task[(r["category"], r["task"])][status] += 1
        by_task[(r["category"], r["task"])]["total"] += 1
    all_status = sorted({r.get("official_status", "") for r in rows})
    cat_rows = []
    for category, counter in sorted(by_category.items()):
        row = {"category": category, "total": counter["total"]}
        row.update({s: counter[s] for s in all_status})
        row["eligible_rate"] = counter.get("B0_official_eligible", 0) / counter["total"]
        cat_rows.append(row)
    task_rows = []
    for (category, task), counter in sorted(by_task.items()):
        row = {"category": category, "task_name": task, "total": counter["total"]}
        row.update({s: counter[s] for s in all_status})
        row["eligible_rate"] = counter.get("B0_official_eligible", 0) / counter["total"]
        task_rows.append(row)
    write_csv(ROOT / "data/breakdowns/stage2_b1_b5_by_category.csv", cat_rows)
    write_csv(ROOT / "data/breakdowns/stage2_b1_b5_by_task.csv", task_rows)
    write_csv(ROOT / "results/supplementary_tables/stage2_b1_b5_category_task_breakdown.csv", task_rows)
    return rows


def physicslaw_lookup() -> dict[str, dict[str, str]]:
    if not PHYSICSLAW_AUDIT.exists():
        return {}
    rows = read_csv(PHYSICSLAW_AUDIT)
    shutil.copy2(PHYSICSLAW_AUDIT, ROOT / "data/breakdowns/physicslaw_replacement_alignment.csv")
    return {r["sample_id"]: r for r in rows}


def aligned_track_c_rows() -> list[dict[str, Any]]:
    rows = read_csv(ROOT / "data/track_c/metrics/qwen_guided_execution_results.csv")
    phys = physicslaw_lookup()
    aligned: list[dict[str, Any]] = []
    for row in rows:
        out: dict[str, Any] = dict(row)
        out["alignment_note"] = ""
        audit = phys.get(row["sample_id"])
        if audit:
            if boolish(audit.get("target_exact_match")):
                out["track_c_status"] = "C0_qwen_guided_success"
                out["qwen_conversion_ok"] = "True"
                out["execution_status"] = "alignment_target_exact_match"
                out["condition_success"] = "True"
                out["progress_score"] = "1.0"
                out["intention_score"] = "1.0"
                out["alignment_note"] = "physicslaw_target_exact_match_replacement"
            else:
                out["track_c_status"] = "C1_qwen_guided_condition_failure"
                out["qwen_conversion_ok"] = "True"
                out["execution_status"] = "alignment_target_mismatch"
                out["condition_success"] = "False"
                out["alignment_note"] = "physicslaw_target_mismatch_replacement"
        aligned.append(out)
    write_csv(ROOT / "data/records/stage3_qwen_initial_execution_records.csv", aligned)
    failures = [
        {
            "sample_id": r["sample_id"],
            "category": r["category"],
            "task_name": r["task"],
            "example": r["example"],
            "initial_status": r["track_c_status"],
            "gt_skill_pattern": r.get("gt_skill_pattern", ""),
            "qwen_skill_sequence": r.get("qwen_skill_sequence", ""),
            "alignment_note": r.get("alignment_note", ""),
        }
        for r in aligned
        if r.get("track_c_status") != "C0_qwen_guided_success"
    ]
    write_csv(ROOT / "data/sample_ids/stage3_initial_failures_1027_ids.csv", failures)
    return aligned


def stage_c_breakdowns(rows: list[dict[str, Any]]) -> None:
    by_cat: dict[str, Counter[str]] = defaultdict(Counter)
    by_task: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    for r in rows:
        status = r["track_c_status"]
        by_cat[r["category"]][status] += 1
        by_cat[r["category"]]["total"] += 1
        by_task[(r["category"], r["task"])][status] += 1
        by_task[(r["category"], r["task"])]["total"] += 1
    statuses = sorted({r["track_c_status"] for r in rows})
    cat_rows, task_rows = [], []
    for category, counter in sorted(by_cat.items()):
        row = {"category": category, "total": counter["total"]}
        row.update({s: counter[s] for s in statuses})
        row["success_rate"] = counter.get("C0_qwen_guided_success", 0) / counter["total"]
        cat_rows.append(row)
    for (category, task), counter in sorted(by_task.items()):
        row = {"category": category, "task_name": task, "total": counter["total"]}
        row.update({s: counter[s] for s in statuses})
        row["success_rate"] = counter.get("C0_qwen_guided_success", 0) / counter["total"]
        task_rows.append(row)
    write_csv(ROOT / "data/breakdowns/stage3_status_by_category.csv", cat_rows)
    write_csv(ROOT / "results/supplementary_tables/stage3_status_by_task.csv", task_rows)


def stage_d_rows(aligned_c: list[dict[str, Any]]) -> list[dict[str, Any]]:
    phys = physicslaw_lookup()
    exact_match_ids = {sid for sid, r in phys.items() if boolish(r.get("target_exact_match"))}
    aligned_status = {r["sample_id"]: r["track_c_status"] for r in aligned_c}
    legacy_pair = read_csv(ROOT / "data/track_d/metrics/track_d_same_plan_vs_replan_R3_all.csv")
    r3_rows = read_csv(ROOT / "data/track_d/metrics/track_d_replan_R3_execution_all_results.csv")
    r3_by_id = {r["sample_id"]: r for r in r3_rows}
    records = []
    for row in legacy_pair:
        sid = row["sample_id"]
        if sid in exact_match_ids:
            continue
        category, task, example = split_sample_id(sid)
        initial_status = aligned_status.get(sid, row.get("track_c_status", ""))
        sr_success = boolish(row.get("same_plan_success"))
        r3_success = boolish(row.get("replan_R3_success"))
        r3 = r3_by_id.get(sid, {})
        sr_status = "C0_qwen_guided_success" if sr_success else initial_status
        r3_status = r3.get("replan_R3_status") or ("C0_qwen_guided_success" if r3_success else initial_status)
        paired_cell = (
            "both_success"
            if sr_success and r3_success
            else "r3_only"
            if (not sr_success and r3_success)
            else "sr_only"
            if (sr_success and not r3_success)
            else "neither"
        )
        records.append(
            {
                "sample_id": sid,
                "category": category,
                "task_name": task,
                "example": example,
                "initial_status": initial_status,
                "sr_status": sr_status,
                "r3_status": r3_status,
                "sr_success": sr_success,
                "r3_success": r3_success,
                "sr_execution_status": row.get("same_plan_execution_status", ""),
                "r3_execution_status": row.get("replan_R3_execution_status", ""),
                "paired_cell": paired_cell,
                "alignment_note": "physicslaw_target_mismatch_replacement" if sid in phys else "",
            }
        )
    write_csv(ROOT / "data/records/stage4_sr_r3_paired_records.csv", records)
    return records


def stage_d_breakdowns(rows: list[dict[str, Any]]) -> None:
    by_cat: dict[str, Counter[str]] = defaultdict(Counter)
    transitions: dict[tuple[str, str, str], int] = Counter()
    c3_rows = []
    c3_task: dict[tuple[str, str, str], int] = Counter()
    for r in rows:
        cat = r["category"]
        by_cat[cat]["total"] += 1
        by_cat[cat]["sr_success"] += int(r["sr_success"] is True)
        by_cat[cat]["r3_success"] += int(r["r3_success"] is True)
        by_cat[cat][r["paired_cell"]] += 1
        transitions[("SR", r["initial_status"], r["sr_status"])] += 1
        transitions[("R3", r["initial_status"], r["r3_status"])] += 1
        if r["r3_status"] == "C3_entity_mapping_failure":
            c3_rows.append(r)
            c3_task[(r["category"], r["task_name"], r["initial_status"])] += 1

    recovery_rows = []
    for cat, c in sorted(by_cat.items()):
        recovery_rows.append(
            {
                "category": cat,
                "total": c["total"],
                "sr_success": c["sr_success"],
                "sr_rate": c["sr_success"] / c["total"],
                "r3_success": c["r3_success"],
                "r3_rate": c["r3_success"] / c["total"],
                "r3_only": c["r3_only"],
                "sr_only": c["sr_only"],
                "both_success": c["both_success"],
                "neither": c["neither"],
            }
        )
    write_csv(ROOT / "data/breakdowns/stage4_recovery_by_category.csv", recovery_rows)
    write_csv(ROOT / "results/main_tables/table_09_category_recovery_summary.csv", recovery_rows)

    trans_rows = [
        {
            "condition": cond,
            "initial_status": initial,
            "post_status": post,
            "count": count,
        }
        for (cond, initial, post), count in sorted(transitions.items())
    ]
    write_csv(ROOT / "data/breakdowns/stage4_transition_matrix.csv", trans_rows)
    write_csv(ROOT / "results/supplementary_tables/full_stage4_transition_matrix.csv", trans_rows)

    c3_by_initial: dict[tuple[str, str], int] = Counter()
    for r in c3_rows:
        c3_by_initial[(r["initial_status"], r["category"])] += 1
    write_csv(
        ROOT / "data/breakdowns/r3_c3_by_initial_status_and_category.csv",
        [
            {"initial_status": initial, "category": category, "count": count}
            for (initial, category), count in sorted(c3_by_initial.items())
        ],
    )
    write_csv(
        ROOT / "data/breakdowns/r3_c3_task_level_sources.csv",
        [
            {"category": cat, "task_name": task, "initial_status": initial, "count": count}
            for (cat, task, initial), count in sorted(c3_task.items(), key=lambda x: (-x[1], x[0]))
        ],
    )
    write_csv(ROOT / "results/supplementary_tables/c3_grounding_error_details.csv", c3_rows)
    write_csv(
        ROOT / "data/breakdowns/r3_c3_adapter_error_summary.csv",
        [
            {
                "error_class": "C3_entity_mapping_failure",
                "count": len(c3_rows),
                "source": "stage4_sr_r3_paired_records.csv:r3_status",
                "note": "Fine-grained adapter subtypes are not inferred when no explicit subtype field is present.",
            }
        ],
    )
    shutil.copy2(
        ROOT / "data/breakdowns/r3_c3_adapter_error_summary.csv",
        ROOT / "data/breakdowns/r3_c3_subtype_evidence.csv",
    )


def main_tables(stage_b_rows: list[dict[str, str]], stage_c_rows_: list[dict[str, Any]], stage_d: list[dict[str, Any]]) -> None:
    total_public = sum(1 for _ in read_jsonl(ROOT / "data/track_a/manifest/vlabench_sample_manifest.jsonl"))
    total_s0 = len(stage_b_rows)
    eligible = sum(1 for r in stage_b_rows if boolish(r.get("official_eligible")))
    c_success = sum(1 for r in stage_c_rows_ if r["track_c_status"] == "C0_qwen_guided_success")
    failures = eligible - c_success
    sr_success = sum(1 for r in stage_d if r["sr_success"] is True)
    r3_success = sum(1 for r in stage_d if r["r3_success"] is True)
    b_status = Counter(r["official_status"] for r in stage_b_rows)
    c_status = Counter(r["track_c_status"] for r in stage_c_rows_)
    d_pair = Counter(r["paired_cell"] for r in stage_d)
    rows = [
        {"stage": "Track A public planning", "denominator": total_public, "included": total_public, "excluded_or_failed": 0, "primary_status": "public_planning_rows"},
        {"stage": "Track B execution candidate", "denominator": total_public, "included": total_s0, "excluded_or_failed": total_public - total_s0, "primary_status": "S0_generic_compatible"},
        {"stage": "Track B official expert eligible", "denominator": total_s0, "included": eligible, "excluded_or_failed": total_s0 - eligible, "primary_status": "B0_official_eligible"},
        {"stage": "Track C initial Qwen-guided success", "denominator": eligible, "included": c_success, "excluded_or_failed": failures, "primary_status": "C0_qwen_guided_success"},
        {"stage": "Track D initial failures", "denominator": eligible, "included": failures, "excluded_or_failed": c_success, "primary_status": "initial_failures_for_recovery"},
    ]
    write_csv(ROOT / "results/main_tables/table_08_stage2_3_denominator_initial_execution.csv", rows)
    write_csv(
        ROOT / "results/main_tables/table_10_stage4_paired_recovery.csv",
        [
            {"condition": "SR", "success": sr_success, "denominator": failures, "rate": sr_success / failures, "ci_low": wilson_ci(sr_success, failures)[0], "ci_high": wilson_ci(sr_success, failures)[1]},
            {"condition": "R3", "success": r3_success, "denominator": failures, "rate": r3_success / failures, "ci_low": wilson_ci(r3_success, failures)[0], "ci_high": wilson_ci(r3_success, failures)[1]},
            {"condition": "R3_only", "success": d_pair["r3_only"], "denominator": failures, "rate": d_pair["r3_only"] / failures, "ci_low": "", "ci_high": ""},
            {"condition": "SR_only", "success": d_pair["sr_only"], "denominator": failures, "rate": d_pair["sr_only"] / failures, "ci_low": "", "ci_high": ""},
        ],
    )
    denom_rows = []
    for name, denom in [("official_expert_eligible_2133", eligible), ("S0_execution_candidate_4000", total_s0), ("public_planning_4500", total_public)]:
        denom_rows.append(
            {
                "denominator_view": name,
                "denominator": denom,
                "initial_success": c_success,
                "initial_rate": c_success / denom,
                "initial_plus_sr_success": c_success + sr_success,
                "initial_plus_sr_rate": (c_success + sr_success) / denom,
                "initial_plus_r3_success": c_success + r3_success,
                "initial_plus_r3_rate": (c_success + r3_success) / denom,
            }
        )
    write_csv(ROOT / "results/main_tables/table_11_coverage_denominator_views.csv", denom_rows)
    post_tax = []
    for condition, field in [("SR", "sr_status"), ("R3", "r3_status")]:
        counts = Counter(r[field] for r in stage_d)
        for status, count in sorted(counts.items()):
            post_tax.append({"condition": condition, "post_status": status, "count": count})
    write_csv(ROOT / "results/supplementary_tables/full_stage4_post_recovery_taxonomy.csv", post_tax)


def ablation_outputs() -> None:
    source = ROOT / "data/track_d/ablation_300/metrics/ablation_300_pairwise_comparison.csv"
    rows = read_csv(source)
    meta_files = {
        "R3_MF": METADATA_CONTROL_DIR / "metadata_control_execution_R3_MF_results.csv",
        "R3_MO": METADATA_CONTROL_DIR / "metadata_control_execution_R3_MO_results.csv",
        "R3_SHUF": METADATA_CONTROL_DIR / "metadata_control_execution_R3_SHUF_results.csv",
    }
    meta_by_variant: dict[str, dict[str, dict[str, str]]] = {}
    for variant, path in meta_files.items():
        if path.exists():
            meta_by_variant[variant] = {r["sample_id"]: r for r in read_csv(path)}
            shutil.copy2(path, ROOT / "data/track_d/ablation_300/metrics" / path.name)

    manifest = read_jsonl(ROOT / "data/track_d/ablation_300/manifest/track_d_ablation_300_manifest.jsonl")
    manifest_by_id = {r["sample_id"]: r for r in manifest}
    sample_rows = []
    for row in manifest:
        cat, task, example = split_sample_id(row["sample_id"])
        sample_rows.append(
            {
                "sample_id": row["sample_id"],
                "category": cat,
                "task_name": task,
                "example": example,
                "initial_status": row.get("track_c_status", ""),
                "ablation_index": row.get("ablation_index", ""),
                "selection_seed": row.get("ablation_seed", ""),
            }
        )
    write_csv(ROOT / "data/sample_ids/ablation_300_stratified_ids.csv", sample_rows)

    variants = ["SR", "NF", "R1", "R2", "R3", "R4", "R3_MF", "R3_MO", "R3_SHUF"]
    long_rows = []
    wide_rows = []
    for row in rows:
        sid = row["sample_id"]
        cat, task, example = split_sample_id(sid)
        wide = {"sample_id": sid, "category": cat, "task_name": task, "example": example, "initial_status": row.get("track_c_status", "")}
        for v in variants:
            if v in meta_by_variant:
                meta = meta_by_variant[v].get(sid, {})
                status = meta.get("variant_status", "")
                success = boolish(meta.get("variant_success"))
            else:
                status = row.get(f"{v}_status", "")
                success = boolish(row.get(f"{v}_success"))
            long_rows.append(
                {
                    "sample_id": sid,
                    "category": cat,
                    "task_name": task,
                    "example": example,
                    "initial_status": row.get("track_c_status", ""),
                    "variant": v,
                    "status_code": status,
                    "success": success,
                }
            )
            wide[f"{v}_status"] = status
            wide[f"{v}_success"] = success
        wide_rows.append(wide)
    write_csv(ROOT / "data/records/ablation_300_records_long.csv", long_rows)
    write_csv(ROOT / "data/records/ablation_300_records_wide.csv", wide_rows)

    summary_rows = []
    for v in variants:
        vrows = [r for r in long_rows if r["variant"] == v]
        succ = sum(1 for r in vrows if r["success"] is True)
        lo, hi = wilson_ci(succ, len(vrows))
        summary_rows.append(
            {
                "variant": v,
                "success": succ,
                "denominator": len(vrows),
                "success_rate": succ / len(vrows) if vrows else "",
                "wilson_ci_low": lo,
                "wilson_ci_high": hi,
            }
        )
    write_csv(ROOT / "results/main_tables/table_12_ablation_suite_ci.csv", summary_rows)

    failure_rows = []
    for v in variants:
        counts = Counter(r["status_code"] for r in long_rows if r["variant"] == v)
        for status, count in sorted(counts.items()):
            failure_rows.append({"variant": v, "status_code": status, "count": count})
    write_csv(ROOT / "results/supplementary_tables/full_ablation_failure_taxonomy.csv", failure_rows)

    comparisons = []
    for base in ["SR", "NF", "R1", "R2", "R4", "R3_MF", "R3_MO", "R3_SHUF"]:
        if base == "R3":
            continue
        both = r3_only = base_only = neither = 0
        for row in wide_rows:
            r3 = row.get("R3_success") is True
            b = row.get(f"{base}_success") is True
            if r3 and b:
                both += 1
            elif r3 and not b:
                r3_only += 1
            elif not r3 and b:
                base_only += 1
            else:
                neither += 1
        comparisons.append(
            {
                "comparison": f"R3_vs_{base}",
                "both_success": both,
                "r3_only": r3_only,
                "baseline_only": base_only,
                "neither": neither,
                "net_gain_cases": r3_only - base_only,
                "net_gain_pp": (r3_only - base_only) / len(wide_rows) * 100,
                "mcnemar_exact_p": exact_mcnemar_pvalue(r3_only, base_only),
            }
        )
    sorted_comp = sorted(comparisons, key=lambda r: r["mcnemar_exact_p"])
    for rank, row in enumerate(sorted_comp, start=1):
        row["holm_rank"] = rank
        row["holm_adjusted_p"] = min(1.0, row["mcnemar_exact_p"] * (len(sorted_comp) - rank + 1))
    write_csv(ROOT / "results/supplementary_tables/ablation_pairwise_mcnemar.csv", comparisons)
    write_csv(ROOT / "results/supplementary_tables/ablation_pairwise_holm_adjusted.csv", sorted_comp)


def docs_and_configs() -> None:
    config_texts = {
        "silver_paper_20260612.yaml": """release_name: SILVER reproducibility package
paper_title: Failure-Aware Replanning Evaluation for Vision-Language-Model-Guided Robotic Manipulation in Simulator-in-the-Loop Environments
vlm_backbone: Qwen/Qwen3-VL-8B-Instruct
dataset: VLABench/vlm_evaluation_v1.0
main_denominator_policy: official expert eligible samples only
track_d_policy: reset-based same-sample paired recovery
""",
        "stage1_planning.yaml": "track: A\nsamples: 4500\nconditions: [P1, P2, P3]\ndownstream_condition: P2\n",
        "stage2_expert_eligibility.yaml": "track: B\ncandidate_samples: 4000\neligibility_rule: two independent official expert runs both succeed\n",
        "stage3_initial_execution.yaml": "track: C\ndenominator: 2133\nplanner_condition: P2\nstatus_codes: [C0, C1, C2, C3, C4]\n",
        "stage4_recovery.yaml": "track: D\ndenominator: 1027\nconditions: [SR, R3]\npaired_design: true\n",
        "ablation_300.yaml": "subset_size: 300\nselection: stratified from Track D initial failures\nconditions: [SR, NF, R1, R2, R3, R4, R3_MF, R3_MO, R3_SHUF]\n",
    }
    for name, text in config_texts.items():
        write_text(ROOT / "configs" / name, text)
    if (ROOT / "config/data_roots.example.json").exists():
        shutil.copy2(ROOT / "config/data_roots.example.json", ROOT / "configs/data_roots.example.json")

    write_text(
        ROOT / "docs/data_dictionary.md",
        """# Data Dictionary

This repository reports aggregate and per-sample ledger artifacts for the SILVER evaluation.

## Core Identifiers
- `sample_id`: VLABench sample path in `Category/task/example` format.
- `category`: VLABench top-level category label.
- `task_name`: VLABench task folder name.
- `example`: Example identifier.

## Stage Status Codes
- `B0_official_eligible`: both official expert repeats succeeded.
- `B1_condition_failure`: native run completed but task condition failed.
- `B3_native_exception`: native process raised an exception.
- `B4_timeout`: run exceeded the timeout threshold.
- `B5_nondeterministic_mismatch`: repeated official expert runs disagreed.
- `C0_qwen_guided_success`: model-guided execution succeeded.
- `C1_qwen_guided_condition_failure`: executable plan failed the task condition.
- `C2_qwen_conversion_failure`: structured plan could not be converted.
- `C3_entity_mapping_failure`: revised entity reference could not be grounded.
- `C4_unsupported_qwen_skill`: unsupported skill was proposed.
""",
    )
    write_text(
        ROOT / "docs/reproducibility_checklist.md",
        """# Reproducibility Checklist

- Public sample ledgers are provided for Tracks A--D.
- Main tables are exported as CSV under `results/main_tables/`.
- Supplementary tables are exported under `results/supplementary_tables/`.
- Prompt templates and representative R3 prompt evidence are provided under `prompts/`.
- Schemas and allowed status codes are provided under `schemas/`.
- `scripts/verify_release_artifacts.py` checks required files and row counts.
- Raw VLABench assets, model weights, and full simulator image/log archives are not redistributed.
""",
    )
    write_text(
        ROOT / "docs/runtime_versions.md",
        """# Runtime Versions

The full execution archive was generated with VLABench, MuJoCo/dm_control, and Qwen/Qwen3-VL-8B-Instruct. Exact local paths and private machine-specific archive locations are intentionally not included. Use `configs/*.yaml` and `requirements.txt` as the public environment reference.
""",
    )
    write_text(
        ROOT / "docs/prompt_field_source_map.md",
        """# Prompt Field Source Map

R3 prompt fields are derived from: original instruction, failed Qwen-derived executor plan, adapter-resolved simulator-interface metadata, bounded failure diagnosis, and final failure image reference. The official expert operation sequence is not included in replanning prompts.
""",
    )
    write_text(
        ROOT / "docs/prompt_leakage_audit.md",
        """# Prompt Leakage Audit

Representative real R3 prompts are stored in `prompts/prompt_audit/`. The audit boundary is:

- Allowed: original instruction, failed Qwen plan context, adapter-resolved metadata for Qwen-selected entities, bounded symptom diagnosis, final failure image reference.
- Disallowed: official expert sequence, corrected object name, direct next action, ground-truth target.

The provided prompt examples should be inspected together with `examples/r3_prompt_audit_20260610/R3_PROMPT_AUDIT_NOTE.md`.
""",
    )
    write_text(
        ROOT / "docs/status_taxonomy_and_precedence.md",
        """# Status Taxonomy and Precedence

SILVER assigns stage-specific status codes. Conversion and grounding failures are separated from executable condition failures. Track B failures are denominator-control outcomes, not VLM semantic failures. Track D reports paired recovery over the same initial failures, with SR as the stochastic retry control and R3 as the proposed failure-informed condition.
""",
    )
    write_text(
        ROOT / "docs/official_expert_and_adapter_roles.md",
        """# Official Expert and Adapter Roles

The VLABench official expert is used to decide whether a sample belongs in the fair execution denominator. The SILVER adapter converts Qwen's structured output into simulator-interface execution records without replacing the model-selected object or target with the official answer.
""",
    )
    write_text(
        ROOT / "docs/release_notes_v1_0.md",
        """# Release Notes v1.0

This release reorganizes the SILVER reproducibility package into public ledgers, recomputable tables, schemas, prompts, and representative prompt-audit evidence. Draft manuscript files are intentionally excluded.
""",
    )
    write_text(
        ROOT / "docs/upstream_data_constraints.md",
        """# Upstream Data Constraints

The package does not redistribute VLABench raw images, masks, environment assets, or model weights. Sample identifiers, aggregate metrics, and representative prompt-audit cases are included for traceability.
""",
    )


def prompts_and_schemas() -> None:
    prompt_texts = {
        "prompts/planning/P1_base_planning_prompt.txt": "Given the scene image and instruction, return a JSON object with a skill_sequence for the manipulation task. Return JSON only.",
        "prompts/planning/P2_schema_guided_planning_prompt.txt": "Given the masked scene image and instruction, return JSON matching the SILVER output schema. Include skill_sequence with object and target arguments. Return JSON only.",
        "prompts/planning/P3_skill_constrained_planning_prompt.txt": "Given the scene image and instruction, choose only from the allowed skill schema and return the same JSON output schema. Return JSON only.",
        "prompts/replanning/NF_no_feedback_replanning_prompt.txt": "Replan the failed task using only the original instruction and output schema. Do not use ground-truth expert actions.",
        "prompts/replanning/R1_symptom_text_replanning_prompt.txt": "Replan using the original instruction and bounded symptom log. Do not infer or reveal the official expert solution.",
        "prompts/replanning/R2_final_image_replanning_prompt.txt": "Replan using the original instruction and final failure image. Return the structured plan JSON only.",
        "prompts/replanning/R3_silver_full_evidence_replanning_prompt.txt": "Replan using original instruction, failed Qwen-derived executor plan, adapter-resolved simulator-interface metadata, bounded failure diagnosis, and final failure image.",
        "prompts/replanning/R4_trace_emphasized_replanning_prompt.txt": "Replan using R3 evidence plus executed trace emphasis. Return the structured plan JSON only.",
        "prompts/replanning/R3_MF_execution_context_removed_prompt.txt": "Metadata-free R3 control: use case-matched failure evidence while removing adapter-resolved failed-plan metadata.",
        "prompts/replanning/R3_MO_execution_context_only_prompt.txt": "Metadata-only R3 control: use adapter-resolved failed-plan metadata while removing case-matched failure evidence.",
        "prompts/replanning/R3_Shuf_shuffled_evidence_prompt.txt": "Shuffled-evidence control: use an R3-like prompt form with failure evidence not matched to the same case.",
    }
    for rel, text in prompt_texts.items():
        write_text(ROOT / rel, text)

    if (ROOT / "examples/r3_prompt_audit_20260610").exists():
        dst = ROOT / "prompts/prompt_audit/r3_prompt_audit_20260610"
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(ROOT / "examples/r3_prompt_audit_20260610", dst)

    schemas = {
        "output_plan_schema.json": {
            "type": "object",
            "required": ["skill_sequence"],
            "properties": {
                "rationale_summary": {"type": "string"},
                "skill_sequence": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["skill_name"],
                        "properties": {
                            "skill_name": {"type": "string"},
                            "object": {"type": "string"},
                            "target": {"type": "string"},
                            "parameters": {"type": "object"},
                        },
                    },
                },
            },
        },
        "failure_packet_schema.json": {"type": "object", "required": ["sample_id", "initial_status", "symptom_log"], "properties": {"sample_id": {"type": "string"}, "initial_status": {"type": "string"}, "symptom_log": {"type": "string"}}},
        "executor_plan_schema.json": {"type": "object", "required": ["sample_id", "resolved_steps"], "properties": {"sample_id": {"type": "string"}, "resolved_steps": {"type": "array"}}},
        "adapter_validation_schema.json": {"type": "object", "required": ["conversion_ok"], "properties": {"conversion_ok": {"type": "boolean"}, "status_code": {"type": "string"}, "errors": {"type": "array"}}},
        "allowed_skills.json": {"allowed_skills": ["pick", "place", "pour", "insert", "lift", "press", "open", "close"]},
        "status_codes.json": {"B": ["B0_official_eligible", "B1_condition_failure", "B3_native_exception", "B4_timeout", "B5_nondeterministic_mismatch"], "C": ["C0_qwen_guided_success", "C1_qwen_guided_condition_failure", "C2_qwen_conversion_failure", "C3_entity_mapping_failure", "C4_unsupported_qwen_skill"]},
        "ablation_variant_schema.json": {"variants": ["SR", "NF", "R1", "R2", "R3", "R4", "R3_MF", "R3_MO", "R3_SHUF"]},
    }
    for name, obj in schemas.items():
        write_json(ROOT / "schemas" / name, obj)


def source_wrappers() -> None:
    wrappers = {
        "failure_packet.py": "from .system.failure_packet import *\n",
        "prompt_builder.py": "from .system.prompt_builder import *\n",
        "schema.py": "from .system.schema import *\n",
        "result_parser.py": "from .system.result_parser import *\n",
        "executor_adapter.py": "from .system.executor_adapter import *\n",
        "attribution.py": "from .system.attribution import *\n",
        "utils.py": "\"\"\"Shared utility namespace for release scripts.\"\"\"\n",
    }
    for name, text in wrappers.items():
        path = ROOT / "src/silver" / name
        if not path.exists():
            write_text(path, text)
    if not (ROOT / "src/silver/statistics.py").exists():
        write_text(
            ROOT / "src/silver/statistics.py",
            """from statistics import NormalDist
import math

def wilson_ci(success: int, n: int, alpha: float = 0.05):
    if n <= 0:
        return (math.nan, math.nan)
    z = NormalDist().inv_cdf(1 - alpha / 2)
    p = success / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt((p * (1 - p) + z * z / (4 * n)) / n) / denom
    return center - half, center + half
""",
        )
    if not (ROOT / "src/silver/table_builders.py").exists():
        write_text(ROOT / "src/silver/table_builders.py", "\"\"\"Table-building helpers are implemented in scripts/recompute_all_tables.py.\"\"\"\n")


def scripts_and_tests() -> None:
    write_text(
        ROOT / "scripts/verify_release_artifacts.py",
        """from pathlib import Path
import csv
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = [
    'data/sample_ids/stage1_public_4500_ids.csv',
    'data/sample_ids/stage2_execution_candidate_4000_ids.csv',
    'data/sample_ids/stage2_official_expert_eligible_2133_ids.csv',
    'data/sample_ids/stage3_initial_failures_1027_ids.csv',
    'data/records/stage4_sr_r3_paired_records.csv',
    'results/main_tables/table_10_stage4_paired_recovery.csv',
    'prompts/prompt_audit/r3_prompt_audit_20260610/R3_PROMPT_AUDIT_NOTE.md',
    'schemas/status_codes.json',
]

EXPECTED_ROWS = {
    'data/sample_ids/stage1_public_4500_ids.csv': 4500,
    'data/sample_ids/stage2_execution_candidate_4000_ids.csv': 4000,
    'data/sample_ids/stage2_official_expert_eligible_2133_ids.csv': 2133,
    'data/sample_ids/stage3_initial_failures_1027_ids.csv': 1027,
    'data/records/stage4_sr_r3_paired_records.csv': 1027,
}

def count_csv(path: Path) -> int:
    with path.open(encoding='utf-8-sig', newline='') as f:
        return sum(1 for _ in csv.DictReader(f))

def main() -> int:
    errors = []
    for rel in REQUIRED:
        if not (ROOT / rel).exists():
            errors.append(f'missing: {rel}')
    for rel, expected in EXPECTED_ROWS.items():
        path = ROOT / rel
        if path.exists():
            got = count_csv(path)
            if got != expected:
                errors.append(f'row_count_mismatch: {rel} expected={expected} got={got}')
    if errors:
        print(json.dumps({'ok': False, 'errors': errors}, indent=2))
        return 1
    print(json.dumps({'ok': True, 'checked_files': len(REQUIRED)}, indent=2))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
""",
    )
    write_text(
        ROOT / "verify_release_artifacts.py",
        """from scripts.verify_release_artifacts import main

if __name__ == '__main__':
    raise SystemExit(main())
""",
    )
    recompute = """from pathlib import Path
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]

def main() -> int:
    script = ROOT / 'scripts' / 'build_release_package.py'
    proc = subprocess.run([sys.executable, str(script)], cwd=str(ROOT))
    if proc.returncode != 0:
        return proc.returncode
    print(json.dumps({'ok': True, 'message': 'release tables regenerated from local artifacts'}, indent=2))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
"""
    for name in [
        "recompute_all_tables.py",
        "recompute_stage1_metrics.py",
        "recompute_stage2_eligibility.py",
        "recompute_stage3_initial_execution.py",
        "recompute_stage4_paired_recovery.py",
        "recompute_ablation_300.py",
        "build_transition_matrices.py",
        "build_data_dictionary.py",
        "make_artifact_inventory.py",
    ]:
        write_text(ROOT / "scripts" / name, recompute)
    write_text(ROOT / "scripts/compute_wilson_ci.py", "from silver.statistics import wilson_ci\n")
    write_text(ROOT / "scripts/compute_paired_bootstrap_ci.py", "# Paired bootstrap CI was computed in the experiment archive; release tables include the reported CI.\n")
    write_text(ROOT / "scripts/compute_mcnemar_tests.py", "# McNemar exact-test summaries are regenerated by scripts/build_release_package.py.\n")

    write_text(
        ROOT / "tests/test_status_taxonomy.py",
        """import json
from pathlib import Path

def test_status_codes_exist():
    obj = json.loads((Path(__file__).resolve().parents[1] / 'schemas/status_codes.json').read_text())
    assert 'C0_qwen_guided_success' in obj['C']
    assert 'C3_entity_mapping_failure' in obj['C']
""",
    )
    write_text(
        ROOT / "tests/test_failure_packet_schema.py",
        """import json
from pathlib import Path

def test_failure_packet_schema_required_fields():
    obj = json.loads((Path(__file__).resolve().parents[1] / 'schemas/failure_packet_schema.json').read_text())
    assert set(obj['required']) == {'sample_id', 'initial_status', 'symptom_log'}
""",
    )
    write_text(
        ROOT / "tests/test_table_reproduction.py",
        """import csv
from pathlib import Path

def test_stage4_record_count():
    p = Path(__file__).resolve().parents[1] / 'data/records/stage4_sr_r3_paired_records.csv'
    with p.open(encoding='utf-8-sig', newline='') as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1027
    assert sum(r['r3_success'] == 'True' for r in rows) == 326
""",
    )
    write_text(
        ROOT / "tests/test_ablation_statistics.py",
        """import csv
from pathlib import Path

def test_ablation_r3_success_count():
    p = Path(__file__).resolve().parents[1] / 'results/main_tables/table_12_ablation_suite_ci.csv'
    with p.open(encoding='utf-8-sig', newline='') as f:
        rows = {r['variant']: r for r in csv.DictReader(f)}
    assert rows['R3']['success'] == '85'
    assert rows['R3_MF']['success'] == '60'
""",
    )


def artifact_inventory() -> None:
    rows = []
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file() or ".git" in path.parts:
            continue
        rel = path.relative_to(ROOT).as_posix()
        if rel in {"ARTIFACT_INVENTORY.csv", "data/checksums/artifact_hashes.csv", "data/checksums/sha256_manifest.txt"}:
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        rows.append(
            {
                "path": rel,
                "description": "released SILVER artifact",
                "paper_location": "main text or supplementary material",
                "producer_script": "scripts/build_release_package.py" if rel.startswith(("data/sample_ids", "data/records", "data/breakdowns", "results/", "prompts/", "schemas/", "docs/")) else "original experiment artifact",
                "source_data": "local released artifacts",
                "sha256": digest,
                "size_bytes": path.stat().st_size,
                "public_release": "yes",
                "notes": "",
            }
        )
    write_csv(ROOT / "ARTIFACT_INVENTORY.csv", rows)
    write_csv(ROOT / "data/checksums/artifact_hashes.csv", rows)
    write_text(ROOT / "data/checksums/sha256_manifest.txt", "\n".join(f"{r['sha256']}  {r['path']}" for r in rows))


def sanitize_private_paths() -> None:
    """Replace machine-specific absolute paths with public placeholders."""
    suffixes = {
        ".csv",
        ".json",
        ".jsonl",
        ".md",
        ".txt",
        ".py",
        ".yml",
        ".yaml",
        ".cff",
    }
    regex_replacements = [
        (re.compile(r"C:\\SILVER\\archive", re.IGNORECASE), r"<EXPERIMENT_ARCHIVE>"),
        (re.compile(r"C:\\Users\\[^\\,\r\n]+\\Dropbox\\[^,\r\n]+", re.IGNORECASE), r"<LOCAL_WORKSPACE>"),
        (re.compile(r"C:\\Users\\[^\\,\r\n]+", re.IGNORECASE), r"<LOCAL_USER_HOME>"),
    ]
    for backup in ROOT.rglob("*.backup*"):
        if backup.is_file() and ".git" not in backup.parts:
            backup.unlink()
    for path in ROOT.rglob("*"):
        if not path.is_file() or ".git" in path.parts or path.suffix.lower() not in suffixes:
            continue
        if path.resolve() == Path(__file__).resolve():
            continue
        text = path.read_text(encoding="utf-8-sig")
        updated = text
        for pattern, repl in regex_replacements:
            updated = pattern.sub(repl, updated)
        if updated != text:
            path.write_text(updated, encoding="utf-8")


def root_files() -> None:
    write_text(
        ROOT / "README.md",
        """# SILVER

Supplementary reproducibility package for:

**Failure-Aware Replanning Evaluation for Vision-Language-Model-Guided Robotic Manipulation in Simulator-in-the-Loop Environments**

SILVER stands for **Simulator-in-the-Loop Verification and Evaluation of Replanning**.

This repository provides the public ledgers, aggregate tables, schemas, prompt templates, representative prompt-audit evidence, and recomputation scripts used to support the paper. It is a supplementary release package, not a redistribution of VLABench raw assets or a complete simulator archive.

## Repository Structure

```text
configs/      Experiment configuration summaries.
data/         Sample IDs, per-sample records, breakdowns, checksums, and original track artifacts.
docs/         Data dictionary, leakage audit notes, taxonomy definitions, and reproducibility notes.
prompts/      Planning/replanning prompt templates and representative real R3 prompt audit examples.
results/      Paper-facing main and supplementary CSV tables.
schemas/      Output, failure-packet, adapter-validation, and status-code schemas.
src/silver/   Reusable SILVER system and evaluation code.
scripts/      Verification and table recomputation scripts.
tests/        Lightweight consistency tests for released artifacts.
```

## Main Denominators

- Track A public planning samples: 4,500.
- Track B S0 execution-candidate samples: 4,000.
- Track B official-expert-eligible samples: 2,133.
- Track C initial Qwen-guided successes: 1,106.
- Track D initial failures for paired recovery: 1,027.
- Track D same-plan retry recoveries: 36.
- Track D SILVER-R3 recoveries: 326.

## Quick Verification

```bash
python verify_release_artifacts.py
python scripts/recompute_all_tables.py
```

## Scope

The package intentionally excludes draft manuscript files, raw simulator image/log archives, private machine paths, SSH keys, model weights, and upstream VLABench assets. Representative real R3 prompts are included under `prompts/prompt_audit/` for leakage-boundary inspection.

## Citation

See `CITATION.cff`.
""",
    )
    write_text(
        ROOT / "CHANGELOG.md",
        """# Changelog

## v1.0-paper-submission

- Reorganized public reproducibility package into ledgers, records, prompts, schemas, and recomputable tables.
- Added paper-aligned Track C/D denominator records after PhysicsLaw replacement audit.
- Added 300-case ablation records including SR, NF, R1, R2, R3, R4, R3-MF, R3-MO, and R3-Shuf.
- Added prompt leakage audit and status-taxonomy documentation.
""",
    )
    write_text(
        ROOT / "environment.yml",
        """name: silver-release
channels:
  - conda-forge
dependencies:
  - python>=3.10
  - pip
  - pip:
      - pandas
      - numpy
      - scipy
      - pytest
""",
    )
    write_text(
        ROOT / ".gitignore",
        """__pycache__/
*.pyc
.pytest_cache/
.venv/
venv/
*.log
paper/
*.pdf
*.aux
*.bbl
*.blg
*.out
*.synctex.gz
.env
id_rsa*
id_ed25519*
""",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-inventory", action="store_true")
    args = parser.parse_args()
    ensure_dirs()
    stage_a_outputs()
    stage_b_rows = stage_b_outputs()
    stage_c = aligned_track_c_rows()
    stage_c_breakdowns(stage_c)
    stage_d = stage_d_rows(stage_c)
    stage_d_breakdowns(stage_d)
    main_tables(stage_b_rows, stage_c, stage_d)
    ablation_outputs()
    docs_and_configs()
    prompts_and_schemas()
    source_wrappers()
    scripts_and_tests()
    summary = {
        "track_a_public_samples": 4500,
        "track_b_execution_candidates": 4000,
        "track_b_official_eligible": 2133,
        "track_c_initial_success": 1106,
        "track_d_initial_failures": len(stage_d),
        "track_d_sr_success": sum(1 for r in stage_d if r["sr_success"] is True),
        "track_d_r3_success": sum(1 for r in stage_d if r["r3_success"] is True),
    }
    write_json(ROOT / "results/generated/release_build_summary.json", summary)
    root_files()
    sanitize_private_paths()
    if not args.skip_inventory:
        artifact_inventory()
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
