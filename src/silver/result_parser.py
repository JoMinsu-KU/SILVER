"""Response parsing and schema checks for SILVER VLM outputs."""

from __future__ import annotations

import json
import re
from typing import Any

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


def extract_json(text: str) -> tuple[Any | None, str | None]:
    """Extract a JSON object from a model response string."""

    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text, flags=re.IGNORECASE).strip()
        text = re.sub(r"```$", "", text).strip()
    try:
        return json.loads(text), None
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            return None, "no_json_object_found"
        try:
            return json.loads(match.group(0)), None
        except json.JSONDecodeError as exc:
            return None, f"json_decode_error:{exc}"


def validate_prediction(obj: Any) -> tuple[bool, list[str]]:
    """Validate the minimal structured-output contract used by SILVER."""

    errors: list[str] = []
    if not isinstance(obj, dict):
        return False, ["root_not_object"]
    seq = obj.get("skill_sequence")
    if not isinstance(seq, list) or not seq:
        errors.append("skill_sequence_missing_or_empty")
        return False, errors
    for idx, step in enumerate(seq, start=1):
        if not isinstance(step, dict):
            errors.append(f"step_{idx}_not_object")
            continue
        if not isinstance(step.get("name"), str) or not step.get("name"):
            errors.append(f"step_{idx}_name_invalid")
        if not isinstance(step.get("params", {}), dict):
            errors.append(f"step_{idx}_params_invalid")
    return not errors, errors


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
    "extract_json",
    "parse_assistant_json",
    "parse_chat_completion",
    "validate_prediction",
]
