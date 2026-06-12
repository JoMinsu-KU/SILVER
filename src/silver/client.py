"""OpenAI-compatible multimodal client helpers for SILVER."""

from __future__ import annotations

import base64
import json
import urllib.request
from pathlib import Path
from typing import Any


def image_to_data_url(path: Path) -> str:
    b64 = base64.b64encode(path.read_bytes()).decode("utf-8")
    return f"data:image/png;base64,{b64}"


def build_multimodal_user_message(prompt: str, image_path: Path | None = None) -> dict[str, Any]:
    """Build a user message with optional visual failure evidence."""

    content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
    if image_path is not None and image_path.exists():
        content.insert(0, {"type": "image_url", "image_url": {"url": image_to_data_url(image_path)}})
    return {"role": "user", "content": content}


def chat_completion(
    *,
    base_url: str,
    model: str,
    messages: list[dict[str, Any]],
    temperature: float = 0,
    max_tokens: int = 1024,
) -> dict[str, Any]:
    """Call an OpenAI-compatible `/chat/completions` endpoint."""

    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    req = urllib.request.Request(
        base_url.rstrip("/") + "/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        return json.loads(resp.read().decode("utf-8"))
