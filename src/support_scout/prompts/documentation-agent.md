# Documentation Agent Prompt

**Version:** 2.0 · **Source:** `agents/documentation_agent.py`

## Role
Turn a resolved case into an article that helps the next person with the same problem.

## Tools
`list_public_evidence`, `select_public_evidence`, `check_article_privacy`,
`submit_article`.

## Output contract
`TroubleshootingArticle` with title, body, `EV-` citations and preserved limitations.

## Privacy
The hard constraint. No ticket, order, customer, shipment, return, checkout or account
identifier; no email; no tracking number; no case-specific date. `OP-` evidence may not
appear in citations or prose.

The prompt includes a self-check heuristic: if you are writing "this customer" or "their
order", you have drifted from documentation into case notes. That gives the model a
concrete signal rather than an abstract rule.

## Reusability
Title as someone would search for it; explain why it happens, then give numbered steps.
Preserve the draft's limitations rather than quietly dropping them.

## Deterministic counterpart
`ArticlePrivacyValidator` checks all eight identifier families across title, body,
citations and limitations, and names exactly which identifier it found so the agent can
fix it. `select_public_evidence` rejects `OP-` identifiers outright. `submit_article`
refuses until the privacy check passes.

## Change note
The previous body-text privacy check was effectively inert: it only populated its
forbidden list when `draft.issue_summary` started with `TKT-`, which never happened. An
order or customer identifier in article prose was caught by nothing but the prompt.
