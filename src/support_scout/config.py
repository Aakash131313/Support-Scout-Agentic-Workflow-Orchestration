"""Environment-driven settings.

Secrets are read from the environment only. They are never written to logs, traces,
artifacts or exception messages.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .exceptions import ConfigurationError


def _int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigurationError(f"{name} must be an integer") from exc


def _float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise ConfigurationError(f"{name} must be a number") from exc


def _bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return raw.strip().casefold() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    """All runtime configuration for a SupportScout run."""

    tavily_api_key: str | None
    udacity_api_key: str | None
    udacity_model_name: str | None
    udacity_base_url: str | None

    request_timeout_seconds: int = 10
    max_search_results: int = 5
    max_pages_to_scrape: int = 3
    max_page_characters: int = 20_000
    max_agent_revisions: int = 1
    classification_confidence_threshold: float = 0.70

    # Execution budgets (bounded agent autonomy).
    max_agent_steps: int = 12
    max_orchestrator_steps: int = 16
    max_total_tool_calls: int = 40
    max_calls_per_tool: int = 6
    max_delegation_failures: int = 2

    # Human-in-the-loop.
    require_human_approval: bool = True
    auto_approve_restricted_actions: bool = False

    output_directory: Path = Path("output")
    log_directory: Path = Path("logs")
    cache_directory: Path = Path(".cache")
    support_data_base_url: str = "http://127.0.0.1:8001"

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            tavily_api_key=os.getenv("TAVILY_API_KEY") or None,
            udacity_api_key=os.getenv("UDACITY_API_KEY") or None,
            udacity_model_name=os.getenv("UDACITY_MODEL_NAME") or None,
            udacity_base_url=os.getenv("UDACITY_BASE_URL") or None,
            request_timeout_seconds=_int("REQUEST_TIMEOUT_SECONDS", 10),
            max_search_results=_int("MAX_SEARCH_RESULTS", 5),
            max_pages_to_scrape=_int("MAX_PAGES_TO_SCRAPE", 3),
            max_page_characters=_int("MAX_PAGE_CHARACTERS", 20_000),
            max_agent_revisions=_int("MAX_AGENT_REVISIONS", 1),
            classification_confidence_threshold=_float(
                "CLASSIFICATION_CONFIDENCE_THRESHOLD", 0.70
            ),
            max_agent_steps=_int("MAX_AGENT_STEPS", 12),
            max_orchestrator_steps=_int("MAX_ORCHESTRATOR_STEPS", 16),
            max_total_tool_calls=_int("MAX_TOTAL_TOOL_CALLS", 40),
            max_calls_per_tool=_int("MAX_CALLS_PER_TOOL", 6),
            max_delegation_failures=_int("MAX_DELEGATION_FAILURES", 2),
            require_human_approval=_bool("SUPPORTSCOUT_REQUIRE_APPROVAL", True),
            auto_approve_restricted_actions=_bool("SUPPORTSCOUT_AUTO_APPROVE", False),
            output_directory=Path(os.getenv("OUTPUT_DIRECTORY", "output")),
            log_directory=Path(os.getenv("LOG_DIRECTORY", "logs")),
            cache_directory=Path(os.getenv("CACHE_DIRECTORY", ".cache")),
            support_data_base_url=os.getenv(
                "SUPPORT_DATA_BASE_URL", "http://127.0.0.1:8001"
            ).rstrip("/"),
        )

    def require_tavily(self) -> str:
        if not self.tavily_api_key:
            raise ConfigurationError("TAVILY_API_KEY is not configured")
        return self.tavily_api_key

    def require_udacity(self) -> tuple[str, str, str]:
        if not (self.udacity_api_key and self.udacity_model_name and self.udacity_base_url):
            raise ConfigurationError(
                "UDACITY_API_KEY, UDACITY_MODEL_NAME and UDACITY_BASE_URL must all be configured"
            )
        return self.udacity_api_key, self.udacity_model_name, self.udacity_base_url
