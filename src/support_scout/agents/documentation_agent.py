"""Documentation Agent: writes a reusable, customer-agnostic troubleshooting article."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from smolagents import ToolCallingAgent

from ..evidence_registry import EvidenceRegistry
from ..schemas import SupportDraft, TroubleshootingArticle
from ..tools.documentation_tools import DocumentationWorkspace, build_documentation_tools
from .base import AgentExecutionError, build_agent, run_agent

INSTRUCTIONS = """
You are SupportScout's Documentation Agent.

You turn a resolved support case into an article that helps the *next* person with the
same problem. That means it must be genuinely reusable: written for anyone, about the
class of problem, not about this one customer.

Required sequence:
1. Call list_public_evidence to see what public sources are available.
2. Call select_public_evidence with the EV- identifiers you will cite.
3. Call check_article_privacy with your complete article JSON.
4. Call submit_article once the privacy check passes.

Privacy, which is the hard constraint:
- Cite only EV- public evidence. OP- operational evidence is one customer's private
  record and must never appear, not in the citations and not in the prose.
- Never include a ticket, order, customer, shipment, return, checkout or account
  identifier, an email address, a tracking number, or a date specific to this case.
- If you find yourself writing "this customer" or "their order", rewrite the sentence
  generically. That is the signal you have drifted from documentation into case notes.

Article shape:
- title: the problem as someone would search for it.
- body_markdown: a short explanation of why it happens, then clear numbered steps.
- source_evidence_ids: only the EV- identifiers you selected.
- limitations: what this guidance does not cover. Preserve the limitations from the
  draft rather than quietly dropping them.

If check_article_privacy rejects your article, it will tell you exactly which
identifier it found. Remove it and try again.

Critical: never call final_answer as a substitute for submit_article. final_answer
ends your turn without completing the task; only submit_article does that.
"""


@dataclass(frozen=True)
class DocumentationResult:
    """What the Documentation Agent produced for one resolved case."""

    article: TroubleshootingArticle
    tool_names: list[str]


class DocumentationAgent:
    """Tool-calling specialist that produces privacy-safe reusable documentation."""

    name = "documentation_agent"

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
        self.workspace = DocumentationWorkspace()
        self.tools = build_documentation_tools(self.workspace, registry=registry)
        self.agent = build_agent(
            model=model,
            tools=self.tools,
            instructions=INSTRUCTIONS,
            name=self.name,
            description=(
                "Creates a reusable, customer-agnostic troubleshooting article from "
                "public evidence only."
            ),
            max_steps=max_steps,
            agent_factory=agent_factory,
        )

    def create_article(self, *, draft: SupportDraft) -> DocumentationResult:
        """Write the reusable article for one approved draft."""
        self.workspace.reset()

        task = (
            "Write a reusable troubleshooting article for this class of problem.\n"
            f"Approved issue summary: {draft.issue_summary}\n"
            f"Approved troubleshooting steps: {draft.troubleshooting_steps}\n"
            f"Limitations to preserve: {draft.limitations}\n"
            "Use public evidence only. Select evidence, check privacy, then submit."
        )

        _, tool_names = run_agent(self.agent, task, logger=self.logger, agent_name=self.name)

        if not self.workspace.submitted or self.workspace.article is None:
            raise AgentExecutionError("Documentation Agent did not submit an article")

        return DocumentationResult(article=self.workspace.article, tool_names=tool_names)

    @staticmethod
    def limited_information_article(limitations: list[str]) -> TroubleshootingArticle:
        """Deterministic fallback used when no reusable guidance can be published."""
        return TroubleshootingArticle(
            title="Support Request Requires Human Review",
            body_markdown=(
                "# Support Request Requires Human Review\n\n"
                "Reliable automated guidance could not be completed for this class of "
                "request. An authorized support specialist should review it."
            ),
            source_evidence_ids=[],
            limitations=limitations[:20],
        )
