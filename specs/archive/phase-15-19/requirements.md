# Phases 15-19 Requirements

## Research Agent

The agent shall create general domain-relevant queries, desired source types, and result limits. It shall prefer official or authoritative support documentation, avoid customer-specific identifiers, and output `SearchPlan`. Invalid output shall fail safely.

## Tavily Adapter

Initialize from environment configuration; execute bounded requests; normalize title, URL, snippet, and rank; deduplicate normalized URLs; distinguish authentication, timeout, transport, malformed, and valid zero-result responses; never log the key; support injected/mock client.

## URL Safety Policy

Permit only public HTTP(S). Reject malformed URLs, non-HTTP schemes, embedded credentials, localhost names, loopback, private, link-local, multicast, reserved/unspecified destinations, and unsafe redirects. Resolve hostnames before requests where practical and revalidate each redirect target. Tests shall mock resolution.

## Scraper

Use Requests with descriptive user agent, timeout, redirect cap, streaming/size controls, and approved content types. Parse HTML with BeautifulSoup; remove script, style, noscript, navigation, and repeated whitespace; retain final URL, title, retrieval time, relevant text, and hash. Do not bypass authentication, CAPTCHA, robots/security controls, or submit forms.

## Evidence Service

Assign deterministic run-local IDs, remove duplicate URLs/content hashes, bound content, preserve source metadata, and supply only relevant evidence downstream. Mark evidence insufficient when no usable source remains or content cannot support the scoped issue. Mark potential conflict when retained sources provide materially incompatible guidance; final conflict judgment may be reviewed later by QA/human.

## Caching

Caching is optional. If implemented, keys shall use normalized URL/query plus safe version metadata. Cached content shall be sanitized, bounded, expirable, and ignored by Git. No credentials or customer message shall be cached.

## Failure Behavior

- No search results: insufficient evidence escalation.
- Some pages fail: continue with remaining approved sources.
- All pages fail: insufficient evidence escalation.
- Unsafe URL: skip and audit reason.
- Timeout/oversize/type rejection: skip and audit category.
- Conflicting evidence: retain attribution and escalate.
- Tool failure must not produce invented content.

## Audit Events

Record counts and statuses for planned queries, results, deduplicated URLs, blocked URLs by reason, pages attempted/succeeded, evidence items retained, cache hit/miss, and insufficiency/conflict decision. Never log API keys or full unreviewed page content.

## Testing Requirements

Unit tests for query bounds, normalization, deduplication, error categories, URL classes, redirects, HTML cleanup, size/type/timeout limits, evidence IDs, hashes, truncation, insufficiency, and conflict flags. Integration tests use mocked Tavily and local HTML fixtures. Required adversarial tests cover prompt injection in pages, unsafe destinations, redirect attacks, oversized HTML, malformed responses, and timeouts.

## Acceptance Criteria

A safe mocked ticket produces a validated SearchPlan, normalized search results, only approved retrieval attempts, attributed `ScrapedEvidence`, and sanitized audit events. An unsafe or evidence-poor run ends in escalation without unsupported guidance.
