"""Documentation tools: public evidence selection, privacy screening, submission.

The privacy rule for reusable articles is stricter than for a customer response: no
customer-specific identifier may appear anywhere in the article, and only EV- public
evidence may be cited. That rule is enforced deterministically by
`ArticlePrivacyValidator` rather than by prompt instruction alone.

Structured arguments are declared `Any` and normalised by `json_args`, because a model
sends a native JSON array or object as often as a JSON string. The article's nested
list fields are normalised too, for the same reason `submit_support_draft` does it: a
live run showed the model sending a valid top-level object whose list fields were bare
strings, wasting a round-trip per attempt. The documentation agent had not yet been
reached on those tickets, so this is a pre-emptive fix for the identical shape.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from smolagents import tool

from ..evidence_registry import EvidenceRegistry
from ..schemas import TroubleshootingArticle
from ..services.content_validation import ArticlePrivacyValidator
from .json_args import (
    ToolArgumentError,
    coerce_json_object,
    coerce_json_string_list,
    normalize_list_fields,
)

#: TroubleshootingArticle fields the schema requires as lists.
ARTICLE_LIST_FIELDS: tuple[str, ...] = ("source_evidence_ids", "limitations")


@dataclass
class DocumentationWorkspace:
    """Mutable state shared by the documentation tools during a single agent run."""

    selected_evidence_ids: list[str] = field(default_factory=list)
    article: TroubleshootingArticle | None = None
    privacy_checked: bool = False
    submitted: bool = False

    def reset(self) -> None:
        self.selected_evidence_ids.clear()
        self.article = None
        self.privacy_checked = False
        self.submitted = False


def build_documentation_tools(
    workspace: DocumentationWorkspace,
    *,
    registry: EvidenceRegistry,
    validator: ArticlePrivacyValidator | None = None,
) -> list[Any]:
    """Create the documentation tool set bound to one run's workspace."""
    validator = validator or ArticlePrivacyValidator()

    @tool
    def list_public_evidence(reason: str) -> str:
        """List the EV- public evidence available for a reusable article.

        Operational OP- evidence is deliberately excluded: it is customer-specific and
        must never appear in reusable documentation.

        Args:
            reason: A short note on why the evidence list is needed.
        """
        del reason
        return json.dumps(
            {
                "public_evidence": [
                    {
                        "evidence_id": item.evidence_id,
                        "title": item.title,
                        "excerpt": item.content[:600],
                    }
                    for item in registry.public_evidence
                ]
            }
        )

    @tool
    def select_public_evidence(evidence_ids_json: Any) -> str:
        """Choose which EV- public evidence identifiers the article will cite.

        Accepts a JSON array of strings, for example ["EV-001", "EV-002"].

        Args:
            evidence_ids_json: A JSON array of EV- prefixed evidence identifiers.
        """
        try:
            ids = coerce_json_string_list(evidence_ids_json, field="evidence_ids_json")
        except ToolArgumentError as exc:
            return json.dumps({"status": "rejected", "reason": str(exc)})

        non_public = [item for item in ids if not item.startswith("EV-")]
        if non_public:
            return json.dumps(
                {
                    "status": "rejected",
                    "reason": f"Reusable documentation may cite only EV- evidence. Rejected: {non_public}",
                }
            )

        unknown = sorted(set(ids) - registry.public_ids())
        if unknown:
            return json.dumps(
                {
                    "status": "rejected",
                    "reason": f"Unknown public evidence identifiers: {unknown}",
                    "available": sorted(registry.public_ids()),
                }
            )

        workspace.selected_evidence_ids = list(dict.fromkeys(ids))
        return json.dumps(
            {"status": "selected", "selected_evidence_ids": workspace.selected_evidence_ids}
        )

    @tool
    def check_article_privacy(article_json: Any) -> str:
        """Screen a candidate article for customer-specific data before submission.

        Rejects ticket, order, customer, shipment, return, checkout, account and
        operational identifiers anywhere in the article, including the body text.

        source_evidence_ids and limitations are lists. A single bare string is accepted
        for either and wrapped automatically.

        Args:
            article_json: The TroubleshootingArticle as a JSON object.
        """
        try:
            payload = coerce_json_object(article_json, field="article_json")
        except ToolArgumentError as exc:
            return json.dumps({"status": "rejected", "reason": str(exc)})

        # Tolerate a bare string where the schema wants a list, rather than spending a
        # retry on a shape the tool can correct itself.
        payload = normalize_list_fields(payload, ARTICLE_LIST_FIELDS)

        try:
            article = TroubleshootingArticle.model_validate(payload)
        except Exception as exc:  # noqa: BLE001 - returned to the agent to correct
            return json.dumps(
                {
                    "status": "rejected",
                    "reason": "The article did not match the required schema.",
                    "detail": str(exc)[:500],
                    "required_keys": ["title", "body_markdown", "source_evidence_ids", "limitations"],
                }
            )

        result = validator.validate(
            article, allowed_evidence_ids=set(workspace.selected_evidence_ids)
        )
        if not result.privacy_safe:
            workspace.privacy_checked = False
            return json.dumps(
                {
                    "status": "rejected",
                    "privacy_safe": False,
                    "issues": result.issues,
                    "matched_identifiers": result.matched_identifiers,
                }
            )

        workspace.article = article
        workspace.privacy_checked = True
        return json.dumps({"status": "ok", "privacy_safe": True})

    @tool
    def submit_article(reason: str) -> str:
        """Submit the reusable article after the privacy check has passed.

        The first submission is final: calling this again returns "already_submitted".

        Args:
            reason: A short note on why the article is ready to publish.
        """
        del reason
        # The first submission wins. A repeat call means the agent has not noticed it
        # is finished; say so plainly instead of silently re-submitting.
        if workspace.submitted and workspace.article is not None:
            return json.dumps(
                {
                    "status": "already_submitted",
                    "reason": (
                        "The article was already submitted for this ticket. Your work "
                        "here is complete; stop calling this tool."
                    ),
                    "title": workspace.article.title,
                }
            )

        if workspace.article is None or not workspace.privacy_checked:
            return json.dumps(
                {
                    "status": "rejected",
                    "reason": "Call check_article_privacy successfully before submitting.",
                }
            )
        workspace.submitted = True
        return json.dumps({"status": "submitted", "title": workspace.article.title})

    return [list_public_evidence, select_public_evidence, check_article_privacy, submit_article]
