# Phase 31 Requirements

## Mission

SupportScout shall execute the complete workflow against live external services while preserving deterministic validation and escalation behavior.

---

## Functional Requirements

### FR-31.1

The system shall connect to a live LLM.

Acceptance Criteria:

- Uses Udacity OpenAI-compatible endpoint
- Uses GPT-4o-mini
- Returns structured JSON responses

---

### FR-31.2

The system shall perform live web research.

Acceptance Criteria:

- Tavily query executes successfully
- Relevant results are returned

---

### FR-31.3

The system shall scrape public web pages.

Acceptance Criteria:

- URLs pass policy validation
- HTML content is retrieved
- Content is normalized

---

### FR-31.4

The system shall generate evidence.

Acceptance Criteria:

- Evidence IDs assigned
- Duplicate sources removed
- Evidence stored in workflow state

---

### FR-31.5

The system shall generate a support response.

Acceptance Criteria:

- Output conforms to SupportDraft
- Uses supplied evidence
- Avoids restricted claims

---

### FR-31.6

The system shall generate a troubleshooting article.

Acceptance Criteria:

- Output conforms to TroubleshootingArticle
- Uses evidence identifiers
- Excludes customer-specific data

---

### FR-31.7

The system shall generate output artifacts.

Acceptance Criteria:

- interaction_summary.json
- customer_response.md
- troubleshooting_article.md
- sources.json
- audit_log.json

---

## Non-Functional Requirements

### NFR-31.1

Live execution shall complete without system crashes.

### NFR-31.2

System shall fail safely when providers return invalid data.

### NFR-31.3

System shall not expose credentials in logs or outputs.

### NFR-31.4

System shall preserve deterministic escalation behavior.

### NFR-31.5

Safety controls shall function identically between mocked and live executions.