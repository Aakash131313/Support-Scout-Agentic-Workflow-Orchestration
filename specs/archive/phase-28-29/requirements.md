# Phases 28-29 Requirements

## Prompt Files

Each agent prompt shall document role, inputs, expected structured output, evidence rules, authority limits, privacy constraints, untrusted-data handling, escalation conditions, and version/change note. Prompt files shall match the implemented fields and enum values.

## Prompt Decision Log

The log shall include examples of scope clarification, refusing automatic refund authorization, limiting scraping, handling insufficient evidence, choosing a custom orchestrator, separating deterministic and probabilistic controls, and selecting offline mocks. Each entry shall state decision, alternatives, concise rationale, impact, and relevant requirement. It shall not contain private chain-of-thought.

## README

The README shall include mission, business problem, domains, features, architecture, agent/tool roles, repository structure, WSL setup, dependency installation, environment placeholders, verified CLI command, sample JSON, output files, tests, evaluation results, safety/human review, token/request limits, caching, limitations, future extensions, and required artifacts.

## Architecture Documentation

Mermaid source and PNG shall show implemented components, evidence flow, QA revision, escalation, terminal states, and file output. Names shall match source modules. Unsupported/deferred components shall not appear as implemented.

## Results and Claims

Test counts and evaluation metrics shall use actual recorded results. Placeholder results shall remain clearly labeled if not yet run. No production accuracy, scalability, or capability claim may be made without evidence.

## Samples

Committed samples shall be synthetic, reproducible, schema-valid, and representative of happy-path and escalation outcomes. Generated outputs shall be reviewed for secrets and customer-specific data.

## Tradeoffs and Limits

Documentation shall explain custom orchestration, CLI scope, Udacity model abstraction, Tavily use, Requests/BeautifulSoup choice, no real customer integration, human authority, network/model uncertainty, bounded retries, request/token controls, caching constraints, and known unsupported actions.

## Acceptance Criteria

A new reviewer can install, run, test, and inspect the project using the documented files; all commands and paths match the repository; prompts match contracts; diagrams match implementation; and security review finds no secret or real customer data.
