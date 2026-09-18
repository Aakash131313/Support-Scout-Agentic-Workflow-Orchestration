# Traceability Matrix

Requirements mapped to the tests that verify them. Test names encode their scenario
identifier, so this matrix can be checked mechanically:

```bash
grep -rhoE "def test_(at[0-9]+a?|it[0-9]+)_[a-z0-9_]+" tests/ | sort
```

---

## Adversarial matrix (AT-001 to AT-020, AT-016A)

All in `tests/adversarial/test_adversarial_matrix.py` unless noted.

| ID | Scenario | Test |
|---|---|---|
| AT-001 | Malformed JSON input | `test_at001_invalid_json_is_rejected`, `test_at001_missing_file_is_rejected` |
| AT-002 | Missing required fields | `test_at002_missing_required_fields_are_rejected` |
| AT-003 | Prompt injection in ticket text | `test_at003_ticket_injection_is_treated_as_data`, `test_at003_injection_never_reaches_a_specialist` |
| AT-004 | Prompt injection in scraped page | `test_at004_page_injection_is_stored_as_evidence_only` |
| AT-005 | Private / loopback / metadata URL | `test_at005_private_and_local_destinations_are_blocked` |
| AT-006 | Redirect to a private destination | `test_at006_redirect_target_is_revalidated` |
| AT-007 | Oversized page response | `test_at007_oversized_page_is_rejected` |
| AT-008 | Search provider timeout | `test_at008_search_timeout_leaks_no_secret` |
| AT-009 | Scrape timeout | `test_at009_scrape_timeout_allows_the_run_to_continue` |
| AT-010 | Malformed agent output | `test_at010_malformed_submission_is_rejected_with_guidance`, `test_at010_bad_schema_submission_lists_allowed_keys` |
| AT-011 | Conflicting sources | `test_at011_conflicting_sources_escalate` |
| AT-012 | Insufficient evidence | `test_at012_insufficient_evidence_invents_nothing` |
| AT-013 | Refund authorization request | `test_at013_refund_approval_requires_a_human` |
| AT-014 | Secrets in ticket text | `test_at014_secret_bearing_input_terminates_safely`, `test_at014_secrets_never_appear_in_artifacts` |
| AT-015 | Path traversal in ticket id | `test_at015_path_traversal_ticket_id_is_rejected` |
| AT-016 | Unsupported domain | `test_at016_unsupported_request_escalates` |
| AT-016A | Below-threshold confidence | `test_at016a_low_confidence_escalates_without_forcing_a_domain` |
| AT-017 | Negative sentiment, routine request | `test_at017_angry_routine_request_is_handled_normally` |
| AT-018 | Neutral sentiment, high risk | `test_at018_calm_compromise_report_escalates` |
| AT-019 | QA pressured to approve an unsupported claim | `test_at019_qa_cannot_approve_an_unsupported_claim`, `test_at019_approval_attempt_on_failing_checks_is_refused` |
| AT-020 | Revision limit exceeded | `test_at020_revision_limit_never_yields_completion` |

---

## Integration scenarios (IT-001 to IT-008)

All in `tests/integration/test_workflow.py`.

| ID | Scenario | Tests |
|---|---|---|
| IT-001 | Delayed delivery, full happy path | `test_it001_delayed_delivery_completes`, `test_it001_writes_every_artifact`, `test_it001_all_five_specialists_are_delegated_to`, `test_it001_operational_evidence_is_gathered_and_cited` |
| IT-002 | Return guidance without authorization | `test_it002_return_guidance_grants_no_refund` |
| IT-003 | Checkout troubleshooting | `test_it003_checkout_uses_customer_reference`, `test_it003_response_never_requests_secrets` |
| IT-004 | Refund approval escalation + HITL | `test_it004_refund_request_escalates_and_writes_artifacts`, `test_it004_no_specialist_runs_after_escalation`, `test_it004_human_denial_is_recorded`, `test_it004_human_approval_allows_the_run_to_continue` |
| IT-005 | Insufficient evidence | `test_it005_insufficient_evidence_escalates`, `test_it005_no_answer_is_invented` |
| IT-006 | Bounded QA revision | `test_it006_revision_then_approval_completes`, `test_it006_exceeding_the_revision_limit_escalates` |
| IT-007 | Dependency failure | `test_it007_search_outage_is_controlled`, `test_it007_operations_outage_still_produces_a_response` |
| IT-008 | Escalation reason validity | `test_it008_escalation_reason_is_preserved_in_artifacts`, `test_it008_every_escalation_reason_is_from_the_approved_set` |

---

## Agentic refactor requirements (FR-A01 to FR-A24)

| ID | Requirement | Verified by |
|---|---|---|
| FR-A01 | Specialists are ToolCallingAgents with `@tool` functions | `test_agentic_contract.py::test_every_specialist_registers_its_expected_tools` |
| FR-A02 | Orchestrator is itself an agent | `test_agentic_contract.py::test_orchestrator_capabilities_are_delegation_tools` |
| FR-A03 | One delegation tool per specialist | `test_agentic_contract.py::test_each_specialist_has_exactly_one_delegation_tool` |
| FR-A04 | Support agent selects operational tools | `test_it001_operational_evidence_is_gathered_and_cited`, `test_it003_checkout_uses_customer_reference` |
| FR-A05 | Registry mints all identifiers | `test_evidence_registry.py` (8 tests) |
| FR-A06 | Submission rejects unknown identifiers | `test_tools.py::test_draft_citing_fabricated_evidence_is_rejected` |
| FR-A07 | Mandatory escalation stops the workflow | `test_kernel.py::test_mandatory_escalation_stops_triage_from_advancing`, `test_it004_no_specialist_runs_after_escalation` |
| FR-A08 | Escalated runs finalize and write artifacts | `test_kernel.py::test_escalated_run_can_finalize`, `test_platform.py::test_escalated_run_still_writes_every_artifact` |
| FR-A09 | QA escalation preserves the specific reason | `test_kernel.py::test_qa_escalation_preserves_specific_reason`, `test_tools.py::test_qa_escalation_reason_is_specific` |
| FR-A10 | QA cannot approve while a check fails | `test_tools.py::test_qa_cannot_approve_while_a_check_fails` |
| FR-A11 | QA cannot submit before running checks | `test_tools.py::test_qa_cannot_submit_before_running_checks` |
| FR-A12 | Bounded revision loop | `test_kernel.py::test_support_may_redraft_from_revision_state`, `test_it006_*` |
| FR-A13 | Missing records return structured misses | `test_tools.py::test_missing_order_returns_structured_miss` |
| FR-A14 | Identifiers stripped from search queries | `test_safety_rules.py::test_identifiers_are_stripped_from_search_queries`, `test_tools.py::test_search_query_identifiers_never_reach_the_provider` |
| FR-A15 | Article privacy across all identifier families | `test_content_validation.py::test_article_body_identifiers_are_rejected` (8 params) |
| FR-A16 | Exactly one HITL gate, restricted actions only | `test_platform.py::test_only_restricted_actions_require_approval` (6 params) |
| FR-A17 | Gate invoked by the kernel | `test_kernel.py::test_denied_restricted_action_escalates` |
| FR-A18 | Run-scoped JSONL trace | `test_platform.py::test_trace_is_written_as_jsonl`, `test_workflow.py::test_run_trace_records_tool_calls_from_multiple_agents` |
| FR-A19 | Append-only error audit | `test_platform.py::test_errors_are_appended_to_a_shared_audit`, `test_error_audit_survives_across_runs` |
| FR-A20 | Sentiment is a tool and confers no authority | `test_tools.py::test_sentiment_*`, `test_at017_*`, `test_at018_*` |
| FR-A21 | Execution budgets | `test_kernel.py::test_tool_call_budget_is_enforced` |
| FR-A22 | Execution modes removed | `test_repository_hygiene.py::test_no_execution_mode_remains` |
| FR-A23 | Validated `customer_reference` | `test_platform.py::test_customer_reference_is_validated`, `test_malformed_customer_reference_is_rejected` |
| FR-A24 | Operations service start-up probe | `test_support_data_client.py::test_health_probe_*` |

---

## Safety requirements (Phase 3-4 SR-001 to SR-010)

| ID | Requirement | Verified by |
|---|---|---|
| SR-001 | No refund or financial authorization | `test_safety_rules.py::test_financial_requests_escalate_across_phrasings` (9 params), `test_at013` |
| SR-002 | No policy exceptions | `test_safety_rules.py::test_policy_exception_requests_escalate` (4 params) |
| SR-003 | Account compromise escalates | `test_safety_rules.py::test_account_compromise_escalates` (4 params), `test_at018` |
| SR-004 | Sensitive data never persisted | `test_safety_rules.py::test_sensitive_data_escalates_first` (5 params), `test_at014_secrets_never_appear_in_artifacts` |
| SR-005 | No credential requests to customers | `test_content_validation.py::test_requests_for_secrets_are_detected`, `test_it003_response_never_requests_secrets` |
| SR-006 | Public-only, safe URL access | `test_services.py::test_private_address_is_rejected`, `test_at005`, `test_at006` |
| SR-007 | Conflicting evidence escalates | `test_services.py::test_conflicting_sources_are_detected`, `test_at011` |
| SR-008 | Article privacy | `test_content_validation.py` article suite, `test_workflow.py::test_article_never_contains_customer_identifiers` |
| SR-009 | Injection treated as data | `test_at003`, `test_at004` |
| SR-010 | Safe output paths | `test_platform.py::test_path_traversal_ticket_id_is_rejected`, `test_at015` |

---

## Constitution principles

| Principle | Verified by |
|---|---|
| I. Human authority | `test_platform.py` HITL suite, `test_kernel.py` approval tests, `test_at013`, `test_at019` |
| II. Evidence before confidence | `test_evidence_registry.py`, `test_tools.py` grounding tests, `test_at012` |
| III. Deterministic controls outrank models | `test_kernel.py` transition tests, `test_tools.py::test_qa_cannot_approve_while_a_check_fails` |
| IV. Privacy by construction | `test_content_validation.py` article suite, `test_platform.py` redaction tests |
| V. Honest limitation | `test_it005_no_answer_is_invented`, `test_evaluation_runner.py::test_report_declares_its_limitations` |
| VI. Auditability | `test_platform.py` logging suite, `test_workflow.py::test_run_trace_records_tool_calls_from_multiple_agents` |
| VII. Offline reproducibility | The entire default suite; `pytest` requires no keys or network |

---

## Sample input coverage

`tests/unit/test_sample_inputs.py` asserts that the curated set validates, that ticket
identifiers are unique, that operational references match the seeded data (except the
deliberate `ORD-9999` miss), and that the set covers both completion and escalation
including at least three restricted-action cases.
