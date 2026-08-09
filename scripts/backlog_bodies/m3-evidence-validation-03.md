## Context

`docs/architecture/agent-design.md` section 3 gives the Evidence Validation Agent no
validation node. Context Extraction is followed by a Context Validation Node, Threat
Analysis by a Threat Validation Node, and Requirement and Control Mapping by a Mapping
Validation Node; evidence validation runs straight into the Critical Review Agent. The
asymmetry appears to be an omission rather than a design intent, because section 14 lists
failure conditions for the agent's output and section 4 classifies every other reasoning
agent as needing deterministic follow-up. `docs/architecture/data-model.md` section 33
requires validation after model-generated structured output regardless of whether a node
is drawn on the diagram, and `docs/architecture/agent-design.md` section 22 states that
agents never write authoritative records.

This issue absorbs that responsibility explicitly and records the asymmetry so it is a
noted decision rather than an accident.

## Scope

- Add `src/trace_ai/workflow/nodes/evidence_assessment_validation.py`. It is deterministic
  and makes no model call.
- Validate schemas; confirm `subject_id` resolves to an existing object of the declared
  `subject_type`; confirm every `evidence_ids` entry resolves to an existing
  `EvidenceReference`; enforce that a rationale quoting evidence matches the referenced
  `quoted_text`; confirm contradictions resolve to the evidence references that disagree
  under the DX-14 representation.
- Detect the section 14 failure conditions that are deterministically checkable: evidence
  references that do not exist; unsupported claims marked supported; model-generated text
  treated as source evidence; contradictions present in the inputs but absent from the
  output.
- Persist validated assessments through the M1 persistence layer. The agent proposes; this
  node validates and writes, per section 22's write model.
- Update object validation statuses that section 14 lists among the agent's outputs, as
  deterministic transitions rather than as free-form edits. A status transition that the
  transition table does not permit is an error.
- Route the section 14 human-review triggers: high-impact conclusions that remain
  contradictory; evidence that is sensitive or difficult to interpret; a proposed
  high-severity finding that is only partially supported; inherited controls that need
  reviewer knowledge to validate.
- Record the asymmetry in `docs/architecture/decision-log.md`: state that
  `docs/architecture/agent-design.md` section 3 shows no validation node for this agent,
  that one is implemented anyway on the strength of
  `docs/architecture/data-model.md` section 33 and `agent-design.md` section 22, and
  whether the workflow diagram at section 3 should be amended to show it.

## Acceptance criteria

- [ ] The node makes no model call and imports no provider SDK.
- [ ] An assessment whose `subject_id` does not resolve, or resolves to an object of a
      different type than declared, is rejected with both values named.
- [ ] An assessment referencing a nonexistent evidence identifier is rejected.
- [ ] An assessment whose rationale quotes text not matching the referenced
      `EvidenceReference.quoted_text` is rejected. `docs/architecture/data-model.md`
      section 8 states that evidence text is not modified after creation, so any divergence
      is the agent's.
- [ ] `validation_status: supported` with empty `evidence_ids` is rejected.
- [ ] A contradiction present in the input evidence but absent from every emitted
      assessment is flagged. Section 14 makes "Contradictory evidence is ignored" a failure
      condition, and ignoring is only detectable at this node.
- [ ] No agent-proposed object reaches persistence without passing this node. A test
      asserts the write path is unreachable from the agent module.
- [ ] A status transition outside the permitted set is an error, not a silent write.
- [ ] Invalid output is preserved for debugging per `docs/architecture/data-model.md`
      section 33 step 1.
- [ ] A test asserts that an assessment set containing no `unsupported` classifications
      passes cleanly. Under DEC-009 that is an expected outcome, not a sign the agent did
      nothing.
- [ ] A decision-log entry records the missing-node asymmetry and states whether
      `docs/architecture/agent-design.md` section 3 should be amended.
- [ ] `uv run mypy` passes in strict mode.

## Out of scope

- Finding consolidation, which applies these assessments in M4.
- The critic, which consumes them next.
- Changing the workflow diagram. The decision entry states whether it should change;
  editing `agent-design.md` section 3 is separate work.

## References

- `docs/architecture/agent-design.md` section 3 (Workflow Overview — the absent node),
  section 4 (Component Classification), section 14 (Evidence Validation Agent — Outputs;
  Failure conditions; Human-review triggers), section 22 (Tool Access Model — Write
  model), section 26 (Retry Policy)
- `docs/architecture/data-model.md` section 20 (EvidenceAssessment), section 8
  (EvidenceReference — Validation rules), section 33 (Schema Validation), section 32
  (Object Lineage)
- `docs/architecture/current-architecture.md` section 2.6 (Deterministic where practical),
  section 5.9, section 11 (Error Handling)
- `docs/architecture/decision-log.md` DEC-006, DEC-009
