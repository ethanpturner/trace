# Security Architecture & Threat Modeling in the Age of AI Coding Agents

Ethan Turner — one-page handout. Everything on this page traces to a committed artifact in
https://github.com/ethanpturner/trace or is marked as the talk's framing.

## Four questions for every agent

1. What can influence it?
2. What can it access?
3. What can it do?
4. How do I know what happened?

## Three things to take home

1. **Model agents as actors.** Put the agent on the architecture diagram and ask what authority
   crosses each trust boundary with it.
2. **Design for least agency, not just least privilege.** Minimize the tools, context, and
   authority available for the task, not only the permissions.
3. **Require evidence from AI security decisions.** A finding without a traceable basis is a
   claim, not a conclusion.

## TRACE, in one paragraph

TRACE is a context-aware security architecture analysis system built to explore question 4. A
fixed fourteen-phase pipeline alternates six model-assisted agents with deterministic validation,
pauses at two structural human checkpoints — context approval, then finding approval, where
severity is assigned by the reviewer and by no one else — and renders a report in which every
conclusion traces back through critique, evidence assessment, control mapping, and threat to a
hashed excerpt of a source document. Missing documentation is never treated as proof of a
vulnerability; it becomes a question to ask. Source documents are untrusted end to end, and the
demo's fixture set includes a deliberate prompt-injection payload the pipeline detects and
declines to follow.

## Measured, not narrated

| What | Number | Where |
|---|---|---|
| Approved findings linked to hashed evidence | 100% (17/17) | `docs/eval/comparison.md` |
| Injected-instruction compliance | 0% across 5 payload classes | `docs/eval/comparison.md` |
| Spurious findings | 4 over 12 scenarios (generic single-prompt baseline: 5 over 4) | `docs/eval/comparison.md` |
| Live run cost / time | $6.92 ± $3.28, ~41 min mean (n=5) | `docs/eval/comparison.md` |
| Honest miss | live run matched 0 of 3 authored expected findings; approved 4 defensible ones the truth set does not name | `docs/product/demo-script.md` |

The whole demo replays offline from committed fixtures — `uv run python
scripts/replay_forgeflow.py` on a fresh clone, no API key, exits non-zero unless the report
reproduces byte-for-byte.

## Where to look

- Repository and user guide: https://github.com/ethanpturner/trace (`docs/guide/`)
- Evaluation results: `docs/eval/comparison.md`, `docs/eval/scorecard.html`
- The demo walkthrough: `docs/product/demo-script.md`
- Contact: linkedin.com/in/ethanpturner
