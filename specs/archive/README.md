# Archived Specifications

Historical phase bundles, preserved verbatim so the project's decision history stays
inspectable. They are **not** authoritative. The current specification is
`specs/001-agentic-refactor/`.

## Status

| Bundle | Status |
|---|---|
| `phase-1` through `phase-32` | Superseded; requirements carried forward into the current spec |
| `phase-33`, `phase-34` | Operations platform; still reflected in `data_server/` and the support tools |
| `refactor-1` | Migration scaffolding; FR-RB-016, FR-RB-017 and NFR-RB-006 retired per `research.md` R-011 |

## How to restore your originals

This archive ships empty because the refactor deliverable contains only generated
files. To preserve your history, copy your existing bundles across:

```bash
cp -r /path/to/old/support-scout/specs/phase-* specs/archive/
cp -r /path/to/old/support-scout/specs/refactor-1 specs/archive/
```

## Note on phase-34

`specs/phase-34/requirements.md` was lost before the refactor. Its content was
reconstructed from the surviving `plan.md` and `validation.md`. If you restore that
bundle, label the reconstructed file as such rather than presenting it as original.

## Superseded requirements

Recorded in full in `specs/001-agentic-refactor/research.md`:

- **R-011** — FR-RB-016 (three execution modes), FR-RB-017 (shadow comparison) and
  NFR-RB-006 (deterministic path availability) are *satisfied and retired*. They
  described migration scaffolding whose purpose was served once the agentic path passed
  its validation gates.
- **R-011** — `tech_stack.md`'s "custom Python orchestrator rather than a third-party
  agent framework", and its listing of smolagents and FastAPI as not selected. Both
  reversed; the document has been regenerated.
