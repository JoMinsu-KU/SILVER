"""Verify VLABench, dm_control, and MuJoCo runtime availability.

This script intentionally performs only small, deterministic smoke checks.
It does not fabricate VLABench task execution results.
"""

from __future__ import annotations

import json
import sys
import traceback
from typing import Any, Callable


def run_check(name: str, fn: Callable[[], Any]) -> dict[str, Any]:
    item: dict[str, Any] = {"name": name, "ok": False}
    try:
        details = fn()
        item["ok"] = True
        if details is not None:
            item["details"] = details
    except Exception as exc:  # noqa: BLE001 - verification must capture all failures
        item["error"] = repr(exc)
        item["traceback"] = traceback.format_exc(limit=10)
    return item


def import_mujoco() -> str:
    import mujoco

    return mujoco.__version__


def import_dm_control() -> str:
    import dm_control

    return str(dm_control.__file__)


def import_vlabench() -> str:
    import VLABench

    return str(VLABench.__file__)


def mujoco_minimal_step() -> dict[str, float]:
    import mujoco

    xml = """
    <mujoco>
      <worldbody>
        <body name="ball" pos="0 0 1">
          <joint name="free" type="free"/>
          <geom type="sphere" size="0.05" mass="1"/>
        </body>
      </worldbody>
    </mujoco>
    """
    model = mujoco.MjModel.from_xml_string(xml)
    data = mujoco.MjData(model)
    for _ in range(10):
        mujoco.mj_step(model, data)
    return {"time": float(data.time), "qpos_z": float(data.qpos[2])}


def dm_control_suite_step() -> dict[str, Any]:
    from dm_control import suite

    env = suite.load(domain_name="cartpole", task_name="balance")
    env.reset()
    action = env.action_spec().generate_value()
    ts = env.step(action)
    return {
        "reward": None if ts.reward is None else float(ts.reward),
        "discount": None if ts.discount is None else float(ts.discount),
        "step_type": str(ts.step_type),
    }


def vlabench_tasks_import() -> dict[str, Any]:
    from VLABench.utils.register import register
    import VLABench.tasks  # noqa: F401

    task_registry = getattr(register, "_tasks", None)
    return {
        "register_type": type(register).__name__,
        "task_count": None if task_registry is None else len(task_registry),
    }


def main() -> int:
    results = {
        "python": sys.version,
        "checks": [
            run_check("import_mujoco", import_mujoco),
            run_check("import_dm_control", import_dm_control),
            run_check("import_vlabench", import_vlabench),
            run_check("mujoco_minimal_step", mujoco_minimal_step),
            run_check("dm_control_suite_step", dm_control_suite_step),
            run_check("vlabench_tasks_import", vlabench_tasks_import),
        ],
    }
    print(json.dumps(results, indent=2, ensure_ascii=False))
    return 0 if all(item["ok"] for item in results["checks"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
