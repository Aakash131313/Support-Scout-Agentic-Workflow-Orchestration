"""Deterministic evidence identifier minting and deduplication.

The model never chooses an evidence identifier. Tools hand raw material to the
registry, the registry mints the next `EV-NNN` / `OP-NNN`, and returns the stored
record. This keeps provenance verifiable: QA can look an identifier up rather than
pattern-matching its shape.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

from .schemas import OperationalEvidence, ScrapedEvidence


def _now() -> datetime:
    return datetime.now(timezone.utc)


class EvidenceRegistry:
    """Run-scoped registry owning every evidence identifier in a workflow."""

    def __init__(self, *, max_content_characters: int = 20_000) -> None:
        self.max_content_characters = max_content_characters
        self._public: list[ScrapedEvidence] = []
        self._operational: list[OperationalEvidence] = []
        self._public_hashes: set[str] = set()
        self._public_urls: set[str] = set()
        self._operational_keys: set[str] = set()

    # -- public web evidence -----------------------------------------------------
    def register_public(
        self,
        *,
        source_url: str,
        title: str,
        content: str,
        content_hash: str | None = None,
    ) -> ScrapedEvidence | None:
        """Register scraped page content. Returns None when it duplicates prior evidence."""
        bounded = content[: self.max_content_characters]
        digest = content_hash or hashlib.sha256(bounded.encode("utf-8")).hexdigest()
        normalized_url = source_url.rstrip("/").casefold()
        if digest in self._public_hashes or normalized_url in self._public_urls:
            return None
        record = ScrapedEvidence(
            evidence_id=f"EV-{len(self._public) + 1:03d}",
            source_url=source_url,
            title=title or "Untitled source",
            retrieved_at=_now(),
            content=bounded,
            content_hash=digest,
        )
        self._public.append(record)
        self._public_hashes.add(digest)
        self._public_urls.add(normalized_url)
        return record

    # -- operational evidence ----------------------------------------------------
    def register_operational(
        self,
        *,
        record_type: str,
        record_id: str,
        facts: dict[str, Any],
        source_system: str = "support-data-api",
    ) -> OperationalEvidence | None:
        """Register one read-only operational record. Returns None when duplicated."""
        key = f"{record_type}:{record_id}".casefold()
        if key in self._operational_keys:
            return None
        record = OperationalEvidence(
            evidence_id=f"OP-{len(self._operational) + 1:03d}",
            source_system=source_system,
            record_type=record_type,
            record_id=record_id,
            retrieved_at=_now(),
            facts=facts,
        )
        self._operational.append(record)
        self._operational_keys.add(key)
        return record

    # -- lookups -----------------------------------------------------------------
    @property
    def public_evidence(self) -> list[ScrapedEvidence]:
        return list(self._public)

    @property
    def operational_evidence(self) -> list[OperationalEvidence]:
        return list(self._operational)

    @property
    def known_ids(self) -> set[str]:
        return {item.evidence_id for item in self._public} | {
            item.evidence_id for item in self._operational
        }

    def public_ids(self) -> set[str]:
        return {item.evidence_id for item in self._public}

    def operational_ids(self) -> set[str]:
        return {item.evidence_id for item in self._operational}

    def unknown_ids(self, cited: list[str]) -> list[str]:
        """Return cited identifiers that this registry never issued."""
        return sorted(set(cited) - self.known_ids)

    def reset(self) -> None:
        self._public.clear()
        self._operational.clear()
        self._public_hashes.clear()
        self._public_urls.clear()
        self._operational_keys.clear()
