"""Public SILVER method-level API."""

from .attribution import assign_recovery_attribution, attributed_recovery_gain, boolish
from .executor_adapter import convert_sequence_to_executor_plan, sequence_from_parsed_output
from .failure_packet import build_failure_packet, stage_trace_summary
from .pipeline import SILVERReplanner
from .prompt_builder import build_r3_prompt
from .result_parser import parse_assistant_json, parse_chat_completion
from .schema import allowed_replanning_schema

__all__ = [
    "SILVERReplanner",
    "allowed_replanning_schema",
    "assign_recovery_attribution",
    "attributed_recovery_gain",
    "boolish",
    "build_failure_packet",
    "build_r3_prompt",
    "convert_sequence_to_executor_plan",
    "parse_assistant_json",
    "parse_chat_completion",
    "sequence_from_parsed_output",
    "stage_trace_summary",
]
