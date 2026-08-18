# The end-user guide: five files, five writers, one editor

## What changed

`docs/guide/` now exists: `getting-started.md`, `assessment-walkthrough.md`, `cli-reference.md`,
`reading-the-report.md`, and `troubleshooting.md`. Until today every document in the repository
served one of three readers — an evaluator judging the design, a contributor changing the code, or
the presenter performing the demo — and none served the person who installs Trace, runs an
assessment on their own documents, works the two checkpoints, and reads the report. Stage 6's
first exit criterion ("a reviewer can understand and run the project from the repository") had no
deliverable behind it. Issue #473 covers the guide; README gained a "Using Trace" table above the
design-corpus table, and `demo/forgeflow/speaker-notes.md` — the most operator-like text in the
repository, until now untracked — is committed beside the scenario it narrates.

## How it was written, and why that shape

Five writer agents in parallel, one file each, zero file overlap, all working from one shared
brief: the register rules, a terminology glossary with the canonical DEC-009 sentence, a heading
map agreed before any file existed so cross-links could be written against real anchors, and a
standing instruction to verify every command against `--help` before documenting it rather than
copying from another document. A sequential editor pass then swept terminology, verified all 28
cross-file anchors, and adjudicated factual conflicts against the code.

The location decision: in-repo, not the GitHub wiki. The wiki is enabled and empty, and it stays
empty deliberately — it is unversioned, writable outside pull-request review, and the Stage 6
rule is that every claim traces to a committed artifact. No decision-log entry was needed; no
binding constraint governs documentation location, and nothing about the pipeline changed.

## What the writing surfaced

Documenting a surface honestly means running it, and running it found three things the corpus had
wrong or unstated:

- **The `context show` hint named a flag that does not exist.** `--resolve-contradiction` in the
  runtime hint, the docstring, the demo script, and — pinning the bug in place — the test. The
  defined flag is `--resolve`. Fixed first, in its own PR (#474, issue #472), so the writers
  documented a CLI whose own hints are correct.
- **`trace verify --help` claimed drift exits 1; the code returns 3.** The epilog was stale
  against `REFUSED`. Fixed in the guide PR alongside the documentation that states 3.
- **Approving an undecided context succeeds and advances nothing.** Two writers (and the shared
  brief) assumed undecided subjects block `context approve`. Driving the pipeline live showed the
  real contract: only an unanswered blocking question or an outstanding validation error refuses
  approval (exit 3); an approve over undecided subjects records the baseline and one decision,
  and `resume` then re-pauses at checkpoint 1 naming what is still awaited. The guide now states
  the approve-versus-advance distinction explicitly, and troubleshooting gained the symptom entry
  ("I approved the context but `resume` pauses again").

## The guard

`tests/unit/test_guide_conformance.py` parses every fenced `trace` invocation in `docs/guide/`
and walks it against the parser `build_parser` builds: the subcommand path must resolve and every
long flag must exist. It validates names, not behavior, so it needs no key and runs in the default
suite. The mutation tests hold it to rejecting a misspelled subcommand and the exact flag that
shipped wrong — the demo-script bug, expressed as the regression this guard exists to catch.

## Open next

The guide unblocks the reader half of Stage 6; the presenter half remains: the ISC2 presentation
folder (#356) and the demo video (#353). One demo-day caution surfaced on the way: a stale local
data root at schema version 1 refuses under the current schema-version-2 build, so `trace reset
--force` before rehearsal is not optional.
