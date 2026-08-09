## Context

`docs/architecture/threat-model.md` does not exist. It is listed among the Stage 0
deliverables in `docs/product/roadmap.md`, and `docs/architecture/current-architecture.md`
section 12 refers to it directly: "detailed risks and mitigations are maintained in threat
model.md." The `.docx` original turned out to be a byte-identical copy of the agent design,
so nothing was lost in the Markdown migration — the document was never written.

`README.md` is already honest about this. Stage 0 is therefore incomplete on two counts,
this one and the missing benchmark fixtures.

The roadmap's cross-cutting workstream requires the threat model to be updated whenever
agents gain tools or sensitive data is introduced. The first outbound model call, which
arrives in M2, is exactly that trigger — so writing it now means writing it before it is
overdue rather than after.

There is a second reason to write it early. This is a project about security architecture
review whose own security boundaries are specified but unanalysed. The threat model is
both a deliverable and a demonstration of the method the project is arguing for.

## Scope

Author `docs/architecture/threat-model.md`, marked *Proposed, version 0.1*, covering the
five boundaries named in `current-architecture.md` section 12:

1. **Source-document boundary.** Untrusted documents that may contain instructions.
   `demo/forgeflow/input/sample-repository-notes.md` is a live example. Cover what prevents
   source content from redefining an agent's role, schema, or tool grants.
2. **Model-provider boundary.** What leaves the local environment, under what terms, and
   what must not. Includes prompt content, source excerpts, and anything an external
   tracing provider would receive.
3. **Browser-to-application boundary.** Applicable only if DX-17 selects a web interface;
   note the dependency rather than assuming an answer.
4. **Assessment-data boundary.** Cross-assessment contamination, and the filename and path
   handling in the artifact store. Source filenames arrive from user input, so path
   construction is a security boundary in its own right.
5. **Generated-output boundary.** Model output treated as data rather than as instruction,
   and the report as a place where unapproved content must not appear.

For each: the risk, the mitigation, and **where the mitigation is enforced in code** — or
an explicit note that it is not yet implemented. A threat model that lists mitigations
without naming their enforcement point is the failure mode this project exists to
criticize, so it should not commit it.

Also cover credential handling (`SecretStr`, `.env` discipline, no key material in logs,
error messages, or committed fixtures) and prompt-injection handling as a cross-cutting
concern.

## Acceptance criteria

- [ ] `docs/architecture/threat-model.md` exists, marked *Proposed, version 0.1*, matching
      the corpus prose register: flat declarative, no marketing language, no emoji.
- [ ] Each of the five boundaries in `current-architecture.md` section 12 is covered.
- [ ] Every mitigation names the component that enforces it, or is explicitly marked as
      unimplemented. Nothing is described as running that does not run.
- [ ] Tense discipline holds: present indicative only for what runs today, "is designed to"
      for everything specified but unbuilt.
- [ ] `README.md`'s note that a threat model is listed among the Stage 0 deliverables and
      has not been written is updated.
- [ ] The document states its own review trigger, matching the roadmap's cross-cutting
      workstream: it is revisited when agents gain data or capability, or when a new
      external service is introduced.
- [ ] Where a boundary depends on an unresolved decision, the relevant DX issue is named
      rather than an answer assumed.

## Out of scope

- ForgeFlow's threat model. That is scenario data and lives in
  `demo/forgeflow/forgeflow-scenario.md`.
- Implementing any mitigation. This issue documents; the enforcement issues are in M1 and
  M2.
- A formal STRIDE pass over the Trace pipeline itself. The five boundaries are the frame.

## References

- `docs/architecture/current-architecture.md` section 12 (Security Boundaries),
  section 5.17
- `docs/product/roadmap.md` Stage 0 deliverables, section 4 (cross-cutting workstreams)
- `docs/product/design-principles.md` sections 13, 14
- `docs/architecture/agent-design.md` sections 2.3, 22, 25
- `README.md`, project status
- `journal/2026-08-08-foundation-and-documentation.md`
