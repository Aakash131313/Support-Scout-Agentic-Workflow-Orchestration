"""Bounded HTML retrieval with redirect revalidation.

Limits enforced: timeout, response size, content type, and retained characters.
The final URL is revalidated after redirects so a safe URL cannot redirect into a
private destination.
"""
from __future__ import annotations

import hashlib
from typing import Any

import requests
from bs4 import BeautifulSoup

from ..exceptions import (
    ScrapeContentTypeError,
    ScrapeError,
    ScrapeSizeError,
    ScrapeTimeoutError,
)

_ALLOWED_CONTENT_TYPES = frozenset({"text/html", "application/xhtml+xml"})
_NOISE_TAGS = ("script", "style", "noscript", "nav", "header", "footer", "aside", "form")


class WebScraper:
    """Retrieves and cleans a single public HTML page within strict bounds."""

    def __init__(
        self,
        session: Any,
        url_policy: Any,
        timeout: int = 10,
        max_bytes: int = 1_000_000,
        max_characters: int = 20_000,
    ) -> None:
        self.session = session
        self.url_policy = url_policy
        self.timeout = timeout
        self.max_bytes = max_bytes
        self.max_characters = max_characters

    def fetch(self, url: str) -> dict[str, str]:
        """Retrieve one page and return its cleaned text plus provenance metadata."""
        self.url_policy.validate(url)

        try:
            response = self.session.get(
                url,
                timeout=self.timeout,
                allow_redirects=True,
                stream=True,
                headers={"User-Agent": "SupportScout/1.0"},
            )
        except (requests.Timeout, TimeoutError) as exc:
            raise ScrapeTimeoutError("Page request timed out") from exc
        except requests.RequestException as exc:
            raise ScrapeError("Page request failed") from exc

        # Revalidate after redirects: the destination may have changed.
        self.url_policy.validate(response.url)

        status_code = getattr(response, "status_code", 200)
        if status_code >= 400:
            raise ScrapeError(f"Page request returned HTTP {status_code}")

        content_type = response.headers.get("Content-Type", "").split(";")[0].strip().casefold()
        if content_type not in _ALLOWED_CONTENT_TYPES:
            raise ScrapeContentTypeError("Unsupported content type")

        data = bytearray()
        try:
            for chunk in response.iter_content(8192):
                if not chunk:
                    continue
                data.extend(chunk)
                if len(data) > self.max_bytes:
                    raise ScrapeSizeError("Page exceeds size limit")
        except requests.RequestException as exc:
            raise ScrapeError("Page response streaming failed") from exc
        finally:
            close = getattr(response, "close", None)
            if callable(close):
                close()

        decoded = data.decode(getattr(response, "encoding", None) or "utf-8", errors="replace")
        return self.clean_html(decoded, response.url)

    def clean_html(self, html: str, final_url: str = "") -> dict[str, str]:
        """Strip navigation noise and return bounded text with a stable content hash."""
        soup = BeautifulSoup(html, "html.parser")

        title = " ".join(soup.title.get_text(" ", strip=True).split()) if soup.title else ""

        for tag in soup(_NOISE_TAGS):
            tag.decompose()

        content = " ".join(soup.get_text(" ", strip=True).split())[: self.max_characters]

        return {
            "title": title,
            "content": content,
            "hash": hashlib.sha256(content.encode("utf-8")).hexdigest(),
            "final_url": final_url,
        }
