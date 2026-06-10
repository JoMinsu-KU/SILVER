"""Report builder and evidence review for VLABench Track A."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


TRACK_ROOT = Path("silver/results/track_a_vlabench_planning_20260510")
CONDITIONS = ("P1", "P2", "P3")


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


def evidence_review(track_root: Path, conditions: tuple[str, ...] = CONDITIONS) -> dict[str, Any]:
    manifest = read_jsonl(track_root / "manifest" / "vlabench_sample_manifest.jsonl")
    missing_visual_or_gt: list[dict[str, Any]] = []
    completed_outputs = 0
    missing_outputs = 0
    for row in manifest:
        local_dir = Path(row.get("local_dir", ""))
        required = ["input.png", "input_mask.png", "instruction.txt", "operation_sequence.json", "env_config.json"]
        missing = [name for name in required if not (local_dir / name).exists()]
        if missing:
            missing_visual_or_gt.append({"sample_id": row.get("sample_id"), "missing": missing})
        for condition in conditions:
            files = [
                local_dir / f"raw_output_{condition}.json",
                local_dir / f"parsed_output_{condition}.json",
                local_dir / f"validation_{condition}.json",
            ]
            if all(path.exists() for path in files):
                completed_outputs += 1
            else:
                missing_outputs += 1
    failed = read_jsonl(track_root / "metrics" / "failed_samples.jsonl")
    retry = read_jsonl(track_root / "metrics" / "retry_log.jsonl")
    review = {
        "manifest_rows": len(manifest),
        "download_ok_rows": sum(1 for r in manifest if r.get("download_ok")),
        "missing_visual_or_gt_count": len(missing_visual_or_gt),
        "missing_visual_or_gt_examples": missing_visual_or_gt[:20],
        "completed_condition_outputs": completed_outputs,
        "missing_condition_outputs": missing_outputs,
        "failed_log_rows": len(failed),
        "retry_log_rows": len(retry),
    }
    out = track_root / "metrics" / "evidence_review.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(review, ensure_ascii=False, indent=2), encoding="utf-8")
    return review


def build_completion_report(track_root: Path) -> Path:
    report_dir = track_root / "report"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "TRACK_A_COMPLETION_REPORT.md"
    preflight_path = track_root / "manifest" / "preflight.json"
    metrics_path = track_root / "metrics" / "vlabench_planning_metrics_summary.json"
    taxonomy_path = track_root / "metrics" / "skill_taxonomy_summary.json"
    review = evidence_review(track_root)

    preflight = json.loads(preflight_path.read_text(encoding="utf-8")) if preflight_path.exists() else {}
    metrics = json.loads(metrics_path.read_text(encoding="utf-8")) if metrics_path.exists() else {}
    taxonomy = json.loads(taxonomy_path.read_text(encoding="utf-8")) if taxonomy_path.exists() else {}
    failed_rows = read_jsonl(track_root / "metrics" / "failed_samples.jsonl")

    lines = [
        "# Track A Completion Report",
        "",
        "## Scope",
        "",
        "- Dataset: `VLABench/vlm_evaluation_v1.0`",
        "- Conditions: `P1`, `P2`, `P3`",
        "- Model: `Qwen/Qwen3-VL-8B-Instruct`",
        "- Execution type: non-interactive public planning only",
        "",
        "## Evidence Paths",
        "",
        f"- Track root: `{track_root}`",
        f"- Manifest: `{track_root / 'manifest' / 'vlabench_sample_manifest.jsonl'}`",
        f"- Data folders: `{track_root / 'data'}`",
        f"- Metrics: `{track_root / 'metrics'}`",
        f"- Failed samples: `{track_root / 'metrics' / 'failed_samples.jsonl'}`",
        "",
        "## Counts",
        "",
        f"- Discovered samples: {preflight.get('discovered_samples', 'unknown')}",
        f"- Manifest rows: {review['manifest_rows']}",
        f"- Download OK rows: {review['download_ok_rows']}",
        f"- Completed condition outputs: {review['completed_condition_outputs']}",
        f"- Missing condition outputs: {review['missing_condition_outputs']}",
        f"- Failed log rows: {review['failed_log_rows']}",
        "",
        "## Taxonomy Summary",
        "",
        "```json",
        json.dumps(taxonomy, ensure_ascii=False, indent=2)[:6000],
        "```",
        "",
        "## Planning Metrics Summary",
        "",
        "```json",
        json.dumps(metrics, ensure_ascii=False, indent=2)[:6000],
        "```",
        "",
        "## Evidence Review",
        "",
        "```json",
        json.dumps(review, ensure_ascii=False, indent=2)[:6000],
        "```",
        "",
        "## Representative Failures",
        "",
    ]
    if failed_rows:
        lines.extend(["```json", json.dumps(failed_rows[:20], ensure_ascii=False, indent=2), "```"])
    else:
        lines.append("- No failed rows recorded.")
    lines.extend(
        [
            "",
            "## Integrity Statement",
            "",
            "No metric in this report should be interpreted as complete unless every intended condition output is present or explicitly counted as failed/missing. Missing and failed rows are preserved in the evidence logs and are not silently dropped.",
        ]
    )
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Track A report and evidence review.")
    parser.add_argument("--track_root", type=Path, default=TRACK_ROOT)
    args = parser.parse_args()
    path = build_completion_report(args.track_root)
    print(path)


if __name__ == "__main__":
    main()
