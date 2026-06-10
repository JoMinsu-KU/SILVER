"""VLABench scene entity registry utilities.

These helpers convert the public VLABench `env_config.json` scene components
into the entity registry used by the Qwen-guided executor adapter.
"""

from __future__ import annotations

from typing import Any


def extract_conditions(env_cfg: dict[str, Any]) -> dict[str, Any]:
    task = env_cfg.get("task", {}) if isinstance(env_cfg, dict) else {}
    conditions = task.get("conditions", {}) if isinstance(task, dict) else {}
    return conditions if isinstance(conditions, dict) else {}


def build_entity_registry(env_cfg: dict[str, Any]) -> list[dict[str, Any]]:
    task = env_cfg.get("task", {}) if isinstance(env_cfg, dict) else {}
    components = task.get("components", []) if isinstance(task, dict) else []
    conditions = extract_conditions(env_cfg)
    contain = conditions.get("contain", {}) if isinstance(conditions.get("contain", {}), dict) else {}
    container_name = contain.get("container")
    contain_entities = set(contain.get("entities", [])) if isinstance(contain.get("entities", []), list) else set()
    registry: list[dict[str, Any]] = []
    for idx, component in enumerate(components):
        if not isinstance(component, dict):
            continue
        name = component.get("name")
        cls = component.get("class")
        role = "background"
        if name == container_name:
            role = "target_container"
        elif name in contain_entities:
            role = "target_entity"
        elif cls in {"Plate", "Bowl", "Basket", "Container"}:
            role = "candidate_container"
        elif cls not in {"Table", "Scene"}:
            role = "candidate_entity"
        registry.append(
            {
                "component_id": idx,
                "name": name,
                "class": cls,
                "xml_path": component.get("xml_path"),
                "position": component.get("position"),
                "orientation": component.get("orientation"),
                "role": role,
                "is_manipulable_candidate": role in {"target_entity", "candidate_entity"},
                "is_container_candidate": role in {"target_container", "candidate_container"},
            }
        )
    return registry

