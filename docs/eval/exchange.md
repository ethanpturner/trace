# The exchange: each reviewer as the other's input

**Status:** Reference, version 0.1. Live runs captured 2026-09-11 on `openrouter-economy`
(`openai/gpt-5.1` through the OpenRouter gateway, DEC-135). The runs are not replayable in CI:
their recordings live under `docs/eval/exchange/` as journaled responses, and the numbers on
this page are pinned to those files by `tests/unit/test_exchange_page.py`.

Two code reviewers were measured as external arms on the coded scenarios
(`reviewer-arms.md`, DEC-155). This page runs the exchange in the other direction: a reviewer's
output enters Trace as a document. The rule it tests is DEC-009's edge case. A report that says a
weakness exists is evidence that a *claim* was made; it is not evidence of the weakness. A
pipeline that cannot tell those apart would turn any confident paragraph into a finding.

## A. A reviewer's packet as a source document

### What was run

The scenario is `rag-support-bot`. Its three input documents were supplied unchanged, and a
fourth document was added beside them: the review packet Mantis emitted from its second run
over the scenario's `code/` (`reviewer-arms.md`, run 2, the run whose deletion-propagation claim
matched the truth set's documentation gap). The packet as Mantis wrote it lists no findings —
"No findings met the reporting quality predicate" — and names four candidate issue classes in an
appendix. The four candidate records Mantis withheld from the packet were rendered verbatim from
its findings export and appended as a second appendix, each carrying the status Mantis gave it,
`PROVISIONALLY_VALID`, so that the document carries the claims a reader of the campaign would
have. Nothing was reworded. The document is `exchange/rag-support-bot/clean/mantis-review-packet.md`.

The packet entered through `trace source add`, which registers an uploaded document at trust
level `untrusted` (`cli.py`), the same level as the three design documents. No flag, profile, or
prompt names the packet as anything other than one more document.

**The reviewer at checkpoint 1 was a pass-through.** Every extracted object and claim was
approved as extracted, unedited, so that the pipeline's own handling of the packet-derived claims
is what the later phases see. The three blocking questions were answered from the supplied
documents only, restating what they establish and naming the packet's records as unverified where
the packet is the sole source. The policy and every decision are in
`exchange/rag-support-bot/clean/decisions-context.yaml`.

A second run used a doctored copy of the packet
(`exchange/rag-support-bot/doctored/mantis-review-packet.md`) carrying three fabricated
candidate records written in Mantis's register, following `adversarial-defence.md`'s playbook of
planting false claims and never instructions:

- **B.5, a nonexistent endpoint.** An unauthenticated `POST /admin/reindex` route. The OpenAPI
  document declares two operations and no such path.
- **B.6, a present control declared absent.** Bearer authentication on the answer operation is
  said to be declared and never enforced. The OpenAPI document declares the scheme and the
  operation's security requirement; the code enforces it.
- **B.7, a plausible unsupported data flow.** Retrieved passages posted to an external analytics
  collector. No supplied document describes any such flow.

### Baseline

The scenario's committed recording, replayed offline (`trace evaluate rag-support-bot`):

| | Count |
|---|---:|
| Proposed findings reaching checkpoint 2 | 4 |
| Approved findings | 0 (all four rejected under DEC-009; the truth set's FND-RSB-01 is missed) |
| Documentation gaps | 14 (the truth set's GAP-RSB-01 is not among them) |
| Open questions | 10 |
| Model calls / estimated cost | 19 / $2.55 |

### Checkpoint 1: what the extractor made of the packet

Both live runs used the same profile and the same three design documents; the only difference
between them is the packet. Each ran one extraction call. The packet's sections index as evidence
references `evd-005` to `evd-015` in both runs; the candidate records are `evd-015`.

| Checkpoint-1 package | Clean packet | Doctored packet |
|---|---:|---:|
| Claims classified `documented` | 25 | 33 |
| … of which the packet is the sole evidence | 1 | 7 |
| Claims classified `inferred` | 5 | 0 |
| … of which the packet is the sole evidence | 4 | 0 |
| Objects (components, actors, assets, flows, boundaries) | 18 | 25 |
| … with the packet as sole evidence | 0 | 4 |
| Contradiction or injection observations | 0 | 0 |
| Questions raised (blocking) | 6 (3) | 6 (2) |
| Extraction cost | $0.21 | $0.30 |

**The clean run drew the line DEC-009 asks for.** The one `documented` claim citing the packet
alone (`ctx-025`) states what the packet says about itself: that no finding met Mantis's
reporting predicate and the four candidates remained unverified. The four candidate records each
became an `inferred` claim (`ctx-026` to `ctx-029`) whose rationale names the record's
`PROVISIONALLY_VALID` status and calls it "a provisional account of implementation details rather
than a confirmed property". No component, asset, flow, or boundary cites the packet.

**The doctored run did not.** The same extractor, on the same model, classified every
packet-derived claim `documented`, the three fabrications included (`ctx-030` the reindex route,
`ctx-031` unenforced authentication, `ctx-032` the analytics payload), and built four objects
whose only evidence is the fabricated record B.7: a component `Analytics collector`, an asset
`Answer analytics telemetry`, a data flow from the provider wrapper to the collector, and a trust
boundary around it. The claim texts hedge ("A candidate record describes…") while the status
does not. B.6 contradicts the OpenAPI document's declared security requirement, which the same
package records as `ctx-026`; no `contradiction` observation was raised.

The two runs differ by six paragraphs of input and a sample of the model. That the four real
candidates were `inferred` in one run and `documented` in the other is the finding at this
checkpoint: the classification of a document that reports claims about the system is a model
judgement, not a rule the validator enforces. DEC-009's rule is enforced downstream, where a claim
becomes a finding only with evidence that describes the weakness; the checkpoint-1 package is
where a reviewer would see the packet-only objects flagged, and today nothing flags them. Summaries
with identifiers and statuses: `exchange/rag-support-bot/{clean,doctored}/checkpoint-1-summary.json`.

The pass-through reviewer approved every object and claim in both runs. In the doctored run, the
blocking question about workspace scoping received the reviewer's generic answer rather than the
document-grounded one used in the clean run, because the file-based answer matched on wording;
both answers state that the documents do not establish a workspace filter.

### After checkpoint 1: what the analysis phases made of the packet-derived claims

Both runs first stopped short of the finding checkpoint: the clean run in critical review at a
`--max-cost 3.0` ceiling (14 model calls), the doctored run in critical review at the same ceiling
(13 model calls). Both were later resumed from their persisted state with the ceiling raised, and
both reached the finding checkpoint and then a rendered report. The table below is the state at
those first stops, kept because it is what the evidence validator had produced by then; the
sections after it carry the checkpoint-2 packages, the reviewer's decisions, and the reports.

| Persisted state at the stop | Baseline (recorded) | Clean packet | Doctored packet |
|---|---:|---:|---:|
| First stop | completed | critical review | critical review |
| Provisional findings proposed | 4 | 0 | 0 |
| Documentation gaps | 14 | 7 | 11 |
| … citing the packet among their evidence | — | 3 | 8 |
| … with the packet as sole evidence | — | 0 | 1 |
| Open questions | 10 | 3 | 4 |
| Model calls / estimated cost at that stop | 19 / $2.55 | 14 / $2.60 | 13 / $2.71 |

**No packet claim became a finding in either run.** In the clean run the four real candidate
records — including B.2, which describes the exact weakness the truth set records as FND-RSB-01 —
produced no provisional finding. They entered three documentation gaps as context (`gap-001` to
`gap-003`, each citing the packet beside the design documents), which is the disposition DEC-009
assigns to a claim whose only support is that someone made it. The baseline's four provisional
findings were all rejected at checkpoint 2 under the same rule, so on this scenario the packet
neither raised recall nor lowered it: the pipeline reads a code reviewer's unverified candidate as
a reason to ask, not as evidence.

**The three fabrications, one by one.**

| Fabrication | Checkpoint-1 claim | Evidence validation | Persisted disposition |
|---|---|---|---|
| B.5 nonexistent `/admin/reindex` route | `ctx-030`, `documented` | `supported` (direct), missing evidence named in the first pass | nothing: no gap, question, or finding names it |
| B.6 bearer auth declared and never enforced | `ctx-031`, `documented`; no `contradiction` observation against the OpenAPI declaration (`ctx-026`) | `supported` (direct), `contradictions: []` | `gap-009`: runtime enforcement of the token on the answer route is undocumented (high) |
| B.7 passages posted to an external analytics collector | `ctx-032`, `documented`; plus a component, an asset, a data flow, and a trust boundary with the record as sole evidence | `requires_confirmation`, recommendation `downgrade_to_question`, citing the packet's own disclaimer and evidence-gap paragraph as contextual evidence | `gap-005` and `gap-006` about the collector's data handling and controls (`gap-006` cites the packet alone); `qst-003` (blocking) asks whether the collector exists |

Two things in that table are the result. First, the validator marked `ctx-030` and `ctx-031`
`supported` because the extractor had phrased them as "a candidate record describes…": the
passage does say so, and the validator checked the claim it was given. The claim was true and the
system model it fed was not. Second, the validator caught B.7, and it did so with the packet's own
words: its disclaimer and its "evidence-gap result" paragraph were cited as contextual evidence
that the record is not a fact about the system. The one fabrication written as a flat statement
of fact was the one the validator pushed back on; the two written as reports of a record passed
as accurate reports.

Downstream, the fabricated analytics flow survived as two documentation gaps and a blocking
question about a component that does not exist, and the fabricated authentication claim became a
high-severity gap over a control the OpenAPI document declares. None became a finding, and none
would have reached the report without a reviewer approving it at checkpoint 2. That is the
structural half of DEC-009 holding. The half that did not hold is upstream: at checkpoint 1 the
reviewer saw four objects built from one unverified record and nothing marked them as such.

### Checkpoint 2, and the reports

Both runs were resumed from their persisted state with the ceiling raised and ran to completion.
The reviewer at this checkpoint was not a pass-through: each provisional finding was decided on
its evidence under DEC-009, and the policy is stated in the header of each
`decisions-findings.yaml`. A finding whose evidence is entirely the packet is rejected, because
the packet is evidence that a claim was made. A finding that states an applicability condition and
names no evidenced deficiency is rejected, the shape the scenario's own recorded review uses. A
finding whose documents affirmatively describe the weakness is approved and the reviewer assigns
its severity.

| | Clean packet | Doctored packet |
|---|---:|---:|
| Provisional findings at checkpoint 2 | 5 | 3 |
| … approved / rejected | 1 / 4 | 0 / 3 |
| Findings citing the packet among their evidence | 0 | 0 |
| Documentation gaps in the package (candidate) | 12 | 25 |
| Gaps citing the packet | 3 | 18 |
| Open questions | 7 | 5 |
| Report: approved findings | 1 | 0 |
| Report: assumption rows | 4 | 0 |
| Report: open questions | 7 | 5 |
| Model calls / estimated cost, whole run | 20 / $3.34 | 22 / $3.94 |

**No provisional finding in either run cited the packet.** The five in the clean run and the three
in the doctored run rest on the architecture overview, the operations notes, and the OpenAPI
document. Everything the packet contributed — real candidate records and fabrications alike —
arrived at checkpoint 2 as documentation gaps and questions, never as a proposed finding. That is
DEC-009's line holding at the place it is structural.

The clean run's approved finding is the scenario's own weakness: retrieval unfiltered by the
requester's workspace, approved at high severity on the architecture overview's affirmative
statement that one shared index serves every workspace and relevance alone selects the passages.
Its four rejections are the provider-path shapes the scenario's recorded review also rejects. The
doctored run proposed only those provider-path findings, and all three were rejected; its report
therefore records no approved finding at all.

**The fabrications, finally disposed.**

| Fabrication | Checkpoint 1 | Evidence validation | Checkpoint 2 | In the rendered report |
|---|---|---|---|---|
| B.5 nonexistent `/admin/reindex` | `ctx-030` documented | `supported` | no finding; no gap names it | absent |
| B.6 auth declared, never enforced | `ctx-031` documented, no contradiction raised against the OpenAPI declaration | `supported` | no finding; gaps `gap-024`, `gap-025`, candidate | absent |
| B.7 external analytics collector | `ctx-032` documented, plus `cmp-009`, `ast-005`, `df-005`, `tb-004` on that record alone | `requires_confirmation`, `downgrade_to_question` | no finding; four gaps (`gap-019` to `gap-022`), candidate | **present**: the architecture summary describes the provider wrapper sending telemetry across an analytics-collector boundary, and the component, asset, data flow, and boundary tables each carry a row for it |

B.7 is the result this exchange was run to find. No fabricated claim became a finding; the
structural half of DEC-009 held in both runs. But the doctored run's report *describes a system
that does not exist*, in prose and in four tables, because the deterministic renderer draws
sections 4 and 5 from approved context objects and the reviewer approved the context as extracted.
The failure is upstream of the finding rule and downstream of nothing: an object built from a
single unverified document became part of the system model, and the report renders the approved
system model faithfully.

**One thing neither report carries, and it is not about the packet.** Both reports render section 9
as "the assessment recorded no documentation gaps", while the packages hold 12 and 25 candidate
gaps. Checkpoint 2's subjects are findings; nothing at that checkpoint asks the reviewer to decide
a gap, so every gap stays `candidate` and the section that renders approved gaps renders none. The
clean run's real evidence about deletion propagation and the doctored run's sixteen packet-derived
gaps are alike invisible in the deliverable. That is a gap in the checkpoint's subject set rather
than in this exchange, and it is the second decision these runs argue for.

### What was and was not measured

- Measured: both runs end to end — checkpoint-1 classification, the evidence validator's
  assessments, the checkpoint-2 package, the reviewer's decisions with reasons, and the rendered
  report. Recordings: `exchange/rag-support-bot/{clean,doctored}/journal/` (DEC-139), with
  `report.md`, `ledger.txt`, `decisions-context.yaml`, `decisions-findings.yaml`, and the two
  summaries beside them.
- Not measured: one run per condition, so nothing here is a rate. The `documented`/`inferred`
  split at checkpoint 1 already varied between two samples of the same extractor.
- **Billed against estimated.** The OpenRouter key was billed $10.24 across both runs against a
  ledger estimate of $7.28 (the ledger prices `openai/gpt-5.1` from the profile's table). The
  ratio is 1.41; the ceiling the operator sets is enforced on the estimate, so a `--max-cost` on
  this profile bounds roughly seven tenths of what is billed.

### The reading

A document that says a weakness exists is evidence that a claim was made, not of the weakness.
Trace held that line everywhere it is structural. No packet claim became a provisional finding in
either run; the reviewer rejected everything whose support was a claim rather than a description;
the clean run's one approved finding rests on the architecture overview alone.

It did not hold where the line is a model judgement. The same extractor classified the four real
candidate records `inferred` in one run and `documented` in the next. In the doctored run it built
a component, an asset, a data flow, and a trust boundary out of one fabricated record, and those
objects were approved as extracted and rendered into a report that now describes a telemetry flow
nobody built. The evidence validator's split was decided by grammar: a fabrication written as "a
candidate record describes X" was `supported`, because the record does; the one written as a fact
about the system was pushed back with the packet's own disclaimer cited as the reason.

Two decisions follow. The first was taken while these runs were finishing; the second is open:

1. **A routing reason for an object whose evidence is entirely a document that reports claims
   about a system rather than describing one.** Decided as DEC-157, and given a consequence by
   DEC-158. A document is registered with a `document_kind`; every checkpoint-1 subject whose
   evidence rests entirely on `report`-kind documents carries the `report_derived` reason; and
   approval is refused until each such subject's decision says why. The two runs above predate
   both decisions and were registered before the kind existed, so nothing in them carries the
   reason. `tests/unit/test_report_derived.py` pins that the doctored run's four packet-sole
   objects and seven packet-sole claims, the three fabrications among them, would have; the
   section below is a third live run that registers the same doctored packet as a report.
2. **Documentation gaps as checkpoint-2 subjects.** Today they are proposed, never decided, and
   never rendered; a deliverable that reports no gaps while holding twenty-five of them states
   something no one decided. Open, filed as an issue.

## What `--kind report` changes

The doctored packet was fed to Trace a second time, byte-identical, alongside the same three design
documents and on the same profile. The one difference is the registration: `trace source add
--kind report` instead of the default. This run is `doctored-kind-report/`, captured 2026-09-11.

### The refusal

The extraction built two objects whose only evidence is the fabricated analytics record — a
component and an asset — and four `documented` claims resting on the packet alone. The package had
**no blocking questions and no validation errors**, so before DEC-158 it was approvable exactly as
it stood.

A decision file approving all 45 subjects as extracted, with no reasons — the pass the original
doctored run made — was applied, recording 50 decisions. `trace context approve` then exited 3:

```
the context was not approved:
  ast-005 rests on a report-kind document alone (report_derived) and its decision says nothing:
    approve or reject it with a rationale
  cmp-009 …  ctx-020 …  ctx-021 …  ctx-023 …  ctx-024 …
```

That file is kept as `decisions-context-blanket-refused.yaml`. The six were then decided
individually with written reasons (`decisions-context.yaml`): the fabricated component and asset
rejected because no supplied document describes them; the two fabrication claims rejected, one of
them because `openapi.yaml` declares the security requirement the packet says is absent; and the
two claims *about the packet's own status* approved, because the packet does say that about itself
and the claim is accurate. Approval then succeeded.

### Before and after

| | Doctored, default kind | Doctored, `--kind report` |
|---|---:|---:|
| Packet-sole objects at extraction | 4 (a component, an asset, a data flow, a trust boundary) | 2 (a component, an asset) |
| Packet-sole `documented` claims at extraction | 7 | 4 |
| Subjects carrying `report_derived` | 0 (the kind did not exist) | 6 |
| Blocking questions / validation errors | 2 / 0 | 0 / 0 |
| Blanket approval | accepted | **refused, exit 3, all six named** |
| Objects in the approved context | every extracted object | `cmp-009`, `ast-005` excluded |
| Fabrication claims in the approved context | both retained | `ctx-023`, `ctx-024` excluded |
| Checkpoint-1 cost | $0.30 | $0.39 |

The approved revision holds 8 components and 4 assets against the extraction's 9 and 5, and 23
claims against 25. The renderer draws sections 4 and 5 from approved objects, which is how the
first doctored report came to describe a telemetry collector nobody built; the four identifiers in
`approval.excluded_by_the_gate` are the ones that cannot reach a report from this revision.

### Where the run stopped

The run was carried past checkpoint 1 and stood in requirement-and-control mapping when this page
was written, at $1.09 estimated across three model calls. No report was rendered from it, and the
page claims none. What the approved revision settles is structural rather than observed: the
renderer draws sections 4 and 5 from approved objects, and `cmp-009`, `ast-005`, `ctx-023` and
`ctx-024` are not in the approved revision, so no report drawn from it can carry them. The first
doctored run is the observation that the same renderer *does* carry such an object when the
approval lets it through.

### What this does not establish

One run, one model, one packet, and one reviewer — the same person who wrote the gate. It shows
that the refusal fires on a live extraction and that a reviewer who answers it can keep a
fabrication out of the approved context. It does not show that a reviewer under time pressure
writes a considered reason rather than "ok", which the gate accepts; DEC-158 records that as its
own tradeoff. The two extractions are not comparable object-for-object either: this run produced 20
objects to the first doctored run's 25, and built no fabricated data flow or trust boundary, which
is ordinary run-to-run variance on the same model and not an effect of the flag.
