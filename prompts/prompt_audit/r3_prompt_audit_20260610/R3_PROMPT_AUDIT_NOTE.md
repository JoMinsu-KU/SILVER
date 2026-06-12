# R3 Prompt Audit Note

Date: 2026-06-10

## Purpose

This audit checks whether the real Track D R3 prompts follow the information boundary described in the paper. R3 is intended to provide failure context for replanning without exposing the official expert plan, the ground-truth operation sequence, or a direct next-action answer.

## Source Archive

- Original archive root: `<EXPERIMENT_ARCHIVE>\silver_track_d_replanning_attribution_20260527`
- Original R3 prompt pattern: `data\<category>\<task>\exampleXX\replan_R3\prompt_R3.txt`
- Legacy archive prompt count: 1,040 R3 prompt files
- Paper-aligned denominator: 1,027 initial failures after the 2026-06-11 PhysicsLaw replacement alignment
- Comparison CSV: `metrics\track_d_same_plan_vs_replan_R3_all.csv`
- R3 execution CSV: `metrics\track_d_replan_R3_execution_all_results.csv`

## Leakage Keyword Scan

The legacy 1,040 `prompt_R3.txt` files were scanned for high-risk leakage terms:

- `ground truth`
- `expert`
- `official`
- `correct action`
- `answer`
- `operation_sequence`
- `gt`
- `oracle`

These phrases were not found in the prompt text bodies inspected for this release.

## Observed R3 Prompt Structure

Five representative cases were copied into this release package. The prompts include:

- the original public task instruction,
- the initial Qwen-derived executor plan,
- bounded failure diagnosis,
- stage-level execution summary,
- allowed skill/output schema.

The R3 inference code attaches the final failure image as a multimodal image input. The image is not embedded as text inside `prompt_R3.txt`.

## Representative Cases

| Case type | Sample ID | R3 result | SR result | Included evidence |
|---|---|---:|---:|---|
| R3 success | `CommenSence/insert_flower_common_sense/example31` | success | fail | prompt, raw/parsed output, adapter validation, executor plan, failure mosaic, initial failure log |
| R3 failure | `CommenSence/insert_flower_common_sense/example9` | fail | fail | prompt, raw/parsed output, adapter validation, executor plan, failure mosaic, initial failure log |
| C2 conversion failure | `CommenSence/select_billiards_common_sense/example1` | conversion failure | conversion failure | prompt, raw/parsed output, adapter validation |
| C3 mapping failure | `CommenSence/select_billiards_common_sense/example3` | mapping failure | mapping failure | prompt, raw/parsed output, adapter validation, executor plan, failure mosaic |
| SR success and R3 failure | `CommenSence/insert_flower_common_sense/example81` | fail | success | prompt, raw/parsed output, adapter validation, executor plan, failure mosaic, initial failure log |

## Interpretation

The copied prompts are consistent with the paper's stated R3 boundary:

- R3 asks the model to revise the failed plan rather than simply retry it.
- The prompt includes failure observation and stage-level trace summaries.
- The prompt does not include the official expert operation sequence, official action order, or a direct next-correct-action instruction.
- The final failure image is supplied as a multimodal input rather than as text.

One important boundary detail is that the initial Qwen executor plan may contain scene entity names, component IDs, positions, and XML paths. These fields are produced by the Track C conversion from the Qwen plan and the scene registry. They are not the official expert answer, but they should be described explicitly when discussing the prompt audit.

## Local Contents

Each copied case directory may include:

- `prompt_R3.txt`
- `raw_output.json`
- `parsed_output.json`
- `adapter_validation.json`
- `executor_plan.json`
- `entity_registry.json`
- `case_audit.json`
- `failure_final_mosaic.png`, when available
- `initial_failure_execution_result.json`, when available
- `initial_failure_orchestrator.log`, when available
