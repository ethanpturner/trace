## Context

The Critical Review agent challenges the draft analysis and returns `Critique` objects carrying a
recommended action of keep, revise, reject, merge or investigate
(`docs/architecture/data-model.md` section 24). Consolidation is where those recommendations take
effect, and `docs/architecture/agent-design.md` section 15 forbids the critic from rewriting objects
without preserving lineage. A finding must remain traceable through the full chain in data-model
section 32 after every critique has been applied.

## Scope

- Apply each `Critique` to its target object during consolidation, according to its
  `recommended_action`, and record which critique caused which change.
- A rejected candidate is retained with the critique identifier as the stated reason, not deleted.
- A revised candidate preserves the pre-revision state, so the difference between the original
  proposal and the post-critique object is visible (design-principles.md section 16).
- Critiques of type `documentation_gap_only` route the candidate through the reclassification
  helpers rather than through an ad hoc path.
- The critic does not approve, and cannot cause a candidate to become approved. Only a reviewer
  decision does that.
- Preserve the full lineage chain of data-model section 32 on every surviving finding: source
  document, evidence reference, context claim, threat, requirement and control mapping, evidence
  assessment, critique, finding. A finding that cannot be walked back through this chain is a
  defect.
- A lineage query surface returning, for any finding, the ordered chain of objects that produced it,
  including the critiques raised against it. This is what the reviewer package and the "why was this
  generated" view later consume.

## Acceptance criteria

- [ ] Every critique-driven change records the originating critique identifier.
- [ ] A candidate rejected on a critique recommendation is retained with the critique as its stated
      reason and is absent from the provisional finding set.
- [ ] A revised candidate preserves its pre-revision state and both are retrievable.
- [ ] A `documentation_gap_only` critique results in a `DocumentationGap`, not in a finding with a
      softened description.
- [ ] No critique path can set a finding's status to `approved`; a test asserts this.
- [ ] For every surviving finding, a lineage walk reaches at least one `EvidenceReference` through
      the chain in data-model section 32, and the test fails if any link is missing.
- [ ] With no critiques present, consolidation output is unchanged and the node completes.
- [ ] `uv run pytest` passes with no provider credential configured.
- [ ] `uv run mypy` passes in strict mode.

## Out of scope

- The Critical Review agent itself.
- Duplicate detection, which handles the `merge` recommendation through its own operation.
- The reviewer-facing presentation of lineage, which the review package assembles.

## References

- `docs/architecture/agent-design.md` — section 15, section 16 ("Responsibilities"), section 18
- `docs/architecture/data-model.md` — section 20, section 21, section 24, section 32
- `docs/architecture/current-architecture.md` — section 5.10, section 5.11
- `docs/product/design-principles.md` — section 8, section 16
