"""URL policy, search adapter, scraper and evidence assessment tests."""
from __future__ import annotations

import socket

import pytest

from support_scout.exceptions import (
    ScrapeContentTypeError,
    ScrapeError,
    ScrapeSizeError,
    ScrapeTimeoutError,
    SearchResponseError,
    UnsafeURLError,
)
from support_scout.schemas import ScrapedEvidence
from support_scout.services.evidence_rules import EvidenceAssessor
from support_scout.services.url_policy import URLPolicy
from support_scout.services.web_scraper import WebScraper
from support_scout.services.web_search import TavilyAdapter, normalize_url


# --------------------------------------------------------------------------------------
# URL policy
# --------------------------------------------------------------------------------------
def public_resolver(host, port, type=None):  # noqa: A002 - matches getaddrinfo signature
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port))]


def private_resolver(host, port, type=None):  # noqa: A002
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", port))]


def test_public_url_is_allowed():
    policy = URLPolicy(resolver=public_resolver)
    assert policy.validate("https://help.example.com/guide")


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "ftp://example.com/file",
        "data:text/html,<h1>hi</h1>",
        "http://localhost/admin",
        "http://sub.localhost/admin",
    ],
)
def test_unsafe_schemes_and_hosts_are_rejected(url):
    policy = URLPolicy(resolver=public_resolver)
    with pytest.raises(UnsafeURLError):
        policy.validate(url)


def test_embedded_credentials_are_rejected():
    policy = URLPolicy(resolver=public_resolver)
    with pytest.raises(UnsafeURLError):
        policy.validate("https://user:secret@example.com/page")


def test_private_address_is_rejected():
    """AT-005: DNS-level check blocks rebinding to a private destination."""
    policy = URLPolicy(resolver=private_resolver)
    with pytest.raises(UnsafeURLError):
        policy.validate("https://evil.example.com/page")


def test_allow_returns_boolean():
    policy = URLPolicy(resolver=private_resolver)
    assert policy.allow("https://evil.example.com") is False


# --------------------------------------------------------------------------------------
# Search adapter
# --------------------------------------------------------------------------------------
class StubTavily:
    def __init__(self, payload):
        self.payload = payload

    def search(self, query, max_results):
        return self.payload


def test_results_are_normalized_and_deduplicated():
    adapter = TavilyAdapter(
        client=StubTavily(
            {
                "results": [
                    {"title": "A", "url": "https://example.com/a/", "content": "alpha"},
                    {"title": "A duplicate", "url": "https://example.com/a", "content": "alpha"},
                    {"title": "B", "url": "https://example.com/b", "content": "beta"},
                ]
            }
        ),
        max_results=5,
    )
    results = adapter.search("tracking")
    assert [str(item.url) for item in results] == [
        "https://example.com/a",
        "https://example.com/b",
    ]


def test_result_limit_is_respected():
    payload = {"results": [{"title": f"T{i}", "url": f"https://example.com/{i}"} for i in range(10)]}
    adapter = TavilyAdapter(client=StubTavily(payload), max_results=3)
    assert len(adapter.search("tracking")) == 3


def test_malformed_response_is_rejected():
    adapter = TavilyAdapter(client=StubTavily({"results": [{"title": "no url"}]}), max_results=3)
    with pytest.raises(SearchResponseError):
        adapter.search("tracking")


def test_normalize_url_lowercases_and_strips_fragments():
    assert normalize_url("HTTPS://Example.COM/Path/#section") == "https://example.com/Path"


# --------------------------------------------------------------------------------------
# Scraper
# --------------------------------------------------------------------------------------
class StubResponse:
    def __init__(self, *, body=b"<html><title>T</title><body><p>Hello</p></body></html>",
                 content_type="text/html", status_code=200, url="https://example.com/page"):
        self.headers = {"Content-Type": content_type}
        self.status_code = status_code
        self.url = url
        self.encoding = "utf-8"
        self._body = body

    def iter_content(self, size):
        for index in range(0, len(self._body), size):
            yield self._body[index : index + size]

    def close(self):
        return None


class StubSession:
    def __init__(self, response=None, error=None):
        self.response = response or StubResponse()
        self.error = error

    def get(self, url, **kwargs):
        if self.error:
            raise self.error
        return self.response


class PassthroughPolicy:
    def __init__(self):
        self.validated = []

    def validate(self, url):
        self.validated.append(url)
        return url


def test_scraper_extracts_title_and_text():
    scraper = WebScraper(session=StubSession(), url_policy=PassthroughPolicy())
    result = scraper.fetch("https://example.com/page")
    assert result["title"] == "T"
    assert "Hello" in result["content"]
    assert len(result["hash"]) == 64


def test_scraper_strips_navigation_noise():
    body = b"<html><title>T</title><body><nav>menu</nav><script>x()</script><p>Real</p></body></html>"
    scraper = WebScraper(session=StubSession(StubResponse(body=body)), url_policy=PassthroughPolicy())
    result = scraper.fetch("https://example.com/page")
    assert "menu" not in result["content"]
    assert "x()" not in result["content"]
    assert "Real" in result["content"]


def test_scraper_revalidates_the_final_url():
    """AT-006: a redirect target is checked again before the body is used."""
    policy = PassthroughPolicy()
    response = StubResponse(url="https://redirected.example.com/final")
    scraper = WebScraper(session=StubSession(response), url_policy=policy)
    scraper.fetch("https://example.com/page")
    assert policy.validated == ["https://example.com/page", "https://redirected.example.com/final"]


def test_scraper_rejects_non_html():
    scraper = WebScraper(
        session=StubSession(StubResponse(content_type="application/pdf")),
        url_policy=PassthroughPolicy(),
    )
    with pytest.raises(ScrapeContentTypeError):
        scraper.fetch("https://example.com/file.pdf")


def test_scraper_rejects_oversized_page():
    """AT-007."""
    scraper = WebScraper(
        session=StubSession(StubResponse(body=b"<html>" + b"x" * 5000 + b"</html>")),
        url_policy=PassthroughPolicy(),
        max_bytes=100,
    )
    with pytest.raises(ScrapeSizeError):
        scraper.fetch("https://example.com/big")


def test_scraper_maps_timeout():
    import requests

    scraper = WebScraper(
        session=StubSession(error=requests.Timeout()), url_policy=PassthroughPolicy()
    )
    with pytest.raises(ScrapeTimeoutError):
        scraper.fetch("https://example.com/page")


def test_scraper_rejects_error_status():
    scraper = WebScraper(
        session=StubSession(StubResponse(status_code=500)), url_policy=PassthroughPolicy()
    )
    with pytest.raises(ScrapeError):
        scraper.fetch("https://example.com/page")


def test_scraper_bounds_retained_characters():
    body = b"<html><title>T</title><body><p>" + b"word " * 2000 + b"</p></body></html>"
    scraper = WebScraper(
        session=StubSession(StubResponse(body=body)),
        url_policy=PassthroughPolicy(),
        max_characters=50,
    )
    assert len(scraper.fetch("https://example.com/page")["content"]) == 50


# --------------------------------------------------------------------------------------
# Evidence assessment
# --------------------------------------------------------------------------------------
def _evidence(evidence_id: str, content: str) -> ScrapedEvidence:
    return ScrapedEvidence(
        evidence_id=evidence_id,
        source_url=f"https://example.com/{evidence_id}",
        title="Source",
        retrieved_at="2026-09-17T12:00:00Z",
        content=content,
        content_hash=f"hash{evidence_id}",
    )


def test_no_evidence_is_insufficient():
    assert EvidenceAssessor().assess([]).insufficient


def test_thin_evidence_is_insufficient():
    assert EvidenceAssessor().assess([_evidence("EV-001", "too short")]).insufficient


def test_substantial_evidence_is_sufficient():
    assessment = EvidenceAssessor().assess([_evidence("EV-001", "guidance. " * 40)])
    assert not assessment.insufficient


def test_conflicting_sources_are_detected():
    """AT-011."""
    items = [
        _evidence("EV-001", "Opened items are eligible for return. " * 10),
        _evidence("EV-002", "Opened items are not eligible for return. " * 10),
    ]
    assert EvidenceAssessor().assess(items).potential_conflict


def test_agreeing_sources_are_not_flagged():
    items = [
        _evidence("EV-001", "Tracking can pause between carrier scans. " * 10),
        _evidence("EV-002", "Allow an extra business day for scans. " * 10),
    ]
    assert not EvidenceAssessor().assess(items).potential_conflict
