# Tool Contracts

Every tool is a `@tool` function. Name, description and argument schema are derived
from the function itself, so this document and the source cannot disagree.

All tools return a JSON string. Validation tools return a structured result rather than
raising, so an agent receives a recoverable observation instead of an error that may
send it into a retry loop.

## Triage — `tools/triage_tools.py`

| Tool | Arguments | Returns |
|---|---|---|
| `analyze_sentiment` | `reason` | label, intensity, rationale, urgency markers |
| `list_supported_domains` | `reason` | the five domains with descriptions |
| `submit_triage` | `domain`, `intent`, `urgency`, `confidence`, `uncertainty_reason` | submitted or rejected |

`submit_triage` refuses until `analyze_sentiment` has run.

## Research — `tools/research_tools.py`

| Tool | Arguments | Returns |
|---|---|---|
| `web_search` | `query` | results, plus whether identifiers were stripped |
| `validate_source_url` | `url` | allowed or blocked with reason |
| `fetch_web_page` | `url` | `EV-` identifier and content preview |
| `assess_evidence` | `reason` | sufficiency and conflict flags |
| `submit_research_result` | `summary` | submitted |

`fetch_web_page` refuses a URL that `validate_source_url` has not allowed.

## Support — `tools/support_tools.py`

| Tool | Arguments | Returns |
|---|---|---|
| `get_order_status` | `order_id` | `available` + `OP-` identifier + facts |
| `get_shipment_status` | `order_id` | as above |
| `get_return_status` | `order_id` | as above; status only, never authorization |
| `get_account_diagnostics` | `customer_id` | as above; no credentials |
| `get_checkout_diagnostics` | `customer_id` | as above; no payment data |
| `list_available_evidence` | `reason` | every citable identifier |
| `submit_support_draft` | `draft_json` | submitted or rejected with the reason |

Missing records return `available: false`. `submit_support_draft` rejects any
identifier the registry did not issue.

## QA — `tools/qa_tools.py`

| Tool | Arguments | Returns |
|---|---|---|
| `check_evidence_grounding` | `reason` | passed + issues |
| `check_restricted_claims` | `reason` | passed + issues |
| `check_sensitive_data` | `reason` | passed + issues |
| `check_operational_claims` | `reason` | passed + issues |
| `request_support_revision` | `instructions_json` | recorded |
| `submit_qa_decision` | `decision`, `issues_json` | submitted or rejected |

`submit_qa_decision` refuses until all four checks have run, and refuses `approve`
while any is failing.

## Documentation — `tools/documentation_tools.py`

| Tool | Arguments | Returns |
|---|---|---|
| `list_public_evidence` | `reason` | EV- evidence only |
| `select_public_evidence` | `evidence_ids_json` | selected or rejected |
| `check_article_privacy` | `article_json` | privacy result + matched identifiers |
| `submit_article` | `reason` | submitted or rejected |

`submit_article` refuses until the privacy check has passed.

## Orchestration — `tools/orchestration_tools.py`

| Tool | Arguments | Returns |
|---|---|---|
| `inspect_workflow_state` | `reason` | authoritative state snapshot |
| `delegate_to_triage` | `reason` | delegated + resulting state |
| `delegate_to_research` | `reason` | as above |
| `delegate_to_support` | `reason` | as above |
| `delegate_to_qa` | `reason` | as above |
| `delegate_to_documentation` | `reason` | as above |
| `finalize_workflow` | `reason` | finalized or the reason it cannot be |

Delegation tools inject workflow context themselves; the orchestrator never copies data
between tools.
