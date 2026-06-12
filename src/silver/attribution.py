"""Recovery attribution utilities for SILVER Track D."""

from __future__ import annotations

from typing import Any


def boolish(value: Any) -> bool | None:
    """Convert common CSV/JSON success values to bool or None."""

    if isinstance(value, bool):
        return value
    if value is None:
        return None
    text = str(value).strip().lower()
    if text in {"true", "1", "yes"}:
        return True
    if text in {"false", "0", "no"}:
        return False
    return None


def assign_recovery_attribution(*, same_plan_success: Any, replan_success: Any) -> str:
    """Assign the coarse recovery-attribution label used in Track D."""

    same_success = boolish(same_plan_success) is True
    silver_success = boolish(replan_success) is True
    if silver_success and not same_success:
        return "A3_or_A4_replan_recovered"
    if same_success:
        return "A1_same_plan_retry_recovered"
    return "A0_no_recovery"


def attributed_recovery_gain(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute paired SR-vs-SILVER recovery gain from saved comparison rows."""

    completed = [
        row
        for row in rows
        if boolish(row.get("same_plan_completed")) is True and boolish(row.get("replan_R3_completed")) is True
    ]
    denominator = len(completed)
    same_success = sum(1 for row in completed if boolish(row.get("same_plan_success")) is True)
    replan_success = sum(1 for row in completed if boolish(row.get("replan_R3_success")) is True)
    gain = (replan_success / denominator - same_success / denominator) if denominator else None
    return {
        "completed_pairs": denominator,
        "same_plan_success": same_success,
        "replan_R3_success": replan_success,
        "attributed_recovery_gain": gain,
    }


__all__ = [
    "assign_recovery_attribution",
    "attributed_recovery_gain",
    "boolish",
]
