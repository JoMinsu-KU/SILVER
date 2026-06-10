from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent


REQUIRED_FILES = [
    "data/track_a/metrics/vlabench_planning_metrics_summary.json",
    "data/track_a/metrics/vlabench_planning_metrics_by_condition.csv",
    "data/track_a/manifest/vlabench_sample_manifest.jsonl",
    "data/track_b/metrics/s0_full_4000_preload_target_official_summary.json",
    "data/track_b/metrics/s0_full_4000_preload_target_official_results.csv",
    "data/track_b/manifest/s0_full_4000_preload_target_official_eligibility_ledger.jsonl",
    "data/track_b/taxonomy/metrics/track_b_taxonomy_summary.json",
    "data/track_c/metrics/qwen_guided_execution_summary.json",
    "data/track_c/metrics/qwen_guided_execution_results.csv",
    "data/track_c/manifest/qwen_guided_case_manifest.jsonl",
    "data/track_d/metrics/track_d_replan_R3_execution_all_summary.json",
    "data/track_d/metrics/track_d_same_plan_vs_replan_R3_all.csv",
    "data/track_d/metrics/track_d_replan_R3_execution_all_results.csv",
    "data/track_d/metrics/track_d_replan_R3_inference_all_results.csv",
    "data/track_d/manifest/track_d_all_failure_cases.jsonl",
    "data/track_d/ablation_300/metrics/ablation_300_summary.json",
    "data/track_d/ablation_300/metrics/ablation_300_pairwise_comparison.csv",
    "data/track_d/ablation_300/manifest/track_d_ablation_300_manifest.jsonl",
    "examples/r3_prompt_audit_20260610/R3_PROMPT_AUDIT_SUMMARY.json",
    "examples/r3_prompt_audit_20260610/R3_PROMPT_AUDIT_NOTE.md",
    "docs/SILVER_FULL_EXPERIMENT_RESULT_REPORT_REVISED_20260602.md",
    "docs/EXPERIMENT_DATA_AUDIT_20260610.md",
]


def count_lines(path: Path) -> int:
    with path.open("r", encoding="utf-8-sig", errors="replace") as f:
        return sum(1 for _ in f)


def load_json(path: Path):
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def main() -> int:
    missing = []
    for rel in REQUIRED_FILES:
        path = ROOT / rel
        if not path.exists():
            missing.append(rel)

    print("SILVER release artifact check")
    print(f"root: {ROOT}")
    print(f"required files: {len(REQUIRED_FILES)}")
    print(f"missing files: {len(missing)}")
    for rel in missing:
        print(f"  MISSING: {rel}")

    checks = {}
    track_a_manifest = ROOT / "data/track_a/manifest/vlabench_sample_manifest.jsonl"
    track_b_results = ROOT / "data/track_b/metrics/s0_full_4000_preload_target_official_results.csv"
    track_c_results = ROOT / "data/track_c/metrics/qwen_guided_execution_results.csv"
    track_d_compare = ROOT / "data/track_d/metrics/track_d_same_plan_vs_replan_R3_all.csv"
    ablation_manifest = ROOT / "data/track_d/ablation_300/manifest/track_d_ablation_300_manifest.jsonl"
    r3_audit = ROOT / "examples/r3_prompt_audit_20260610/R3_PROMPT_AUDIT_SUMMARY.json"

    if track_a_manifest.exists():
        checks["track_a_manifest_lines"] = count_lines(track_a_manifest)
    if track_b_results.exists():
        checks["track_b_results_lines_including_header"] = count_lines(track_b_results)
    if track_c_results.exists():
        checks["track_c_results_lines_including_header"] = count_lines(track_c_results)
    if track_d_compare.exists():
        checks["track_d_compare_lines_including_header"] = count_lines(track_d_compare)
    if ablation_manifest.exists():
        checks["track_d_ablation_manifest_lines"] = count_lines(ablation_manifest)
    if r3_audit.exists():
        audit = load_json(r3_audit)
        checks["r3_prompt_files"] = audit.get("counts", {}).get("prompt_R3_files")
        checks["r3_global_forbidden_term_scan"] = audit.get("global_forbidden_term_scan")

    print(json.dumps(checks, ensure_ascii=False, indent=2))
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
