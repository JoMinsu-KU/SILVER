"""Prompt builders for SILVER replanning conditions."""

from __future__ import annotations

import json
from typing import Any

from .failure_packet import build_failure_packet, stage_trace_summary
from .schema import allowed_replanning_schema


def build_r3_prompt(
    *,
    instruction: str,
    initial_executor_plan: dict[str, Any],
    track_c_status: str,
    execution_result: dict[str, Any],
    adapter_validation: dict[str, Any],
) -> str:
    """Build the SILVER R3 replanning prompt."""

    failure_packet = build_failure_packet(track_c_status, execution_result, adapter_validation)
    trace = stage_trace_summary(execution_result)
    schema = allowed_replanning_schema()
    return (
        "You are revising a robot manipulation plan after a failed simulator execution.\n"
        "Return ONLY valid JSON. Do not include markdown.\n\n"
        "Rules:\n"
        "- Use only the allowed output schema.\n"
        "- Do not invent unsupported skills.\n"
        "- Do not copy the failed plan if the failure suggests a wrong object, target, or sequence.\n"
        "- Do not reveal chain-of-thought; use only a short rationale_summary.\n\n"
        f"Instruction:\n{instruction.strip()}\n\n"
        f"Initial Qwen executor plan:\n{json.dumps(initial_executor_plan, ensure_ascii=False)}\n\n"
        f"Failure observation:\n{failure_packet}\n\n"
        f"Executed trace summary:\n{trace}\n\n"
        f"Allowed output schema:\n{json.dumps(schema, ensure_ascii=False, indent=2)}\n"
    )
