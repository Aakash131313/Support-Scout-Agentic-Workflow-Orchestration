"""Orchestrator Agent: an agent whose tools are its specialists.

The orchestrator does no support work itself. It reads authoritative state from the
kernel and chooses which specialist to delegate to next. The kernel validates every
choice, so a confused or adversarial model can stall a run but cannot corrupt it.

Artifacts are written in a `finally` block. A run that escalates, fails, or exhausts
its budget still leaves a complete, truthful record behind -- previously an escalated
run raised before writing anything at all.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from smolagents import ToolCallingAgent

from ..artifacts import ArtifactWriter, write_run_artifacts
from ..exceptions import SupportScoutError
from ..hitl import ApprovalGate
from ..schemas import (
    EscalationReason,
    SupportTicket,
    WorkflowState,
    WorkflowStatus,
)
from ..services.safety_rules import SafetyScreener
from ..tools.orchestration_tools import build_orchestration_tools
from ..workflow.kernel import WorkflowKernel
from .base import build_agent, run_agent

INSTRUCTIONS = """
You are SupportScout's Orchestrator Agent.

You coordinate five specialist agents by calling delegation tools. You never do their
work yourself: no classifying, no researching, no drafting, no reviewing, no writing.

The kernel is the only source of truth.
- Call inspect_workflow_state whenever you are unsure what has happened.
- Never assume the current state from memory. Read it.
- Every tool observation tells you the resulting state. Use it.

Normal progression, one tool call per step:
  validated              -> delegate_to_triage
  triaged                -> delegate_to_research
  researched             -> delegate_to_support
  drafted                -> delegate_to_qa
  qa_revision_requested  -> delegate_to_support        (QA asked for one revision)
  qa_approved            -> delegate_to_documentation
  documented             -> finalize_workflow
  escalated              -> finalize_workflow, then stop

Escalation:
- Escalation is a legitimate, successful outcome, not an error. It means the request
  needs a human. When a delegation reports that the workflow escalated, do not try to
  route around it, do not call another specialist, and do not retry. Call
  finalize_workflow and stop.

When a tool call fails:
- Read the reason. It is specific and usually tells you exactly what to do instead.
- Do not repeat an identical failing call. Call inspect_workflow_state once, then take
  the valid next action.
- If the same action fails twice, stop. A stalled run that reports honestly is far
  better than a loop.

Finish by calling final_answer with one sentence describing the outcome.
"""


@dataclass(frozen=True)
class RunResult:
    """The outcome of one complete workflow run."""

    state: WorkflowState
    output_directory: Path | None
    run_id: str


class OrchestratorAgent:
    """Agentic orchestrator backed by a deterministic workflow kernel."""

    name = "orchestrator_agent"

    def __init__(
        self,
        *,
        model: Any,
        triage_agent: Any,
        research_agent: Any,
        support_agent: Any,
        qa_agent: Any,
        documentation_agent: Any,
        registry: Any,
        logger_factory: Callable[[str], Any],
        artifact_writer: ArtifactWriter,
        approval_gate: ApprovalGate,
        screener: SafetyScreener | None = None,
        confidence_threshold: float = 0.70,
        max_revisions: int = 1,
        max_total_tool_calls: int = 40,
        max_steps: int = 16,
        agent_factory: Callable[..., Any] = ToolCallingAgent,
    ) -> None:
        self.model = model
        self.triage_agent = triage_agent
        self.research_agent = research_agent
        self.support_agent = support_agent
        self.qa_agent = qa_agent
        self.documentation_agent = documentation_agent
        self.registry = registry
        self.logger_factory = logger_factory
        self.artifact_writer = artifact_writer
        self.approval_gate = approval_gate
        self.screener = screener or SafetyScreener()
        self.confidence_threshold = confidence_threshold
        self.max_revisions = max_revisions
        self.max_total_tool_calls = max_total_tool_calls
        self.max_steps = max_steps
        self.agent_factory = agent_factory

    # -- specialist adapters -----------------------------------------------------
    def _triage_runner(self) -> Callable[[WorkflowKernel], dict[str, Any]]:
        def run(kernel: WorkflowKernel) -> dict[str, Any]:
            result = self.triage_agent.triage(kernel.state.ticket)

            screening = self.screener.screen_classification(
                result.classification, confidence_threshold=self.confidence_threshold
            )
            classification = result.classification
            if screening.required and screening.escalation.reason_code is EscalationReason.LOW_CONFIDENCE:
                classification = classification.model_copy(
                    update={
                        "domain": classification.domain
                        if classification.domain.value == "uncertain"
                        else classification.domain,
                        "uncertainty_reason": classification.uncertainty_reason or "low_confidence",
                    }
                )

            kernel.apply_triage(
                classification=classification,
                sentiment=result.sentiment,
                escalation=screening.escalation,
            )
            return {
                "domain": classification.domain.value,
                "urgency": classification.urgency.value,
                "sentiment": result.sentiment.label.value,
                "tools_used": result.tool_names,
            }

        return run

    def _research_runner(self) -> Callable[[WorkflowKernel], dict[str, Any]]:
        def run(kernel: WorkflowKernel) -> dict[str, Any]:
            classification = kernel.state.classification
            result = self.research_agent.research(
                domain=classification.domain.value if classification else "uncertain",
                intent=classification.intent if classification else "",
                customer_message=kernel.state.ticket.customer_message,
            )
            kernel.apply_research(
                search_results=result.search_results,
                evidence=result.evidence,
                insufficient=result.insufficient,
                conflicting=result.potential_conflict,
            )
            return {
                "evidence_ids": [item.evidence_id for item in result.evidence],
                "insufficient": result.insufficient,
                "tools_used": result.tool_names,
            }

        return run

    def _support_runner(self) -> Callable[[WorkflowKernel], dict[str, Any]]:
        def run(kernel: WorkflowKernel) -> dict[str, Any]:
            previous_qa = kernel.state.qa_result
            result = self.support_agent.create_draft(
                ticket=kernel.state.ticket,
                classification=kernel.state.classification,
                sentiment=kernel.state.sentiment,
                revision_instructions=(
                    previous_qa.revision_instructions if previous_qa else None
                ),
            )
            kernel.apply_support(
                draft=result.draft, operational_evidence=result.operational_evidence
            )
            return {
                "evidence_cited": result.draft.evidence_ids,
                "operational_tools_used": result.tools_attempted,
                "tools_used": result.tool_names,
            }

        return run

    def _qa_runner(self) -> Callable[[WorkflowKernel], dict[str, Any]]:
        def run(kernel: WorkflowKernel) -> dict[str, Any]:
            review = self.qa_agent.review(draft=kernel.state.support_draft)
            kernel.apply_qa(result=review.result)
            return {
                "decision": review.result.decision.value,
                "deterministic_passed": review.deterministic_passed,
                "checks_run": review.checks_run,
                "tools_used": review.tool_names,
            }

        return run

    def _documentation_runner(self) -> Callable[[WorkflowKernel], dict[str, Any]]:
        def run(kernel: WorkflowKernel) -> dict[str, Any]:
            result = self.documentation_agent.create_article(draft=kernel.state.support_draft)
            kernel.apply_documentation(article=result.article)
            return {"title": result.article.title, "tools_used": result.tool_names}

        return run

    # -- run ---------------------------------------------------------------------
    def run(self, ticket: SupportTicket) -> RunResult:
        """Execute the full workflow for one ticket and always write artifacts."""
        run_id = uuid4().hex[:12]
        logger = self.logger_factory(run_id)

        # One registry per run. Specialist tools close over this exact object, so it is
        # reset rather than replaced -- swapping the attribute would leave the tools
        # pointing at the previous run's evidence.
        self.registry.reset()

        state = WorkflowState(
            run_id=run_id, current_state=WorkflowStatus.RECEIVED, ticket=ticket
        )
        kernel = WorkflowKernel(
            state,
            logger=logger,
            approval_gate=self.approval_gate,
            max_revisions=self.max_revisions,
            max_total_tool_calls=self.max_total_tool_calls,
        )

        # Point every specialist at this run's logger so the trace is single-sourced.
        for agent in (
            self.triage_agent,
            self.research_agent,
            self.support_agent,
            self.qa_agent,
            self.documentation_agent,
        ):
            if hasattr(agent, "logger"):
                agent.logger = logger

        logger.event("run_started", ticket_id=ticket.ticket_id)

        try:
            # Deterministic pre-model screening. This runs before the agent sees anything.
            screening = self.screener.screen_ticket(ticket)
            kernel.transition(WorkflowStatus.VALIDATED)

            if screening.required and screening.escalation.reason_code is not None:
                self._handle_prescreen_escalation(kernel, screening)
            else:
                self._run_orchestration(kernel, logger)

            if not kernel.finalized and state.current_state not in {
                WorkflowStatus.COMPLETED,
                WorkflowStatus.ESCALATED,
                WorkflowStatus.FAILED,
            }:
                kernel.fail("orchestrator_did_not_finalize")

        except SupportScoutError as exc:
            logger.error(exc, agent_name=self.name)
            kernel.fail(getattr(exc, "category", type(exc).__name__))
        except Exception as exc:  # noqa: BLE001 - nothing may escape without an artifact
            logger.error(exc, agent_name=self.name)
            kernel.fail(type(exc).__name__)

        output_directory = write_run_artifacts(
            self.artifact_writer, state, trace_events=logger.events
        )

        logger.insight(
            "final",
            {
                "Ticket": ticket.ticket_id,
                "Run": run_id,
                "Status": state.current_state.value,
                "Escalation": (
                    state.escalation.reason_code.value if state.escalation.reason_code else "none"
                ),
                "Delegations": ", ".join(item.specialist for item in state.delegations) or "none",
                "Output": str(output_directory),
            },
        )

        return RunResult(state=state, output_directory=output_directory, run_id=run_id)

    # -- internals ---------------------------------------------------------------
    def _handle_prescreen_escalation(self, kernel: WorkflowKernel, screening: Any) -> None:
        """Handle a safety rule that fired before any model call."""
        from ..hitl import requires_human_approval

        reason = screening.escalation.reason_code
        kernel.audit("safety_screening", "triggered", {"rule_ids": screening.rule_ids})

        if requires_human_approval(reason):
            approved = kernel.request_human_approval(
                reason, action=f"Continue automated handling despite {reason.value}"
            )
            if approved:
                # A human accepted responsibility, so automated handling may continue.
                self._run_orchestration(kernel, kernel.logger)
                return

        kernel.escalate(
            reason,
            summary=screening.escalation.summary,
            recommended_action=screening.escalation.recommended_human_action,
        )
        kernel.finalize()

    def _run_orchestration(self, kernel: WorkflowKernel, logger: Any) -> None:
        """Build and run the orchestrator agent over its delegation tools."""
        tools = build_orchestration_tools(
            kernel,
            triage=self._triage_runner(),
            research=self._research_runner(),
            support=self._support_runner(),
            qa=self._qa_runner(),
            documentation=self._documentation_runner(),
        )

        agent = build_agent(
            model=self.model,
            tools=tools,
            instructions=INSTRUCTIONS,
            name=self.name,
            description=(
                "Coordinates SupportScout specialists by selecting delegation tools "
                "while the deterministic kernel validates every state change."
            ),
            max_steps=self.max_steps,
            agent_factory=self.agent_factory,
        )

        task = (
            "Run the SupportScout workflow for this ticket.\n"
            f"Ticket id: {kernel.state.ticket.ticket_id}\n"
            "Start by calling inspect_workflow_state, then follow the progression in "
            "your instructions, one tool call per step."
        )

        run_agent(agent, task, logger=logger, agent_name=self.name)
