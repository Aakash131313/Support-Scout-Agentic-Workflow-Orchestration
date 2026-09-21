"""Shared offline test harness.

The suite never calls a live model, search API or website. Instead of faking the model
protocol (which would couple tests to smolagents internals), it injects a
`ScriptedAgent` in place of `ToolCallingAgent`. The scripted agent executes a chosen
sequence of tool calls against the *real* tool objects, so the tools, the workspaces,
the evidence registry and the kernel are all genuinely exercised -- only the model's
choice of what to call next is scripted.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Callable, Iterator

import pytest

from support_scout.evidence_registry import EvidenceRegistry
from support_scout.exceptions import ScrapeError, SupportDataNotFound
from support_scout.schemas import SearchResult, SupportTicket


# --------------------------------------------------------------------------------------
# Scripted agent harness
# --------------------------------------------------------------------------------------
class ScriptContext:
    """Passed to a script generator so it can react to tool observations."""

    def __init__(self) -> None:
        self.observations: list[str] = []

    def last(self) -> str:
        return self.observations[-1] if self.observations else ""

    def last_json(self) -> dict[str, Any]:
        try:
            return json.loads(self.last())
        except (json.JSONDecodeError, TypeError):
            return {}


class _ToolCall:
    def __init__(self, name: str, arguments: dict[str, Any]) -> None:
        self.name = name
        self.arguments = arguments


class _Step:
    def __init__(self, tool_calls: list[_ToolCall]) -> None:
        self.tool_calls = tool_calls


class _Memory:
    def __init__(self) -> None:
        self.steps: list[_Step] = []


class _RunResult:
    def __init__(self, output: Any, memory: _Memory) -> None:
        self.output = output
        self.memory = memory


Script = Callable[[ScriptContext], Iterator[tuple[str, dict[str, Any]]]]


class ScriptedAgent:
    """Stands in for ToolCallingAgent and runs a scripted tool sequence."""

    def __init__(
        self,
        model: Any,
        tools: list[Any],
        max_steps: int = 12,
        instructions: str = "",
        name: str = "agent",
        description: str = "",
        **_: Any,
    ) -> None:
        self.model = model
        self.tools = {tool.name: tool for tool in tools}
        self.tool_list = tools
        self.max_steps = max_steps
        self.instructions = instructions
        self.name = name
        self.description = description
        # Real smolagents agents accumulate step history on the agent itself, and
        # agents/base.py reads it from there. Mirror that so the offline suite
        # exercises the same extraction path production uses.
        self.memory = _Memory()

    def run(self, task: str, return_full_result: bool = False, **_: Any) -> Any:
        script = self.model.script_for(self.name)
        # Reset per run, then expose the same object through the run result.
        self.memory = _Memory()
        memory = self.memory
        context = ScriptContext()

        if script is None:
            return _RunResult("no script", memory) if return_full_result else "no script"

        generator = script(context)
        steps = 0
        try:
            tool_name, kwargs = next(generator)
            while steps < self.max_steps:
                steps += 1
                memory.steps.append(_Step([_ToolCall(tool_name, kwargs)]))

                tool = self.tools.get(tool_name)
                if tool is None:
                    observation = json.dumps(
                        {"status": "error", "reason": f"unknown tool {tool_name}"}
                    )
                else:
                    try:
                        observation = str(tool(**kwargs))
                    except Exception as exc:  # noqa: BLE001 - surfaced to the script
                        observation = json.dumps({"status": "error", "reason": str(exc)})

                context.observations.append(observation)
                tool_name, kwargs = generator.send(observation)
        except StopIteration:
            pass

        return _RunResult("done", memory) if return_full_result else "done"


class ScriptedModel:
    """Holds one script per agent name."""

    def __init__(self, **scripts: Script) -> None:
        self.scripts = scripts

    def script_for(self, agent_name: str) -> Script | None:
        return self.scripts.get(agent_name)

    def with_script(self, agent_name: str, script: Script) -> "ScriptedModel":
        self.scripts[agent_name] = script
        return self


# --------------------------------------------------------------------------------------
# Fake external dependencies
# --------------------------------------------------------------------------------------
class FakeURLPolicy:
    """Allows public example URLs and blocks anything explicitly marked unsafe."""

    BLOCKED = ("localhost", "127.0.0.1", "169.254.", "10.", "192.168.", "file:", "ftp:")

    def __init__(self, blocked_extra: tuple[str, ...] = ()) -> None:
        self.blocked = self.BLOCKED + blocked_extra
        self.validated: list[str] = []

    def validate(self, url: str) -> str:
        from support_scout.exceptions import UnsafeURLError

        if not url.startswith(("http://", "https://")):
            raise UnsafeURLError("Only public HTTP(S) URLs are allowed")
        if any(token in url for token in self.blocked):
            raise UnsafeURLError("Non-public destination is forbidden")
        if "@" in url.split("://", 1)[1].split("/", 1)[0]:
            raise UnsafeURLError("Embedded credentials are forbidden")
        self.validated.append(url)
        return url

    def allow(self, url: str) -> bool:
        try:
            self.validate(url)
        except Exception:  # noqa: BLE001
            return False
        return True


class FakeSearchAdapter:
    """Returns canned search results and records every query it was given."""

    def __init__(self, results: list[dict[str, str]] | None = None, error: Exception | None = None) -> None:
        self.queries: list[str] = []
        self.error = error
        self.results = results or [
            {
                "title": "Why tracking stops updating",
                "url": "https://help.example.com/tracking-delays",
                "snippet": "Tracking can pause between carrier scans.",
            },
            {
                "title": "What to do about a late delivery",
                "url": "https://help.example.com/late-delivery",
                "snippet": "Steps to take when a parcel is late.",
            },
        ]

    def search(self, query: str) -> list[SearchResult]:
        self.queries.append(query)
        if self.error:
            raise self.error
        return [
            SearchResult(title=item["title"], url=item["url"], snippet=item["snippet"], rank=index)
            for index, item in enumerate(self.results, start=1)
        ]


class FakeScraper:
    """Returns canned page content keyed by URL.

    The default content deliberately spans all three support domains. Research now
    screens each page for topical relevance, so a tracking-only fixture would be
    rejected for returns and checkout tickets and every integration test would
    escalate on insufficient evidence. A generic help-centre page keeps the fake out
    of the way; tests that exercise relevance supply explicit `pages`.
    """

    DEFAULT_CONTENT = (
        "Tracking updates can pause between carrier scans while a parcel is in transit. "
        "Confirm the delivery address shown on your order before reporting a package as "
        "lost. If an item arrives damaged, a return can be requested through the returns "
        "centre and a refund is processed once the warehouse receives it. For checkout or "
        "payment problems, verify the billing address on your account and try the payment "
        "again."
    )

    def __init__(self, pages: dict[str, dict[str, str]] | None = None, error: Exception | None = None) -> None:
        self.pages = pages or {}
        self.error = error
        self.fetched: list[str] = []

    def fetch(self, url: str) -> dict[str, str]:
        self.fetched.append(url)
        if self.error:
            raise self.error
        if url in self.pages:
            return self.pages[url]
        return {
            "title": "Help centre guidance",
            "content": self.DEFAULT_CONTENT,
            "hash": f"hash-{abs(hash(url)) % 10_000_000:07d}",
            "final_url": url,
        }


class FakeDataClient:
    """In-memory stand-in for the operations service."""

    def __init__(self, *, unavailable: bool = False) -> None:
        self.unavailable = unavailable
        self.calls: list[tuple[str, str]] = []
        self.orders = {
            "ORD-1001": {
                "order_id": "ORD-1001",
                "customer_id": "CUS-001",
                "order_status": "shipped",
                "shipping_method": "standard",
                "total": "89.99",
                "currency": "USD",
            }
        }
        self.shipments = {
            "ORD-1001": {
                "shipment_id": "SHP-1001",
                "order_id": "ORD-1001",
                "carrier": "Demo Carrier",
                "tracking_number_masked": "TRK-****1001",
                "shipment_status": "in_transit",
                "last_tracking_event": "Arrived at regional facility",
                "expected_delivery_date": "2026-09-14",
            }
        }
        self.returns = {
            "ORD-2001": {
                "return_id": "RET-2001",
                "order_id": "ORD-2001",
                "return_status": "received",
                "refund_status": "pending_review",
            }
        }
        self.checkout = {
            "CUS-003": {
                "attempt_id": "CHK-3001",
                "customer_id": "CUS-003",
                "result": "failed",
                "error_code": "ADDRESS_VALIDATION_FAILED",
                "safe_error_message": "The billing address could not be validated.",
            }
        }
        self.accounts = {
            "CUS-004": {
                "diagnostic_id": "ACC-4001",
                "customer_id": "CUS-004",
                "account_status": "active",
                "latest_event": "account_recovery_completed",
                "latest_login_result": "failed",
            }
        }

    def _lookup(self, table: dict[str, dict], key: str, kind: str) -> dict:
        self.calls.append((kind, key))
        if self.unavailable:
            from support_scout.exceptions import SupportDataClientError

            raise SupportDataClientError("Operations service request failed")
        if key not in table:
            raise SupportDataNotFound(f"{kind} {key} not found")
        return dict(table[key])

    def get_order(self, order_id: str) -> dict:
        return self._lookup(self.orders, order_id, "order")

    def get_shipment(self, order_id: str) -> dict:
        return self._lookup(self.shipments, order_id, "shipment")

    def get_return(self, order_id: str) -> dict:
        return self._lookup(self.returns, order_id, "return")

    def get_checkout_diagnostic(self, customer_id: str) -> dict:
        return self._lookup(self.checkout, customer_id, "checkout_diagnostic")

    def get_account_diagnostic(self, customer_id: str) -> dict:
        return self._lookup(self.accounts, customer_id, "account_diagnostic")

    def health(self) -> dict:
        if self.unavailable:
            from support_scout.exceptions import SupportDataClientError

            raise SupportDataClientError("unreachable")
        return {"status": "ok", "service": "support-data"}

    def is_healthy(self) -> bool:
        return not self.unavailable


# --------------------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------------------
@pytest.fixture
def registry() -> EvidenceRegistry:
    return EvidenceRegistry()


@pytest.fixture
def url_policy() -> FakeURLPolicy:
    return FakeURLPolicy()


@pytest.fixture
def search_adapter() -> FakeSearchAdapter:
    return FakeSearchAdapter()


@pytest.fixture
def scraper() -> FakeScraper:
    return FakeScraper()


@pytest.fixture
def data_client() -> FakeDataClient:
    return FakeDataClient()


@pytest.fixture
def run_logger(tmp_path):
    from support_scout.logging_config import RunLogger

    return RunLogger("test-run", log_directory=tmp_path / "logs", echo=False)


@pytest.fixture
def ticket() -> SupportTicket:
    return SupportTicket(
        ticket_id="TKT-TEST-001",
        created_at=datetime(2026, 9, 17, 12, 0, tzinfo=timezone.utc),
        customer_message="My delivery is late and the tracking has not updated in days.",
        order_reference="ORD-1001",
    )


def make_ticket(message: str, **overrides: Any) -> SupportTicket:
    """Build a ticket with a custom message for a specific scenario."""
    payload = {
        "ticket_id": "TKT-TEST-001",
        "created_at": datetime(2026, 9, 17, 12, 0, tzinfo=timezone.utc),
        "customer_message": message,
    }
    payload.update(overrides)
    return SupportTicket.model_validate(payload)


@pytest.fixture
def orchestrator_builder(tmp_path, data_client, search_adapter, scraper, url_policy):
    """Build a fully wired orchestrator whose externals are all fakes."""
    from support_scout.config import Settings
    from support_scout.workflow.assembly import build_orchestrator

    def build(model, *, auto_approve: bool = False, max_revisions: int = 1, **overrides):
        settings = Settings(
            tavily_api_key="test",
            udacity_api_key="test",
            udacity_model_name="test-model",
            udacity_base_url="https://example.test/v1",
            max_agent_revisions=max_revisions,
            output_directory=tmp_path / "output",
            log_directory=tmp_path / "logs",
        )
        return build_orchestrator(
            settings,
            model=model,
            search_adapter=overrides.get("search_adapter", search_adapter),
            scraper=overrides.get("scraper", scraper),
            url_policy=overrides.get("url_policy", url_policy),
            data_client=overrides.get("data_client", data_client),
            agent_factory=ScriptedAgent,
            auto_approve=auto_approve,
            interactive=False,
            echo_insights=False,
        )

    return build


__all__ = [
    "FakeDataClient",
    "FakeScraper",
    "FakeSearchAdapter",
    "FakeURLPolicy",
    "ScrapeError",
    "ScriptContext",
    "ScriptedAgent",
    "ScriptedModel",
    "make_ticket",
]
