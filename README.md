# SILVER Reproducibility Package

This repository contains the code, aggregate artifacts, and representative evidence for the paper:

**Failure-Aware Replanning Evaluation for Vision-Language-Model-Guided Robotic Manipulation in Simulator-in-the-Loop Environments**

The package is intentionally clean. It includes the scripts and aggregate files needed to inspect and recompute the main reported metrics, while excluding large raw simulator evidence folders.

## What Is Included

```text
src/silver/
  system/                  Reusable SILVER prompt, parser, executor-adapter, attribution, and pipeline code
  evaluation/              Core Track A-D evaluation and analysis scripts

data/
  track_a/                 Public planning metrics, manifest, and report
  track_b/                 Official expert eligibility metrics, manifest, taxonomy, evidence audit
  track_c/                 Qwen-guided execution metrics, manifest, and reports
  track_d/                 Same-plan retry, R3 replanning, and ablation metrics/manifests/reports
    ablation_300/          Stratified 300-case NF/R1/R2/R3/R4 ablation artifacts

examples/
  r3_prompt_audit_20260610/
                            Representative real R3 prompts and evidence exported from the experiment archive

docs/
  SILVER_FULL_EXPERIMENT_RESULT_REPORT_REVISED_20260602.md
  EXPERIMENT_DATA_AUDIT_20260610.md
  protocol and setup notes

verify_release_artifacts.py
                            Lightweight integrity checker for the released artifacts
```

## Main Experimental Tracks

- **Track A:** public VLABench planning evaluation with P1/P2/P3 prompting conditions.
- **Track B:** official expert eligibility filtering and failure taxonomy over the executable VLABench subset.
- **Track C:** Qwen-guided execution over Track-B-eligible samples.
- **Track D:** failure-aware replanning attribution using same-plan retry and SILVER R3.

## Important Scope Notes

- The released package contains aggregate CSV/JSON/JSONL artifacts and representative prompt/evidence cases.
- Full raw simulator evidence, including all images/logs for every execution case, is not included because of size. The paper reports that those artifacts were retained in the experiment archive.
- R3 prompt examples are included under `examples/r3_prompt_audit_20260610/` to support leakage-boundary inspection.
- The reusable SILVER method code is exposed under `src/silver/system/`, including the VLABench SkillLib-compatible executor adapter used to convert structured VLM plans into executable plan records.
- Draft manuscript files are intentionally not included in this repository.
- The package does not include model weights or the VLABench dataset itself. Download those from their original sources.

## Quick Integrity Check

From the repository root:

```bash
python verify_release_artifacts.py
```

The script checks for required metrics, manifest files, reports, and representative R3 prompt evidence.

## Reproducing Aggregate Tables

The released CSV/JSON files are sufficient to recompute the paper-level aggregate tables. Start with:

```text
data/track_a/metrics/vlabench_planning_metrics_summary.json
data/track_b/metrics/s0_full_4000_preload_target_official_summary.json
data/track_c/metrics/qwen_guided_execution_summary.json
data/track_d/metrics/track_d_same_plan_vs_replan_R3_all.csv
data/track_d/metrics/track_d_replan_R3_execution_all_summary.json
```

For the full interpretation, see:

```text
docs/SILVER_FULL_EXPERIMENT_RESULT_REPORT_REVISED_20260602.md
docs/EXPERIMENT_DATA_AUDIT_20260610.md
```

## Environment Summary

The original experiments used:

- VLABench / MuJoCo / dm_control runtime
- Qwen3-VL-8B-Instruct served through an OpenAI-compatible `/v1/chat/completions` endpoint
- Windows + WSL execution for VLABench native simulator runs
- GCP H100 inference server for VLM serving in the remote execution setup

See `docs/ENVIRONMENT_TEMPLATE.md` for a public-safe environment template. Private hostnames, IP addresses, and SSH key material are intentionally not included in this repository.

Some CSV files preserve original `C:\SILVER\archive\...` artifact paths from the experiment machine. These paths are kept as trace identifiers for the original run; they are not required to inspect the aggregate metrics in this package.

## License

This release package is distributed under the MIT License. See `LICENSE`.
