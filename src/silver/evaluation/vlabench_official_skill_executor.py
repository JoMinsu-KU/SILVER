"""Native VLABench official expert / adapter executor.

Run this inside the WSL VLABench runtime. The script writes observed execution
results only. It does not synthesize success or fill missing samples.
"""

from __future__ import annotations

import argparse
import inspect
import json
import os
import sys
import time
import traceback
from pathlib import Path
from typing import Any

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def now_iso() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def capture_views(env: Any, out_dir: Path, prefix: str) -> dict[str, Any]:
    import imageio.v2 as imageio

    out_dir.mkdir(parents=True, exist_ok=True)
    paths: list[str] = []
    frames = []
    ncam = int(env.physics.model.ncam)
    for cam_id in range(ncam):
        frame = env.render(camera_id=cam_id, height=480, width=480)
        path = out_dir / f"{prefix}_cam{cam_id}.png"
        imageio.imwrite(path, frame)
        paths.append(str(path))
        frames.append(frame)
    mosaic_path = None
    if len(frames) >= 4:
        mosaic = np.vstack([np.hstack(frames[:2]), np.hstack(frames[2:4])])
        mosaic_path = out_dir / f"{prefix}_mosaic.png"
        imageio.imwrite(mosaic_path, mosaic)
    return {"camera_count": ncam, "frames": paths, "mosaic": None if mosaic_path is None else str(mosaic_path)}


def load_native_env(task: str, env_config: dict[str, Any], reset_wait_step: int) -> Any:
    import VLABench.robots  # noqa: F401
    import VLABench.tasks  # noqa: F401
    from VLABench.envs import load_env

    env = load_env(
        task,
        robot="franka",
        episode_config=env_config,
        random_init=False,
        run_mode="eval",
        reset_wait_step=reset_wait_step,
    )
    # VLABench official evaluators and trajectory-generation scripts both reset
    # after load_env(). Keep the native wrapper aligned with that lifecycle.
    env.reset()
    return env


def condition_success(env: Any) -> bool | None:
    conditions = getattr(env.task, "conditions", None)
    if conditions is None:
        return None
    try:
        return bool(conditions.is_met(env.physics))
    except Exception:
        return None


def apply_episode_targets(env: Any, env_config: dict[str, Any]) -> dict[str, Any]:
    """Align VLABench task target fields with the fixed episode config.

    Some VLABench task classes keep target_entity/target_container fields that
    are normally set during random task generation. The public VLM dataset gives
    a fixed env_config with condition entities/containers. For deterministic
    replay we align those task fields to the saved condition before requesting
    the official expert skill sequence.
    """

    task_cfg = env_config.get("task", {}) if isinstance(env_config, dict) else {}
    conditions = task_cfg.get("conditions", {}) if isinstance(task_cfg, dict) else {}
    contain = conditions.get("contain", {}) if isinstance(conditions, dict) and isinstance(conditions.get("contain"), dict) else {}
    entities = contain.get("entities", []) if isinstance(contain.get("entities"), list) else []
    container = contain.get("container")
    applied: dict[str, Any] = {"condition_entities": entities, "condition_container": container, "updates": {}}
    if entities:
        try:
            value = entities[0] if len(entities) == 1 else list(entities)
            if hasattr(env.task, "config_manager"):
                env.task.config_manager.target_entity = value
            else:
                env.task.target_entity = value
            applied["updates"]["target_entity"] = value
        except Exception as exc:  # noqa: BLE001
            applied["updates"]["target_entity_error"] = repr(exc)
    if container:
        try:
            if hasattr(env.task, "config_manager"):
                env.task.config_manager.target_container = container
            else:
                env.task.target_container = container
            applied["updates"]["target_container"] = container
        except Exception as exc:  # noqa: BLE001
            applied["updates"]["target_container_error"] = repr(exc)
    try:
        env.task.reset_task_progress()
        applied["updates"]["reset_task_progress"] = True
    except Exception as exc:  # noqa: BLE001
        applied["updates"]["reset_task_progress_error"] = repr(exc)
    return applied


def build_registry_from_env_config(env_config: dict[str, Any]) -> tuple[dict[int, dict[str, Any]], dict[str, dict[str, Any]]]:
    task_cfg = env_config.get("task", {}) if isinstance(env_config, dict) else {}
    components = task_cfg.get("components", []) if isinstance(task_cfg, dict) else []
    by_id: dict[int, dict[str, Any]] = {}
    by_name: dict[str, dict[str, Any]] = {}
    for idx, component in enumerate(components):
        if not isinstance(component, dict):
            continue
        by_id[idx] = component
        if component.get("name") is not None:
            by_name[str(component["name"])] = component
    return by_id, by_name


def component_name_from_param(value: Any, by_id: dict[int, dict[str, Any]], by_name: dict[str, dict[str, Any]]) -> str | None:
    if isinstance(value, int) and value in by_id:
        return by_id[value].get("name")
    if isinstance(value, str) and value in by_name:
        return value
    if isinstance(value, str) and value.strip().isdigit():
        idx = int(value.strip())
        if idx in by_id:
            return by_id[idx].get("name")
    return None


def walk_condition_refs(obj: Any, refs: dict[str, list[str]]) -> None:
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key in {"target_entity", "entity", "entities"}:
                if isinstance(value, str):
                    refs["condition_entities"].append(value)
                elif isinstance(value, list):
                    refs["condition_entities"].extend(str(item) for item in value if isinstance(item, str))
            elif key in {"target_container", "container", "platform", "target_platform"}:
                if isinstance(value, str):
                    refs["condition_containers"].append(value)
                elif isinstance(value, list):
                    refs["condition_containers"].extend(str(item) for item in value if isinstance(item, str))
            walk_condition_refs(value, refs)
    elif isinstance(obj, list):
        for item in obj:
            walk_condition_refs(item, refs)


def unique_keep_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            out.append(value)
    return out


def extract_runtime_targets(env_config: dict[str, Any], operation_sequence: dict[str, Any] | None) -> dict[str, Any]:
    by_id, by_name = build_registry_from_env_config(env_config)
    target_entities: list[str] = []
    target_containers: list[str] = []
    seq = operation_sequence.get("skill_sequence", []) if isinstance(operation_sequence, dict) else []
    for step in seq if isinstance(seq, list) else []:
        if not isinstance(step, dict):
            continue
        params = step.get("params", {}) if isinstance(step.get("params", {}), dict) else {}
        if "target_entity_name" in params:
            name = component_name_from_param(params["target_entity_name"], by_id, by_name)
            if name:
                target_entities.append(str(name))
        if "target_container_name" in params:
            name = component_name_from_param(params["target_container_name"], by_id, by_name)
            if name:
                target_containers.append(str(name))

    task_cfg = env_config.get("task", {}) if isinstance(env_config, dict) else {}
    conditions = task_cfg.get("conditions", {}) if isinstance(task_cfg, dict) else {}
    if isinstance(conditions, dict):
        refs = {"condition_entities": [], "condition_containers": []}
        walk_condition_refs(conditions, refs)
        target_entities.extend(name for name in unique_keep_order(refs["condition_entities"]) if name in by_name)
        target_containers.extend(name for name in unique_keep_order(refs["condition_containers"]) if name in by_name)

    target_entities = unique_keep_order(target_entities)
    target_containers = unique_keep_order(target_containers)
    task_name = str(task_cfg.get("name") or "")
    if "take_chemistry_experiment" in task_name:
        chemistry_entities = [name for name in target_entities if name in by_name and by_name[name].get("class") == "ChemistryTube"]
        if chemistry_entities:
            target_entities = unique_keep_order(chemistry_entities)
    return {"target_entities": target_entities, "target_containers": target_containers}


def make_runtime_env_config(env_config: dict[str, Any], operation_sequence: dict[str, Any] | None) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return an in-memory episode config with fixed targets set before load_env().

    The public dataset files are not modified. This only prevents VLABench's
    internal reset from using a random/default target before the wrapper can
    align the fixed public episode.
    """

    runtime_config = json.loads(json.dumps(env_config))
    task_cfg = runtime_config.setdefault("task", {})
    targets = extract_runtime_targets(runtime_config, operation_sequence)
    entities = targets["target_entities"]
    containers = targets["target_containers"]
    applied = {"preload_target_entities": entities, "preload_target_containers": containers, "updates": {}}
    task_name = str(task_cfg.get("name") or "")
    if entities:
        if "take_chemistry_experiment" in task_name:
            task_cfg["target_entity"] = list(entities)
            task_cfg["target_entities"] = list(entities)
        else:
            task_cfg["target_entity"] = entities[0]
            task_cfg["target_entities"] = list(entities)
        applied["updates"]["task.target_entity"] = task_cfg["target_entity"]
        applied["updates"]["task.target_entities"] = task_cfg["target_entities"]
    if containers:
        task_cfg["target_container"] = containers[0]
        applied["updates"]["task.target_container"] = containers[0]
    return runtime_config, applied


def apply_operation_sequence_targets(env: Any, env_config: dict[str, Any], operation_sequence: dict[str, Any]) -> dict[str, Any]:
    """Align task targets from saved VLABench operation_sequence/env_config.

    This does not mutate the dataset. It only updates the loaded runtime task so
    VLABench expert templates use the fixed public VLM sample targets instead
    of internally sampled/random target fields.
    """

    by_id, by_name = build_registry_from_env_config(env_config)
    targets = extract_runtime_targets(env_config, operation_sequence)
    target_entities = targets["target_entities"]
    target_containers = targets["target_containers"]

    applied: dict[str, Any] = {
        "operation_sequence_target_entities": target_entities,
        "operation_sequence_target_containers": target_containers,
        "updates": {},
    }

    def set_attr(name: str, value: Any) -> None:
        if hasattr(env.task, "config_manager"):
            setattr(env.task.config_manager, name, value)
        else:
            setattr(env.task, name, value)
        applied["updates"][name] = value

    task_name = getattr(env.task, "task_name", "") or getattr(env.task, "name", "")
    task_name = str(task_name)
    if "take_chemistry_experiment" in task_name:
        chemistry_entities = [name for name in target_entities if name in by_name and by_name[name].get("class") == "ChemistryTube"]
        chemistry_entities = unique_keep_order(chemistry_entities)
        if chemistry_entities:
            try:
                set_attr("target_entity", list(chemistry_entities))
            except Exception as exc:  # noqa: BLE001
                applied["updates"]["target_entity_error"] = repr(exc)
            try:
                set_attr("target_entities", list(chemistry_entities))
            except Exception as exc:  # noqa: BLE001
                applied["updates"]["target_entities_error"] = repr(exc)
    elif target_entities:
        try:
            set_attr("target_entity", target_entities[0])
        except Exception as exc:  # noqa: BLE001
            applied["updates"]["target_entity_error"] = repr(exc)
        try:
            set_attr("target_entities", list(target_entities))
        except Exception as exc:  # noqa: BLE001
            applied["updates"]["target_entities_error"] = repr(exc)
    if target_containers:
        try:
            set_attr("target_container", target_containers[0])
        except Exception as exc:  # noqa: BLE001
            applied["updates"]["target_container_error"] = repr(exc)
        try:
            set_attr("target_containers", list(target_containers))
        except Exception as exc:  # noqa: BLE001
            applied["updates"]["target_containers_error"] = repr(exc)
        try:
            set_attr("target_platform", target_containers[0])
        except Exception as exc:  # noqa: BLE001
            applied["updates"]["target_platform_error"] = repr(exc)
    try:
        env.task.reset_task_progress()
        applied["updates"]["reset_task_progress"] = True
    except Exception as exc:  # noqa: BLE001
        applied["updates"]["reset_task_progress_error"] = repr(exc)
    return applied


def apply_plan_targets(env: Any, plan: dict[str, Any]) -> dict[str, Any]:
    """Set task target fields from a converted model/adapter plan.

    This is used for qwen_guided_expert mode. It does not read GT conditions;
    it only uses object/target components already selected by the model output
    and resolved by the adapter.
    """

    target_entity = None
    target_container = None
    for action in plan.get("actions", []):
        obj = action.get("object")
        target = action.get("target")
        if target_entity is None and isinstance(obj, dict) and obj.get("name"):
            target_entity = obj["name"]
        if target_container is None and isinstance(target, dict) and target.get("name"):
            target_container = target["name"]
    applied: dict[str, Any] = {"plan_target_entity": target_entity, "plan_target_container": target_container, "updates": {}}
    if target_entity is not None:
        try:
            if hasattr(env.task, "config_manager"):
                env.task.config_manager.target_entity = target_entity
            else:
                env.task.target_entity = target_entity
            applied["updates"]["target_entity"] = target_entity
        except Exception as exc:  # noqa: BLE001
            applied["updates"]["target_entity_error"] = repr(exc)
        try:
            setattr(env.task, "target_entities", [target_entity])
            applied["updates"]["target_entities"] = [target_entity]
        except Exception as exc:  # noqa: BLE001
            applied["updates"]["target_entities_error"] = repr(exc)
    if target_container is not None:
        try:
            if hasattr(env.task, "config_manager"):
                env.task.config_manager.target_container = target_container
            else:
                env.task.target_container = target_container
            applied["updates"]["target_container"] = target_container
        except Exception as exc:  # noqa: BLE001
            applied["updates"]["target_container_error"] = repr(exc)
        try:
            setattr(env.task, "target_containers", [target_container])
            applied["updates"]["target_containers"] = [target_container]
        except Exception as exc:  # noqa: BLE001
            applied["updates"]["target_containers_error"] = repr(exc)
        try:
            setattr(env.task, "target_platform", target_container)
            applied["updates"]["target_platform"] = target_container
        except Exception as exc:  # noqa: BLE001
            applied["updates"]["target_platform_error"] = repr(exc)
    try:
        env.task.reset_task_progress()
        applied["updates"]["reset_task_progress"] = True
    except Exception as exc:  # noqa: BLE001
        applied["updates"]["reset_task_progress_error"] = repr(exc)
    return applied


def progress_score(env: Any) -> float | None:
    try:
        return float(env.get_task_progress())
    except Exception:
        return None


def intention_score(env: Any) -> float | None:
    try:
        return float(env.get_intention_score())
    except Exception:
        return None


def callable_name(obj: Any) -> str:
    func = getattr(obj, "func", obj)
    return getattr(func, "__name__", repr(func))


def callable_signature(obj: Any) -> str | None:
    try:
        return str(inspect.signature(obj))
    except Exception:
        return None


def call_skill(skill: Any, env: Any) -> Any:
    try:
        signature = inspect.signature(skill)
        params = [
            param
            for param in signature.parameters.values()
            if param.default is inspect.Parameter.empty
            and param.kind in {inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD}
        ]
        has_varargs = any(param.kind == inspect.Parameter.VAR_POSITIONAL for param in signature.parameters.values())
        if has_varargs or params:
            return skill(env)
        return skill()
    except (TypeError, ValueError):
        return skill(env)


def record_skill(stage_index: int, skill: Any, env: Any) -> dict[str, Any]:
    t0 = time.time()
    row: dict[str, Any] = {
        "stage_index": stage_index,
        "skill_name": callable_name(skill),
        "skill_signature": callable_signature(skill),
        "stage_success": False,
        "task_success": False,
        "observation_count": 0,
        "waypoint_count": 0,
        "elapsed_s": None,
        "error": None,
    }
    try:
        result = call_skill(skill, env)
        row["elapsed_s"] = time.time() - t0
        if result is None:
            row["error"] = "skill_returned_none"
            return row
        if isinstance(result, tuple) and len(result) >= 4:
            observations, waypoints, stage_success, task_success = result[:4]
            row.update(
                {
                    "stage_success": bool(stage_success),
                    "task_success": bool(task_success),
                    "observation_count": len(observations) if observations is not None else 0,
                    "waypoint_count": len(waypoints) if waypoints is not None else 0,
                }
            )
        else:
            row["error"] = f"unexpected_skill_return:{type(result).__name__}"
        return row
    except Exception as exc:  # noqa: BLE001
        row.update({"elapsed_s": time.time() - t0, "error": repr(exc), "traceback": traceback.format_exc(limit=10)})
        return row


def execute_official_expert(env: Any) -> tuple[list[dict[str, Any]], list[str]]:
    errors: list[str] = []
    try:
        sequence = env.get_expert_skill_sequence()
    except Exception as exc:  # noqa: BLE001
        return [], [f"get_expert_skill_sequence_failed:{repr(exc)}"]
    if not isinstance(sequence, list) or not sequence:
        return [], ["expert_sequence_missing_or_empty"]
    rows: list[dict[str, Any]] = []
    for idx, skill in enumerate(sequence):
        rows.append(record_skill(idx, skill, env))
    return rows, errors


def execute_qwen_pick_place(env: Any, task: str, object_name: str, target_name: str) -> list[dict[str, Any]]:
    from VLABench.utils.skill_lib import SkillLib

    rows: list[dict[str, Any]] = []

    def wrap(name: str, fn: Any) -> dict[str, Any]:
        t0 = time.time()
        try:
            result = fn()
            row = {
                "stage_index": len(rows),
                "skill_name": name,
                "stage_success": False,
                "task_success": False,
                "observation_count": 0,
                "waypoint_count": 0,
                "elapsed_s": time.time() - t0,
                "error": None,
            }
            if isinstance(result, tuple) and len(result) >= 4:
                observations, waypoints, stage_success, task_success = result[:4]
                row.update(
                    {
                        "stage_success": bool(stage_success),
                        "task_success": bool(task_success),
                        "observation_count": len(observations) if observations is not None else 0,
                        "waypoint_count": len(waypoints) if waypoints is not None else 0,
                    }
                )
            elif result is None:
                row["error"] = "skill_returned_none"
            else:
                row["error"] = f"unexpected_skill_return:{type(result).__name__}"
            return row
        except Exception as exc:  # noqa: BLE001
            return {
                "stage_index": len(rows),
                "skill_name": name,
                "stage_success": False,
                "task_success": False,
                "observation_count": 0,
                "waypoint_count": 0,
                "elapsed_s": time.time() - t0,
                "error": repr(exc),
                "traceback": traceback.format_exc(limit=10),
            }

    if "toy" in task:
        def toy_pick() -> Any:
            grasp_point = np.array(env.task.entities[object_name].get_grasped_keypoints(env.physics)[-1])
            return SkillLib.pick(
                env,
                target_entity_name=object_name,
                target_pos=grasp_point - np.array([0, 0, 0.02]),
                prior_eulers=[[-np.pi, 0, 0]],
            )

        rows.append(wrap("pick", toy_pick))
    else:
        rows.append(wrap("pick", lambda: SkillLib.pick(env, target_entity_name=object_name)))
    rows.append(wrap("lift", lambda: SkillLib.lift(env, lift_height=0.3, gripper_state=np.zeros(2))))
    rows.append(wrap("place", lambda: SkillLib.place(env, target_container_name=target_name)))
    return rows


def _component_name(component: Any) -> str | None:
    if isinstance(component, dict) and component.get("name") is not None:
        return str(component["name"])
    return None


def _component_position(component: Any) -> np.ndarray | None:
    if isinstance(component, dict) and isinstance(component.get("position"), list) and len(component["position"]) >= 3:
        return np.array(component["position"][:3], dtype=float)
    return None


def _target_place_point(env: Any, target_name: str | None, fallback_component: dict[str, Any] | None = None) -> np.ndarray | None:
    if target_name and target_name in getattr(env.task, "entities", {}):
        entity = env.task.entities[target_name]
        try:
            points = entity.get_place_point(env.physics)
            if points:
                return np.array(points[0] if isinstance(points, list) else points, dtype=float)
        except Exception:
            pass
    return _component_position(fallback_component)


def execute_skilllib_plan(env: Any, task: str, plan: dict[str, Any]) -> list[dict[str, Any]]:
    from VLABench.utils.skill_lib import SkillLib

    rows: list[dict[str, Any]] = []

    def wrap(name: str, fn: Any, action: dict[str, Any]) -> dict[str, Any]:
        t0 = time.time()
        try:
            result = fn()
            row = {
                "stage_index": len(rows),
                "skill_name": name,
                "adapter_strategy": action.get("adapter_strategy"),
                "stage_success": False,
                "task_success": False,
                "observation_count": 0,
                "waypoint_count": 0,
                "elapsed_s": time.time() - t0,
                "error": None,
            }
            if isinstance(result, tuple) and len(result) >= 4:
                observations, waypoints, stage_success, task_success = result[:4]
                row.update(
                    {
                        "stage_success": bool(stage_success),
                        "task_success": bool(task_success),
                        "observation_count": len(observations) if observations is not None else 0,
                        "waypoint_count": len(waypoints) if waypoints is not None else 0,
                    }
                )
            elif result is None:
                row["error"] = "skill_returned_none"
            else:
                row["error"] = f"unexpected_skill_return:{type(result).__name__}"
            return row
        except Exception as exc:  # noqa: BLE001
            return {
                "stage_index": len(rows),
                "skill_name": name,
                "adapter_strategy": action.get("adapter_strategy"),
                "stage_success": False,
                "task_success": False,
                "observation_count": 0,
                "waypoint_count": 0,
                "elapsed_s": time.time() - t0,
                "error": repr(exc),
                "traceback": traceback.format_exc(limit=10),
            }

    for action in plan.get("actions", []):
        skill = action.get("skill")
        object_name = _component_name(action.get("object"))
        target_name = _component_name(action.get("target"))
        target_pos = _target_place_point(env, target_name, action.get("target"))

        if skill == "pick":
            if not object_name:
                rows.append(wrap("pick", lambda: None, {**action, "adapter_strategy": "missing_object"}))
                continue
            if "toy" in task:
                def toy_pick(name: str = object_name) -> Any:
                    grasp_point = np.array(env.task.entities[name].get_grasped_keypoints(env.physics)[-1])
                    return SkillLib.pick(
                        env,
                        target_entity_name=name,
                        target_pos=grasp_point - np.array([0, 0, 0.02]),
                        prior_eulers=[[-np.pi, 0, 0]],
                    )

                rows.append(wrap("pick", toy_pick, action))
            else:
                rows.append(wrap("pick", lambda name=object_name: SkillLib.pick(env, target_entity_name=name), action))
        elif skill == "place":
            if not target_name:
                rows.append(wrap("place", lambda: None, {**action, "adapter_strategy": "missing_target"}))
                continue
            rows.append(wrap("place", lambda name=target_name: SkillLib.place(env, target_container_name=name), action))
        elif skill == "lift":
            rows.append(wrap("lift", lambda: SkillLib.lift(env, lift_height=0.3, gripper_state=np.zeros(2)), action))
        elif skill == "pull":
            rows.append(wrap("pull", lambda: SkillLib.pull(env, gripper_state=np.zeros(2)), action))
        elif skill == "push":
            rows.append(wrap("push", lambda pos=target_pos: SkillLib.push(env, target_pos=pos, gripper_state=np.ones(2) * 0.04), action))
        elif skill == "press":
            if target_pos is None:
                rows.append(wrap("press", lambda: None, {**action, "adapter_strategy": "missing_target_position"}))
                continue
            rows.append(wrap("press", lambda pos=target_pos: SkillLib.press(env, target_pos=pos + np.array([0, 0, 0.04])), action))
        elif skill == "pour":
            if target_pos is not None:
                rows.append(wrap("moveto_before_pour", lambda pos=target_pos: SkillLib.moveto(env, target_pos=pos + np.array([0, 0, 0.15]), gripper_state=np.zeros(2)), action))
            rows.append(wrap("pour", lambda: SkillLib.pour(env), action))
        elif skill == "insert":
            if not target_name:
                rows.append(wrap("insert", lambda: None, {**action, "adapter_strategy": "missing_target"}))
                continue
            rows.append(wrap("insert_as_place", lambda name=target_name: SkillLib.place(env, target_container_name=name), action))
        else:
            rows.append(wrap(str(skill), lambda: None, {**action, "adapter_strategy": "unsupported_runtime_skill"}))
    return rows


def run(sample_id: str, category: str, task: str, example: str, sample_dir: Path, out_dir: Path, mode: str, plan_path: Path | None, reset_wait_step: int) -> dict[str, Any]:
    os.environ.setdefault("MUJOCO_GL", "egl")
    result: dict[str, Any] = {
        "sample_id": sample_id,
        "category": category,
        "task": task,
        "example": example,
        "mode": mode,
        "started_at": now_iso(),
        "execution_attempted": False,
        "execution_status": "not_started",
        "condition_success": None,
        "progress_score": None,
        "intention_score": None,
        "elapsed_s": None,
    }
    t0 = time.time()
    env = None
    try:
        if mode in {"qwen_adapter", "qwen_guided_expert"}:
            if plan_path is None or not plan_path.exists():
                result.update({"execution_status": "not_run_missing_plan", "failure_reason": str(plan_path)})
                return result
            plan = read_json(plan_path)
            result["conversion_ok"] = bool(plan.get("conversion_ok"))
            if not plan.get("conversion_ok"):
                result.update(
                    {
                        "execution_status": "not_run_conversion_failed",
                        "failure_reason": ";".join(plan.get("conversion_errors", [])),
                    }
                )
                return result
        env_config = read_json(sample_dir / "env_config.json")
        operation_sequence = None
        operation_sequence_path = sample_dir / "operation_sequence.json"
        if operation_sequence_path.exists():
            operation_sequence = read_json(operation_sequence_path)
        runtime_env_config, preload_alignment = make_runtime_env_config(env_config, operation_sequence)
        result["env_load_options"] = {
            "robot": "franka",
            "episode_config": "public_vlm_env_config",
            "random_init": False,
            "run_mode": "eval",
            "reset_called": True,
            "reset_wait_step": reset_wait_step,
        }
        result["preload_target_alignment"] = preload_alignment
        env = load_native_env(task, runtime_env_config, reset_wait_step)
        if mode == "official_expert":
            if operation_sequence is not None:
                result["episode_target_alignment"] = apply_operation_sequence_targets(env, runtime_env_config, operation_sequence)
            else:
                result["episode_target_alignment"] = apply_episode_targets(env, runtime_env_config)
        elif mode == "qwen_guided_expert":
            result["plan_target_alignment"] = apply_plan_targets(env, plan)
        result["execution_attempted"] = True
        result["initial_capture"] = capture_views(env, out_dir, "initial")
        if mode == "official_expert":
            stage_rows, errors = execute_official_expert(env)
            result["expert_sequence_errors"] = errors
            if errors:
                result["execution_status"] = "expert_sequence_error"
        elif mode == "qwen_adapter":
            stage_rows = execute_skilllib_plan(env, task, plan)
        elif mode == "qwen_guided_expert":
            stage_rows, errors = execute_official_expert(env)
            result["expert_sequence_errors"] = errors
            if errors:
                result["execution_status"] = "expert_sequence_error"
        else:
            raise ValueError(f"unsupported mode: {mode}")
        result["stage_results"] = stage_rows
        result["condition_success"] = condition_success(env)
        result["progress_score"] = progress_score(env)
        result["intention_score"] = intention_score(env)
        result["final_capture"] = capture_views(env, out_dir, "final")
        if result["execution_status"] == "not_started":
            result["execution_status"] = "completed"
    except Exception as exc:  # noqa: BLE001
        result.update({"execution_status": "exception", "error": repr(exc), "traceback": traceback.format_exc(limit=12)})
    finally:
        if env is not None:
            try:
                env.close()
            except Exception:
                pass
        result["elapsed_s"] = time.time() - t0
        result["completed_at"] = now_iso()
        write_json(out_dir / "execution_result.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Run VLABench official expert or Qwen adapter execution.")
    parser.add_argument("--sample-id", required=True)
    parser.add_argument("--category", required=True)
    parser.add_argument("--task", required=True)
    parser.add_argument("--example", required=True)
    parser.add_argument("--sample-dir", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--mode", choices=["official_expert", "qwen_adapter", "qwen_guided_expert"], required=True)
    parser.add_argument("--plan-path", type=Path, default=None)
    parser.add_argument("--reset-wait-step", type=int, default=1)
    args = parser.parse_args()
    result = run(args.sample_id, args.category, args.task, args.example, args.sample_dir, args.out_dir, args.mode, args.plan_path, args.reset_wait_step)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("execution_status") != "exception" else 1


if __name__ == "__main__":
    raise SystemExit(main())
