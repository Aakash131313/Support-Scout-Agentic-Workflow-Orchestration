"""QA Agent: runs deterministic verification tools and recommends a decision."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from smolagents import ToolCallingAgent

from ..evidence_registry import EvidenceRegistry
from ..schemas import QAResult, SupportDraft
from ..tools.qa_tools import QAWorkspace, build_qa_tools
from .base import AgentExecutionError, build_agent, run_agent

INSTRUCTIONS = """
You are SupportScout's Quality Assurance Agent, the senior reviewer before a response
reaches a customer.

You must run every verification tool before deciding. Do not judge the draft from
memory; the tools are the evidence:
- check_evidence_grounding
- check_restricted_claims
- check_sensitive_data
- check_operational_claims

Deciding:
- approve  when every check passes and the reply genuinely answers the question.
- revise   when the problems are specific and correctable. Call
           request_support_revision with concrete instructions first, then submit.
           Say what is wrong and what would fix it, not merely that it is wrong.
- escalate when the draft claims a restricted action, leaks sensitive data, asserts
           customer-specific facts with no operational evidence, or cannot be repaired.

Authority:
- A failed deterministic check cannot be argued away. The submit tool will refuse an
  approval while any check is failing, and that refusal is correct.
- Approving an unsupported claim is the most damaging thing you can do here. When
  genuinely torn between approve and revise, choose revise.

Finish by calling submit_qa_decision exactly once.

Critical: never call final_answer as a substitute for submit_qa_decision.
final_answer ends your turn without completing the task; only submit_qa_decision
does that.
"""


@dataclass(frozen=True)
class QAReview:
    """What the QA Agent concluded about one draft."""

    result: QAResult
    deterministic_passed: bool
    blocking_issues: list[str]
    checks_run: list[str]
    tool_names: list[str]


class QAAgent:
    """Tool-calling specialist with deterministic verification authority."""

    name = "qa_agent"

    def __init__(
        self,
        *,
        model: Any,
        registry: EvidenceRegistry,
        logger: Any,
        max_steps: int = 12,
        agent_factory: Callable[..., Any] = ToolCallingAgent,
    ) -> None:
        self.logger = logger
        self.workspace = QAWorkspace()
        self.tools = build_qa_tools(self.workspace, registry=registry)
        self.agent = build_agent(
            model=model,
            tools=self.tools,
            instructions=INSTRUCTIONS,
            name=self.name,
            description=(
                "Runs deterministic verification tools over a support draft and "
                "recommends approve, revise or escalate."
            ),
            max_steps=max_steps,
            agent_factory=agent_factory,
        )

    def review(self, *, draft: SupportDraft) -> QAReview:
        """Review one draft against every deterministic check."""
        self.workspace.reset(draft)

        task = (
            "Review this support draft before it reaches the customer.\n"
            f"Draft JSON: {draft.model_dump_json()}\n"
            "Run every verification tool, then submit exactly one decision."
        )

        _, tool_names = run_agent(self.agent, task, logger=self.logger, agent_name=self.name)

        if not self.workspace.submitted or self.workspace.result is None:
            raise AgentExecutionError("QA Agent did not submit a decision")

        blockers = self.workspace.blocking_issues
        return QAReview(
            result=self.workspace.result,
            deterministic_passed=not blockers,
            blocking_issues=blockers,
            checks_run=sorted(self.workspace.checks),
            tool_names=tool_names,
        )
