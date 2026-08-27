# Trace — Competitive Landscape

**Project:** Trace

**Subtitle:** Context-Aware Security Architecture Analysis

**Document version:** 0.1

**Status:** Proposed

**Last updated:** 2026-08-27

## 1. Purpose

This document records who else builds what Trace builds, as of August 2026, and which of the
project's stated differentiators survive contact with that market.

It exists for two reasons. The first is that roadmap Stage 6 and
[interview-package.md](interview-package.md) both require an answer to "who else does this," and
the corpus did not carry one. The second is that a differentiator is a claim about other
systems as much as about this one, and a claim about other systems decays. Every finding below
carries a date and a source so that a later reader can tell what has aged.

The survey was conducted on 2026-08-26 and 2026-08-27 by search and by direct retrieval of
vendor material, product documentation, funding records, and the arXiv API. Where a fact could
not be verified it is marked unverified rather than omitted.

## 2. Method and its limits

Four of the six planned research streams were interrupted and completed by direct retrieval
instead of search. The consequence is uneven depth, and it is stated here rather than hidden:

- Threat-modeling platforms, AI-native open source, recent entrants, and the published
  evaluation literature are covered in depth.
- Application security posture management vendors and AI code-review agents are covered
  thinly. Several vendor sites refuse automated retrieval.

For the thin categories, absence of a finding is not evidence of absence.

## 3. What the market now sells

An automated security design review category exists and is funded. It did not exist when this
project's scope was written.

| Company | Raised | Input | Evidence |
| --- | --- | --- | --- |
| Clover Security | $36M at launch, November 2025 | Design documents, code, product specifications, architecture | clover.security; Notable Capital, Team8, SVCI, Wiz founders, Shlomo Kramer; ServiceNow invested March 2026 |
| Prime Security | Undisclosed | Confluence, Google Drive, Jira, Miro, SharePoint, alongside repositories | primesec.ai; Foundation Capital, Flybridge, Scale Venture Partners |
| Seezo | $7M, Accel-led, autumn 2025 | Product requirement documents, Jira epics, Confluence, Google Docs | seezo.io; AWS Marketplace |
| Oplane | EUR 4.5M seed, June 2026 | Repositories only; architecture is derived from code | oplane.io |

Named customers are published for the first three: HubSpot, Expedia, Notion, Plaid and
ServiceNow for Clover; PayPal, Elastic, Bumble, Qualtrics and Oscar for Prime; Razorpay for
Seezo.

The established threat-modeling platforms have moved in the same direction. IriusRisk's Jeff AI
is generally available and accepts, in the vendor's own words, "virtually any textual
representation including: A simple written out statement, Documentation, User stories, Source
code, Meeting transcriptions, SBOMs." ThreatModeler has rebranded to threatmodeler.ai and its
Nexus product accepts design documents alongside diagrams, infrastructure as code and cloud
configuration. Apiiro analyses feature requests and design documents before code is written,
using a private model.

Two consolidations are worth recording. `devici.com` now redirects to
`securitycompass.com/devici`, which indicates that Security Compass has absorbed Devici; the
terms and date are unverified. `clearlyai.com`, previously an entrant in this category,
redirects to a domain-for-sale page.

## 4. Differentiators that no longer differentiate

Four claims the corpus has leaned on are now held by other products. They remain correct
descriptions of Trace. They are no longer distinguishing, and leading with them invites a
reviewer to name a funded company that also has them.

**Design documentation as input.** Held by Seezo, Prime Security, Clover, Apiiro, IriusRisk,
ThreatModeler and SecureFlag's ThreatCanvas.

**Evidence citation and traceability.** Held by Seezo, which markets it in nearly the terms this
project uses: "a full decision tree for every requirement: the exact logic path, the rule
triggered, and the part of your input it was based on," described as fully traceable and
audit-ready.

**Specialized agents behind deterministic validation, with human review points.** Anthropic's
Claude Security is a multi-agent system that maps architecture, identifies threats, verifies
findings to reduce false positives, and proposes patches. OpenAI's Codex Security occupies the
same shape. ThreatForest (arXiv 2607.27528, July 2026) describes an academic system as "a
directed graph with deterministic verification gates, bounded retries, and three human-in-the-
loop validation points," which is this pipeline's architecture arrived at independently.

**Generating a threat model from a text description.** SecureFlag's ThreatCanvas does it
commercially; Cytix does it without charge.

## 5. Differentiators that survive

Three claims were not found in any product, vendor publication, or paper reviewed.

### Abstention

No surveyed vendor markets the ability to decline. The category markets the opposite: Prime
Security and Clover Security both headline complete coverage. The nearest academic work,
ASTRAL (arXiv 2604.05674, April 2026), addresses incomplete architecture documentation by
reconstructing the missing architecture, and does not distinguish an undocumented control from
an absent one.

That distinction is DEC-009, and it is the project's oldest binding constraint. It appears to be
unclaimed.

### Published measurement

No vendor surveyed publishes precision or recall. Vendor claims take the form of capacity
multiples and coverage percentages without denominators. The academic position is thinner still:
an arXiv search for "security design review" returns no results, and across roughly forty recent
papers on language models and threat modeling, two evaluate output against ground truth.

Trace publishes per-scenario precision and recall against authored truth sets, three
single-prompt baselines, an ablation set and an adversarial condition. The numbers are currently
weak. The fact that they exist, and are reproducible offline, is the differentiator.

### Measured resistance to injected instructions

An arXiv search for prompt injection against code review returns no results. Anthropic's own
security review action states in its documentation that it is not hardened against prompt
injection and should only review trusted changes.

Trace's fence is designed to hold, and its compliance rate is reported per payload class in
[comparison.md](../eval/comparison.md). The zero currently rests on authored recordings: no model
has been run against a poisoned document in either scored condition, because `trace capture` takes
a scenario and a stage and has no condition parameter. DEC-152 records that distinction and makes
the page say which kind of zero it is showing. Capturing the adversarial condition against a live
model is open work, and until it lands the figure states what a correct run was expected to do
rather than what one did.

### Local operation

Every commercial product surveyed is delivered as a service. IriusRisk offers an on-premises
deployment; none offers operation without a provider. Trace runs on one machine, and
`--model-profile offline-fake` runs the pipeline without a provider at all. This is a deployment
property rather than a capability, and the market for it is small.

## 6. Price

One price point is published in this category. Seezo's AWS Marketplace listing is $27,500 for a
twelve-month contract covering 500 scans, which is $55 per scan, delivered as a service.

A Trace assessment run costs roughly $3 to $7 in provider charges and runs locally
(`docs/eval/live-stability.json`). The comparison is not like for like — a scan and an
assessment are not the same unit of work, and Trace carries no support, integration or
service obligation — but it is the only external price anchor available.

## 7. Whether a frontier model removes the need for the pipeline

The published evidence says the scaffold still earns its cost, and says nothing about this
project's specific task.

- Frontier models over-predict. "Are Frontier LLMs Ready for Cybersecurity?" (arXiv 2605.23243,
  May 2026) evaluated six frontier models and reports that "every frontier model produces
  10-50% false positive rates in white-box detection, systematically over-predicting
  vulnerabilities," with ground-truth coverage of 4-8% on black-box testing. Its conclusion is
  that "methodology, not scale, is the primary lever."
- Structure raises precision. A schema-constrained, rule-validated pipeline reached 0.58
  precision against 0.29 for human analysts on security annotation (arXiv 2608.14370,
  August 2026).
- Repository access is not security competence. A survey of 373 studies (arXiv 2608.21107,
  August 2026) concludes that "repository access improves engineering tasks but does not
  establish security."
- The scaffolded state of the art is not strong. ThreatForest scores 0.63 to 0.68 on its own
  sixteen-dimension rubric.

Against that, the scaffold is no longer scarce. Anthropic's security guidance plugin runs a
separate review model with fresh context on every turn, at no additional charge on all plans,
and its documentation states that it "does not ask the same Claude instance that wrote the code
to grade itself." The reference harness that Anthropic published carries a threat-modeling skill
whose stated rationale is that a threat model reduces false positives.

The honest reading is that the architecture is defensible and unremarkable, and that no
published evaluation measures a frontier model on security review of design documentation in
either direction. That gap is the reason the evaluation harness matters more than the pipeline
shape.

## 8. What this changes

The pipeline does not change. The claims do.

1. Abstention becomes the leading claim, and requires a metric that isolates it. The current
   comparison reports spurious findings as one number, which mixes inventing a weakness from
   silence with mapping a real weakness to an unexpected requirement (DEC-148).
2. The adversarial condition needs to be captured against a live model rather than authored, so
   that the injected-instruction figure measures a defence rather than an expectation.
3. Design-document input, evidence citation, validation gates and human checkpoints move from
   differentiators to requirements, described as what the system does rather than what makes it
   unusual.

## 9. A name collision

arXiv 2606.22214 (June 2026) is "TRACE: A Threat Modelling Methodology for Distributed,
Cloud-First, and Decentralized Organisations." It proposes threat actors, assets and trust edges
as "first-class, evidence-linked objects" and "human-AI co-working in which language models
accelerate coverage while senior reviewers retain judgement over invariants, severity, and
collusion." It carries no implementation and its author records empirical validation as an open
question.

The overlap is independent and was discovered during this survey. It is recorded here because a
reader who finds it should find it acknowledged.

## 10. Sources

Vendor and product material, retrieved 2026-08-26 and 2026-08-27:

- Clover Security — https://www.clover.security/ and https://www.clover.security/news
- Prime Security — https://www.primesec.ai/platform and https://www.primesec.ai/resources
- Seezo — https://seezo.io/ and https://aws.amazon.com/marketplace/pp/prodview-clxugwcqh2r5o
- Oplane — https://www.oplane.io/
- IriusRisk Jeff AI — https://www.iriusrisk.com/ai-threat-modeling
- ThreatModeler Nexus — https://www.threatmodeler.ai/
- Apiiro — https://cybersectools.com/tools/apiiro-ai-powered-risk-detection
- Anthropic Claude Security — https://www.securityweek.com/anthropic-unveils-claude-security-to-counter-ai-powered-exploit-surge/
- Anthropic security guidance plugin — https://code.claude.com/docs/en/security-guidance
- Anthropic security review action — https://github.com/anthropics/claude-code-security-review
- OpenAI Aardvark and Codex Security — https://openai.com/index/introducing-aardvark/

Literature:

- Are Frontier LLMs Ready for Cybersecurity? — https://arxiv.org/abs/2605.23243
- ThreatForest — https://arxiv.org/abs/2607.27528
- ASTRAL, From Incomplete Architecture to Quantified Risk — https://arxiv.org/abs/2604.05674
- Hybrid LLM security annotation — https://arxiv.org/abs/2608.14370
- LLMs at the intersection of software engineering and software security — https://arxiv.org/abs/2608.21107
- TRACE threat modelling methodology — https://arxiv.org/abs/2606.22214

Searches that returned nothing, recorded because the absence is load-bearing:

- arXiv, `all:"security design review"` — no results
- arXiv, `abs:"threat model" AND abs:"design document"` — no results
- arXiv, `abs:"prompt injection" AND abs:"code review"` — no results
- GitHub, `"security design review"` — fourteen repositories, the largest with five stars
