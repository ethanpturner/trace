## Context

`docs/architecture/agent-design.md` section 11 defines a deterministic node that validates
candidate threats before control mapping. It carries one explicitly unresolved element:
semantic duplicate detection "may use embeddings or a model-assisted comparison, but the
merge decision should remain explicit and traceable." Section 38 question 7 leaves the
method open, and `docs/architecture/current-architecture.md` section 17 defers vector
database infrastructure, so an embedding-based approach has no substrate in the MVP. The
duplicate-detection approach is decided and recorded inside this issue.

## Scope

- Add `src/trace_ai/workflow/nodes/threat_validation.py`. It is deterministic and makes no
  model call.
- Implement each responsibility in section 11: validate threat schemas; confirm referenced
  components and assets exist; reject empty or circular attack paths; detect exact or
  highly similar duplicates; enforce required impact descriptions; confirm categories use
  the vocabulary fixed by the threat-model issue; flag threats resting entirely on
  unsupported assumptions; route invalid output for retry or review.
- Implement duplicate detection using deterministic feature comparison first: normalised
  title, affected component and asset sets, and category overlap. Record the outcome as an
  explicit merge proposal rather than a silent merge, which section 11 requires.
- Record the deduplication choice in `docs/architecture/decision-log.md`, answering
  section 38 question 7 for the MVP and stating the condition under which embeddings or a
  model-assisted comparison would be revisited.
- Route invalid output per section 26 and `docs/architecture/data-model.md` section 33:
  preserve the invalid output for debugging, return validation feedback to the generating
  node, retry within limits, then stop or request human review.
- Surface the human-review triggers listed in section 10: a potentially critical threat
  resting on an uncertain assumption; threats relying on contradictory context; a likely
  missing core component; a materially incomplete architecture.

## Acceptance criteria

- [ ] The node makes no model call and imports no provider SDK.
- [ ] A threat referencing a component or asset identifier absent from the approved
      context is rejected, with the offending identifier named in the message.
- [ ] A circular attack path, meaning a step sequence that revisits a prior state, is
      rejected.
- [ ] A threat whose `impact` is empty or whitespace-only is rejected.
- [ ] Duplicate detection produces a merge proposal carrying both threat identifiers and
      the features that matched. It never mutates or deletes a threat directly.
- [ ] Invalid output is preserved rather than discarded, per
      `docs/architecture/data-model.md` section 33 step 1.
- [ ] A low threat count is never treated as a validation failure. A test asserts that a
      single well-formed threat passes.
- [ ] A decision-log entry records the deduplication approach and marks
      `docs/architecture/agent-design.md` section 38 question 7 resolved for the MVP.
- [ ] `uv run mypy` passes in strict mode.

## Out of scope

- Embedding infrastructure or a vector store, deferred by
  `docs/architecture/current-architecture.md` section 17.
- Merge execution. Section 16 assigns merging to Finding Consolidation, which is M4.
- Threat approval. There is no human checkpoint between threat analysis and mapping;
  DEC-005 fixes the two checkpoints at context and findings.

## References

- `docs/architecture/agent-design.md` section 11 (Threat Validation Node —
  Responsibilities; Important constraint), section 10 (Human-review triggers; Retry
  behavior), section 16 (Finding Consolidation Node — the boundary this node must not
  cross), section 26 (Retry Policy), section 38 question 7
- `docs/architecture/data-model.md` section 16 (Threat), section 33 (Schema Validation)
- `docs/architecture/current-architecture.md` section 17 (Deferred Capabilities — vector
  database infrastructure), section 19 question 9
- `docs/architecture/decision-log.md` DEC-005, DEC-006
