# Phase 32: Interactive Chat Frontend

## Objective

Provide a lightweight conversational interface that submits messages into the existing SupportScout workflow.

The frontend improves usability without changing any core workflow logic.

---

## Scope

### In Scope

- Interactive CLI
- User message input
- Ticket generation
- Workflow execution
- Result presentation

### Out of Scope

- Conversation memory
- Multi-turn support sessions
- User authentication
- Web UI

---

## Deliverables

### New File

- src/support_scout/chat.py

### Features

- Interactive shell
- Exit commands
- Automatic ticket generation
- Workflow execution
- Result display

---

## Success Criteria

- User can type a support request
- SupportScout processes request
- Output displayed
- Existing workflow reused unchanged