## Context

Finding consolidation converts validated threats, mappings and evidence assessments into a small set
of provisional findings, questions and documentation gaps
(`docs/architecture/agent-design.md` section 16). It is classified as primarily deterministic:
a model may assist semantic comparison, but deterministic rules control object creation and status
transitions. This node is where "quality over finding volume" becomes a structural property rather
than an instruction (`docs/product/design-principles.md` section 9), and where the DX-08 evidence
threshold is first applied.

## Scope

- A deterministic workflow node that consumes validated threats, control mappings, evidence
  assessments and critiques, and emits provisional `Finding`, `Question` and `DocumentationGap`
  objects plus a retained set of rejected candidates.
- Apply the minimum finding criteria of data-model section 21 and the outcome table fixed in DX-08.
- Outcome routing follows agent-design section 16: a `Question` when the answer could materially
  change the assessment, evidence is missing but obtainable, or control status is unknown; a
  `DocumentationGap` when the primary issue is inability to verify architecture or control design
  and no implementation weakness is yet supported; and no output at all when the requirement is not
  applicable, a control is adequately supported, the threat is implausible, or the issue has no
  meaningful impact.
- Contradictory evidence is represented per DX-14 and produces a question rather than a silent
  choice between the conflicting statements.
- Stable, normalised titles that do not change between runs over identical input.
- Preliminary severity per DX-11. Where DX-11 assigns severity to the reviewer, findings leave this
  node with `unassigned`.
- Rejected candidates are persisted with the reason for rejection and are not surfaced as results
  (design-principles.md section 9, agent-design section 18).
- Unresolved cases are routed to human review rather than resolved here.
- No finding quota, floor, ceiling or target count appears anywhere in the implementation.

## Acceptance criteria

- [ ] Given input in which every requirement is satisfied or not applicable, the node emits zero
      findings and completes successfully. A zero-finding assessment is a valid success, not an
      error or an empty-result warning.
- [ ] Given an unverified mapping with no evidence of weakness, the node emits a `DocumentationGap`
      or a `Question` and never a `Finding`.
- [ ] A regression test named for DEC-009 asserts that a candidate whose sole support is the absence
      of documentation cannot leave this node as a `Finding`.
- [ ] Titles are byte-identical across two runs over identical input.
- [ ] Contradictory source statements produce a question and are not resolved in either direction.
- [ ] Rejected candidates are persisted with a stated reason and are absent from the provisional
      finding set.
- [ ] Every emitted object records the node name and node version that produced it.
- [ ] A fixture test over the ForgeFlow scenario asserts that no candidate corresponding to any item
      in `demo/forgeflow/forgeflow-scenario.md` section 22 survives consolidation.
- [ ] A fixture test asserts that the two contradictions in `forgeflow-scenario.md` section 16
      produce questions.
- [ ] No quota, target or minimum finding count exists in the code; a reviewer can confirm this by
      inspection and the acceptance criterion is recorded in the module docstring.
- [ ] `uv run pytest` passes with no provider credential configured.
- [ ] `uv run mypy` passes in strict mode.

## Out of scope

- Duplicate detection and merging, which is a separate issue.
- Applying critique recommendations, which is a separate issue.
- Severity calculation, settled by DX-11.
- Human review.

## References

- `docs/architecture/agent-design.md` — section 4 (classification table), section 15, section 16,
  section 18 ("Workflow rule"), section 26 ("Non-retryable analysis conditions"), section 27
- `docs/architecture/data-model.md` — section 19 ("Important rule"), section 21, section 22,
  section 23, section 31
- `docs/architecture/current-architecture.md` — section 5.9, section 5.11, section 11
  ("Insufficient evidence")
- `docs/architecture/decision-log.md` — DEC-006, DEC-009
- `docs/product/design-principles.md` — section 4, section 7, section 9
- `demo/forgeflow/forgeflow-scenario.md` — section 14, section 16, section 21, section 22
