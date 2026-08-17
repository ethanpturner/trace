# Recorded run for the rag-support-bot scenario

Authored offline against the `offline-fake` profile and the deterministic model, shaped
exactly as recordings are consumed (one JSON per model call, the schema named by the #461
envelope, replayed in order). Reviewer decisions reach the workflow through the same writers an
interactive session uses (DEC-017); replay is not an ablation (DEC-012). A live capture
(`trace capture rag-support-bot`, DEC-091) replaces these files file for file. Version pins:
profile offline-fake, workflow 0.1, catalog 0.2 (pinned through the registry's
`catalog_version`, DEC-098), report template report-v1.

## Scope

The AI system threat-modeling pack's scenario (#489, DEC-098): a RAG support assistant whose
documents affirmatively state that one shared retrieval index serves every workspace and that
relevance alone selects the passages that reach the prompt. The recording exercises the 0.2
catalog's retrieval-augmentation requirements:

- **One finding** (req-RAG-002): the documented absence of an entitlement filter is an
  affirmative statement, not silence, so the unmet mapping becomes a finding the reviewer
  approves at high severity.
- **One documentation gap** (req-RAG-003): deletion propagation from the support platform to
  the index is unstated either way. The evidence-validation assessment recommends the gap
  route, consolidation converts the unverified mapping deterministically (DEC-013), and the
  gap's paired question asks for the propagation statement.
- **Two rejections by construction** (req-AI-001, req-RAG-001): prompt fencing and the governed
  corpus write path are documented, the mappings assess as satisfied, and no finding is built —
  the false positives the baselines commit and the pipeline's structure refuses.

| | |
|---|---|
| Authored | 2026-08-17, offline, with the truth set |
| Catalog | core 0.2 (draft; the scenario pins it via the registry) |
| Replayed by | `uv run trace evaluate rag-support-bot` |
