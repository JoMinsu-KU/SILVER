# Track A Completion Report

## Scope

- Dataset: `VLABench/vlm_evaluation_v1.0`
- Conditions: `P1`, `P2`, `P3`
- Model: `Qwen/Qwen3-VL-8B-Instruct`
- Execution type: non-interactive public planning only

## Evidence Paths

- Track root: `silver\results\track_a_vlabench_planning_20260510`
- Manifest: `silver\results\track_a_vlabench_planning_20260510\manifest\vlabench_sample_manifest.jsonl`
- Data folders: `silver\results\track_a_vlabench_planning_20260510\data`
- Metrics: `silver\results\track_a_vlabench_planning_20260510\metrics`
- Failed samples: `silver\results\track_a_vlabench_planning_20260510\metrics\failed_samples.jsonl`

## Counts

- Discovered samples: 4500
- Manifest rows: 4500
- Download OK rows: 4500
- Completed condition outputs: 13500
- Missing condition outputs: 0
- Failed log rows: 0

## Taxonomy Summary

```json
{
  "manifest_rows": 4500,
  "download_ok_rows": 4500,
  "skill_counts": {
    "pick": 4735,
    "pour": 700,
    "insert": 400,
    "place": 2135,
    "lift": 800,
    "pull": 900,
    "push": 500,
    "press": 600
  },
  "sequence_length_distribution": {
    "2": 3420,
    "9": 200,
    "4": 71,
    "6": 71,
    "5": 100,
    "10": 8,
    "8": 30,
    "1": 600
  },
  "category_counts": {
    "CommenSence": 800,
    "Complex": 500,
    "M&T": 900,
    "PhysicsLaw": 600,
    "Semantic": 900,
    "Spatial": 800
  },
  "parameter_key_counts": {
    "target_entity_name": 5335,
    "target_container_name": 3735
  }
}
```

## Planning Metrics Summary

```json
{
  "evaluated_outputs": 13500,
  "by_condition": [
    {
      "condition": "P1",
      "n": 4500,
      "schema_valid": 0.7342222222222222,
      "operation_sequence_exact_match": 0.0,
      "skill_name_accuracy": 0.48036666666666666,
      "action_recall_rate": 0.48926172839506177,
      "action_order_accuracy": 0.24977777777777777,
      "step_level_f1": 0.0,
      "sequence_edit_distance": 2.3993333333333333,
      "latency_s": 3.352731250921885,
      "object_argument_accuracy": 0.0,
      "target_argument_accuracy": 0.0
    },
    {
      "condition": "P2",
      "n": 4500,
      "schema_valid": 0.7982222222222223,
      "operation_sequence_exact_match": 0.132,
      "skill_name_accuracy": 0.5008135802469136,
      "action_recall_rate": 0.5087098765432099,
      "action_order_accuracy": 0.2564444444444444,
      "step_level_f1": 0.3138987493987494,
      "sequence_edit_distance": 1.7313333333333334,
      "latency_s": 3.2827841755019294,
      "object_argument_accuracy": 0.5001855976243504,
      "target_argument_accuracy": 0.7184626436781609
    },
    {
      "condition": "P3",
      "n": 4500,
      "schema_valid": 0.8024444444444444,
      "operation_sequence_exact_match": 0.0,
      "skill_name_accuracy": 0.4543676767676768,
      "action_recall_rate": 0.5613975308641975,
      "action_order_accuracy": 0.27111111111111114,
      "step_level_f1": 0.0,
      "sequence_edit_distance": 2.8297777777777777,
      "latency_s": 3.6206115244759456,
      "object_argument_accuracy": 0.0,
      "target_argument_accuracy": 0.0
    }
  ],
  "gains": [
    {
      "gain": "visual_prompt_gain_P2_minus_P1",
      "operation_sequence_exact_match": 0.132,
      "step_level_f1": 0.3138987493987494
    },
    {
      "gain": "schema_guidance_gain_P3_minus_P1",
      "operation_sequence_exact_match": 0.0,
      "step_level_f1": 0.0
    }
  ]
}
```

## Evidence Review

```json
{
  "manifest_rows": 4500,
  "download_ok_rows": 4500,
  "missing_visual_or_gt_count": 0,
  "missing_visual_or_gt_examples": [],
  "completed_condition_outputs": 13500,
  "missing_condition_outputs": 0,
  "failed_log_rows": 0,
  "retry_log_rows": 13500
}
```

## Representative Failures

- No failed rows recorded.

## Integrity Statement

No metric in this report should be interpreted as complete unless every intended condition output is present or explicitly counted as failed/missing. Missing and failed rows are preserved in the evidence logs and are not silently dropped.
