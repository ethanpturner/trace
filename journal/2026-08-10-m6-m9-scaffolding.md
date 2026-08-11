# M6 through M9: the survey looks outward, and the next four milestones get names

Third entry for the day. With M4 closed and M5 queued, the question was what comes after —
not as a wish list, but as milestones with issues that respect the corpus. The session ran a
three-way research pass: the repository's own state against its roadmap, the tooling
landscape Trace would be compared to, and what makes an agentic pipeline credible to a
skeptical reviewer in 2026. Twenty-six issues came out of it: five decisions into M0 and
twenty-one implementation issues across four new milestones.

## What the landscape survey changed

The uncomfortable finding first: most of what Trace's design treats as load-bearing —
an agent extracts an architecture model, requirements get mapped, context informs analysis —
is also what the incumbents *claim*. Threat Designer and Devici say "AI reads your
architecture"; SD Elements maps requirements; DryRun markets context-awareness. Leading the
demo with any of those invites a shrug.

Four properties survived the survey uncontested: evidence linkage with content hashes,
deterministic offline replay, the finding-versus-documentation-gap type distinction, and
analyzed content treated as untrusted input with the checkpoint enforced structurally. No
tool in either category — rule-engine or LLM — has any of the four, and the ecosystem's
published failures land on exactly those axes: every major agentic reviewer was compromised
through its analyzed content this past year, reproducibility is the loudest academic
criticism, and the market consolidated around selling threat volume into an industry
drowning in false positives. DEC-009 turns out to be counter-positioning the incumbents
cannot adopt without invalidating their own metrics.

The credibility research said the same thing from the other side: the artifacts that read
as senior are measured ones — ablations, baselines against a named incumbent, run-to-run
variance, a truth set with negative cases and a written construction method. The
differentiators Trace already possesses are worthless unproven; the proving layer is the
work.

## Why Assembly is a milestone and not a chore

The gap nobody's issue owned: the `Orchestrator` has never been instantiated outside a
test, and no CLI command drives an assessment past checkpoint 1. Eleven phases of nodes,
five agents, and no way to run the pipeline the architecture describes. M6 exists because
every differentiated claim downstream — the harness, the baselines, the adversarial suite,
the demo — measures a pipeline that has to run end to end from the command line first. The
roadmap's stages assumed the assembly implicitly; the milestone makes it explicit and adds
the two artifacts that make claims verifiable in a minute: the committed end-to-end replay
fixture and `trace verify`.

## Five decisions, filed rather than improvised

The harness design, the baseline protocol, the adversarial evaluation design, the published
scorecard, and run-to-run stability all got M0 decision issues instead of going straight to
implementation issues, on the established discipline: where the corpus is silent, the answer
is a DEC entry, not an improvisation. The scorecard one matters most structurally — it has
to record that a static HTML metrics page is not the report, or DEC-035's Markdown-only rule
gets quietly eroded by the first person who conflates them.

Sequencing was decided deliberately: evaluation before adversarial before demo. The
adversarial demonstration is the loudest asset, but its two-axis numbers are harness output,
and the demo's comparison table is harness output; everything cites M7.

## Doc changes

Roadmap section 3 now carries the milestone decomposition table. Future-features 9.1 and
9.2 flip to Promoted — the first items to earn the status — and 13.1 records its partial
promotion into the M9 read-only view. Decision-log entries wait for the decisions to close;
the issue bodies say so themselves.

## Open next

M5 Alignment is still the active milestone by the WIP rule; M6 opens when it closes. The
first M6 move is the driver, and the first thing the driver will surface is whatever the
context-slice pipeline path and the orchestrator disagree about — they have never had to
agree before.
