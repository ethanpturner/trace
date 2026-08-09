## Context

Both the consolidation node and the human reviewer need to move a candidate across the
Finding/DocumentationGap/Question boundary without losing the evidence and lineage that justify it.
`docs/architecture/agent-design.md` section 16 gives the reclassification rules, and
`docs/architecture/data-model.md` section 4.6 gives the reviewer the dispositions
`convert_to_question` and `convert_to_documentation_gap`. Lineage must survive the conversion, since
`docs/product/design-principles.md` section 16 requires that a reviewer can explain why a finding
changed or disappeared.

## Scope

- Conversion helpers between the three outcome objects: `Finding` to `DocumentationGap`, `Finding`
  to `Question`, and `DocumentationGap` to `Finding` where later evidence supports it.
- Each conversion preserves `evidence_ids`, the originating threat, requirement and control-mapping
  identifiers, the assumptions and limitations recorded on the source object, and a reference back
  to the object it was converted from.
- Conversion never fabricates a required field. Where the target object requires something the
  source does not carry — for example `DocumentationGap.importance` or `Question.rationale` — the
  caller supplies it and the helper refuses to invent one.
- Converting to a `Finding` runs the full minimum-criteria check and the DX-08 outcome table. A
  conversion is not an escape hatch around the DEC-009 invariant.
- The superseded object is retained rather than deleted, consistent with data-model section 2.6 and
  section 2.5.
- A single query surface that, given any of the three objects, returns the chain of objects it was
  converted from.

## Acceptance criteria

- [ ] Converting a `Finding` to a `DocumentationGap` preserves `evidence_ids` and every originating
      object identifier, and records the source finding identifier on the result.
- [ ] Converting a `Finding` to a `Question` preserves the evidence and records why the answer
      matters, supplied by the caller rather than generated.
- [ ] Converting a `DocumentationGap` to a `Finding` fails when the resulting finding would not
      satisfy the minimum criteria, with an error naming the unmet criterion.
- [ ] The source object is retained after conversion and remains retrievable.
- [ ] Given a converted object, the conversion chain back to the original candidate is queryable.
- [ ] A conversion helper never populates a required target field with a placeholder or an empty
      string.
- [ ] `uv run pytest` passes with no provider credential configured. No model is involved in any
      conversion.
- [ ] `uv run mypy` passes in strict mode.

## Out of scope

- The reviewer interface that invokes these conversions.
- Automatic reclassification during consolidation, which uses these helpers but owns the routing
  decision itself.
- Merging duplicates, which is a separate relationship.

## References

- `docs/architecture/data-model.md` — section 2.5, section 2.6, section 4.6, section 21,
  section 22, section 23, section 32
- `docs/architecture/agent-design.md` — section 16 ("Reclassification rules"), section 18
- `docs/architecture/current-architecture.md` — section 5.12
- `docs/architecture/decision-log.md` — DEC-009
- `docs/product/design-principles.md` — section 4, section 16
