"""Sanitized logging, run-scoped tracing and an append-only error audit.

Three sinks, one run:

* stdout  - human-readable `[AGENT INSIGHT]` lines for live demonstration.
* trace   - `logs/<run_id>/trace.jsonl`, one JSON object per event (agent steps,
            tool calls, tool results, delegations, state transitions, HITL decisions).
* errors  - `logs/errors.jsonl`, append-only across all runs, one StructuredError
            per caught failure including failures raised inside tools.

Everything written by this module passes through `redact()` first.
"""
from __future__ import annotations

import json
import logging
import os
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .schemas import StructuredError

# --------------------------------------------------------------------------------------
# Redaction
# --------------------------------------------------------------------------------------
_REDACTED = "[REDACTED]"

_SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?i)\b(?:api[_-]?key|apikey|token|secret|password|passcode|authorization)\b\s*[:=]\s*\S+"),
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._\-]{8,}"),
    re.compile(r"\bsk-[A-Za-z0-9._\-]{8,}\b"),
    re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)"),
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
)

#: Keys whose values are never recorded, regardless of content.
_BLOCKED_KEYS = frozenset(
    {
        "api_key",
        "apikey",
        "authorization",
        "customer_message",
        "content",
        "page_content",
        "password",
        "secret",
        "token",
        "tavily_api_key",
        "udacity_api_key",
    }
)

_MAX_VALUE_CHARACTERS = 600


def redact(value: Any) -> Any:
    """Recursively remove secrets and unbounded free text from a log payload."""
    if isinstance(value, str):
        cleaned = value
        for pattern in _SECRET_PATTERNS:
            cleaned = pattern.sub(_REDACTED, cleaned)
        if len(cleaned) > _MAX_VALUE_CHARACTERS:
            cleaned = cleaned[:_MAX_VALUE_CHARACTERS] + "...[truncated]"
        return cleaned
    if isinstance(value, dict):
        return {
            str(key): (_REDACTED if str(key).casefold() in _BLOCKED_KEYS else redact(item))
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [redact(item) for item in value]
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return redact(str(value))


class RedactingFilter(logging.Filter):
    """Applies `redact()` to every log record message before it is emitted."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact(record.getMessage())
        record.args = ()
        return True


def configure_logging(level: str | int = logging.INFO) -> None:
    """Install the redacting stdout handler exactly once."""
    root = logging.getLogger()
    if any(getattr(handler, "_support_scout", False) for handler in root.handlers):
        return
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
    handler.addFilter(RedactingFilter())
    handler._support_scout = True  # type: ignore[attr-defined]
    root.addHandler(handler)
    root.setLevel(level)


# --------------------------------------------------------------------------------------
# Run-scoped trace
# --------------------------------------------------------------------------------------
def _now() -> datetime:
    return datetime.now(timezone.utc)


class RunLogger:
    """Writes one JSONL trace per run plus a shared append-only error audit."""

    def __init__(
        self,
        run_id: str,
        *,
        log_directory: Path | str = "logs",
        echo: bool = True,
    ) -> None:
        self.run_id = run_id
        self.echo = echo
        self.log_directory = Path(log_directory)
        self.run_directory = self.log_directory / run_id
        self.trace_path = self.run_directory / "trace.jsonl"
        self.errors_path = self.log_directory / "errors.jsonl"
        self.events: list[dict[str, Any]] = []
        self.errors: list[StructuredError] = []
        self._lock = threading.Lock()
        self.run_directory.mkdir(parents=True, exist_ok=True)

    # -- low level ---------------------------------------------------------------
    def _append(self, path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
        with self._lock:
            with path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
                handle.flush()
                os.fsync(handle.fileno())

    def event(self, event_type: str, **fields: Any) -> dict[str, Any]:
        """Record one sanitized trace event."""
        payload = {
            "run_id": self.run_id,
            "event": event_type,
            "timestamp": _now().isoformat(),
            **redact(fields),
        }
        self.events.append(payload)
        self._append(self.trace_path, payload)
        return payload

    # -- semantic helpers --------------------------------------------------------
    def agent_started(self, agent_name: str, *, task_kind: str = "") -> None:
        self.event("agent_started", agent_name=agent_name, task_kind=task_kind)

    def agent_finished(self, agent_name: str, *, status: str, tool_names: list[str]) -> None:
        self.event(
            "agent_finished",
            agent_name=agent_name,
            status=status,
            tool_names=tool_names,
            tool_call_count=len(tool_names),
        )

    def tool_called(
        self,
        agent_name: str,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
        *,
        step_number: int = 0,
    ) -> None:
        self.event(
            "tool_called",
            agent_name=agent_name,
            tool_name=tool_name,
            step_number=step_number,
            tool_arguments=arguments or {},
        )

    def tool_result(
        self,
        agent_name: str,
        tool_name: str,
        *,
        status: str,
        detail: str = "",
    ) -> None:
        self.event(
            "tool_result",
            agent_name=agent_name,
            tool_name=tool_name,
            status=status,
            detail=detail,
        )

    def delegation(self, specialist: str, tool_name: str, *, status: str, state: str) -> None:
        self.event(
            "delegation",
            specialist=specialist,
            tool_name=tool_name,
            status=status,
            resulting_state=state,
        )

    def state_transition(self, source: str, target: str, *, accepted: bool) -> None:
        self.event("state_transition", source=source, target=target, accepted=accepted)

    def human_decision(self, *, action: str, reason_code: str, approved: bool, approver: str) -> None:
        self.event(
            "human_decision",
            requested_action=action,
            reason_code=reason_code,
            approved=approved,
            approver=approver,
        )

    def token_usage(self, agent_name: str, *, input_tokens: int, output_tokens: int) -> None:
        self.event(
            "token_usage",
            agent_name=agent_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

    # -- errors ------------------------------------------------------------------
    def error(
        self,
        exc: BaseException,
        *,
        agent_name: str | None = None,
        tool_name: str | None = None,
    ) -> StructuredError:
        """Record a caught failure in both the run trace and the global error audit."""
        record = StructuredError(
            run_id=self.run_id,
            error_category=getattr(exc, "category", type(exc).__name__),
            agent_name=agent_name,
            tool_name=tool_name,
            retryable=bool(getattr(exc, "retryable", False)),
            safe_message=redact(str(exc)) or type(exc).__name__,
            occurred_at=_now(),
        )
        self.errors.append(record)
        payload = record.model_dump(mode="json")
        self._append(self.errors_path, payload)
        self.event("error", **payload)
        return record

    # -- human readable ----------------------------------------------------------
    def insight(self, title: str, lines: dict[str, Any]) -> None:
        """Emit a readable `[TITLE INSIGHT]` block and mirror it into the trace."""
        self.event("insight", title=title, values=lines)
        if not self.echo:
            return
        rendered = "\n".join(f"{key}: {value}" for key, value in redact(lines).items())
        print(f"\n[{title.upper()} INSIGHT]\n{rendered}")
