"""Small helpers for table recomputation scripts."""

from __future__ import annotations

from collections import Counter
from typing import Iterable


def count_by(rows: Iterable[dict[str, str]], key: str) -> dict[str, int]:
    """Count rows by a string field."""

    return dict(Counter(row.get(key, "") for row in rows))
