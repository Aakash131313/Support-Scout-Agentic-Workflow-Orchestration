# Phases 15-19 Plan: Research and Evidence Pipeline

## Purpose

Implement the complete bounded research subsystem: Research Agent, Tavily search, URL safety, public-page scraping, and evidence preparation.

## Pipeline

```text
Sanitized ticket + classification
  -> Research Agent/SearchPlan
  -> Tavily/SearchResult[]
  -> URL Policy
  -> Scraper
  -> Evidence Service/ScrapedEvidence[]
  -> sufficient evidence or escalation
```

## Implementation Sequence

1. Implement SearchPlan prompt and validation.
2. Implement Tavily adapter with result normalization and deduplication.
3. Implement URL parsing, DNS/IP safety checks, and redirect revalidation.
4. Implement bounded Requests/BeautifulSoup scraper.
5. Implement text cleanup and content hashing.
6. Implement evidence deduplication, IDs, truncation, and sufficiency checks.
7. Add optional sanitized cache.
8. Add unit, integration, and adversarial tests.

## Research Limits

Use configured limits for query count, results per query, pages per ticket, request timeout, redirects, response bytes, and retained characters. Search queries must omit unnecessary customer identifiers.

## Deliverables

- `agents/research_agent.py` and prompt
- `tools/web_search.py`
- `services/url_policy.py`
- `tools/web_scraper.py`
- `services/evidence_service.py`
- Fixtures, mocks, and tests
- Completed validation

## Exit Criteria

Mocked pipeline produces attributed evidence; unsafe URLs never reach HTTP; scraper limits work; evidence is bounded/deduplicated; insufficient or conflicting evidence escalates; tests remain offline.

## Recommended Commit

`feat: implement bounded research retrieval and evidence pipeline`
