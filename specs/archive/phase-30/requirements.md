# Phase 30 Requirements

## Repository Integrity

The repository shall contain:

- README.md
- requirements.txt
- .env.example
- docs/
- specs/
- src/
- tests/
- diagrams/
- prompt documentation
- evaluation artifacts

Missing required artifacts block completion.

## Documentation Consistency

README, roadmap, mission, technology stack, architecture documentation, prompt documentation, evaluation artifacts, repository paths, commands, output filenames, and validation records shall match the implemented project.

Documentation shall not describe unimplemented functionality as available.

## Test Verification

The repository shall successfully execute:

```bash
pytest
```

Recorded results shall reflect actual execution results.

## Evaluation Verification

The repository shall successfully execute:

```bash
PYTHONPATH=src python -m evaluation.evaluation_runner
```

Recorded metrics shall originate directly from generated results.

Required metrics:

- Domain accuracy
- Escalation accuracy
- Escalation reason accuracy
- Grounding compliance
- QA protection rate
- Evidence relevance

## Prompt Review

Each implemented agent shall have prompt documentation containing:

- Role
- Inputs
- Outputs
- Evidence rules
- Authority limits
- Privacy rules
- Escalation conditions

Prompt documentation shall not contain hidden chain-of-thought.

## Architecture Review

Architecture artifacts shall:

- Match implemented modules
- Match workflow behavior
- Show escalation path
- Show QA revision path
- Show terminal states
- Show output generation

## Security Review

Tracked files shall not contain:

- API keys
- Credentials
- Tokens
- Real customer data
- Payment information
- Generated secrets
- Hidden reasoning

Environment files with secrets shall not be committed.

## Sample Review

Committed samples shall:

- Be synthetic
- Be schema-valid
- Be reproducible
- Contain no personal information

## Acceptance Criteria

A reviewer can:

1. Install the project.
2. Execute documented commands.
3. Run tests.
4. Run the evaluation framework.
5. Review prompts.
6. Review architecture.
7. Review limitations and tradeoffs.

No unresolved validation issues remain.