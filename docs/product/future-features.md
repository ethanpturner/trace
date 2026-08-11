# Trace — Future Features

**Project:** Trace

**Subtitle:** Context-Aware Security Architecture Analysis

**Document version:** 0.1

**Status:** Proposed

**Last updated:** 2026-08-10

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

**Status:** Deferred

Allow Trace to ingest repository documentation and selected configuration files directly from GitHub.

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

**Status:** Candidate

Compare two assessment versions and identify meaningful changes.

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

**Status:** Candidate

Maintain a reusable catalog of organization-wide controls.

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

**Status:** Idea

Analyze Terraform, CloudFormation, Kubernetes manifests, or similar artifacts for architecture and control evidence.

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

**Status:** Research

Extract components, flows, and trust boundaries from architecture diagrams.

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

**Status:** Candidate

Add threat patterns and requirements specifically for systems using:

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

**Status:** Promoted

Promoted 2026-08-10 into milestone M7 Evaluation as the static evaluation scorecard
(issue #271), gated on the published-scorecard decision (issue #258). The scorecard is the
non-interactive form of this feature; interactive and longitudinal views remain future work.

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

**Status:** Promoted

Promoted 2026-08-10 into milestone M7 Evaluation (issue #270), gated on the evaluation
harness design decision (issue #255). Ablations are applied by the harness per DEC-012, and
an ablated run is marked non-authoritative.

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

**Status:** Candidate

The read-only demonstration form of this view is promoted into milestone M9 Demo and
Portfolio (issue #276) under DEC-032. The interactive product form remains a candidate.

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

**Status:** Candidate

Render components, data flows, assets, and trust boundaries from the approved structured context.

The visualization should reflect reviewer-approved state rather than raw model output.

## 13.3 Assessment Comparison Report

**Status:** Idea

Generate a human-readable summary of changes between assessment versions.

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

**Status:** Idea

Support formats beyond Markdown, potentially including:

- PDF
- HTML
- JSON
- SARIF
- Ticketing-system formats
- Audit packages

Markdown remains sufficient for the MVP.

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

The current priorities remain:

1. Complete product and architecture documentation.
2. Define the fictional developer-platform scenario.
3. Create the initial benchmark fixtures.
4. Draft the initial requirements catalog.
5. Establish the repository and development environment.
6. Implement evidence-backed context extraction.
7. Evaluate context extraction before adding additional agents.

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
