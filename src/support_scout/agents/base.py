"""Shared agent construction, execution and tracing.

Every specialist is a `smolagents.ToolCallingAgent`. This module owns the three things
they all need: building the agent, running it with tracing, and extracting the tool
call sequence from the run result. Keeping it here means there is exactly one place
where tool calls are recorded, so the trace can never disagree with what happened.
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


def extract_tool_names(run_result: Any) -> list[str]:
    """Read the ordered tool call sequence out of a smolagents run result."""
    names: list[str] = []
    memory = getattr(run_result, "memory", None)
    steps = getattr(memory, "steps", []) if memory is not None else []

    for step in steps:
        for call in getattr(step, "tool_calls", None) or []:
            function = getattr(call, "function", None)
            name = getattr(function, "name", None) or getattr(call, "name", None)
            if name:
                names.append(str(name))

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

    tool_names = extract_tool_names(run_result)

    for index, tool_name in enumerate(tool_names, start=1):
        logger.tool_called(agent_name, tool_name, step_number=index)

    logger.agent_finished(agent_name, status="succeeded", tool_names=tool_names)
    logger.event(
        "agent_duration",
        agent_name=agent_name,
        seconds=(datetime.now(timezone.utc) - started).total_seconds(),
    )

    return run_result, tool_names
