"""SILVER output schema definitions."""

from __future__ import annotations

from typing import Any


SUPPORTED_SKILLS = ("pick", "place", "lift", "pull", "press", "push", "pour", "insert")


def allowed_replanning_schema() -> dict[str, Any]:
    """Return the JSON schema fragment used in SILVER replanning prompts."""

    return {
        "skill_sequence": [
            {
                "name": " | ".join(SUPPORTED_SKILLS),
                "params": {
                    "target_entity_name": "object name or numeric visible component id for pick/press",
                    "target_container_name": "container/target name or numeric visible component id for place/pull/push/pour/insert",
                },
            }
        ],
        "rationale_summary": "brief non-chain-of-thought explanation",
    }
