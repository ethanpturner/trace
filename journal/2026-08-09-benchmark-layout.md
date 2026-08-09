# 2026-08-09 — The layout was never the disagreement

Closes #39 as DEC-027, DEC-028 and DEC-029. The issue framed three conflicts — two layout
specifications, two spellings of one filename, and expected counts that disagreed with the scenario
document. Two of the three turned out not to be conflicts.

## The two layouts describe different halves

`evaluation-plan.md` section 5 lists `README.md`, `architecture.md`, `requirements.json`, three
`expected-*.yaml` files and `review-notes.md`. `forgeflow-scenario.md` section 25 lists seven
`expected-*.yaml` files and `reviewer-notes.md`. They look like rival specifications of one
directory.

They are not. **Section 5 describes a scenario's inputs and section 25 describes its expected
outputs.** They overlap on exactly three files and agree on all three. Neither document says which
half it covers, which is the entire defect — two partial descriptions read as two full ones.

ForgeFlow already had `input/` and `expected/` as separate directories, so the structure both
documents were half-describing was sitting on disk the whole time.

Reconciling by picking a winner would have thrown away correct information. Section 5 is the only
place saying a scenario carries its own inputs; section 25 is the only place saying the expected
files are never supplied to Trace.

## The list should not have been a list

The more useful finding is why the drift happened at all. DEC-021 added `SourceObservation`, and
neither document gained a file for it — so the evaluation contract counted two contradictions and
an injection fixture that had nowhere to live. An enumerated file list is a second source of truth
about the object model, and it fell behind the first one within a day of that object existing.

So the rule is now **one `expected-*.yaml` per domain object type the pipeline produces and the
benchmark grades**, plus the negative set. The list in the documents is what the rule produces
today, explicitly not an independent specification; where they disagree, the rule governs.

That adds `expected-observations.yaml`, which covers both of DEC-021's `kind` values, because they
are one object type and get one file.

## `requirements.json` was answered by dissolving it

DEC-010's first open question asks whether the per-scenario `requirements.json` should reference
catalog identifiers rather than restate requirement text. Both options assume the file.

DEC-024, merged this morning, removed its role. The whole catalog reaches the mapping step on every
call, so a per-scenario requirement list could only narrow what the pipeline sees — which is the
pre-filter DEC-024 rejected, arriving through the benchmark instead of the pipeline. What the file
was reaching for is a version pin, and `catalog_version` already exists.

This is the fourth time this week a question dissolved rather than resolved. It is starting to look
like a property of a corpus written faster than it was cross-read, rather than luck.

## Counts: the conflict was the format, not the numbers

The contract declared three findings and five questions; the scenario document listed four findings
and ten candidate questions. The issue asks which is right.

Neither, and the question is wrong. **A declared count that can disagree with its own enumeration is
a second source of truth** — structurally the same defect as the layout being specified twice, which
is what this issue exists to fix. And a count used as a grading target is a finding quota by another
name, which is what #18 removed from the input fixture. Moving that block out of `input/` stopped it
contaminating measurements; it did not stop it being a quota.

So the contract now declares no counts at all. The expected set is the enumerated content of the
files, and a count is `len()` of a file when a report needs one.

The test that guarded #18's fix had to invert. It used to require the `expected_outputs` block to
survive the move intact — correct then, since the concern was placement. It now requires the block
to be absent at any nesting depth. I checked that it fails when a count is reintroduced rather than
assuming it.

## FND-001 is the best thing in this benchmark and it is not a finding

DEC-013 forced the finding question and the answer is sharper than I expected.

FND-001 required evidence that "delivery identifiers are not tracked". Nothing establishes that.
`github-integration.md` says webhook requests are validated; `operations-guide.md` shows a delivery
identifier in the payload without mentioning deduplication; and `architecture-overview.md` section
26 lists **"Webhook replay handling"** under its own *Known Documentation Gaps*.

The only direct evidence is a document volunteering that the topic is undocumented. Expecting a
finding there would have graded the DEC-009 failure as correct.

It is now GAP-004, and it is the single most valuable item in the scenario. A generic review reports
an undocumented control as a missing control, and it will do so confidently here, because section 26
is about exactly the right subject. I also added "ForgeFlow lacks webhook replay protection" to the
rejected-findings list in section 22 — the conclusion most likely to be wrong should be named as
wrong.

**FND-003 survives the same test, and that contrast is worth more than either case alone.**
Retention is *also* listed in section 26, but `operations-guide.md` states a 30-day period
affirmatively. One rests on a positive statement, one on silence, and they sit two sections apart in
the same fixture.

## Open question 8, and the count that was right by accident

Whether prompt injection and automatic publishing are one finding or two: **two.** Section 19's own
consolidation test is whether remediation and impact are substantially related, and they are related
without being the same — FND-002 needs an approval gate, FND-004 needs input isolation, and fixing
either alone leaves real exposure.

The expected set records the finer decomposition deliberately, because a matcher can collapse two
into one and cannot split one into two. Trace producing a single well-reasoned combined finding is
still correct behaviour.

That leaves FND-002, FND-003, FND-004 — **three findings.** The contract's disputed 3 was right and
the scenario's 4 was right about the candidates. What drops out is FND-001, not FND-004, so both
documents were partly correct and the number was never what they disagreed about.

Documentation gaps go from three to four. Under DEC-028 nothing needs correcting, because nothing
declares the number.

## Where it strains

Two homes for scenarios is a smell, and I kept it. ForgeFlow stays at `demo/forgeflow/` because it
is the demo as well as scenario one — the 40,000-character narrative is a demo artifact and
scenarios two onward will have no equivalent. That role split is real, but the cheap reason is also
true and worth admitting: the path appears 153 times outside `demo/` and in 29 open issue bodies.

The registry is what makes it safe, and I wrote the test rather than leaving it as the open question
I had first recorded. `benchmarks/scenarios.yaml` is authoritative; directory scanning is
prohibited; a directory the registry does not name fails a test rather than silently never running.

What remains unguarded is the layout rule itself. Nothing checks that a scenario's expected files
are named correctly, because the expected files do not exist yet to check.

## Open next

Removing the counts leaves the contract declaring less than it did, and the enumerated files that
replace them are M3 and M4 work. That is a real regression in what is written down, held
deliberately.

Four M0 decisions remain: #38 (report template), #37 (severity ownership), #35 (CLI versus web), and
#19, which needs writing rather than deciding.
