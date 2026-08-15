# Reading the report

Trace's output is a single Markdown document with sixteen numbered sections, rendered by
`trace report show` once the pipeline has run to completion through both checkpoints. This page
explains what each section means, how to read a finding without over-reading it, and how to trace
any conclusion back to the passage in your documentation that supports it — which is what you will
need when someone asks "why does the report say this?"

The examples on this page come from the ForgeFlow demonstration report, which ships in the
repository at `demo/forgeflow/assets/forgeflow-report.md`. You can open it directly, or produce
it yourself with the offline replay described in
[getting started](getting-started.md#first-touch-the-offline-replay).

Throughout this page, identifiers like `asm-001` are allocated in order from a fresh data root; on
a reused data root the next create mints `asm-002` and the transcript diverges.
`uv run trace reset --force` returns the data root to the fresh-clone state and is destructive.

## The sixteen sections

The report's shape is fixed by `templates/report-v1.md`. Section numbers, titles, and anchors do
not depend on content: two renders of the same approved data produce the same structure, and a
section never disappears because it is empty.

Every section has exactly one owner. Four sections are prose written by the Report Generation
agent; the other twelve are rendered deterministically from objects a human approved. Prose and
rendered data are never interleaved in one section, so you always know which parts of the page a
model wrote.

| # | Section | Owner | What to look for |
|---|---------|-------|------------------|
| 1 | Executive summary | Agent prose | The counts and the caveats — how many findings, how many open questions, and what the assessment does not claim. |
| 2 | Scope | Rendered | The assessment configuration and every source document with its ingestion status; anything not listed here was never seen. |
| 3 | System overview | Agent prose | The system as the approved context describes it, with identifiers — a narrative you can check against sections 4 and 5. |
| 4 | Architecture summary | Rendered | Components, actors, and data flows as tables; `unknown` in a cell means the documentation did not say, not that the answer is no. |
| 5 | Assets and trust boundaries | Rendered | What the system holds that matters, and where trust changes. |
| 6 | Risk summary | Agent prose | How the findings relate to each other and which open questions bear on them. |
| 7 | Significant threats | Rendered | The approved threats, each with its reasoning and impact, anchored by identifier (`thr-001`). |
| 8 | Approved findings | Rendered | The findings the reviewer approved at checkpoint 2, with severity, confidence, validation status, evidence, and any recorded assumptions and limitations. |
| 9 | Documentation gaps | Rendered | What could not be determined from the material provided. |
| 10 | Assumptions | Rendered | Claims the context rests on that no document states, each with its rationale. |
| 11 | Open questions | Rendered | Questions raised and not answered, listed with the priority each carries. |
| 12 | Existing controls | Rendered | Controls the evidence confirmed, each with the passages that confirm it and any recorded limits on what it achieves. |
| 13 | Recommended actions | Rendered | One line per finding, in severity order — the work the report proposes. |
| 14 | Methodology | Rendered | How the report was produced: the source-coverage table, and the version pins (model, prompts, catalog, workflow). |
| 15 | Evidence appendix | Rendered | Every cited evidence reference with its quoted excerpt and source location. |
| 16 | Assessment limitations | Agent prose | What qualifies the whole report — findings that rest on assumptions, and the bounds of what was reviewed. |

Two properties of the rendered sections are worth knowing before you rely on the report:

- **A finding's text is what the reviewer approved.** A `Finding.description` in section 8 is the
  text approved at checkpoint 2, carried into the report verbatim. The Report Generation agent
  writes the four prose sections and never rewrites an approved object's wording, so nothing a
  human signed off on is paraphrased by a model afterwards.
- **Empty sections carry authored wording rather than vanishing.** When a section has nothing to
  report, it renders a fixed statement of what the absence means. The ForgeFlow report's section 9
  reads: "The assessment recorded no documentation gaps. Every requirement it applied could be
  evaluated against the documentation provided. This is not a statement that the documentation is
  complete — only that its silences did not block a conclusion the assessment tried to reach."
  That wording is authored in the template, not composed at runtime, so it cannot drift between
  reports. A section that disappeared when empty would read as a section that was never
  considered.

## Findings, gaps, and questions

The report separates three things that other tools often collapse into one, and the separation is
the point of the tool. A Finding means evidence supports a weakness; a DocumentationGap means it
cannot be determined whether a control exists. Missing documentation is never proof of a
vulnerability — it becomes a question to ask, never a finding.

Each appears in its own section:

- **Findings (section 8)** are candidate weaknesses that survived deterministic validation,
  critique, and human review. Each names the requirement it engages and the threat it addresses
  — ForgeFlow's `fnd-001` opens with "req-AUTHZ-001 is partially_satisfied for thr-001" — and
  lists severity, confidence, validation status, affected components and assets, impact,
  recommendation, and the evidence excerpts that support it. When a finding rests on an
  assumption, or the critique recorded a limitation in its reasoning, those are printed as part
  of the finding: they were part of what the reviewer approved and should be read with it.
- **Documentation gaps (section 9)** record requirements that could not be evaluated because the
  documentation is silent. A gap is not a weaker finding; it is a different kind of statement. A
  control that exists but is undocumented is indistinguishable, from the material provided, from
  one that does not exist — and the report says so rather than guessing either way.
- **Open questions (section 11)** are what to ask the system's owners. The ForgeFlow report
  carries twenty-six of them alongside four findings, and several bear directly on whether the
  findings hold: `qst-004`, on how webhook requests are validated, would settle `fnd-001` one way
  or the other.

Two consequences follow. First, **a report with zero findings can be a successful assessment.**
Trace optimizes for the quality of each conclusion, never for finding volume, and the template's
authored wording for an empty section 8 states the position: no findings means no candidate
weakness reached the bar this assessment applies — not that the system is secure, and not that no
weaknesses exist. It is a statement about what the material provided supports. Second, **severity
is the reviewer's judgement, not the pipeline's.** No pipeline step proposes a severity; the
reviewer assigns it at checkpoint 2, because severity depends on business context the source
documents do not carry, and a finding cannot be approved while its severity is unassigned. When
you defend a severity rating, you are defending a human decision, and the decision record shows
who made it.

The severity vocabulary is `informational`, `low`, `medium`, `high`, `critical` — plus
`unassigned`, which is the value a finding is created with and which cannot survive approval.

## Confidence and evidence strength

Every finding carries a confidence level, and every evidence reference a finding cites was rated
for how strongly it supports the specific claim it is attached to. These are separate vocabularies
measuring separate things, and the data model keeps them apart deliberately.

**Confidence** is categorical — `low`, `medium`, `high` — and no numeric score exists anywhere in
the system. A decimal alongside a three-value scale invites reading confidence as a probability,
which it is not. Read the levels as:

| Level | Reading |
|---|---|
| `low` | Significant uncertainty or weak evidence. |
| `medium` | Plausible and partially supported. |
| `high` | Strongly supported by evidence or user confirmation. |

A low-confidence finding is not a mistake to be deleted. It signals that the reviewer judged the
weakness worth recording while the evidence beneath it is thin — usually because the
documentation gestures at a behaviour without stating it. The right response is in section 11: the
open questions that would raise or collapse the finding are usually already listed there. All four
ForgeFlow findings are rated `medium`, and each carries the reasoning for that rating in its
assumptions and limitations.

**Evidence strength** describes how strongly one excerpt supports one claim: `direct`, `indirect`,
`contextual`, or `contradictory`. Strength is relational, not intrinsic — the same passage can be
direct evidence for one claim and merely contextual for another, which is why it is recorded on
the evidence assessment rather than on the excerpt itself.

**Validation status** is the third vocabulary you will see on findings and controls: `supported`,
`partially_supported`, `unsupported`, `contradicted`, `requires_confirmation`, or
`not_evaluated`. A finding marked `partially_supported`, like ForgeFlow's `fnd-001`, is telling
you the deterministic validation found the evidence chain incomplete in a stated way — and the
finding's limitations say exactly where.

## Tracing a conclusion

Every finding is required to be traceable through an unbroken chain of objects, from the source
document forward:

    source document → evidence reference → context claim → threat →
    control mapping → evidence assessment → critique → finding

Not every finding uses every link — a chain with no critique is ordinary — but a named reference
that resolves to nothing is treated as a defect, and a finding's evidence list is non-empty by
schema, so no finding's history bottoms out in silence.

In the rendered report, the chain is navigable by identifier. A finding cites evidence identifiers
inline (`evd-028`, `evd-042`); each is quoted in full beneath the finding and again in the section
15 appendix, with its source document, section heading, and line range:

    [evd-028 — architecture-overview.md, 8. Webhook Receiver, lines 200-219]

To see one evidence reference on its own, outside the report:

```
uv run trace evidence show evd-028 --assessment asm-001
```

This prints the quoted passage with its source document, section, line range, and content hash —
the hash is what ties the quote to the stored document. `trace evidence list` enumerates every
reference the assessment holds, and `trace evidence verify` re-checks each one against its stored
source document, so a quote that no longer matches its origin is caught rather than trusted.

The report itself is pinned by a manifest. On disk the rendered report lives under
`data/assessments/<id>/outputs/` next to its `.manifest.json`, which records the report's content
hash and every version the run depended on — model, prompts, requirements catalog, workflow. To
print it:

```
uv run trace report show asm-001 --manifest
```

When you defend a conclusion, this is the order to walk: the finding names its requirement and
threat; the threat's reasoning cites evidence; the evidence quotes a passage; and the passage
verifies against the stored document's hash. At no point does the chain rest on "the model said
so" — every link is either a quoted excerpt or a recorded human decision.

## The lineage view

The same chain can be browsed in a local web view:

```
uv run trace view
```

This serves a read-only rendering of the persisted assessments on `127.0.0.1`, port 8765 by
default. It serves GET requests only and drives nothing — review stays on the command line, and
closing the server loses nothing, because everything it shows comes from the store.

For an assessment `asm-001`, the view offers the overview, context, workflow, questions, and
findings pages, plus the lineage walk:

- `http://127.0.0.1:8765/asm-001/lineage` lists the findings that can be walked.
- `http://127.0.0.1:8765/asm-001/lineage/fnd-001` renders the full chain for one finding — every
  object from source document to approved finding, in order.

The lineage is computed from the objects at request time, not stored separately, so what the walk
shows is by construction what the store holds. If the port is already taken — running the view
twice is the likeliest slip — the command exits 1 with a one-line error suggesting `--port`:

```
uv run trace view --port 8899
```

## Verifying integrity

Before circulating a report, or when returning to an assessment after time has passed, verify
that nothing the report rests on has drifted:

```
uv run trace verify asm-001
```

This walks the whole evidence chain: it re-hashes every stored source document against its
recorded hash, re-checks every evidence reference against its source, and verifies the report
manifest against the store. On a clean pass it exits 0 and summarizes what it checked:

```
verified: 8 document(s), 153 evidence reference(s), 1 manifest
```

On any drift it exits 3, naming each item that no longer verifies — identifier, expected hash,
found hash — and never printing the content that changed, since a drifted document may hold
anything. A non-zero exit here is an answer, not a fault; the exit-code conventions are in
[the CLI reference](cli-reference.md#exit-codes).

Verification tells you the report is intact. It does not tell you the report is good — that
judgement is a human's, and Trace gives it a place to be recorded:

```
uv run trace report rubric asm-001 \
    --score context_accuracy=4 --score threat_quality=4 \
    --score finding_usefulness=5 --score false_positives=4 \
    --score evidence_quality=5 --score report_quality=4 \
    --score overall_confidence=4 \
    --comments "Findings hold up; webhook questions are the priority follow-up."
```

The rubric has seven categories — `context_accuracy`, `threat_quality`, `finding_usefulness`,
`false_positives`, `evidence_quality`, `report_quality`, `overall_confidence` — each scored one to
five by a person, and all seven are required in one invocation so a stored rubric is never
partial. Scores persist as reviewer judgement; no rubric value is ever computed by the system.

For what to do once the report is read and recorded, see
[the assessment walkthrough](assessment-walkthrough.md#after-the-report).
