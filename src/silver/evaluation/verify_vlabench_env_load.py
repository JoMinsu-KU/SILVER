"""Load one native VLABench task and perform one environment step."""

from __future__ import annotations

import argparse
import json
import time
import traceback


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", default="select_toy")
    parser.add_argument("--robot", default="franka")
    parser.add_argument("--reset-wait-step", type=int, default=1)
    args = parser.parse_args()

    result = {"ok": False, "task": args.task, "robot": args.robot}
    try:
        import VLABench.robots  # noqa: F401 - registers robots
        import VLABench.tasks  # noqa: F401 - registers tasks/entities
        from VLABench.envs import load_env

        t0 = time.time()
        env = load_env(args.task, robot=args.robot, reset_wait_step=args.reset_wait_step)
        timestep = env.step()
        result.update(
            {
                "ok": True,
                "elapsed_s": time.time() - t0,
                "timestep_type": str(getattr(timestep, "step_type", None)),
                "ncam": int(env.physics.model.ncam),
                "nq": int(env.physics.model.nq),
            }
        )
        env.close()
    except Exception as exc:  # noqa: BLE001 - runtime smoke test must capture all failures
        result["error"] = repr(exc)
        result["traceback"] = traceback.format_exc(limit=12)

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
