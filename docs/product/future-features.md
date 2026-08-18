# Trace — Future Features

**Project:** Trace

**Subtitle:** Context-Aware Security Architecture Analysis

**Document version:** 0.1

**Status:** Proposed

**Last updated:** 2026-08-05

## 1. Purpose

This document captures product ideas that are intentionally outside the active Trace roadmap.

Its purpose is to:

- Preserve useful ideas
- Reduce distraction
- Prevent premature implementation
- Separate product possibilities from current commitments
- Record why ideas are promoted, deferred, or rejected

An item appearing here is not a promise to build it.

Features should remain here until the core Trace thesis has been demonstrated:

Approved context and evidence can produce more defensible security analysis with fewer false positives than a generic AI security review.

## 2. Feature Status

Each future feature may use one of the following statuses:

| Status | Meaning |
|---|---|
| Idea | Captured but not evaluated |
| Research | Requires investigation or experimentation |
| Candidate | Potentially valuable and sufficiently understood |
| Deferred | Valuable, but intentionally postponed |
| Rejected | Not aligned with Trace or not worth the complexity |
| Promoted | Moved into the active roadmap |

Most items in this document should remain Idea or Deferred.

# 3. Repository and Developer Workflow Integrations

## 3.1 GitHub Repository Ingestion

**Status:** Built (DEC-132, issue #597)

`trace source add-repo` fetches an allowlisted, loader-readable file set from a named repository
at a pinned full-SHA commit — read-only, the commit as the capture identity, fetched content
entering as untrusted source documents through the existing boundary, and a configured token
confined to the clone subprocess. The deferral's stated condition below was met by the parser
family, PDF ingestion, and the lineage walk; the threat model's source-document boundary carries
the channel's transport rows.

The original sketch — allow Trace to ingest repository documentation and selected configuration files directly from GitHub.

Possible inputs include:

- README files
- Architecture documents
- CODEOWNERS
- Workflow files
- Infrastructure configuration
- Security policies
- Dependency metadata

This should not be added until local document ingestion and evidence traceability are reliable.

## 3.2 Pull-Request Analysis

**Status:** Idea

Analyze architecture-relevant changes in pull requests and determine whether an existing assessment should be updated.

Potential use cases include:

- New internet-facing endpoints
- New third-party integrations
- Authentication changes
- Data-store changes
- Privilege changes
- CI/CD changes
- New AI capabilities

The feature should focus on meaningful architecture changes rather than acting as another generic code-review bot.

## 3.3 GitHub Actions Integration

**Status:** Idea

Allow a GitHub Actions workflow to initiate or update a Trace assessment.

Possible behaviors include:

- Validate assessment artifacts
- Run benchmark evaluations
- Generate an assessment diff
- Comment with unresolved questions
- Publish a review artifact

Trace should not initially block a pipeline based on unreviewed model output.

## 3.4 Design-Review Checks

**Status:** Idea

Provide a lightweight check during software design or architecture review.

The check could identify:

- Missing critical context
- Unresolved high-priority questions
- Changed trust boundaries
- Unverified high-impact controls
- Required human approvals

The goal would be to improve review readiness, not automatically approve designs.

## 3.5 Developer-Facing Security Guidance

**Status:** Idea

Present contextual security guidance inside developer workflows.

Guidance might include:

- Why a control applies
- Acceptable implementation patterns
- Evidence required for validation
- Existing approved platform capabilities
- Examples of secure alternatives

Guidance should be based on approved requirements and architecture context rather than generic recommendations.

# 4. Continuous Architecture Analysis

## 4.1 Assessment Diffing

**Status:** Built (DEC-097, issue #488)

`trace diff <before> <after>` compares two assessments' approved models: added, removed, and
changed per object family, identity matched by content fingerprint rather than per-assessment
identifiers, threats and gaps compared by ground and never force-paired. Stale-evidence and
trend analysis (4.4, 4.5) remain future work.

The original sketch: compare two assessment versions and identify meaningful changes.

Possible outputs include:

- Added or removed components
- Changed data flows
- New trust boundaries
- Changed controls
- Resolved or reopened questions
- New findings
- Findings no longer supported
- Stale evidence

This is one of the strongest potential extensions because it builds directly on Trace’s structured data model.

## 4.2 Architecture Change Detection

**Status:** Idea

Detect changes in source documentation, repository metadata, or external evidence that may affect the architecture baseline.

Trace should distinguish between:

- Editorial changes
- Documentation improvements
- Material architecture changes
- Control changes
- New uncertainty

## 4.3 Continuous Assessment

**Status:** Deferred

Maintain an assessment as a living product-security artifact rather than a point-in-time report.

A continuous assessment might update when:

- Architecture changes
- Controls change
- Evidence expires
- Requirements change
- New dependencies are introduced
- Risk is accepted or remediated

This requires reliable change detection and strong protection against alert fatigue.

## 4.4 Stale-Evidence Detection

**Status:** Idea

Identify evidence that may no longer support a conclusion.

Examples include:

- Old screenshots
- Superseded configuration
- Removed documentation
- Changed platform guarantees
- Retired controls
- Expired reviewer confirmation

Trace should not continue presenting a conclusion as current when its supporting evidence is stale.

## 4.5 Risk Trend Analysis

**Status:** Idea

Show how an application’s risk posture changes over time.

Potential measurements include:

- Open findings
- Resolved findings
- Unverified controls
- Documentation gaps
- Evidence age
- Reopened risks
- Reviewer acceptance trends

Trend analysis should not reduce complex risk to a misleading single score.

# 5. Organizational Context and Control Inheritance

## 5.1 Organizational Control Catalog

**Status:** Built (DEC-115 and DEC-122, issues #528 and #568)

A deliberate v0 shipped with DEC-115: a flat, version-controlled `org-controls/` catalog read by
its own loader, a fourth structured parser, and existence-only assertions — an organizational
control enters context as a documented claim, never as authority. The oidc-portal scenario
asserts `enterprise-idp-mfa` from its first commit. DEC-122 filled in what v0 stated as gaps:
catalog 0.2 is the operator fact set, each control carries `references` — pointers to
organizational documentation, riding in the seeded claim's value, never authority — and the
fifteenth scenario (nightly-reconciler) measures the suppression the sketch promised: two
false positives a generic review raises, answered by asserted organizational facts. The
inheritance graph is 5.2 and stays Research.

The original sketch — maintain a reusable catalog of organization-wide controls.

Examples include:

- Enterprise identity
- Managed database encryption
- Central logging
- Secrets management
- Endpoint protection
- Network segmentation
- Approved CI/CD platforms

This would allow Trace to recognize controls that are not repeated in every application document.

## 5.2 Control Inheritance Graph

**Status:** Research

Model how controls flow from platforms and shared services to dependent applications.

The model may need to represent:

- Control provider
- Protected systems
- Inheritance conditions
- Exceptions
- Validation evidence
- Control limitations
- Ownership
- Expiration

This is strategically important but could add substantial data-model complexity.

## 5.3 Approved Architecture Patterns

**Status:** Idea

Represent approved implementation patterns that satisfy groups of security requirements.

Examples include:

- Enterprise OIDC integration
- Approved webhook-validation pattern
- Standard managed-database deployment
- Approved secrets-delivery pattern
- Standard service-to-service authentication

Pattern matching should remain evidence-based and should not assume a control is correctly implemented merely because a technology is named.

## 5.4 Technology-Specific Requirement Packs

**Status:** Idea

Create focused requirement collections for technologies such as:

- Kubernetes
- GitHub Actions
- Cloud object storage
- Webhooks
- OAuth and OIDC
- APIs
- AI model integrations
- Managed databases

Requirement packs should improve relevance without recreating rigid checklists.

## 5.5 Organizational Exceptions

**Status:** Deferred

Represent approved exceptions, compensating controls, and risk acceptances.

This may include:

- Scope
- Owner
- Approval
- Expiration
- Compensating controls
- Affected requirements
- Review conditions

This feature requires governance and access-control capabilities outside the initial MVP.

# 6. Evidence Integrations

## 6.1 Cloud Configuration Evidence

**Status:** Idea

Retrieve selected cloud configuration to validate architecture claims.

Examples include:

- Encryption settings
- Network exposure
- Identity configuration
- Logging
- Backup configuration
- Public-access settings

Cloud configuration should be treated as evidence, not as a replacement for architecture reasoning.

## 6.2 CI/CD Configuration Evidence

**Status:** Idea

Inspect pipeline configuration for evidence related to:

- Secret handling
- Workflow permissions
- Artifact integrity
- Deployment approvals
- Identity federation
- Third-party actions
- Branch protections

The initial implementation should be read-only.

## 6.3 Identity-System Evidence

**Status:** Idea

Validate identity-related claims using configuration from:

- OIDC providers
- Cloud IAM
- Application authorization systems
- Service identities
- Privileged-access systems

This would require strict access controls and careful handling of sensitive information.

## 6.4 Vulnerability and Scanner Evidence

**Status:** Idea

Use outputs from existing security tools as evidence.

Possible sources include:

- Static analysis
- Dependency scanning
- Container scanning
- Cloud security tools
- Dynamic testing
- Penetration-testing reports

Trace should correlate scanner results with architecture context rather than duplicating scanning capabilities.

## 6.5 Ticketing-System Evidence

**Status:** Idea

Connect findings and remediation status to ticketing systems.

Possible capabilities include:

- Create remediation tickets
- Track status
- Link evidence
- Record acceptance
- Detect stale remediation
- Update assessment state

Automated ticket creation should require human approval to avoid generating operational noise.

## 6.6 Evidence Expiration Policies

**Status:** Research

Allow evidence types to have different expected lifetimes.

Examples:

- Reviewer confirmation
- Architecture documents
- Configuration snapshots
- Scanner results
- Platform attestations
- Risk acceptances

Expiration policies could help prevent conclusions from relying on outdated information.

# 7. Analysis Capabilities

## 7.1 Source-Code Analysis

**Status:** Deferred

Analyze selected source code for evidence related to architectural controls.

Trace should not attempt to replace mature static-analysis products.

Potential use cases include validating:

- Webhook signature checks
- Authorization enforcement
- Encryption usage
- Input validation
- Secret retrieval
- Audit logging

This feature should be narrow and evidence-oriented.

## 7.2 Infrastructure-as-Code Analysis

**Status:** Built (DEC-113, DEC-121, DEC-124, and DEC-128; issues #525, #569, #593, and #594)

DEC-113 shipped the first member: a Terraform JSON parser, corpus-measured, reading stated
booleans as documented claims. DEC-121 added HCL syntax through a deterministic subset scanner
and put the attribute table under a coverage rule — literal boolean, self-contained meaning,
both directions meaningful — which admitted `encrypted` and `deletion_protection` beside the
first pair. DEC-124 added CloudFormation — JSON plus tag-free YAML, the syntax boundary the
loader's own safe-parse rule — under the same table in CloudFormation's spelling. DEC-128
closed the sketch with Kubernetes manifests: a deliberate kind allowlist, multi-document
streams admitted at the loader, and container-level attributes read uniformly or not at all.
The parsing-over-model-analysis instinct below held: technology-specific parsing is what was
built. DEC-130 widened the admission rule once, deliberately — closed-vocabulary strings join
stated booleans — and closed cross-resource reading permanently: no IaC parser derives a claim
from more than one resource declaration.

The original sketch — analyze Terraform, CloudFormation, Kubernetes manifests, or similar artifacts for architecture and control evidence.

Potential outputs include:

- Components
- Data stores
- Network boundaries
- Public exposure
- Identities
- Encryption
- Secrets
- Dependencies

This could strengthen context extraction, but technology-specific parsing may be more reliable than model-only analysis.

## 7.3 Architecture Diagram Analysis

**Status:** Built in part (DEC-129, issue #599)

The first slice shipped without a vision model: the Mermaid DFD dialect `trace export mermaid`
emits parses back deterministically as the DEC-070 family's sixth member — components, flows,
and trust-boundary membership entering as documented claims, decided at checkpoint 1. Both of
the sketch's constraints held by construction: a diagram-versus-prose disagreement surfaces as
a cross-claim observation, and a parser that only proposes cannot override anything. Hand-drawn
diagrams in the wild — and any format needing vision — stay Research.

The original sketch — extract components, flows, and trust boundaries from architecture diagrams.

The feature would need to reconcile diagram content with written documentation and surface contradictions.

Diagram interpretation should not silently override structured or textual evidence.

## 7.4 Attack-Path Analysis

**Status:** Idea

Connect multiple threats, components, identities, and trust boundaries into longer attack paths.

This may help identify risks that appear minor individually but become significant when chained.

The feature should avoid creating dramatic but implausible attack graphs.

## 7.5 Abuse-Case Generation

**Status:** Idea

Generate business-logic and misuse scenarios that extend beyond basic technical threat categories.

Examples include:

- Repository access abuse
- Administrative workflow abuse
- Approval bypass
- Data-export misuse
- Resource-consumption abuse
- Tenant-boundary abuse

## 7.6 Remediation Alternative Analysis

**Status:** Idea

Compare multiple approaches for reducing a risk.

Possible outputs include:

- Preventive controls
- Detective controls
- Compensating controls
- Platform solutions
- Application changes
- Process changes

Trace should not recommend changes without considering architecture constraints and existing controls.

## 7.7 Automatic Severity Calculation

**Status:** Research

Provide more structured severity support using:

- Impacted assets
- Exposure
- Preconditions
- Existing controls
- Scope
- Business criticality
- Evidence quality

Final severity should remain subject to reviewer judgment.

# 8. AI-Specific Capabilities

## 8.1 AI System Threat-Modeling Pack

**Status:** Built (DEC-098 and DEC-114, issues #489 and #531)

The pack arrived in three waves: ai-input-handling and agentic-orchestration with DEC-058;
retrieval-augmentation (req-RAG-001..003) and model-generated-code (req-CODEGEN-001..002) with
DEC-098, alongside the rag-support-bot benchmark scenario; and the fine-tuning category
(req-TRAIN-001..003) with DEC-114 in catalog 0.3, alongside the reply-tuner scenario. DEC-114
completes the sketch below — every row has requirements and a measuring scenario.

The original sketch — add threat patterns and requirements specifically for systems using:

- LLM APIs
- Retrieval-augmented generation
- AI agents
- Tool calling
- Model-generated code
- External model providers
- Fine-tuning data

This aligns strongly with the initial Trace demonstration and speaking topic.

## 8.2 Agent Permission Analysis

**Status:** Idea

Analyze what data and tools an AI agent can access.

Potential concerns include:

- Excessive permissions
- Unsafe tool combinations
- Untrusted instructions
- Data exfiltration
- Indirect prompt injection
- Cross-user contamination
- Unbounded actions

## 8.3 Prompt and Policy Analysis

**Status:** Research

Evaluate model prompts and agent policies for security weaknesses.

Potential checks include:

- Trusted and untrusted content separation
- Tool-authorization boundaries
- Sensitive-data handling
- Output validation
- Injection resistance
- Conflicting instructions

Prompt analysis should supplement, not replace, runtime controls.

## 8.4 AI Evidence Provenance

**Status:** Idea

Track whether assessment information came from:

- Original source documents
- User input
- External retrieval
- Model inference
- Another agent
- Reviewer confirmation

This could make model-derived claims easier to distinguish from real evidence.

## 8.5 Model Risk Comparison

**Status:** Research

Compare model providers or model versions for:

- Structured-output reliability
- Unsupported claims
- Prompt-injection resistance
- Security reasoning
- Cost
- Latency
- Consistency

Model comparisons should use the versioned benchmark suite.

# 9. Evaluation and Research Capabilities

## 9.1 Evaluation Dashboard

**Status:** Built in part (DEC-076)

DEC-076's first form is built (issue #271): a static HTML scorecard generated deterministically
from the harness's results feeds by `scripts/build_scorecard.py`, regenerated and checked by CI
from recorded runs, metrics-only and never carrying assessment content, committed at
`docs/eval/scorecard.html`. The fuller live dashboard below remains a candidate.

Display evaluation metrics across workflow and prompt versions.

Potential views include:

- False positives
- False negatives
- Evidence coverage
- Reviewer acceptance
- Reviewer edits
- Duplicate findings
- Runtime
- Cost
- Model calls
- Regression results

This should be added after the underlying metrics are reliable.

## 9.2 Workflow Ablation Testing

**Status:** Built (issue #270)

The harness applies the section-14 ablations (evidence validation, critical review, context
approval) harness-side per DEC-012, marks each ablated run non-authoritative (DEC-031), and
`trace evaluate --ablation-set` reports what each removal changes at the finding level — the
DEC-012 decision gate answered per scenario. The restructuring ablation's first member is built:
DEC-126's `baseline-single-pass` prices the whole agent set against one combined-schema call
(issue #592; its recording and live pair ride the keyed capture step). Remaining from the
sketch: the per-stage-schemas-in-sequence variant that isolates decomposition from iteration.

Compare the full Trace workflow with individual stages removed.

Examples:

- Without context review
- Without control mapping
- Without evidence validation
- Without the critic
- Without human finding review

This would help determine which workflow stages create measurable value.

## 9.3 Multi-Model Evaluation

**Status:** Idea

Run the same benchmark scenarios against multiple model configurations.

The goal is to identify the simplest and least expensive model configuration that meets quality targets.

## 9.4 Reviewer-Time Measurement

**Status:** Research

Measure whether Trace actually reduces reviewer effort.

Possible metrics include:

- Time to understand architecture
- Time to approve context
- Time to review findings
- Time to produce report
- Number of manual corrections
- Number of follow-up meetings

This may become one of the most important product-value measurements.

## 9.5 Reviewer Agreement Analysis

**Status:** Research

Compare how multiple reviewers assess the same output.

This could help distinguish model-quality problems from normal differences in professional judgment.

## 9.6 Benchmark Sharing

**Status:** Idea

Publish selected synthetic benchmark scenarios for broader evaluation and community contributions.

Public benchmarks must remain:

- Fictional
- Independently authored
- Free from employer-derived content
- Clear about expected-answer limitations

# 10. Collaboration and Governance

## 10.1 Multi-Reviewer Collaboration

**Status:** Deferred

Allow multiple reviewers to work on one assessment.

Potential capabilities include:

- Assigned review sections
- Comments
- Conflicting decisions
- Approval workflows
- Reviewer identity
- Decision history

This requires authentication, authorization, and concurrency controls.

## 10.2 Engineering-Team Collaboration

**Status:** Idea

Allow system owners to answer questions, provide evidence, and comment on findings without giving them full security-review authority.

## 10.3 Approval Workflows

**Status:** Deferred

Support formal approval for:

- Architecture context
- Findings
- Severity
- Risk acceptance
- Exceptions
- Final reports

The MVP requires only one local reviewer.

## 10.4 Remediation Tracking

**Status:** Idea

Track a finding through:

- Proposed
- Approved
- Assigned
- In progress
- Mitigated
- Verified
- Closed
- Risk accepted

Trace should not become a general-purpose project-management tool.

## 10.5 Risk Acceptance

**Status:** Deferred

Record:

- Accepted risk
- Rationale
- Owner
- Approver
- Expiration
- Compensating controls
- Review date

This would require stronger governance and access control.

## 10.6 Audit and Compliance Exports

**Status:** Idea

Produce evidence packages that show:

- What was reviewed
- Which evidence was used
- Which conclusions were accepted
- Who approved them
- Which requirements were evaluated
- What changed over time

Exports should reflect actual assessment evidence rather than generating superficial compliance claims.

# 11. Enterprise Platform Capabilities

## 11.1 Enterprise Authentication

**Status:** Deferred

Support organizational identity providers and strong authentication.

Potential mechanisms include:

- OIDC
- SAML
- Enterprise SSO
- Multi-factor authentication

## 11.2 Role-Based Access Control

**Status:** Deferred

Define permissions for:

- Reviewers
- Engineering teams
- Administrators
- Risk owners
- Auditors
- Read-only users

## 11.3 Multi-Tenant Isolation

**Status:** Deferred

Support separation among organizations, teams, or business units.

This would require major changes to:

- Identity
- Authorization
- Storage
- Logging
- Encryption
- Data deletion
- Model-provider isolation

## 11.4 Cloud Deployment

**Status:** Deferred

Deploy Trace as a managed service.

This would introduce requirements for:

- Secure authentication
- Secrets management
- Encryption
- Availability
- Observability
- Backup and recovery
- Data residency
- Tenant isolation
- Incident response

## 11.5 Enterprise Search and Retrieval

**Status:** Idea

Retrieve context from approved organizational sources such as:

- Architecture repositories
- Internal standards
- Service catalogs
- Control catalogs
- Cloud inventories
- Ownership systems

Retrieval permissions must match the user’s access and prevent cross-project disclosure.

## 11.6 Data-Retention Controls

**Status:** Deferred

Allow organizations to define:

- Retention periods
- Deletion policies
- Model-response retention
- Trace retention
- Evidence expiration
- Export restrictions
- Legal holds

# 12. Policy and Automation

## 12.1 Policy-as-Code Integration

**Status:** Idea

Use deterministic policy engines for controls that can be evaluated reliably.

Possible tools or formats might support:

- Requirement applicability
- Evidence thresholds
- Approval gates
- Prohibited configurations
- Organizational exceptions

Policy-as-code should complement contextual analysis rather than forcing all security judgment into rigid rules.

## 12.2 Automated Release Gating

**Status:** Rejected for MVP

Automatically block software delivery based on Trace output.

This is rejected for the MVP because:

- Findings remain model-assisted
- Human judgment is required
- Evidence may be incomplete
- False positives could disrupt delivery
- The project has not demonstrated sufficient reliability

This may be reconsidered only for narrow deterministic conditions.

## 12.3 Automated Remediation

**Status:** Deferred

Propose or apply changes intended to resolve approved findings.

Initial versions, if pursued, should be limited to:

- Drafting remediation guidance
- Generating suggested configuration
- Preparing a pull request for review
- Creating a ticket

Trace should not autonomously modify production systems.

## 12.4 Automated Evidence Requests

**Status:** Idea

Generate targeted requests for missing evidence and route them to the appropriate owner.

The feature would need to avoid generating excessive or low-value requests.

# 13. Presentation and Reporting

## 13.1 Interactive Finding Lineage

**Status:** Built (DEC-078, DEC-108 amendment; issues #276, #572, #600)

Delivered in three forms. The localhost view (issue #276, DEC-078) renders finding lineage from
persisted objects over stdlib `http.server`, GET-only and read-only; #572 made the walk
clickable hop by hop down to the highlighted source span, with live re-verification at the
evidence leaf; and #600 made it portable — the nine-hop walk travels in the DEC-108 HTML report
as an expandable appendix per approved finding, so the chain survives the server stopping. The
walk ends at the same hash verification the CLI offers in every form.

Provide a visual “Why was this generated?” view.

It should show:

Evidence

→ Context

→ Threat

→ Requirement

→ Control

→ Evidence Assessment

→ Critique

→ Reviewer Decision

→ Finding

This is likely valuable for both the demo and eventual product.

## 13.2 Architecture Visualization

**Status:** Built (DEC-072 amendment, issue #503)

`trace export mermaid` renders the approved architecture as a deterministic Mermaid DFD —
components, actors, labelled flows, trust boundaries as subgraphs — derived from
reviewer-approved state and nothing else. Interactive or styled visualization beyond the
diagram source remains future work.

The original sketch follows.

Render components, data flows, assets, and trust boundaries from the approved structured context.

The visualization should reflect reviewer-approved state rather than raw model output.

## 13.3 Assessment Comparison Report

**Status:** Built (DEC-103, issue #509)

`trace diff --report` renders the structural diff (DEC-097) as a Markdown comparison report in
the later assessment's outputs area — findings and open questions first, context after, so the
things that change a conclusion lead. An output artifact like the exports; DEC-035's report
contract is untouched.

The original sketch: generate a human-readable summary of changes between assessment versions.

## 13.4 Executive Reporting

**Status:** Idea

Create a concise leadership-oriented report focused on:

- Material risks
- Business impact
- Major changes
- Unresolved decisions
- Remediation priorities
- Risk trends

The executive report must remain traceable to the technical assessment.

## 13.5 Export Formats

**Status:** Built in part (DEC-072 family; DEC-108)

Markdown remains the report's only authoritative format. DEC-072 separates *exports* from
report formats, and the family is delivered: TM-BOM (issue #383), SARIF (issue #487), and the
standalone Mermaid DFD (issue #503) all ship as deterministic serializers over approved
objects; CycloneDX for the catalog stays deferred until a consumer exists. No export contains
prose or a model call. DEC-108 (issue #527) added HTML rendering as a derived view of the
Markdown report — a rendering, not a second format. The family's last open question is closed:
TM-BOM round-trips as input through the DEC-070 parser family (DEC-120, issue #573), with the
schema's conservative booleans refused as negatives on the way back in.

Still ideas, not decided: PDF, ticketing-system formats, audit packages, and any
executive-report format.

# 14. Potential Research Questions

The following questions require investigation before becoming product commitments.

1. Can structured context materially improve threat recall as well as precision?
2. Which requirements can be evaluated deterministically?
3. How should inherited controls be represented at organizational scale?
4. Can evidence expiration be automated reliably?
5. Which reviewer edits provide the strongest signal for workflow improvement?
6. Does a critical-review agent improve quality enough to justify cost?
7. Should threat generation operate by component, asset, trust boundary, or system?
8. Can small models perform narrow validation tasks as well as larger models?
9. How should contradictory evidence be ranked without hiding disagreement?
10. Can Trace reduce total review time without increasing reviewer fatigue?
11. Which explanation format produces the highest reviewer trust?
12. How stable are results across repeated runs?
13. When is a documentation gap itself a material security risk?
14. How can agent permissions be evaluated automatically?
15. How should assessment quality be compared with expert manual reviews?

# 15. Promotion Criteria

A feature should move from this document into the active roadmap only when all relevant criteria are satisfied.

## Demonstrated problem

There is evidence that a real user or workflow problem exists.

The feature should not be promoted solely because it is technically interesting.

## MVP limitation

The current Trace capabilities cannot adequately solve the problem.

## Clear user decision

The feature makes a specific reviewer or engineering decision:

- Faster
- More accurate
- Easier to explain
- Easier to maintain

## Measurable value

There is a practical way to evaluate whether the feature succeeds.

## Architectural fit

The feature aligns with Trace’s product vision and design principles.

## Security understanding

The primary security and privacy implications are understood.

## Scope compatibility

The feature will not derail the current milestone.

## Simpler alternatives considered

A less complex solution has been evaluated.

## Ownership

Someone is prepared to design, implement, test, document, and maintain it.

# 16. Rejected or Intentionally Limited Ideas

## General Autonomous Security Agent

**Status:** Rejected

Trace should not become a broadly autonomous agent with unrestricted tools and loosely defined goals.

This would conflict with:

- Least privilege
- Structured state
- Human authority
- Explainability
- Bounded evaluation

## Finding-Count Optimization

**Status:** Rejected

Trace should not optimize for the number of generated findings.

Finding volume is not a meaningful success metric.

## Agent Debate for Every Decision

**Status:** Rejected

Running multiple agents to argue every conclusion would add cost, latency, and complexity without guaranteed quality improvement.

Critical review should remain targeted and measurable.

## Fully Autonomous Risk Acceptance

**Status:** Rejected

Risk acceptance is an organizational decision requiring accountable human authority.

## Immediate Kubernetes Deployment

**Status:** Rejected for MVP

Kubernetes would not prove the core analysis thesis and would add unnecessary operational complexity.

## Immediate Vector Database

**Status:** Rejected for MVP

The first fixtures and requirement catalog should be small enough for deterministic filtering and bounded retrieval.

A vector database should be introduced only if scale or retrieval quality requires it.

## Multiple Model Providers From Day One

**Status:** Rejected for MVP

The MVP should begin with one primary model configuration.

Additional providers should be added for evaluated quality, cost, resilience, or privacy reasons.

## Direct Production-System Writes

**Status:** Rejected for MVP

Trace agents should not directly modify:

- Production infrastructure
- Source repositories
- Security configuration
- Tickets
- Policies

Initial integrations should remain read-only or require explicit human approval.

# 17. Current Priority Boundary

None of the features in this document should interrupt the active roadmap sequence.

The original Stage 0–2 priority list this section carried is delivered in full; what bounds
promotion now is the delivered system's own gates:

1. The keyed measurements come before new capability: the live sweep, the comparison
   recordings, and the usage backfill (#484, #331, #332) are the standing evidence debt.
2. Decided-but-unbuilt items are executed in their decided order before new decisions are
   opened (DEC-070's parsers, DEC-072's serializers).
3. A promotion carries its measurement with it (DEC-097 and DEC-098 are the precedents), and
   the nine criteria in section 15 all hold.

New ideas should be added here and revisited only during planned roadmap reviews.

# 18. Review Cadence

Review this document:

- At the end of each roadmap stage
- When evaluation reveals a significant product limitation
- When a user need repeatedly appears
- Before promoting a major integration
- When the project’s vision or scope changes

Do not review it every time a new idea appears.

Capture the idea, assign an initial status, and return to the active milestone.

# 19. Product Discipline

A future feature should not enter development because it is exciting.

It should enter development because:

- The problem is real.
- The current product cannot solve it.
- The value can be measured.
- The design fits Trace.
- The security implications are understood.
- The active milestone can support the work.

Until then, the feature belongs here.
