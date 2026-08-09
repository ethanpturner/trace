# 2026-08-08 — Getting the answer key out of the exam

Closes the first M0 item, #18. Short piece of work, but it is the one backlog item that
needed no decision, and it was correcting a real contamination rather than a documentation
gap.

## What was wrong

`demo/forgeflow/input/structured-system-input.yaml` ended with an `evaluation:` block
declaring `findings: 3, questions: 5, documentation_gaps: 3, contradictions: 2,
prompt_injection_fixture: true`. That file is one of the eight documents the scenario
supplies to Trace as material under review. `forgeflow-scenario.md` section 25 already said
expected files must not be supplied during an assessment.

Two distinct problems, and the second is worse than the first.

The measurement problem is obvious: the system under test was holding its own answer key,
so every number taken against this scenario was worthless.

The quota problem is the one that matters. `design-principles.md` section 9 and
`evaluation-plan.md` section 20 both reject optimizing for finding count, and `CLAUDE.md`
lists it as binding. A model that reads `findings: 3` in its input has been told how many to
produce. This project exists to argue that a security review should report what the evidence
supports and nothing more; its own benchmark fixture was instructing the reviewer to hit a
number.

`README.md` quoted the block approvingly, under a heading arguing that the small finding
count was the point.

## What changed

The block moved to `demo/forgeflow/expected/evaluation-contract.yaml`, which is where
section 25 says it belongs, and the directory is otherwise still empty pending #39.

The counts were **not** corrected in the move, deliberately. They are disputed: the scenario
document lists four findings against the recorded three, and ten candidate questions against
five. Correcting them while relocating would have made the move unreviewable — two changes
in one diff, neither verifiable against the other. The dispute is recorded in the new file
under a `disputed` key with references to the scenario sections, and #39 resolves it.

The filename is provisional for the same reason. The benchmark layout is specified twice in
the corpus and the two specifications disagree, down to two spellings of the reviewer-notes
file. #39 fixes the layout and this file gets renamed to match.

`README.md` now points at the contract's real location and states that it is never supplied
to Trace. The narrative survives — questions and documentation gaps are outputs a generic
review does not produce at all — but it no longer asserts specific disputed counts, and it
now says explicitly that the counts are a ceiling on defensible conclusions rather than a
target, and that nothing in the pipeline is designed to read them.

## The test, and why it is shaped this way

`tests/unit/test_forgeflow_fixture.py` guards the leak in two ways, because one was not
enough. A textual check catches any contract key appearing in any input document, which
works on Markdown as well as YAML. A structural check parses the YAML and walks every
mapping key, which catches a key that a textual scan could miss through formatting.

I verified the guard by reintroducing the block and confirming two tests fail, then removing
it and confirming they pass. A guard that passes in both states is not a guard, and this is
cheap enough that there is no excuse for not checking.

One test asserts that nothing under `src/` reads the expected directory. Today that is an
assertion about an empty set — there is no ingestion path yet. It is written now because the
moment ingestion exists is the moment it can regress, and a test added after that point is a
test added after the bug.

There is also a test that the injection fixture in `sample-repository-notes.md` is preserved
verbatim. Removing the contract from one input file is exactly the kind of change during
which someone tidies away a block of text that looks like it should not be there. The
payload is test data and sanitizing it would destroy the case it exists to prove.

## Open next

- #39 resolves the disputed counts and the layout, after which the contract file is renamed
  and its `disputed` key is removed.
- #20 and #26 remain the two decisions with the widest blast radius.
- The rest of `demo/forgeflow/expected/` is still unwritten, so Stage 0 stays incomplete on
  benchmark fixtures as well as on the threat model.
