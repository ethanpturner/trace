## Context

`docs/architecture/agent-design.md` section 13 defines a deterministic node validating
requirement, threat, and control relationships. One of its ten responsibilities is
load-bearing for the whole project: "Prevent unverified from silently becoming unmet."
`docs/architecture/data-model.md` section 19 states the same rule from the data side —
"An unverified requirement does not automatically create a finding." DX-08 supplies the
evidence rules this node applies; DX-09 supplies the disposition of a conclusion
suppressed by `common_false_positives`.

## Scope

- Add `src/trace_ai/workflow/nodes/mapping_validation.py`. It is deterministic and makes
  no model call.
- Implement all ten responsibilities in section 13: referenced requirements exist;
  referenced threats exist; control identifiers exist; applicability states are permitted;
  satisfaction states are permitted; applicability rationales are present; evidence policy
  is enforced; unverified cannot silently become unmet; conflicting mappings are flagged;
  duplicate mappings are detected.
- Check requirement existence against the catalog version recorded on the assessment
  rather than against whatever is on disk. A mapping citing a requirement from a different
  catalog version is an error, not a warning, because the requirement text may have
  changed underneath it.
- Apply the DX-08 evidence rules to the unverified and unmet boundary. A mapping proposing
  `unmet` without qualifying positive evidence is downgraded to `unverified`, and the
  downgrade is recorded with its reason rather than applied silently. A silent downgrade
  is as invisible to evaluation as a silent upgrade.
- Detect the section 12 failure conditions that are deterministically checkable: mappings
  referring to nonexistent objects; unverified controls marked implemented; missing
  applicability rationales; and the discrimination check, meaning every candidate
  requirement marked `applicable` for a single threat with no `not_applicable` or
  `conditionally_applicable` among them.
- Persist suppressions recorded by the mapping agent in the DX-09 representation, so the
  false-negative measurement in `docs/architecture/evaluation-plan.md` section 8 can see
  them.
- Route the section 12 human-review triggers: contradictory evidence on a high-impact
  requirement; unclear inherited-control scope; compensating controls needing business
  judgment; applicability depending on unknown deployment details; a requirement possibly
  satisfied by an undocumented enterprise platform.

## Acceptance criteria

- [ ] The node makes no model call and imports no provider SDK.
- [ ] A mapping citing a requirement identifier absent from the assessment's catalog
      version is rejected, with the identifier and both versions named.
- [ ] A mapping with `satisfaction_status: unmet` that fails the DX-08 evidence rules is
      downgraded to `unverified`, and the downgrade is recorded with its reason. A test
      asserts the record exists, not only that the status changed.
- [ ] A mapping with an empty `applicability_reason` is rejected.
- [ ] A run in which every candidate requirement is marked `applicable` for one threat is
      flagged, per the section 12 failure condition.
- [ ] Duplicate mappings, meaning the same `threat_id` and `requirement_id`, are detected
      and surfaced rather than silently deduplicated.
- [ ] Conflicting mappings, meaning the same requirement resolving to different
      satisfaction statuses for the same threat, are flagged.
- [ ] Invalid output is preserved for debugging per `docs/architecture/data-model.md`
      section 33 step 1.
- [ ] A test asserts that a run producing only `unverified` and `not_applicable` mappings
      passes validation cleanly, with no warning and no flag. This is the expected shape
      of most assessments under DEC-009 and must not read as a defect.
- [ ] Suppressions recorded by the mapping agent survive validation in the DX-09
      representation.
- [ ] `uv run mypy` passes in strict mode.

## Out of scope

- Finding creation and reclassification into Question or DocumentationGap.
  `docs/architecture/agent-design.md` section 16 assigns those to Finding Consolidation in
  M4.
- Evidence Validation, which is a separate agent at section 14.
- Deciding the evidence rules. DX-08 owns them; this issue applies them.

## References

- `docs/architecture/agent-design.md` section 13 (Mapping Validation Node —
  Responsibilities), section 12 (Failure conditions; Human-review triggers; Retry
  behavior), section 16 (Finding Consolidation Node), section 26 (Retry Policy)
- `docs/architecture/data-model.md` section 19 (Important rule; Satisfaction-status
  values), section 5 (Assessment — requirements_catalog_version), section 33 (Schema
  Validation)
- `docs/architecture/decision-log.md` DEC-009, DEC-011
- `docs/architecture/evaluation-plan.md` section 8 (False Negative Rate), section 20
- `requirements/README.md` — *How to read a requirement*
