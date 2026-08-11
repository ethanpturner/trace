# Invoice Agent reviewer notes

The judgement calls behind this truth set, and how it was constructed. Nothing in this
directory is supplied to Trace during an assessment.

## Construction method

The truth set derives from `input/agent-overview.md` and nothing else. The scenario is seeded
from the GenAI Agent Security Initiative's insecure invoice-agent sample (cited by URL in
`scenarios.yaml`); its threat list arrived independently written and became
`expected-threats.yaml`, and the outcome-side files here were derived from the input document
against catalog 0.1 afterwards. Every `evidence_establishes` entry was checked against the
document by rereading the cited section; an entry that required the sample's lore rather than
the document's text was cut.

Single annotator (the project author). In place of inter-annotator agreement, the set was
re-derived from the input document after an interval without consulting the first pass;
FND-IA-01, FND-IA-02, GAP-IA-01, and the three rejections were reproduced identically, and
GAP-IA-02 was reproduced with a different paired-question wording, which the matcher does not
compare. No count is declared anywhere (DEC-028); the files enumerate what they enumerate.

## The boundary cases

**FND-IA-02 sits closest to the line.** "The schema does not enforce a maximum amount" reads
like an absence, which DEC-009 forbids building on. It qualifies as a finding because the
document affirmatively states where the ceiling *is* applied — by the agent from its
instructions, under a discretion clause — so the conclusion rests on a documented enforcement
design, not on silence. The re-derivation pass reached the same classification.

**GAP-IA-02 is deliberately not a finding.** Section 4 says submitters are not authenticated
*to the workflow*; whether an upstream system authenticates them is genuinely undetermined.
A generic review reports "no submitter authentication" as a vulnerability; the correct output
is a gap with a load-bearing question. This is the scenario's DEC-009 exercise.

**REJ-IA-02 is the scenario's counter-instinct entry.** The obvious recommendation for an
agent system is an injection-phrase filter, and the catalog names exactly that conclusion a
false positive because it is not a durable control. The genuine structural weakness is
FND-IA-01.

## What is deliberately not authored

`expected-context.yaml`, `expected-control-mappings.yaml`, and `expected-observations.yaml`
are not authored for this scenario. The outcome-side files carry the evaluation the harness
scores today (findings, gaps, questions, rejections); the context-side truth arrives if this
scenario is promoted to the depth ForgeFlow carries. Stating the omission here keeps it a
decision rather than an oversight.
