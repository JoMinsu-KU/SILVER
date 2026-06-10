"""Public executor-adapter API used by SILVER.

The implementation is re-exported from the evaluated VLABench adapter so the
release package exposes the exact conversion rules used in the experiments.
This layer does not execute MuJoCo/VLABench by itself; it converts a structured
VLM plan into the SkillLib-compatible executor-plan representation.
"""

from __future__ import annotations

from silver.evaluation.vlabench_executor_adapter import (
    SUPPORTED_PARAMS,
    SUPPORTED_SKILLS,
    convert_sequence_to_executor_plan,
    normalize_sequence,
    registry_by_id,
    registry_by_name,
    resolve_component,
    sequence_from_parsed_output,
)

__all__ = [
    "SUPPORTED_PARAMS",
    "SUPPORTED_SKILLS",
    "convert_sequence_to_executor_plan",
    "normalize_sequence",
    "registry_by_id",
    "registry_by_name",
    "resolve_component",
    "sequence_from_parsed_output",
]

