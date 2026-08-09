## Context

Duplicate findings create review fatigue and hide high-impact risk in noise
(`docs/product/design-principles.md` section 9), and `duplicate_finding_rate` is a tracked metric
(`docs/architecture/data-model.md` section 28). `docs/architecture/agent-design.md` section 11 sets
the governing constraint for the comparable problem in threat validation: semantic duplicate
detection may use embeddings or a model-assisted comparison, but the merge decision itself must
remain explicit and traceable. This issue implements deduplication for findings under that rule.

## Scope

- Deterministic duplicate detection over provisional findings, using structural features first:
  shared threat identifiers, shared requirement identifiers, shared affected components and assets,
  and shared control mappings.
- A merge operation that selects a surviving canonical finding, sets `duplicate_of_id` on the
  others, and unions the evidence, threat, requirement and mapping references onto the survivor
  without losing any.
- A persisted merge record naming the surviving identifier, the merged identifiers, the features
  that matched, and whether the decision was structural or model-assisted.
- Merged findings are retained rather than deleted, so a reviewer can see why a finding disappeared
  (design-principles.md section 16).
- If a model-assisted semantic comparison is used at all, it is confined to proposing candidate
  pairs. It does not perform the merge, its proposals are recorded as proposals, and the code path
  is exercised in tests with a stub. Any test reaching a live provider carries the `integration`
  marker.
- Deduplication never merges a `Finding` with a `DocumentationGap`. They are different conclusions
  about different things, and merging them across the boundary would reintroduce the DEC-009 failure
  through the side door.

## Acceptance criteria

- [ ] Two candidates sharing a threat and a requirement are merged, and the surviving finding carries
      the union of both evidence sets.
- [ ] Two candidates sharing only an affected component are not merged.
- [ ] Every merge writes a record naming the survivor, the merged identifiers, the matching features,
      and whether the decision was structural or model-assisted.
- [ ] Merged findings remain retrievable and carry `duplicate_of_id` pointing at the survivor.
- [ ] A `Finding` and a `DocumentationGap` are never merged into one object; a test asserts this.
- [ ] Merge results are identical across two runs over identical input.
- [ ] With a single provisional finding, or with none, the node completes and changes nothing.
- [ ] `uv run pytest` passes with no provider credential configured; any model-assisted comparison is
      exercised with a stub and its live path is marked `integration`.
- [ ] `uv run mypy` passes in strict mode.

## Out of scope

- Reviewer-initiated merges at the approval checkpoint, which reuse this operation but are triggered
  by a `ReviewerDecision`.
- Duplicate threat detection, owned by the Threat component.
- Embedding infrastructure or a vector store. `docs/architecture/current-architecture.md`
  section 17 defers vector database infrastructure.

## References

- `docs/architecture/agent-design.md` — section 11 ("Important constraint"), section 16, section 38
  question 7
- `docs/architecture/data-model.md` — section 21 (`duplicate_of_id`), section 28, section 39
  question 8
- `docs/architecture/current-architecture.md` — section 5.11, section 17, section 19 question 9
- `docs/product/design-principles.md` — section 9, section 16
