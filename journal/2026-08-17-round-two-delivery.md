# Round two: ten more, from decided-but-unbuilt to the diff's narrative layer

**Date:** 2026-08-17

## What changed

The second feature plan (#500–#509) landed on develop the same day as the first, one
squash-merged PR per issue, DEC-099 through DEC-103 plus amendments to DEC-070, DEC-072,
DEC-073, and DEC-096. Where round one built new capability, round two divides into three
honest bands: executing items already decided, closing the gaps the first wave created, and
one promotion whose value was measurable with what existed.

- **#500 / DEC-099** — catalog 0.2 released under a now-stated condition (a version releases
  when the first committed recorded scenario pins it), kept separate from the default; the ASVS
  resolver extended to every registered version (the 14 new requirements' citations were
  unchecked); the eval stamps made version-honest ("0.1 (12), 0.2 (1)" — the single stamp had
  gone false over the mixed corpus, the stop condition inside the measurement artifacts).
- **#501 / DEC-100** — `trace capture` gains baseline stages, the last hand-authoring step
  between a provider key and the keyed gate clearing in one sitting.
- **#502** — seven documentation-drift sites reconciled, and the guide-conformance guard made
  two-way so a wave of new flags can no longer strand the reference silently. The duplicate
  DEC-083 heading became DEC-101.
- **#503 / DEC-072 amendment** — Mermaid DFD export, closing the serializer family's decided
  build-out and discharging future-features 13.2.
- **#504 / DEC-070 amendment** — the OpenAPI parser, answering the entry's placement question
  (parsers ride the first scenario that supplies their input) with rag-support-bot's new spec.
- **#505 / DEC-073 + DEC-096 amendments** — `trace evaluate --json`, CLI-reachable page
  renderers, and generalized offline replay-hash pins the harness verifies with an exit-3 drift
  answer.
- **#506** — rag-support-bot's adversarial condition, the corpus-poisoning path, taking the
  DEC-075 instrument from 1 measured scenario to 2.
- **#507 / DEC-102** — the severity-concordance metric, answering DEC-030's open question from
  `severity_guidance` that had sat unused in every truth set.
- **#508** — the read-only view's threats, ledger, and diff pages, catching it up to the CLI.
- **#509 / DEC-103** — the assessment comparison report, the diff's narrative layer, promoting
  future-features 13.3.

## Decisions and reasoning worth keeping

- **Release is not the default** (DEC-099): freezing content a replay depends on and switching
  what every unpinned run maps against are different risks. 0.2 froze because rag-support-bot's
  replay depends on it; the default stays 0.1 until the DEC-024 cost question is measured,
  because switching it changes every default run's mapping input surface.
- **The offline pin is distinct from the capture pin** (DEC-073 amendment): the two replay
  paths stamp different model profiles into the report, so one hash cannot serve both. The new
  check exposed the discrepancy the moment it existed; each pin now names its path.
- **The severity metric measures agreement, not correctness** (DEC-102): the guidance is one
  author's judgment, and the method string says so. It answers DEC-030's actual question —
  whether the blank-field checkpoint produces predictable severities — without a second
  annotator DEC-004 does not have.
- **The two-way flag guard** (#502): the conformance test could only catch documented-flags-
  that-do-not-exist, never flags-that-exist-and-are-undocumented — exactly how round one's
  `--json` wave stranded the docs. The reverse direction, with the Global section vouching for
  single-sourced flags and a teeth test, closes it.

## Process note

A backgrounded `git push` raced foreground edits on another branch once (the pre-push hook runs
pytest against the working tree). The fix, recorded in memory: commit and push in the
foreground on a clean tree; background only the remote-side create→CI→merge pipeline.

## Open next

- The keyed gate is unchanged and now fully unblocked: the eleven-scenario live sweep with live
  baselines (baseline capture shipped in #501), the #331/#332 comparison recordings, the usage
  backfill, and the demo video (#353) — all needing a provider key/budget or the user's voice.
- DEC-024's partitioning cost question is the one measurement that would unlock the next tier
  (semantic dedup, a structured-applicability pass, switching the default catalog to 0.2).
- Remaining decided-but-unbuilt: DEC-070's IaC parser (third, "the hardest semantics, waits"),
  DEC-072's CycloneDX (deferred until a consumer). Remaining adversarial scenarios are corpus
  work, not a mechanism change.
