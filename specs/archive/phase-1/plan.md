# Phase 1 Plan: Finalize and Validate the Technology Stack

## Document Status

- **Project:** SupportScout
- **Phase:** Phase 1
- **Status:** Ready for execution
- **Depends on:** `mission.md`, `tech-stack.md`, `roadmap.md`, `README.md`
- **Related documents:** `phase-1-requirements.md`, `phase-1-validation.md`

## 1. Purpose

This phase confirms that the minimum technology stack selected for SupportScout works in the local WSL development environment before application features or agents are implemented.

The phase prevents later implementation from depending on unverified assumptions about Python, the Udacity-provided model endpoint, Tavily, dependency compatibility, environment variables, or secret handling.

## 2. Phase Objective

Establish a small, reproducible, and secure project foundation that can:

1. Run with Python 3.11 or later in WSL.
2. Load configuration from environment variables.
3. Connect to Tavily using the developer's existing key.
4. Connect to the Udacity-provided model using the already verified request pattern.
5. Import the selected runtime and testing dependencies.
6. Keep credentials and generated local artifacts out of version control.
7. Produce documented validation evidence without exposing secrets.

This phase does not implement the customer-support agents, orchestration workflow, scraping pipeline, or production output generation.

## 3. Confirmed Technology Decisions

### Runtime

- Python 3.11 or later
- Ubuntu on WSL2
- Visual Studio Code with WSL integration

### Application Interface

- Command-line interface
- No FastAPI or frontend in the initial version

### Agent Coordination

- Custom Python orchestrator
- No external agent framework in the initial version

### Model Access

- Udacity-provided model endpoint
- Provider-specific code isolated behind a future model-client abstraction
- Request pattern must match the mechanism already verified in the Udacity environment

### Web Search

- Tavily Search API

### HTTP and HTML Processing

- `requests`
- `beautifulsoup4`

### Validation and Testing

- `pydantic`
- `pytest`
- `python-dotenv`

### Storage

- In-memory workflow state during execution
- JSON and Markdown files for validated outputs
- Optional local cache in a later phase

## 4. Scope

### In Scope

- Verify WSL and Python environment
- Create or confirm the virtual environment
- Define minimal dependencies
- Install dependencies
- Create `.env.example`
- Confirm `.env` and local credential files are ignored
- Verify environment-variable loading
- Verify Tavily connectivity with a minimal bounded query
- Verify Udacity model connectivity with a minimal non-sensitive prompt
- Verify dependency imports
- Verify Pytest discovery
- Review tracked files for accidental credentials
- Record validation results

### Out of Scope

- Ticket schemas
- Support-domain classification
- Sentiment analysis
- Agent prompts
- Agent implementations
- Web-page scraping
- URL safety policy
- Evidence preparation
- Customer-response generation
- QA agent
- Troubleshooting article generation
- Orchestration
- Accuracy evaluation
- Live e-commerce integrations

## 5. Required Deliverables

Phase 1 produces or confirms the following files:

```text
support-scout/
├── mission.md
├── tech-stack.md
├── roadmap.md
├── README.md
├── phase-1-plan.md
├── phase-1-requirements.md
├── phase-1-validation.md
├── requirements.txt
├── .env.example
├── .gitignore
└── tests/
    └── test_environment.py
```

Temporary connectivity scripts may be created locally, but they should be removed or placed under a clearly named development-only directory before the phase is completed.

## 6. Implementation Tasks

### Task 1. Verify the Local Runtime

Confirm that the terminal is running inside WSL and that Python 3.11 or later is available.

Suggested checks:

```bash
uname -a
python3 --version
which python3
```

Expected result:

- The environment identifies as Linux under WSL.
- Python reports version 3.11 or later.
- The Python path resolves to the Linux environment rather than a Windows executable.

### Task 2. Create or Confirm the Virtual Environment

From the SupportScout project root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python --version
which python
```

Expected result:

- The virtual environment activates successfully.
- `which python` resolves inside `support-scout/.venv/`.
- The active Python version is 3.11 or later.

### Task 3. Define Minimal Dependencies

Use the following initial `requirements.txt`:

```text
pydantic>=2.0,<3.0
python-dotenv>=1.0,<2.0
tavily-python
requests>=2.31,<3.0
beautifulsoup4>=4.12,<5.0
pytest>=8.0,<9.0
```

Do not add an agent framework, FastAPI, Playwright, a database, or a vector store during this phase.

### Task 4. Install and Verify Dependencies

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m pip check
```

Verify key imports:

```bash
python -c "import pydantic, dotenv, requests, bs4, pytest; from tavily import TavilyClient; print('dependency imports passed')"
```

Expected result:

- Installation completes without unresolved dependency conflicts.
- `pip check` reports no broken requirements.
- All imports succeed.

### Task 5. Configure Secret Handling

Create `.env.example` with placeholders only:

```env
TAVILY_API_KEY=
UDACITY_API_KEY=
UDACITY_MODEL_NAME=
UDACITY_BASE_URL=
REQUEST_TIMEOUT_SECONDS=10
MAX_SEARCH_RESULTS=5
MAX_PAGES_TO_SCRAPE=3
MAX_PAGE_CHARACTERS=20000
MAX_AGENT_REVISIONS=1
OUTPUT_DIRECTORY=output
CACHE_DIRECTORY=.cache
```

Create a local `.env` from the example:

```bash
cp .env.example .env
```

Add real values only to `.env` or to the established Udacity credential file. Never add real values to `.env.example`.

The `.gitignore` must include at least:

```gitignore
.venv/
.env
.env.*
!.env.example
config.env
__pycache__/
.pytest_cache/
.coverage
htmlcov/
.cache/
output/
*.log
```

If the verified Udacity setup uses a differently named credential file, add that exact filename to `.gitignore`.

### Task 6. Verify Configuration Loading

Create a minimal check that loads environment variables without printing their values.

The validation must report only whether required values are present. It must not print, log, serialize, or include the values in screenshots.

Expected result:

- Tavily configuration can be detected.
- Udacity configuration can be detected using the exact variables required by the existing verified request pattern.
- Missing variables produce a clear message.

### Task 7. Verify Tavily Connectivity

Perform one minimal, bounded search query using the existing Tavily key.

Validation constraints:

- Use one query.
- Request only a small number of results.
- Do not print the API key.
- Do not use customer or confidential information.
- Record only success or failure, result count returned by the API, and sanitized titles or domains if needed.

Expected result:

- Tavily authentication succeeds.
- A structured response is returned.
- At least the response shape can be inspected without exposing credentials.

A zero-result search does not by itself prove a connection failure. Authentication, request completion, and response structure must be evaluated separately.

### Task 8. Verify Udacity Model Connectivity

Use the same client or request pattern already proven in the Udacity project. Do not assume that the OpenAI Agents SDK is compatible.

Use a small, non-sensitive prompt with a deterministic expected shape, such as a request to return a short JSON object.

Validation constraints:

- Do not print the API key or authorization header.
- Do not send customer or enterprise information.
- Limit the response size.
- Record the configured model name, if it is non-secret.
- Record whether the response was received and parseable.

Expected result:

- Authentication succeeds.
- A model response is returned.
- The response can be read through the verified request mechanism.
- Any incompatibility is documented before agent implementation begins.

### Task 9. Verify Pytest Discovery

Create `tests/test_environment.py` with tests that do not require live API calls by default.

The tests should verify:

- Required packages can be imported.
- Python meets the minimum version.
- `.env.example` exists.
- Required placeholder names exist in `.env.example`.
- `.gitignore` protects expected secret and generated files.

Run:

```bash
pytest --collect-only
pytest
```

Expected result:

- Pytest discovers the tests.
- Offline environment tests pass.
- Live API checks are not required by the default test command.

### Task 10. Inspect Version-Control Safety

Run:

```bash
git status --short
git ls-files
```

Check that none of the following are tracked:

- `.env`
- `config.env`
- `.venv/`
- API keys or tokens
- Cached search results
- Generated output files
- Logs containing request headers

Optional secret-pattern checks may be used, but automated scanning does not replace manual inspection.

### Task 11. Complete the Validation Record

Update `phase-1-validation.md` with:

- Environment details
- Commands executed
- Pass, fail, or blocked status for every validation item
- Sanitized evidence
- Deviations from the planned stack
- Unresolved risks
- Final go or no-go decision

Do not mark an item as passed unless its evidence has been observed.

## 7. Execution Order

Complete tasks in this order:

1. Verify WSL and Python.
2. Activate the virtual environment.
3. Review `requirements.txt`.
4. Install dependencies.
5. Configure `.gitignore` and `.env.example`.
6. Create the local credential configuration.
7. Verify environment loading.
8. Verify Tavily connectivity.
9. Verify the Udacity model endpoint.
10. Run offline tests.
11. Inspect Git-tracked files.
12. Complete the validation record.

Secret protection must be set up before any real credentials are added.

## 8. Risk Controls

| Risk | Control |
|---|---|
| API key committed accidentally | Ignore local credential files before adding keys and inspect `git ls-files` |
| Udacity endpoint incompatible with an SDK | Reuse only the previously verified request pattern |
| Live tests consume API resources | Keep live checks separate from default Pytest execution |
| Tavily response differs from assumptions | Inspect and normalize only the actual response shape |
| Dependency conflict | Use a virtual environment and run `pip check` |
| Windows and Linux Python paths become mixed | Confirm `which python` points into the WSL virtual environment |
| Secrets appear in output | Never print environment values, request headers, or credentials |
| Scope expands prematurely | Do not implement agents or scraping during Phase 1 |

## 9. Completion Criteria

Phase 1 is complete only when all mandatory requirements in `phase-1-requirements.md` pass and the following evidence exists:

- Python 3.11 or later runs from the WSL virtual environment.
- Dependencies install and import successfully.
- `pip check` reports no broken requirements.
- `.env.example` contains placeholders only.
- `.gitignore` protects local secrets and generated artifacts.
- Tavily authentication and a minimal request succeed.
- The Udacity model endpoint returns a parseable response through the verified request method.
- Default Pytest execution passes without live API calls.
- `git ls-files` contains no secrets or ignored local artifacts.
- `phase-1-validation.md` records observed results and a final decision.

## 10. Phase Exit Decision

### Go

Proceed to Phase 2 when all mandatory checks pass and no unresolved security issue remains.

### Conditional Go

Proceed only with documented limitations when a noncritical optional check fails and the failure does not block the planned implementation.

### No-Go

Do not begin agent or feature implementation if:

- Model access has not been verified.
- Tavily access has not been verified.
- The environment cannot install required packages.
- Credentials are exposed or tracked.
- The active Python environment is ambiguous.


# Phase 1 Plan - UPDATE SNIPPETS

## UPDATE-01: Environment Snapshot (insert after Task 4)

### UPDATE: Environment Snapshot

After dependency validation succeeds, record the resolved package versions.

Suggested command:

```bash
pip freeze > docs/validation/pip-freeze-phase1.txt
```

The snapshot is for reproducibility only and must not contain credentials.

---

## UPDATE-02: .gitignore Template Protection (replace existing ignore guidance section)

```gitignore
.env*
!.env.example
!*.example
```

Example configuration templates SHALL remain eligible for tracking.
