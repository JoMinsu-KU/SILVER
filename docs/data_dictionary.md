# Data Dictionary

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
