"""Research tools: public web search, URL validation, page retrieval, evidence prep.

Every tool below is a real `@tool` function. smolagents derives the tool name,
description and argument schema from the function signature and docstring, so what
the model sees is exactly what is written here.

Tools are built by a factory so they can close over a run-scoped workspace without
becoming classes. State stays injected; the tool stays a readable function.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from smolagents import tool

from ..evidence_registry import EvidenceRegistry
from ..exceptions import ScrapeError, SearchError, SupportScoutError, UnsafeURLError
from ..schemas import SearchResult
from ..services.evidence_rules import EvidenceAssessor
from ..services.safety_rules import query_contains_identifier, sanitize_search_query


@dataclass
class ResearchWorkspace:
    """Mutable state shared by the research tools during a single agent run."""

    search_results: list[SearchResult] = field(default_factory=list)
    validated_urls: set[str] = field(default_factory=set)
    fetched_urls: set[str] = field(default_factory=set)
    insufficient: bool = False
    potential_conflict: bool = False
    assessment_reasons: list[str] = field(default_factory=list)
    submitted: bool = False
    summary: str = ""

    def reset(self) -> None:
        self.search_results.clear()
        self.validated_urls.clear()
        self.fetched_urls.clear()
        self.insufficient = False
        self.potential_conflict = False
        self.assessment_reasons.clear()
        self.submitted = False
        self.summary = ""


def build_research_tools(
    workspace: ResearchWorkspace,
    *,
    registry: EvidenceRegistry,
    search_adapter: Any,
    url_policy: Any,
    scraper: Any,
    assessor: EvidenceAssessor | None = None,
    max_pages: int = 3,
) -> list[Any]:
    """Create the research tool set bound to one run's workspace and services."""
    assessor = assessor or EvidenceAssessor()

    @tool
    def web_search(query: str) -> str:
        """Search the public web for general troubleshooting guidance.

        Customer, order, account and refund identifiers are stripped from the query
        automatically before it is sent, because research may only ever look up
        general public information.

        Args:
            query: A short, general troubleshooting question with no customer details.
        """
        safe_query = sanitize_search_query(query)
        if not safe_query:
            return json.dumps(
                {
                    "status": "rejected",
                    "reason": "The query contained only identifiers and nothing to search.",
                }
            )
        try:
            results = search_adapter.search(safe_query)
        except SearchError as exc:
            return json.dumps({"status": "error", "reason": str(exc), "results": []})

        workspace.search_results.extend(results)
        return json.dumps(
            {
                "status": "ok",
                "query_used": safe_query,
                "identifiers_removed": safe_query != query.strip(),
                "results": [
                    {
                        "title": item.title,
                        "url": str(item.url),
                        "snippet": item.snippet[:300],
                        "rank": item.rank,
                    }
                    for item in results
                ],
            }
        )

    @tool
    def validate_source_url(url: str) -> str:
        """Check that a URL is a safe public destination before retrieving it.

        A URL must pass this check before fetch_web_page will accept it.

        Args:
            url: The exact URL copied from a web_search result.
        """
        try:
            url_policy.validate(url)
        except UnsafeURLError as exc:
            return json.dumps({"status": "blocked", "url": url, "reason": str(exc)})
        workspace.validated_urls.add(url)
        return json.dumps({"status": "allowed", "url": url})

    @tool
    def fetch_web_page(url: str) -> str:
        """Retrieve a validated public page and register it as public evidence.

        The page is stored under a deterministic EV- identifier. Never invent an
        evidence identifier: use the one this tool returns.

        Args:
            url: A URL that validate_source_url has already allowed.
        """
        if url not in workspace.validated_urls:
            return json.dumps(
                {
                    "status": "rejected",
                    "reason": "Call validate_source_url for this exact URL first.",
                }
            )
        if len(workspace.fetched_urls) >= max_pages:
            return json.dumps(
                {"status": "rejected", "reason": f"Page budget of {max_pages} reached."}
            )

        try:
            scraped = scraper.fetch(url)
        except ScrapeError as exc:
            return json.dumps({"status": "error", "url": url, "reason": str(exc)})
        except SupportScoutError as exc:
            return json.dumps({"status": "error", "url": url, "reason": str(exc)})

        workspace.fetched_urls.add(url)
        record = registry.register_public(
            source_url=scraped.get("final_url") or url,
            title=scraped.get("title") or "Untitled source",
            content=scraped.get("content", ""),
            content_hash=scraped.get("hash"),
        )
        if record is None:
            return json.dumps(
                {"status": "duplicate", "url": url, "reason": "This page duplicates earlier evidence."}
            )

        return json.dumps(
            {
                "status": "ok",
                "evidence_id": record.evidence_id,
                "title": record.title,
                "source_url": str(record.source_url),
                "content_preview": record.content[:800],
            }
        )

    @tool
    def assess_evidence(reason: str) -> str:
        """Check whether the gathered evidence is sufficient and internally consistent.

        Call this once after fetching pages and before submitting. If evidence is
        insufficient or conflicting, say so rather than inventing an answer.

        Args:
            reason: A short note on why the gathered evidence is ready to assess.
        """
        del reason
        assessment = assessor.assess(registry.public_evidence)
        workspace.insufficient = assessment.insufficient
        workspace.potential_conflict = assessment.potential_conflict
        workspace.assessment_reasons = list(assessment.reasons)
        return json.dumps(
            {
                "status": "ok",
                "evidence_ids": [item.evidence_id for item in assessment.items],
                "insufficient": assessment.insufficient,
                "potential_conflict": assessment.potential_conflict,
                "reasons": assessment.reasons,
            }
        )

    @tool
    def submit_research_result(summary: str) -> str:
        """Submit the completed research. Call this exactly once, at the end.

        Args:
            summary: One or two sentences describing what guidance was found.
        """
        if not workspace.assessment_reasons and not registry.public_evidence:
            # assess_evidence has not run and nothing was gathered.
            return json.dumps(
                {"status": "rejected", "reason": "Call assess_evidence before submitting."}
            )
        workspace.submitted = True
        workspace.summary = summary
        return json.dumps(
            {
                "status": "submitted",
                "evidence_ids": [item.evidence_id for item in registry.public_evidence],
                "insufficient": workspace.insufficient,
                "potential_conflict": workspace.potential_conflict,
            }
        )

    return [
        web_search,
        validate_source_url,
        fetch_web_page,
        assess_evidence,
        submit_research_result,
    ]
