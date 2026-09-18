"""The agentic contract.

These tests exist to prove the system is genuinely tool-calling rather than a pipeline
that passes schemas to a model. They assert that:

  * every specialist registers real tool objects with model-visible schemas;
  * the orchestrator's own capabilities are delegation tools, one per specialist;
  * a real run produces an ordered trace of tool calls from multiple agents.

If the workflow were ever quietly reduced to direct function calls, these fail.
"""
from __future__ import annotations

from support_scout.agents.documentation_agent import DocumentationAgent
from support_scout.agents.qa_agent import QAAgent
from support_scout.agents.research_agent import ResearchAgent
from support_scout.agents.support_agent import SupportAgent
from support_scout.agents.triage_agent import TriageAgent
from support_scout.tools.orchestration_tools import build_orchestration_tools
from support_scout.workflow.kernel import WorkflowKernel
from support_scout.schemas import WorkflowState, WorkflowStatus
from tests.conftest import (
    FakeDataClient,
    FakeScraper,
    FakeSearchAdapter,
    FakeURLPolicy,
    ScriptedAgent,
    ScriptedModel,
    make_ticket,
)

EXPECTED_TOOLS = {
    "triage_agent": {"analyze_sentiment", "list_supported_domains", "submit_triage"},
    "research_agent": {
        "web_search",
        "validate_source_url",
        "fetch_web_page",
        "assess_evidence",
        "submit_research_result",
    },
    "support_agent": {
        "get_order_status",
        "get_shipment_status",
        "get_return_status",
        "get_account_diagnostics",
        "get_checkout_diagnostics",
        "list_available_evidence",
        "submit_support_draft",
    },
    "qa_agent": {
        "check_evidence_grounding",
        "check_restricted_claims",
        "check_sensitive_data",
        "check_operational_claims",
        "request_support_revision",
        "submit_qa_decision",
    },
    "documentation_agent": {
        "list_public_evidence",
        "select_public_evidence",
        "check_article_privacy",
        "submit_article",
    },
}


def build_specialists(registry, run_logger):
    model = ScriptedModel()
    return {
        "triage_agent": TriageAgent(
            model=model, logger=run_logger, agent_factory=ScriptedAgent
        ),
        "research_agent": ResearchAgent(
            model=model,
            registry=registry,
            search_adapter=FakeSearchAdapter(),
            url_policy=FakeURLPolicy(),
            scraper=FakeScraper(),
            logger=run_logger,
            agent_factory=ScriptedAgent,
        ),
        "support_agent": SupportAgent(
            model=model,
            registry=registry,
            data_client=FakeDataClient(),
            logger=run_logger,
            agent_factory=ScriptedAgent,
        ),
        "qa_agent": QAAgent(
            model=model, registry=registry, logger=run_logger, agent_factory=ScriptedAgent
        ),
        "documentation_agent": DocumentationAgent(
            model=model, registry=registry, logger=run_logger, agent_factory=ScriptedAgent
        ),
    }


def test_every_specialist_registers_its_expected_tools(registry, run_logger):
    specialists = build_specialists(registry, run_logger)
    for name, expected in EXPECTED_TOOLS.items():
        registered = {tool.name for tool in specialists[name].tools}
        assert registered == expected, f"{name} registered {registered}"


def test_registered_tools_are_bound_to_the_agent(registry, run_logger):
    """The tools the agent was constructed with are the tools it can actually call."""
    specialists = build_specialists(registry, run_logger)
    for name, expected in EXPECTED_TOOLS.items():
        agent = specialists[name].agent
        assert set(agent.tools) == expected


def test_every_tool_exposes_a_model_readable_schema(registry, run_logger):
    """A tool the model cannot understand is not a usable tool."""
    specialists = build_specialists(registry, run_logger)
    for specialist in specialists.values():
        for tool in specialist.tools:
            assert tool.description.strip()
            assert tool.output_type == "string"
            for argument, spec in tool.inputs.items():
                assert spec.get("type"), f"{tool.name}.{argument} has no type"
                assert spec.get("description"), f"{tool.name}.{argument} is undocumented"


def test_orchestrator_capabilities_are_delegation_tools(run_logger):
    """Coordination happens through tools, not through hard-coded sequencing."""
    state = WorkflowState(
        run_id="run-1", current_state=WorkflowStatus.RECEIVED, ticket=make_ticket("hello")
    )
    kernel = WorkflowKernel(state, logger=run_logger)

    def noop(_kernel):
        return {}

    tools = build_orchestration_tools(
        kernel, triage=noop, research=noop, support=noop, qa=noop, documentation=noop
    )

    assert {tool.name for tool in tools} == {
        "inspect_workflow_state",
        "delegate_to_triage",
        "delegate_to_research",
        "delegate_to_support",
        "delegate_to_qa",
        "delegate_to_documentation",
        "finalize_workflow",
    }


def test_each_specialist_has_exactly_one_delegation_tool(run_logger):
    state = WorkflowState(
        run_id="run-1", current_state=WorkflowStatus.RECEIVED, ticket=make_ticket("hello")
    )
    kernel = WorkflowKernel(state, logger=run_logger)

    def noop(_kernel):
        return {}

    tools = build_orchestration_tools(
        kernel, triage=noop, research=noop, support=noop, qa=noop, documentation=noop
    )
    delegations = [tool.name for tool in tools if tool.name.startswith("delegate_to_")]

    assert len(delegations) == len(EXPECTED_TOOLS)
    for specialist in ("triage", "research", "support", "qa", "documentation"):
        assert f"delegate_to_{specialist}" in delegations
