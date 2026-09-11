# The system that wrote the threat model

**2026-09-11.** Two code reviewers and Trace itself were pointed at trace. The result is
`docs/eval/self-review.md`, four issues, and a finding about the fence that the threat model
had marked Enforced.

## Why this run existed

Every scenario in the corpus is synthetic, and `benchmark-package.md` says so. The two coded
scenarios landed yesterday give the reviewers real code to read, but the code was written from a
truth set by the person who owns the truth set. Trace's own repository is the one system in reach
whose threat model was written by someone with no idea a reviewer would be scored against it,
and whose code has a decision log behind every boundary. Project 1's exchange phase named this as
the cleanest illustration of the docs-versus-code thesis on a non-synthetic system.

## What was done

The reviewers received the packages behind the three highest-risk boundaries in
`threat-model.md`: ingestion and the repository fetch, the fence and its budget, the artifact
store, the read-only view, and the redaction and configuration modules they import. Twenty-four
files, four thousand lines, a README stating the deployment model, no tests and no truth.

Mantis ran its trimmed pipeline at medium effort on gpt-5.6-sol and produced seven distinct
findings in seventeen minutes for about five dollars. Codex Security reached its five-dollar cap
in four minutes and wrote nothing. Trace ingested four of its own architecture documents and ran
through both checkpoints on the economy profile.

## What the reviewers found

Three of Mantis's seven findings were real and uncovered by any threat-model row, and became
issues. The one that matters is #675: the fence wraps excerpt bodies, and the trusted region of
the same package serialises document filenames, section titles, evidence locations, and the
whole structured-input dictionary as JSON. Section 3 of the threat model names the fence as
Enforced. It is, for the text it fences. Repository paths, Markdown headings, and the output of
the DEC-070 parsers are document-derived text that reaches the region the prompt tells the agent
to trust. The adversarial suite never aimed a payload there because the design never said that
was a surface.

The other two are smaller and true: the budget charges blocks without the separators it joins
them with (#676), and frozen domain models carry mutable dictionaries (#677). Of the remaining
four, one is covered by a row that could name the exposure more plainly (the token in git's argv),
two are excluded by DEC-004's single-user model (a symlink race on temporaries, a time-of-check
race in the loader), and one is not a security gap because evidence is verified by line range and
hash rather than by the JSON Pointer it complains about.

None of the seven was invented. Every path resolved. Mantis's review and critic stages, as in all
ten scored runs on the coded scenarios, left every one of them provisionally valid. Its
architecture stage did produce a knowledge base this time, with seven inferred boundaries against
the document's five and a deployment intent of PRODUCTION against a README that said otherwise.

## What Trace found about itself

Trace stopped at its own ceiling. Five dollars was the cap set for the run and the fourth
evidence-validation batch would have crossed it, so the orchestrator stopped with a classified
error at thirteen model calls and checkpoint 2 was never reached. That is the behaviour section
27 specifies, and a self-review that raised the ceiling to get a tidier result would have been
the wrong kind of self-review.

What it had recorded by then is enough to read. Context Validation caught a contradiction between
two of the documents it was given: current-architecture.md still says the browser boundary is
absent in the MVP, and threat-model.md section 5 describes the read-only view. The extractor
raised it as a blocking question, the checkpoint resolved it in favour of the document whose
mitigations are enforced in code, and it became #678. Seven threats, every one a section of the
threat model. Three documentation gaps and no finding: the provider's retention terms are not
written down anywhere, and neither is where the credential lives. That is DEC-009 doing its
job on the project that wrote it.

The split is the one the guide predicted. Mantis found three things in the code the documents
do not describe. Trace found one thing wrong between the documents and three things the
documents do not say. Neither found anything the other did.

## What changed, and what did not

Nothing in the code changed in this PR. The findings are issues because each touches a decision:
the fence design under DEC-021 and DEC-070, the budget's role under DEC-070, the DomainModel
contract under DEC-006, and the staleness of `current-architecture.md` section 12 against
DEC-078. The classification is recorded with its reasons so it can be argued with row by row.

The feeds live under `results/*/self-review/`, in a subdirectory the sweep's feed discovery does
not enter, because there is no `expected/` to score them against and a self-review is not a
benchmark scenario.
