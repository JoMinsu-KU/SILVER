# SILVER Experiment Data Audit

Audit date: 2026-06-10  
Remote host: `[remote-host-redacted]` / `DESKTOP-4F6BFJ8`  
Remote archive root: `C:\SILVER\archive`

## 1. Remote Artifact Roots

The following remote result roots were found and used for this audit.

| Track | Remote path | Status |
|---|---|---|
| Track A/B | `C:\SILVER\archive\silver_track_ab_20260523` | Found |
| Track C | `C:\SILVER\archive\silver_track_c_qwen_guided_20260524` | Found |
| Track D | `C:\SILVER\archive\silver_track_d_replanning_attribution_20260527` | Found |

## 2. Track A Verification

Source files:

- `track_a_vlabench_planning_20260510\manifest\vlabench_sample_manifest.jsonl`
- `track_a_vlabench_planning_20260510\metrics\vlabench_planning_metrics_summary.json`

Verified results:

| Item | Recomputed / read from artifact | Paper value | Match |
|---|---:|---:|---|
| Public samples | 4,500 | 4,500 | Yes |
| Evaluated outputs | 13,500 | 13,500 | Yes |
| P1 schema valid | 73.4% | 73.4% | Yes |
| P1 exact match | 0.0% | 0.0% | Yes |
| P1 step F1 | 0.0% | 0.0% | Yes |
| P1 edit distance | 2.399 | 2.399 | Yes |
| P2 schema valid | 79.8% | 79.8% | Yes |
| P2 exact match | 13.2% | 13.2% | Yes |
| P2 step F1 | 31.4% | 31.4% | Yes |
| P2 edit distance | 1.731 | 1.731 | Yes |
| P3 schema valid | 80.2% | 80.2% | Yes |
| P3 exact match | 0.0% | 0.0% | Yes |
| P3 step F1 | 0.0% | 0.0% | Yes |
| P3 edit distance | 2.830 | 2.830 | Yes |

Conclusion: Track A was executed over 4,500 samples and three prompt conditions, yielding 13,500 evaluated outputs. The paper's Track A table is consistent with the remote metrics summary.

## 3. Track B Verification

Source files:

- `silver-official-guided-evaluation-20260516\track_b\generic_compatible_official\metrics\s0_full_4000_preload_target_official_summary.json`
- `silver-official-guided-evaluation-20260516\track_b\generic_compatible_official\metrics\s0_full_4000_preload_target_official_results.csv`

Verified results:

| Item | Recomputed / read from artifact | Paper value | Match |
|---|---:|---:|---|
| S0 generic-compatible samples | 4,000 | 4,000 | Yes |
| Processed rows | 4,000 | 4,000 | Yes |
| Completed | true | true | Yes |
| B0 official eligible | 2,133 | 2,133 | Yes |
| B1 condition failure | 1,217 | 1,217 | Yes |
| B3 native exception | 214 | 214 | Yes |
| B4 timeout | 57 | 57 | Yes |
| B5 nondeterministic mismatch | 379 | 379 | Yes |

Category breakdown:

| Category | B0 eligible | B1 condition failure | B3 native exception | B4 timeout | B5 nondeterministic |
|---|---:|---:|---:|---:|---:|
| CommenSence | 519 | 213 | 13 | 2 | 53 |
| M&T | 616 | 222 | 1 | 0 | 61 |
| PhysicsLaw | 42 | 296 | 100 | 0 | 162 |
| Semantic | 507 | 228 | 100 | 1 | 64 |
| Spatial | 449 | 258 | 0 | 54 | 39 |

Conclusion: Track B was fully executed for 4,000 samples. The official-expert-eligible denominator of 2,133 used in the paper is directly supported by the Track B summary and CSV ledger.

## 4. Track C Verification

Source file:

- `silver_track_c_qwen_guided_20260524\metrics\qwen_guided_execution_results.csv`

Verified results:

| Item | Recomputed / read from artifact | Paper value | Match |
|---|---:|---:|---|
| Track C rows | 2,133 | 2,133 | Yes |
| Unique sample IDs | 2,133 | 2,133 | Yes |
| C0 Qwen-guided success | 1,093 | 1,093 | Yes |
| C1 condition failure | 790 | 790 | Yes |
| C2 conversion failure | 210 | 210 | Yes |
| C3 entity mapping failure | 39 | 39 | Yes |
| C4 unsupported skill | 1 | 1 | Yes |
| Initial failures for Track D | 1,040 | 1,040 | Yes |

Execution-status cross-check:

| Track C status | Execution status | Count |
|---|---|---:|
| C0 Qwen-guided success | completed | 1,093 |
| C1 condition failure | completed | 772 |
| C1 condition failure | expert_sequence_error | 18 |
| C2 conversion failure | not_run_conversion_failed | 210 |
| C3 entity mapping failure | not_run_conversion_failed | 39 |
| C4 unsupported skill | not_run_conversion_failed | 1 |

Category breakdown:

| Category | C0 | C1 | C2 | C3 | C4 |
|---|---:|---:|---:|---:|---:|
| CommenSence | 311 | 174 | 34 | 0 | 0 |
| M&T | 326 | 193 | 95 | 2 | 0 |
| PhysicsLaw | 0 | 0 | 42 | 0 | 0 |
| Semantic | 342 | 127 | 37 | 0 | 1 |
| Spatial | 114 | 296 | 2 | 37 | 0 |

Conclusion: Track C was executed on the 2,133 Track B eligible samples. The paper's Track C status table and category table are consistent with the remote ledger. One nuance should be kept in mind: 18 of the C1 condition-failure cases have `execution_status=expert_sequence_error`; they are included in the C1 failure class in the current paper.

## 5. Track D Main Recovery Verification

Source files:

- `silver_track_d_replanning_attribution_20260527\metrics\track_d_same_plan_retry_all_summary.json`
- `silver_track_d_replanning_attribution_20260527\metrics\track_d_replan_R3_execution_all_summary.json`
- `silver_track_d_replanning_attribution_20260527\metrics\track_d_replan_R3_inference_all_summary.json`
- `silver_track_d_replanning_attribution_20260527\metrics\track_d_R3_summary_all.json`
- `silver_track_d_replanning_attribution_20260527\metrics\track_d_same_plan_vs_replan_R3_all.csv`

Verified results:

| Item | Recomputed / read from artifact | Paper value | Match |
|---|---:|---:|---|
| Track D initial failure cases | 1,040 | 1,040 | Yes |
| Paired completed cases | 1,040 | 1,040 | Yes |
| Same-plan retry success | 36 | 36 | Yes |
| R3 success | 326 | 326 | Yes |
| Attributed recovery gain | 0.278846 | 27.9%p | Yes |
| A0 no recovery | 702 | 702 | Yes |
| A1 same-plan retry recovered | 36 | 36 | Yes |
| A3/A4 replan recovered | 302 | 302 | Yes |

Post-recovery status:

| Status | Same-plan retry | R3 |
|---|---:|---:|
| C0 recovered success | 36 | 326 |
| C1 condition failure | 754 | 302 |
| C2 conversion failure | 210 | 174 |
| C3 entity mapping failure | 39 | 238 |
| C4 unsupported skill | 1 | 0 |

Paired outcome:

| Pair | Count |
|---|---:|
| SR success / R3 success | 24 |
| SR success / R3 fail | 12 |
| SR fail / R3 success | 302 |
| SR fail / R3 fail | 702 |

Evidence completeness:

| Artifact requirement | Count |
|---|---:|
| Case directory exists | 1,040 |
| `track_d_case_manifest.json` exists | 1,040 |
| `same_plan_retry/execution_result.json` exists | 1,040 |
| `replan_R3/raw_output.json` exists | 1,040 |
| `replan_R3/parsed_output.json` exists | 1,040 |
| `replan_R3/adapter_validation.json` exists | 1,040 |
| `replan_R3/executor_plan.json` exists | 1,040 |
| `replan_R3/prompt_R3.txt` exists | 1,040 |
| R3 completed native execution result exists | 628 |

The 628 R3 native execution results match the R3 conversion-success count. The remaining cases are not executed natively because they are conversion or entity-mapping failures.

Conclusion: Track D was executed over the correct 1,040 initial failure cases, and the paired SR/R3 recovery claims in the paper match the remote artifacts.

## 6. Track D Ablation Verification

Source files:

- `ablation_300\metrics\ablation_300_condition_success_by_variant.csv`
- `ablation_300\metrics\ablation_300_failure_taxonomy_by_variant.csv`
- `ablation_300\metrics\ablation_300_pairwise_comparison.csv`

Verified results:

| Variant | Completed rows | Success | Success rate | Paper value | Match |
|---|---:|---:|---:|---:|---|
| SR | 300 | 14 | 4.7% | 14/300 | Yes |
| NF | 300 | 51 | 17.0% | 51/300 | Yes |
| R1 | 300 | 75 | 25.0% | 75/300 | Yes |
| R2 | 300 | 41 | 13.7% | 41/300 | Yes |
| R3 | 300 | 85 | 28.3% | 85/300 | Yes |
| R4 | 300 | 78 | 26.0% | 78/300 | Yes |

Conclusion: The ablation table in the paper is supported by the remote `ablation_300` metrics.

## 7. Overall Audit Conclusion

The remote experimental artifacts support the main paper analysis:

1. Track A was executed on 4,500 samples under P1/P2/P3, yielding 13,500 evaluated outputs.
2. Track B was executed on 4,000 S0 generic-compatible samples and produced the 2,133 official-expert-eligible denominator.
3. Track C was executed on the 2,133 eligible samples and produced 1,093 initial successes and 1,040 initial failures.
4. Track D was executed on the 1,040 initial failures with paired same-plan retry and R3 replanning results.
5. The 300-case ablation results match the remote ablation metrics.
6. The paper's main numeric claims match the remote metrics and ledgers checked in this audit.

Remaining interpretive cautions:

- Track C includes 18 C1 cases with `execution_status=expert_sequence_error`; these are currently folded into C1 condition failure.
- R3 increases residual C3 entity-mapping failures from 39 under SR to 238 under R3. The paper correctly frames this as a residual grounding bottleneck rather than as solved grounding.
- Track B excludes 1,867 of the 4,000 S0 samples from the main execution denominator. The paper should continue to state clearly that execution and recovery claims are restricted to the official-expert-eligible subset.

