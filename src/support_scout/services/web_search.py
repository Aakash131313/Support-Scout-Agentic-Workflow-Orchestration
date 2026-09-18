"""Bounded Tavily adapter producing normalized, deduplicated search results."""
from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit, urlunsplit

from ..exceptions import (
    SearchAuthenticationError,
    SearchError,
    SearchResponseError,
    SearchTimeoutError,
)
from ..schemas import SearchResult


def normalize_url(url: str) -> str:
    """Canonicalise a URL so near-duplicates collapse during deduplication."""
    parts = urlsplit(url.strip())
    return urlunsplit(
        (
            parts.scheme.casefold(),
            parts.netloc.casefold(),
            parts.path.rstrip("/") or "/",
            parts.query,
            "",
        )
    )


class TavilyAdapter:
    """Wraps the Tavily client behind a bounded, provider-neutral contract."""

    def __init__(self, client: Any = None, max_results: int = 5) -> None:
        self.client = client
        self.max_results = max_results

    def normalize(self, results: list[dict[str, Any]]) -> list[SearchResult]:
        """Validate, deduplicate and rank raw provider results."""
        seen: set[str] = set()
        normalized: list[SearchResult] = []

        for raw in results[: self.max_results]:
            try:
                url = normalize_url(raw["url"])
                title = raw["title"]
            except (KeyError, TypeError, AttributeError) as exc:
                raise SearchResponseError("Malformed search response") from exc

            if url in seen:
                continue
            seen.add(url)

            normalized.append(
                SearchResult(
                    title=title,
                    url=url,
                    snippet=raw.get("content", raw.get("snippet", "")),
                    rank=len(normalized) + 1,
                )
            )

        return normalized

    def search(self, query: str) -> list[SearchResult]:
        """Execute one bounded search. Never leaks the API key into an error."""
        if self.client is None:
            raise SearchError("Search client is not configured")

        try:
            response = self.client.search(query=query, max_results=self.max_results)
        except TimeoutError as exc:
            raise SearchTimeoutError("Search timed out") from exc
        except PermissionError as exc:
            raise SearchAuthenticationError("Search authentication failed") from exc
        except Exception as exc:  # noqa: BLE001 - provider errors are sanitized here
            raise SearchError("Search transport failed") from exc

        if not isinstance(response, dict) or not isinstance(response.get("results"), list):
            raise SearchResponseError("Malformed search response")

        return self.normalize(response["results"])
