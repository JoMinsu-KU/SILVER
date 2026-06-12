"""Skill-level executor-plan adapter used by SILVER.

The adapter converts a structured VLM output into a SkillLib-compatible
executor-plan representation. It does not run the simulator, mark success, or
fill in missing entities from ground truth.
"""

from __future__ import annotations

from typing import Any


SUPPORTED_SKILLS = {"pick", "place", "lift", "pull", "press", "push", "pour", "insert"}
SUPPORTED_PARAMS = {"target_entity_name", "target_container_name"}


def _norm_name(value: Any) -> str:
    return "".join(ch for ch in str(value).lower() if ch.isalnum())


def normalize_sequence(obj: Any) -> list[dict[str, Any]]:
    if not isinstance(obj, dict):
        return []
    seq = obj.get("skill_sequence", [])
    if not isinstance(seq, list):
        return []
    out: list[dict[str, Any]] = []
    for step in seq:
        if not isinstance(step, dict):
            continue
        params = step.get("params", {})
        out.append({"name": step.get("name"), "params": params if isinstance(params, dict) else {}})
    return out


def sequence_from_parsed_output(parsed_output: dict[str, Any]) -> list[dict[str, Any]]:
    parsed_json = parsed_output.get("parsed_json") if isinstance(parsed_output, dict) else None
    return normalize_sequence(parsed_json)


def registry_by_id(registry: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    return {
        item["component_id"]: item
        for item in registry
        if isinstance(item, dict) and isinstance(item.get("component_id"), int)
    }


def registry_by_name(registry: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(item["name"]): item for item in registry if isinstance(item, dict) and item.get("name") is not None}


def resolve_component(value: Any, registry: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, str | None]:
    by_id = registry_by_id(registry)
    by_name = registry_by_name(registry)
    if isinstance(value, str) and value.strip().isdigit():
        int_value = int(value.strip())
        if int_value in by_id:
            return by_id[int_value], None
    if isinstance(value, int) and value in by_id:
        return by_id[value], None
    if isinstance(value, str) and value in by_name:
        return by_name[value], None
    if isinstance(value, str):
        normalized = _norm_name(value)
        normalized_matches = [item for item in registry if item.get("name") is not None and _norm_name(item["name"]) == normalized]
        if len(normalized_matches) == 1:
            return normalized_matches[0], None
        substring_matches = [
            item
            for item in registry
            if item.get("name") is not None
            and normalized
            and (normalized in _norm_name(item["name"]) or _norm_name(item["name"]) in normalized)
        ]
        role_filtered = [
            item
            for item in substring_matches
            if item.get("role") in {"target_entity", "target_container", "candidate_entity", "candidate_container"}
        ]
        candidates = role_filtered or substring_matches
        if len(candidates) == 1:
            return candidates[0], None
        if len(candidates) > 1:
            return None, f"ambiguous_component:{value}=>{[item.get('name') for item in candidates]}"
    return None, f"unmapped_component:{value}"


def _param_component(
    step: dict[str, Any],
    key: str,
    registry: list[dict[str, Any]],
    *,
    required: bool,
) -> tuple[dict[str, Any] | None, str | None]:
    params = step.get("params", {})
    if not isinstance(params, dict):
        return None, "params_not_dict"
    if key not in params:
        return None, f"missing_param:{key}" if required else None
    return resolve_component(params[key], registry)


def convert_sequence_to_executor_plan(
    sample_id: str,
    sequence: list[dict[str, Any]],
    registry: list[dict[str, Any]],
    source: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    errors: list[str] = []
    warnings: list[str] = []
    actions: list[dict[str, Any]] = []
    current_object: dict[str, Any] | None = None

    if not sequence:
        errors.append("sequence_missing_or_empty")

    for idx, step in enumerate(sequence):
        skill = step.get("name")
        params = step.get("params", {}) if isinstance(step.get("params", {}), dict) else {}
        if skill not in SUPPORTED_SKILLS:
            errors.append(f"unsupported_skill:{skill}")
            continue
        for key in params:
            if key not in SUPPORTED_PARAMS:
                errors.append(f"unsupported_param:{skill}.{key}")

        action: dict[str, Any] = {
            "index": idx,
            "skill": skill,
            "params": params,
            "object": None,
            "target": None,
            "adapter_strategy": "direct_skilllib",
        }

        if skill == "pick":
            component, err = _param_component(step, "target_entity_name", registry, required=True)
            if err:
                errors.append(f"step{idx}:{err}")
            action["object"] = component
            current_object = component or current_object
        elif skill == "place":
            component, err = _param_component(step, "target_container_name", registry, required=True)
            if err:
                errors.append(f"step{idx}:{err}")
            action["object"] = current_object
            action["target"] = component
        elif skill == "lift":
            action["object"] = current_object
            if current_object is None:
                warnings.append(f"step{idx}:lift_without_known_current_object")
        elif skill in {"pull", "push"}:
            action["object"] = current_object
            component, err = _param_component(step, "target_container_name", registry, required=False)
            if err:
                component = None
            action["target"] = component
        elif skill == "press":
            component, err = _param_component(step, "target_entity_name", registry, required=True)
            if err:
                errors.append(f"step{idx}:{err}")
            action["target"] = component
        elif skill == "pour":
            component, err = _param_component(step, "target_container_name", registry, required=False)
            if err:
                component = None
            action["object"] = current_object
            action["target"] = component
            action["adapter_strategy"] = "move_above_target_then_skilllib_pour" if component else "direct_skilllib_pour"
        elif skill == "insert":
            component, err = _param_component(step, "target_container_name", registry, required=True)
            if err:
                errors.append(f"step{idx}:{err}")
            action["object"] = current_object
            action["target"] = component
            action["adapter_strategy"] = "skilllib_place_as_insert_adapter"
            warnings.append(f"step{idx}:insert_has_no_direct_skilllib_method_using_place_adapter")

        actions.append(action)

    conversion_ok = not errors
    plan = {
        "schema_version": "vlabench_skilllib_executor_plan_v1.0",
        "sample_id": sample_id,
        "source": source,
        "conversion_ok": conversion_ok,
        "conversion_errors": errors,
        "conversion_warnings": warnings,
        "supported_skills": sorted(SUPPORTED_SKILLS),
        "actions": actions,
    }
    validation = {
        "sample_id": sample_id,
        "source": source,
        "conversion_ok": conversion_ok,
        "conversion_errors": errors,
        "conversion_warnings": warnings,
        "action_count": len(actions),
        "skill_sequence": [action.get("skill") for action in actions],
        "adapter_strategies": [action.get("adapter_strategy") for action in actions],
    }
    return plan, validation


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
