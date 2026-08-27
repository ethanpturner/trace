# The differentiators, surveyed and then scored

A session in two halves. The first asked what the market had done to this project's claims while
it was being built, and found that most of them had been taken. The second built the measurement
for the one claim that had not been.

## The survey

The landscape as of August 2026 is not the one `project-scope.md` was written against. An
automated security design review category now exists and is funded: Clover Security raised $36M at
launch in November 2025 with ServiceNow as both investor and customer, Prime Security and Seezo
sell the same thing, and the established threat-modeling platforms have moved to meet them --
IriusRisk's Jeff AI accepts "Documentation, User stories, Meeting transcriptions" and
ThreatModeler's Nexus accepts design documents. Apiiro analyses feature requests and design
documents pre-code with a private model.

Four claims the corpus leaned on are consequently held elsewhere. **Design documentation as
input** is now table stakes. **Evidence citation** is marketed by Seezo in nearly this project's
own words -- "the exact logic path, the rule triggered, and the part of your input it was based
on." **Specialized agents behind deterministic validation with human review points** is what
Anthropic and OpenAI both ship, and what ThreatForest (arXiv 2607.27528) published in July as "a
directed graph with deterministic verification gates, bounded retries, and three human-in-the-loop
validation points" -- this pipeline's architecture, arrived at independently. And **a threat model
from a text description** is sold by SecureFlag and given away free by Cytix.

Three survived, and the searches that found nothing are the load-bearing evidence for them: arXiv
returns no results for "security design review", none for prompt injection against code review,
and GitHub's entire corpus for the phrase is fourteen repositories, the largest with five stars.
Abstention, published measurement, and a measured injected-instruction compliance rate.

The one price point in the category is worth recording: Seezo's AWS Marketplace listing is $27,500
for twelve months and 500 scans -- $55 a scan, against $3 to $7 a run here.

## The unpushed branch

Planning the follow-on work turned up eight commits sitting on a local branch with no remote and
no pull request: DEC-150 through DEC-153 and a journal entry, a complete session's work from the
day before. It carried the corrections the landscape doc depended on, which is how it was found --
a citation to DEC-152 that did not resolve on `develop`. Opened as #666 and merged ahead of the
new work.

## The metric

DEC-147 had already decided where a wrongly produced claim gets graded: "the rejection entry is
where that wrongness is authored and graded." Fifty rejections across fifteen scenarios, and
nothing had ever read them except a ForgeFlow-only regression test over constructed objects. No
run scored against them, no baseline shown them.

DEC-154 scores them. The reasoning that made it the right next thing rather than the obvious next
thing: the existing spurious count **conflates** inventing a weakness from silence with mapping a
real weakness to an unexpected requirement, and the negative set is the only separation the truth
sets can support, because it is the only one a person wrote down in advance. #653's own evidence
had already said which axis was worth measuring -- `missing-docs` produced zero spurious findings
in five of five runs while `reply-tuner`'s expected finding appeared in three of five. Not
inventing reproduces; recall does not.

Two constraints kept it honest rather than flattering. **Attribution is requirement-level, not
claim-level**, which over-attributes -- it can report more breaches than were committed, never
fewer, so the error runs against the tool being measured. And **`reply-tuner` is unscoreable**: it
authors `conclusion`/`suppressed_by` with no requirement, because nothing had ever loaded these
files and no schema was ever enforced on them. It renders a dash. Normalizing it is a truth-set
edit needing its own argument (DEC-149) and was deliberately left alone.

## What it said

Stratified per DEC-143, because the pooled number is the misleading one:

| Arm | Current shape (0.2) | Pre-batching (0.1) | Pooled |
| --- | --- | --- | --- |
| Generic prompt | 8/32 (25%) | 2/15 (13%) | 10/47 (21%) |
| Structured single-pass | 3/32 (9%) | 0/15 | 3/47 (6%) |
| Whole assessment, one call | 2/32 (6%) | 0/15 | 2/47 (4%) |
| Trace | **2/32 (6%)** | 3/15 (20%) | 5/47 (11%) |

On the current shape the pipeline breaches a quarter of what the generic prompt does and ties the
strongest baseline; on `common_false_positives`, where the catalog names the trap outright, it
breaches 0 of 14 against the generic prompt's 5. That is the first metric on which the pipeline
clearly beats the generic baseline on the current shape while matching the structured ones.

The pooled row is worse than both structured baselines and is published as measured. Three of the
five breaches are the two pre-batching rows carrying DEC-116's funnel. The rest concentrate in
`no_evidence` -- 4 of 22, against 1 for each structured baseline -- which is silence resolving to
an assertion, DEC-009's failure in its purest form, and two of those four are `crypto-wallet`,
whose truth set expects no findings at all.

That last paragraph is the point. A metric built to make a project look good would not have been
built this way, and the number it produced is one this project now has to answer for.

## Open next

- **`--condition` for `trace capture`** (DEC-152's named work), then the two live adversarial
  captures. The plumbing costs nothing; the captures cost about $6 and need approval.
- **#653**, the truth-set reconciliation, which needs a decision and possibly keyed spend.
- **The narrative documents** still lead with differentiators the survey found to be table stakes.
  Repositioning them waits on having the new numbers to lead with, which #667 now supplies.
- **#648**, the scorecard-currency check that is not a required status check, so a stale
  evaluation page can still merge silently. Filed, small, and directly against the one
  differentiator that survived.
- **`reply-tuner`'s rejection schema**, whose normalization DEC-154 deliberately deferred.
