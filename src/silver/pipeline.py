"""Minimal SILVER replanning pipeline API."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .client import build_multimodal_user_message, chat_completion
from .executor_adapter import convert_sequence_to_executor_plan, sequence_from_parsed_output
from .prompt_builder import build_r3_prompt
from .result_parser import parse_chat_completion


@dataclass
class SILVERReplanner:
    """Small convenience wrapper around the SILVER R3 method."""

    base_url: str
    model: str
    temperature: float = 0
    max_tokens: int = 1024

    def build_prompt(
        self,
        *,
        instruction: str,
        initial_executor_plan: dict[str, Any],
        track_c_status: str,
        execution_result: dict[str, Any],
        adapter_validation: dict[str, Any],
    ) -> str:
        return build_r3_prompt(
            instruction=instruction,
            initial_executor_plan=initial_executor_plan,
            track_c_status=track_c_status,
            execution_result=execution_result,
            adapter_validation=adapter_validation,
        )

    def build_message(self, prompt: str, image_path: Path | None = None) -> dict[str, Any]:
        return build_multimodal_user_message(prompt, image_path)

    def call(self, messages: list[dict[str, Any]]) -> dict[str, Any]:
        return chat_completion(
            base_url=self.base_url,
            model=self.model,
            messages=messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )

    def parse_response(self, raw_response: dict[str, Any]) -> dict[str, Any]:
        return parse_chat_completion(raw_response)

    def convert_to_executor_plan(
        self,
        *,
        sample_id: str,
        parsed_output: dict[str, Any],
        entity_registry: list[dict[str, Any]],
        source: str = "silver_r3",
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        sequence = sequence_from_parsed_output(parsed_output)
        return convert_sequence_to_executor_plan(sample_id, sequence, entity_registry, source)


__all__ = ["SILVERReplanner"]
