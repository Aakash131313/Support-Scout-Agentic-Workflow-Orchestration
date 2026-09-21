"""Shared agent construction, execution and tracing.

Every specialist is a `smolagents.ToolCallingAgent`. This module owns the three things
they all need: building the agent, running it with tracing, and extracting the tool
call sequence. Keeping it here means there is exactly one place where tool calls are
recorded, so the trace can never disagree with what happened.

Tracing source
--------------
Tool call history is read from `agent.memory.steps` -- the agent object itself, which
accumulates step history as it runs and is what smolagents' own console renderer reads
to print its "Calling tool: ..." panels -- rather than from whatever
`agent.run(..., return_full_result=True)` returns.

The previous implementation read the run result. An eighteen-ticket batch recorded
`total_tool_calls: 0` across every run, including four that completed normally with
evidence gathered and drafts approved, which proves tools ran and the run result did
not carry their history. The agent's own memory is the stable source.

Because the exact attribute name smolagents uses on a recorded tool call is not
guaranteed across versions -- some expose `.name` directly, others nest it under
`.function.name` in an OpenAI-wire-format style -- extraction tries several known
shapes. If none match, a diagnostic event is logged carrying the unrecognised type
name, so the next run says exactly what to add rather than silently reporting zero.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable

from smolagents import ToolCallingAgent

from ..exceptions import SupportScoutError


class AgentExecutionError(SupportScoutError):
    """A specialist agent finished without submitting a valid result."""

    category = "agent_execution_error"


def build_agent(
    *,
    model: Any,
    tools: list[Any],
    instructions: str,
    name: str,
    description: str,
    max_steps: int,
    agent_factory: Callable[..., Any] = ToolCallingAgent,
) -> Any:
    """Construct a tool-calling agent with a bounded step budget."""
    agent = agent_factory(
        model=model,
        tools=tools,
        max_steps=max_steps,
        instructions=instructions,
        name=name,
        description=description,
    )
    # Serialise tool execution so the trace order matches the real call order.
    if hasattr(agent, "max_tool_threads"):
        agent.max_tool_threads = 1
    return agent


def _tool_call_name(call: Any) -> str | None:
    """Extract a tool name from one recorded call, trying each known shape.

    Order: a direct `.name` attribute (the smolagents ToolCall dataclass shape), a
    nested `.function.name` (OpenAI wire format), then dict-style access for either.
    Returns None when nothing matches so the caller can log a diagnostic rather than
    guess further.
    """
    name = getattr(call, "name", None)
    if name:
        return str(name)

    function = getattr(call, "function", None)
    name = getattr(function, "name", None)
    if name:
        return str(name)

    if isinstance(call, dict):
        name = call.get("name")
        if name:
            return str(name)
        function = call.get("function")
        if isinstance(function, dict):
            name = function.get("name")
            if name:
                return str(name)

    return None


def extract_tool_names(
    agent: Any, *, logger: Any = None, agent_name: str = ""
) -> list[str]:
    """Read the ordered tool call sequence out of an agent's own memory."""
    names: list[str] = []
    memory = getattr(agent, "memory", None)
    steps = getattr(memory, "steps", None) or []

    steps_with_calls = 0
    unrecognized_call_types: set[str] = set()

    for step in steps:
        calls = getattr(step, "tool_calls", None)
        if not calls:
            continue
        steps_with_calls += 1
        for call in calls:
            name = _tool_call_name(call)
            if name:
                names.append(name)
            else:
                unrecognized_call_types.add(type(call).__name__)

    # Self-diagnosing fallback: if steps clearly carried tool calls but nothing was
    # extracted, record the shape that was seen instead of silently reporting zero.
    if logger is not None and steps_with_calls and not names:
        logger.event(
            "tool_name_extraction_failed",
            agent_name=agent_name,
            steps_with_tool_calls=steps_with_calls,
            unrecognized_call_types=sorted(unrecognized_call_types),
            note=(
                "Tool calls were present in agent.memory.steps but no tool name could "
                "be read from any known shape. Inspect unrecognized_call_types and "
                "update _tool_call_name() in agents/base.py accordingly."
            ),
        )

    return names


def run_agent(
    agent: Any,
    task: str,
    *,
    logger: Any,
    agent_name: str,
) -> tuple[Any, list[str]]:
    """Run an agent, trace every tool call it made, and return the result."""
    started = datetime.now(timezone.utc)
    logger.agent_started(agent_name)

    try:
        run_result = agent.run(task, return_full_result=True)
    except Exception as exc:  # noqa: BLE001 - recorded, then re-raised for the kernel
        logger.error(exc, agent_name=agent_name)
        logger.agent_finished(agent_name, status="failed", tool_names=[])
        raise

    tool_names = extract_tool_names(agent, logger=logger, agent_name=agent_name)

    for index, tool_name in enumerate(tool_names, start=1):
        logger.tool_called(agent_name, tool_name, step_number=index)

    logger.agent_finished(agent_name, status="succeeded", tool_names=tool_names)
    logger.event(
        "agent_duration",
        agent_name=agent_name,
        seconds=(datetime.now(timezone.utc) - started).total_seconds(),
    )

    return run_result, tool_names
