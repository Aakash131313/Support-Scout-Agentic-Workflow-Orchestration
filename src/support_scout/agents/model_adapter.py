"""Model construction for the OpenAI-compatible provider.

Provider isolation lives here: every agent receives an already-built model object and
never sees a base URL, key or provider name. Swapping providers is a change to this
file alone.
"""
from __future__ import annotations

from typing import Any

from smolagents import OpenAIServerModel


def create_model(
    *,
    api_key: str,
    model_name: str,
    base_url: str,
    timeout_seconds: int = 30,
    temperature: float = 0.0,
) -> Any:
    """Create the shared tool-calling model used by every agent in a run."""
    return OpenAIServerModel(
        model_id=model_name,
        api_base=base_url,
        api_key=api_key,
        timeout=timeout_seconds,
        temperature=temperature,
    )
