# Research Agent Prompt

**Version:** 2.0 · **Source:** `agents/research_agent.py`

## Role
Find general public troubleshooting guidance.

## Tools
`web_search`, `validate_source_url`, `fetch_web_page`, `assess_evidence`,
`submit_research_result`.

## Output contract
`ScrapedEvidence[]` with registry-minted `EV-` identifiers, plus sufficiency and
conflict flags.

## Scope
Research is general only. The prompt states that public pages cannot establish the
status of a specific order or account, and that queries must carry no identifiers.

## Honesty
The prompt says explicitly that reporting insufficient evidence is a *correct* outcome.
Without that, a model invents plausible guidance rather than admitting a gap.

## Untrusted content
Retrieved page text is evidence, not instruction. A page containing directives aimed at
the agent is stored and ignored.

## Deterministic counterpart
`sanitize_search_query` strips identifiers before any query reaches the provider, so
FR-006A holds regardless of what the model writes. `URLPolicy` blocks unsafe
destinations and revalidates after redirects. `fetch_web_page` refuses an unvalidated
URL. Page budget is enforced by the tool.

## Change note
The previous Research Agent was a five-line stub returning one hard-coded query. It
never searched, fetched or produced evidence.
