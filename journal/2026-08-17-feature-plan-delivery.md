# Eight issues in one push: the feature plan's buildable half, delivered

**Date:** 2026-08-17

## What changed

The next-ten-features plan (filed as issues #482–#489 plus the pre-existing #452 and #484)
moved from backlog to develop in one session, in dependency order, one squash-merged PR per
issue. Eight decision-log entries landed with them, DEC-091 through DEC-098.

- **#482 / DEC-091** — `trace capture <scenario>` replaces `scripts/capture_forgeflow.py`,
  generalized over the registry, with the staging-then-promote semantics and spend guards kept
  and the fake provider refused before any side effect. The unit suite drives all three stages
  offline against the committed ForgeFlow recording and reproduces the committed report hash
  byte for byte.
- **#483 / DEC-092** — the measured cost supersedes the estimate: five completed live runs at
  $6.92 ± $3.28 sit above the $2.25–$5.97 estimate's ceiling, and every document that quoted
  the estimate now quotes the measurement. `trace ledger` prints per-run, per-node spend with
  dashes for the unmeasured — absent and zero are different answers. CLAUDE.md's "no live
  provider run has been measured" claim, contradicted by the committed eval artifacts, is gone.
- **#484 part 1 / DEC-093** — stability-protocol object decisions replay by content
  fingerprint. The defaulted count now measures extraction novelty rather than the harness's
  own leniency, which is what makes the eleven-scenario sweep worth running. The sweep itself
  is the remaining, keyed half of #484.
- **#452 / DEC-094** — WS11's residuals: `build_model` is the one overlay-resolution point
  (the driver's per-node `for_agent` and `AgentOverlay.settings` are gone), and
  `PromptDefinition.template_hash` covers the pre-substitution composition, the cross-corpus
  identity #331's comparison needs.
- **#485 / DEC-095** — the OpenAI adapter proves the seam: two providers under one conformance
  suite, each adapter importing exactly its own SDK, creativity mapped to `reasoning_effort`,
  non-strict structured output with the fallback recorded, cached spans subtracted to keep
  DEC-067's inputs disjoint. Two shipped profiles, `openai-experimental` and `economy-mapping`
  — the first shipped DEC-069 overlay. No live OpenAI pipeline run has been measured, and the
  docs say exactly that much.
- **#486 / DEC-096** — `--json` on every read command with the load-bearing clause that the
  JSON view carries the same information as the human view and no more, plus the read commands
  that should have existed: `trace threats`, `trace questions`, `trace catalog show|validate`.
- **#487** — SARIF export, second in DEC-072's decided order, recorded as an amendment rather
  than a fresh entry. A gap exports as `kind: "review"` at `level: "none"` — DEC-009 kept
  structural in the interchange format.
- **#488 / DEC-097** — assessment diffing promotes future-features 4.1: two scoped reads,
  identity by content fingerprint, ambiguity to added/removed, threats and gaps by ground and
  never force-paired, changed objects naming their fields.
- **#489 / DEC-098** — the AI system threat-modeling pack promotes 8.1 in part: catalog 0.2
  grows to 37 requirements (retrieval-augmentation, model-generated-code), scenarios pin their
  catalog version through the registry, and the thirteenth scenario — rag-support-bot — makes
  the pack measurable with a full truth set replaying offline at FP 0, FN 0, gap precision 1.

## Decisions and reasoning worth keeping

- **The capture decision's sharp edge** (DEC-091): committed `decisions-*.yaml` answer a
  replay, never a fresh live run — a fresh run allocates its own identifiers, and a decision
  applied to an object its reviewer never saw would be a clean approval record over an
  unreviewed run. The issue body had assumed the opposite; the DEC entry corrected it, which
  is the decision-log discipline working as intended.
- **Pick-one meant pick-the-only-one-that-can-work** (DEC-094): the overlay's model identity
  lives in the adapter and a single `StructuredModel` object is load-bearing for replay
  ordering, so the factory path was the only resolution point that could survive. The
  driver-side path could never change what model answered; deleting it deleted a fact written
  twice.
- **The structured baseline lost its clean record deliberately** (DEC-098): on the retrieval
  scenario it reads silence about deletion propagation as a violation. The tidy sentence
  ("structured produced no spurious finding") gave way to the more useful one: structure alone
  does not stop the DEC-009 failure; the process does.
- **The scenario-authoring loop is the capture loop.** rag-support-bot was authored by driving
  the real CLI stage by stage — extract, export, decide, approve, resume — with hand-authored
  responses in place of a live model, letting each validator's refusal (satisfaction enums,
  the gap-versus-question routing on `missing_evidence`, the report's required-limitations
  set) correct the recording. The pipeline's own strictness is what makes an authored
  recording trustworthy.

## Open next

- The keyed half of the plan: the eleven-scenario live sweep and the unsigned-webhooks failure
  diagnosis (#484), the prompt- and model-comparison recordings (#331, #332 — both now
  unblocked by template_hash and the second adapter), and the usage backfill via re-captures.
  All need a provider key and budget.
- The narrated demo video (#353) remains the last Stage 6 asset.
- DEC-024's catalog-partitioning cost question is now live rather than latent: 37 requirements
  ride every mapping call, and DEC-092's measured token data is what should answer it.
