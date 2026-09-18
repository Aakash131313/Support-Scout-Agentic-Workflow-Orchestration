"""Builds the live dependency graph.

One function, one wiring path. There is no mode switch: the agentic workflow is the
only workflow, so the graph that runs in production is the graph the tests exercise.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

import requests

from ..agents.documentation_agent import DocumentationAgent
from ..agents.model_adapter import create_model
from ..agents.orchestrator_agent import OrchestratorAgent
from ..agents.qa_agent import QAAgent
from ..agents.research_agent import ResearchAgent
from ..agents.support_agent import SupportAgent
from ..agents.triage_agent import TriageAgent
from ..artifacts import ArtifactWriter
from ..clients.support_data_client import SupportDataClient
from ..config import Settings
from ..evidence_registry import EvidenceRegistry
from ..exceptions import ConfigurationError
from ..hitl import build_gate
from ..logging_config import RunLogger, configure_logging
from ..services.evidence_rules import EvidenceAssessor
from ..services.safety_rules import SafetyScreener
from ..services.url_policy import URLPolicy
from ..services.web_scraper import WebScraper
from ..services.web_search import TavilyAdapter


def create_tavily_client(api_key: str) -> Any:
    """Import the Tavily client lazily so offline tests never need the package."""
    from tavily import TavilyClient

    return TavilyClient(api_key=api_key)


def build_orchestrator(
    settings: Settings | None = None,
    *,
    output_override: str | None = None,
    interactive: bool = False,
    auto_approve: bool | None = None,
    model: Any = None,
    search_adapter: Any = None,
    data_client: Any = None,
    scraper: Any = None,
    url_policy: Any = None,
    agent_factory: Callable[..., Any] | None = None,
    echo_insights: bool = True,
) -> OrchestratorAgent:
    """Assemble the orchestrator and all five specialists.

    Every external dependency is injectable, which is what lets the offline suite run
    the real orchestration path with fakes instead of network calls.
    """
    settings = settings or Settings.from_env()
    configure_logging()

    if model is None:
        api_key, model_name, base_url = settings.require_udacity()
        model = create_model(
            api_key=api_key,
            model_name=model_name,
            base_url=base_url,
            timeout_seconds=settings.request_timeout_seconds,
        )

    if url_policy is None:
        url_policy = URLPolicy()

    if search_adapter is None:
        search_adapter = TavilyAdapter(
            client=create_tavily_client(settings.require_tavily()),
            max_results=settings.max_search_results,
        )

    if scraper is None:
        scraper = WebScraper(
            session=requests.Session(),
            url_policy=url_policy,
            timeout=settings.request_timeout_seconds,
            max_characters=settings.max_page_characters,
        )

    if data_client is None:
        data_client = SupportDataClient(
            base_url=settings.support_data_base_url,
            timeout_seconds=settings.request_timeout_seconds,
        )

    output_root = Path(output_override) if output_override else settings.output_directory
    artifact_writer = ArtifactWriter(output_root)

    approval_gate = build_gate(
        require_approval=settings.require_human_approval,
        auto_approve=(
            settings.auto_approve_restricted_actions if auto_approve is None else auto_approve
        ),
        interactive=interactive,
    )

    def logger_factory(run_id: str) -> RunLogger:
        return RunLogger(run_id, log_directory=settings.log_directory, echo=echo_insights)

    # A single registry instance is shared by every specialist. Tools bind to it at
    # construction time, so it must be the same object for the whole process; the
    # orchestrator resets it at the start of each run.
    registry = EvidenceRegistry(max_content_characters=settings.max_page_characters)
    bootstrap_logger = logger_factory("bootstrap")
    factory_kwargs = {"agent_factory": agent_factory} if agent_factory else {}

    triage_agent = TriageAgent(
        model=model,
        logger=bootstrap_logger,
        max_steps=settings.max_agent_steps,
        **factory_kwargs,
    )
    research_agent = ResearchAgent(
        model=model,
        registry=registry,
        search_adapter=search_adapter,
        url_policy=url_policy,
        scraper=scraper,
        logger=bootstrap_logger,
        assessor=EvidenceAssessor(),
        max_pages=settings.max_pages_to_scrape,
        max_steps=settings.max_agent_steps,
        **factory_kwargs,
    )
    support_agent = SupportAgent(
        model=model,
        registry=registry,
        data_client=data_client,
        logger=bootstrap_logger,
        max_steps=settings.max_agent_steps,
        **factory_kwargs,
    )
    qa_agent = QAAgent(
        model=model,
        registry=registry,
        logger=bootstrap_logger,
        max_steps=settings.max_agent_steps,
        **factory_kwargs,
    )
    documentation_agent = DocumentationAgent(
        model=model,
        registry=registry,
        logger=bootstrap_logger,
        max_steps=settings.max_agent_steps,
        **factory_kwargs,
    )

    return OrchestratorAgent(
        model=model,
        triage_agent=triage_agent,
        research_agent=research_agent,
        support_agent=support_agent,
        qa_agent=qa_agent,
        documentation_agent=documentation_agent,
        registry=registry,
        logger_factory=logger_factory,
        artifact_writer=artifact_writer,
        approval_gate=approval_gate,
        screener=SafetyScreener(),
        confidence_threshold=settings.classification_confidence_threshold,
        max_revisions=settings.max_agent_revisions,
        max_total_tool_calls=settings.max_total_tool_calls,
        max_steps=settings.max_orchestrator_steps,
        **factory_kwargs,
    )


def check_operations_service(settings: Settings, client: Any = None) -> tuple[bool, str]:
    """Probe the operations service and return a clear remediation message if it is down."""
    client = client or SupportDataClient(
        base_url=settings.support_data_base_url,
        timeout_seconds=settings.request_timeout_seconds,
    )
    if client.is_healthy():
        return True, f"Operations service is healthy at {settings.support_data_base_url}"
    return False, (
        f"Operations service is unreachable at {settings.support_data_base_url}. "
        "Start it with: python -m support_scout.main serve"
    )


def ensure_operations_service(settings: Settings, client: Any = None) -> None:
    """Fail loudly at start-up rather than mid-run with a confusing 404."""
    healthy, message = check_operations_service(settings, client)
    if not healthy:
        raise ConfigurationError(message)
