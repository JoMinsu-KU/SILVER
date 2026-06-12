"""Bounded failure-packet construction for SILVER replanning."""

from __future__ import annotations

from typing import Any


def stage_trace_summary(exec_result: dict[str, Any], *, max_stages: int = 8) -> str:
    """Create a compact non-oracle trace summary from an execution result."""

    stages = exec_result.get("stage_results")
    if not isinstance(stages, list):
        return "No stage trace was available."
    parts = []
    for stage in stages[:max_stages]:
        parts.append(
            f"stage {stage.get('stage_index')}: skill={stage.get('skill_name')}, "
            f"stage_success={stage.get('stage_success')}, task_success={stage.get('task_success')}, "
            f"error={stage.get('error')}"
        )
    return "\n".join(parts) if parts else "No stage trace was available."


def build_failure_packet(track_c_status: str, exec_result: dict[str, Any], adapter_validation: dict[str, Any]) -> str:
    """Build the bounded textual failure packet used by R3."""

    errors = ";".join(str(x) for x in adapter_validation.get("conversion_errors", []))
    if track_c_status == "C1_qwen_guided_condition_failure":
        return (
            "The initial Qwen plan was executed, but the task condition was not satisfied. "
            f"execution_status={exec_result.get('execution_status')}; "
            f"condition_success={exec_result.get('condition_success')}; "
            f"progress_score={exec_result.get('progress_score')}; "
            f"intention_score={exec_result.get('intention_score')}."
        )
    if track_c_status == "C2_qwen_conversion_failure":
        return "The initial Qwen output could not be converted into an executable plan: " + errors
    if track_c_status == "C3_entity_mapping_failure":
        return "The initial Qwen output referenced an object or target that could not be mapped to the scene registry: " + errors
    if track_c_status == "C4_unsupported_qwen_skill":
        return "The initial Qwen output proposed an unsupported skill: " + errors
    return "The initial attempt failed."
