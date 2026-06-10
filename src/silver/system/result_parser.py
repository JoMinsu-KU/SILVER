"""Response parsing and schema checks for SILVER VLM outputs."""

from __future__ import annotations

from typing import Any

from silver.evaluation.vlabench_plan_evaluator import extract_json, validate_prediction

from .executor_adapter import normalize_sequence


def assistant_text(raw_response: dict[str, Any]) -> str:
    """Extract assistant content from an OpenAI-compatible chat response."""

    choices = raw_response.get("choices", []) if isinstance(raw_response, dict) else []
    if not choices or not isinstance(choices[0], dict):
        return ""
    message = choices[0].get("message", {})
    if not isinstance(message, dict):
        return ""
    content = message.get("content", "")
    return content if isinstance(content, str) else ""


def parse_assistant_json(text: str) -> dict[str, Any]:
    """Parse a text response into the release-package parsed-output format."""

    parsed_json, parse_error = extract_json(text)
    schema_valid, schema_errors = validate_prediction(parsed_json) if parse_error is None else (False, [parse_error])
    return {
        "assistant_text": text,
        "parsed_json": parsed_json,
        "parse_error": parse_error,
        "schema_valid": schema_valid,
        "schema_errors": schema_errors,
        "skill_sequence": normalize_sequence(parsed_json),
    }


def parse_chat_completion(raw_response: dict[str, Any]) -> dict[str, Any]:
    """Parse an OpenAI-compatible chat completion response."""

    return parse_assistant_json(assistant_text(raw_response))


__all__ = [
    "assistant_text",
    "parse_assistant_json",
    "parse_chat_completion",
]

