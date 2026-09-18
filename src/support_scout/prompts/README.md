# Prompt Documentation

The authoritative prompt for each agent is the `INSTRUCTIONS` constant in that agent's
module. These documents record the contract, the boundaries and the reasoning behind
each prompt, so a reviewer can check intent against implementation.

| Agent | Prompt source | Document |
|---|---|---|
| Orchestrator | `agents/orchestrator_agent.py` | `orchestrator-agent.md` |
| Triage | `agents/triage_agent.py` | `triage-agent.md` |
| Research | `agents/research_agent.py` | `research-agent.md` |
| Support | `agents/support_agent.py` | `support-agent.md` |
| QA | `agents/qa_agent.py` | `qa-agent.md` |
| Documentation | `agents/documentation_agent.py` | `documentation-agent.md` |

`prompt-decision-log.md` records design decisions, alternatives considered and the
rationale. It contains no hidden chain-of-thought.

## Principle

A prompt asks. A tool enforces. Wherever a rule matters for safety, privacy or
provenance, it is implemented in a tool or validator and the prompt merely explains it.
Every instruction below has a deterministic counterpart in code.
