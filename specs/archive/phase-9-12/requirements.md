# Phases 9-12 Requirements

## Foundation Requirements

**FND-001** The project shall use a `src/support_scout` package layout.

**FND-002** `python -m support_scout.main --help` shall run without loading live credentials.

**FND-003** Expected user/configuration errors shall use project-specific exceptions rather than unhandled tracebacks.

**FND-004** Logging shall record component, operation, status, and sanitized error category.

## Configuration Requirements

**CFG-001** Settings shall load from environment variables through one module.

**CFG-002** Required live credentials shall be checked only when the related live operation is invoked.

**CFG-003** Numeric limits shall reject nonpositive or unreasonable values.

**CFG-004** Settings representations shall mask secret fields.

**CFG-005** The initial settings shall include model endpoint/name/key, Tavily key, timeouts, search/page/content/revision limits, output directory, and cache directory.

## Schema Requirements

Implement enums for domain, urgency, sentiment, QA decision, workflow status, and escalation reason. Implement `SupportTicket`, `TicketClassification`, `SentimentAssessment`, `EscalationDecision`, `SearchPlan`, `SearchResult`, `ScrapedEvidence`, `SupportDraft`, `QAResult`, `TroubleshootingArticle`, `InteractionSummary`, `AuditEvent`, and `WorkflowState`.

Validation shall include safe ticket IDs, bounded text, confidence from 0 to 1, public HTTP(S) URL shape where applicable, nonempty evidence references, and valid terminal states.

## File Writer Requirements

**IO-001** Output shall be written beneath the configured output root only.

**IO-002** Ticket IDs shall be validated or sanitized before path construction.

**IO-003** The writer shall create `interaction_summary.json`, `customer_response.md`, `troubleshooting_article.md`, `sources.json`, and `audit_log.json`.

**IO-004** JSON shall use stable indentation and UTF-8.

**IO-005** Writes should use temporary files followed by replacement where practical.

**IO-006** Existing unrelated files shall not be deleted.

**IO-007** Serialization errors shall produce sanitized project exceptions.

## Model Client Interface

```python
class ModelClient(Protocol):
    def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_model: type[BaseModel],
    ) -> BaseModel: ...
```

The Udacity adapter shall isolate transport-specific request and response details. It shall enforce request timeout, bounded retries for retryable transport errors, response-length limits where supported, JSON extraction, Pydantic validation, and sanitized error mapping.

## Failure Rules

- Missing configuration: `ConfigurationError`
- Invalid input/model object: `ValidationError` or project wrapper
- Model authentication/transport/timeout: sanitized `ModelClientError` subtype
- Invalid model JSON after retry: `ModelResponseError`
- Unsafe output path or write failure: `FileOutputError`
- Secrets and request headers must not be included in exception text.

## Unit Test Requirements

Tests shall cover valid/invalid settings, secret masking, all schema examples, invalid enums and bounds, path traversal, deterministic JSON formatting, Markdown encoding, mocked valid model response, malformed JSON, timeout, transport error, and exhausted retry. Tests shall use temporary directories and no live API.

## Acceptance Matrix

| Area | Acceptance |
|---|---|
| Package | Imports and CLI help succeed |
| Config | Defaults validate; secrets masked |
| Schemas | Approved examples pass; adversarial examples fail |
| Output | Required files written below output root |
| Security | Traversal and secret leakage tests pass |
| Model client | Mocked structured response validates |
| Tests | Default `pytest` remains offline |
