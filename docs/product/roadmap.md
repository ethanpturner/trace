# Trace — Product Roadmap

**Project:** Trace

**Subtitle:** Context-Aware Security Architecture Analysis

**Document version:** 0.1

**Status:** Proposed

**Last updated:** 2026-08-12

## 1. Purpose

This roadmap defines the order in which Trace should be designed, built, evaluated, and demonstrated.

The roadmap is organized around product capabilities and measurable exit criteria rather than feature volume.

The immediate objective is not to build a complete enterprise security platform.

The objective is to prove that Trace can:

1. Understand a documented software architecture.
2. Preserve evidence and uncertainty.
3. Generate architecture-specific threats.
4. Recognize existing and inherited controls.
5. Avoid turning missing documentation into unsupported findings.
6. Produce a small set of defensible security conclusions.
7. Demonstrate measurable improvement over a simpler AI workflow.

## 2. Roadmap Principles

The roadmap follows several constraints.

### Prove the thesis before expanding the platform

Trace should first demonstrate that context and evidence reduce false positives.

Direct integrations, cloud deployment, and enterprise workflows are secondary.

### Build one vertical slice before completing every subsystem

The first working version should process one small assessment from input through final report.

It does not need every planned object, agent, or interface.

### Evaluate each major layer

Every new workflow stage should justify its existence through measurable improvement.

Examples include:

- Context review enabled versus disabled
- Control mapping versus direct requirement-to-finding generation
- Evidence validation enabled versus disabled
- Critical review enabled versus disabled

### Keep the demonstration reliable

A smaller workflow that works consistently is more valuable than a complex workflow that fails during a presentation or interview.

### Preserve clean-room boundaries

All scenarios, requirements, prompts, code, and outputs must be independently created from fictional or public material.

## 3. Product Stages

The current roadmap contains seven stages:

| Stage | Outcome |
|---|---|
| 0 | Product and architecture foundation |
| 1 | Development environment and repository foundation |
| 2 | Context extraction vertical slice |
| 3 | Threat, requirement, and control analysis |
| 4 | Evidence-driven findings and human review |
| 5 | Evaluation and demo hardening |
| 6 | Public portfolio release |
| Later | Integrations and enterprise expansion |

Stages should generally be completed in order.

Some research, documentation, and fixture preparation can occur in parallel.

### Delivery milestones

The repository tracks delivery in GitHub milestones. Stages 1 through 4 were delivered as
milestones M1 Foundation through M4 Results. Design decisions are held in M0 Decisions, each
closing with a decision-log entry, and citation and vocabulary alignment is held in M5
Alignment. Stages 5 and 6 were decomposed into four further milestones, all since delivered:

| Milestone | Scope | State |
|---|---|---|
| M6 Assembly | The orchestrator drives all fourteen phases end to end. CLI commands reach both checkpoints and the report. `trace verify` re-hashes evidence and the report manifest. A recorded ForgeFlow run replays offline, and the README describes the assembled state. | Delivered |
| M7 Evaluation | The evaluation harness over the scenario registry. The completed ForgeFlow truth set and further scenarios. Baseline comparisons, ablations, run-to-run variance, and the evaluation scorecard. | Delivered |
| M8 Adversarial | The poisoned-document corpus as scenario variants. Two-axis adversarial metrics. Typed injection routing at the context checkpoint. The structural-defence demonstration. | Delivered |
| M9 Demo and Portfolio | The read-only demonstration interface with the finding lineage view. The measured comparison table. The demo script and recovery plan. The limitations section, the failure taxonomy, and the ablation narrative. | Delivered |

M6 preceded the Stage 5 work because the demonstration measures a pipeline that must first
run end to end from the command line; the stages assumed that assembly implicitly. Five
design decisions gated the evaluation milestones and were held in M0 — the harness design,
the baseline comparison protocol, the adversarial evaluation design, the published
scorecard, and run-to-run stability measurement — each now closed with its decision-log
entry.

Later scaffolding added M10 Demo Hardening, M11 Evaluation Completion, M12 Decision Debt
(the DEC-057..072 features decided in the M0 wave and left unbuilt — closed 2026-08-12),
and M13 Surface Completion.

# Stage 0 — Product and Architecture Foundation

## Goal

Complete enough design work that implementation can begin without repeatedly reconsidering the project’s purpose or core structure.

## Deliverables

### Product documentation

- vision.md
- design principles.md
- roadmap.md
- future features.md
- Optional glossary.md

### Architecture documentation

- project scope.md
- current architecture.md
- data model.md
- agent design.md
- threat model.md
- evaluation plan.md
- decision log.md

### Demo definition

Create a concise description of the fictional GitHub-integrated developer platform that Trace will analyze.

Define:

- System purpose
- Components
- Actors
- Assets
- Data flows
- Trust boundaries
- Existing controls
- Inherited controls
- Genuine weaknesses
- Missing information
- Contradictions
- Prompt-injection content

### Initial benchmark design

Define at least three benchmark fixtures:

1. OIDC delegated authentication
2. Managed database with inherited encryption
3. Potentially unsigned webhook requiring clarification

## Exit criteria

Stage 0 is complete when:

- The MVP problem and non-goals are clear.
- The core workflow is documented.
- The initial data model is coherent.
- Agent responsibilities are bounded.
- The fictional demo system is defined.
- At least three benchmark scenarios have expected outcomes.
- Major current decisions appear in the decision log.
- No confidential former-employer material is included.

## Work that can occur before the development laptop arrives

Nearly all Stage 0 work can be completed without the new development environment.

This includes:

- Documentation
- Architecture diagrams
- Synthetic source documents
- Requirements drafting
- Expected benchmark outputs
- Prompt outlines
- Demo script
- Product naming
- Repository structure planning

# Stage 1 — Development and Repository Foundation

## Goal

Create a reliable, professional development foundation for Trace.

## Deliverables

### Repository

Create the initial repository with:

trace/

README.md

pyproject.toml

src/

prompts/

requirements/

demo/

benchmarks/

tests/

docs/

### Development tooling

Configure:

- Python
- uv
- Pydantic
- Pytest
- Ruff
- Type checking
- Environment-variable management
- Pre-commit or equivalent quality checks
- Secret exclusion through .gitignore

### Core application models

Implement the first domain models:

- Assessment
- SourceDocument
- EvidenceReference
- SystemContext
- ContextClaim
- Component
- Actor
- Asset
- DataFlow
- TrustBoundary
- Question

### Persistence

Implement basic local persistence using:

- SQLite for structured assessment data
- Local directories for source and generated artifacts

### Basic application entry point

Create a simple CLI before building the full interface.

Initial commands may include:

trace assessment create

trace assessment list

trace assessment status

trace assessment archive

trace source add

trace context extract

trace context show

`list` and `archive` were added after this stage was first written. A reviewer needs `list` because
identifiers are allocated by the store rather than chosen (DEC-018), and `archive` because DEC-031
makes archiving the one assessment status transition a person performs.

### Test foundation

Add tests for:

- Model validation
- Stable identifiers
- Invalid relationships
- Evidence references
- File ingestion
- Assessment isolation

## Exit criteria

Stage 1 is complete when:

- A new assessment can be created.
- Markdown or text sources can be registered.
- Sources receive stable identifiers and hashes.
- Structured objects can be persisted and retrieved.
- Tests run through one documented command.
- Formatting, linting, and type checks operate consistently.
- No model calls are required to verify the foundation.

## Explicit non-goals

Do not build:

- A polished web interface
- Cloud deployment
- Multiple model providers
- Vector infrastructure
- GitHub integration
- Every object in the full data model

# Stage 2 — Context Extraction Vertical Slice

## Goal

Demonstrate that Trace can turn source documentation into a reviewable architecture model with evidence links.

This is the first meaningful product milestone.

## Deliverables

### Ingestion and evidence indexing

Support:

- Markdown
- Plain text
- Basic JSON
- Basic YAML

Create addressable evidence references with:

- Source identifier
- Section or line location
- Quoted text
- Content hash

### Context Extraction Agent

Implement the first model-assisted agent.

It should propose:

- Components
- Actors
- Assets
- Data flows
- Trust boundaries
- Context claims
- Assumptions
- Unknowns
- Contradictions
- Clarifying questions

### Context validation

Implement deterministic checks for:

- Invalid identifiers
- Missing object relationships
- Unsupported documented claims
- Invalid data flows
- Duplicate components
- Invalid confidence values

### Human context review

The initial review experience may be CLI-based or use simple structured files.

The reviewer should be able to:

- Approve
- Reject
- Edit
- Add missing context
- Answer questions

### Initial context fixture

Run the fictional developer-platform documentation through the context workflow.

## Exit criteria

Stage 2 is complete when:

- Trace extracts the major components of the demo system.
- Important claims link to evidence.
- Inferences and facts are clearly separated.
- Contradictions are surfaced.
- Missing information becomes questions.
- A reviewer can approve a context baseline.
- Reviewer changes are preserved.
- The workflow can be rerun consistently.

## Evaluation targets

Initial targets should be treated as directional rather than release guarantees.

- Major component recall: high
- Unsupported documented claims: near zero
- Evidence coverage for documented claims: near 100%
- Reviewer correction burden: manageable
- Prompt-injection instructions followed: zero

## Decision gate

Before advancing, answer:

Is context extraction useful and reliable enough to serve as the authoritative input to downstream analysis?

If not, improve the context layer before adding threat agents.

# Stage 3 — Threat, Requirement, and Control Analysis

## Goal

Generate architecture-specific threats and determine which security expectations actually apply.

This stage introduces the core false-positive-reduction mechanism.

## Deliverables

### Threat Analysis Agent

Generate scenario-based threats containing:

- Threat actor or failure source
- Preconditions
- Attack path
- Affected components
- Affected assets
- Security impact
- Supporting context
- Confidence
- Open questions

### Threat validation

Deterministically validate:

- Object relationships
- Required assets and components
- Impact descriptions
- Duplicate threats
- Unsupported architectural assumptions

### Initial requirements catalog

Build a small version-controlled catalog.

The first catalog should contain approximately 10–20 high-quality requirements relevant to the demo.

Possible categories:

- Webhook validation
- Authentication
- Authorization
- Secrets management
- Data protection
- Administrative access
- CI/CD trust
- Logging
- Third-party integration
- AI input handling

Each requirement should define:

- Applicability
- Non-applicability
- Acceptable implementations
- Evidence expectations
- Rationale

### Control representation

Model:

- Implemented controls
- Inherited controls
- Compensating controls
- Claimed controls
- Unknown controls

### Requirement and Control Mapping Agent

For each threat, determine:

- Which requirements apply
- Why they apply
- Which controls address them
- Whether control status is satisfied, partial, unverified, or unmet
- Which questions or evidence are still needed

## Exit criteria

Stage 3 is complete when:

- Threats are specific to the approved architecture.
- Generic STRIDE labels are not treated as complete threats.
- Requirements are applied selectively.
- Inherited controls are represented.
- Requirement applicability includes a rationale.
- Missing documentation remains unverified, not automatically unmet.
- OIDC and managed-database fixtures do not create known false positives.
- The unsigned-webhook fixture produces a threat and question or supported finding, depending on evidence.

## Evaluation comparisons

Compare:

1. Generic one-pass threat-model prompt
2. Trace with approved context
3. Trace with context and requirement/control mapping

Measure:

- False positives
- Relevant threat coverage
- Reviewer acceptance
- Requirement applicability accuracy
- Inherited-control recognition

## Decision gate

Before advancing, answer:

Does the control-mapping layer measurably improve the assessment over direct threat-to-finding generation?

If not, simplify or redesign it.

# Stage 4 — Evidence-Driven Findings and Human Review

## Goal

Convert analysis into a small, defensible set of findings, questions, and documentation gaps.

## Deliverables

### Evidence Validation Agent

Classify conclusions as:

- Supported
- Partially supported
- Unsupported
- Contradicted
- Requires confirmation

### Critical Review Agent

Challenge:

- Unsupported conclusions
- Misapplied requirements
- Ignored inherited controls
- Duplicate issues
- Weak attack paths
- Overstated severity
- Documentation gaps presented as vulnerabilities

### Finding consolidation

Create deterministic minimum criteria for findings.

Separate outputs into:

- Provisional findings
- Questions
- Documentation gaps
- Rejected candidates
- Confirmed controls

### Human finding review

Allow the reviewer to:

- Approve
- Reject
- Edit
- Merge
- Change severity
- Request more analysis
- Convert a finding into a question
- Convert a finding into a documentation gap

### Report generation

Generate report sections from approved structured objects.

### Deterministic report rendering

Render a final Markdown report containing only approved conclusions.

## Exit criteria

Stage 4 is complete when:

- Every provisional finding has traceable lineage.
- Questions and documentation gaps remain separate from findings.
- Unsupported candidates are rejected or downgraded.
- Only approved findings appear in the final report.
- The report does not invent new conclusions.
- Reviewer decisions are stored.
- The demo includes at least one example of each:
  - Approved finding
  - Rejected false positive
  - Inherited control
  - Clarifying question
  - Documentation gap
  - Contradictory evidence

## Evaluation targets

- Finding evidence coverage: approximately 100%
- Report-only invented findings: zero
- Known false-positive fixtures: zero or clearly identified regressions
- Reviewer acceptance rate: improving across versions
- Reviewer edit rate: tracked and decreasing
- Critical-review usefulness: demonstrable

## Decision gate

Before advancing, answer:

Is the multi-stage workflow producing conclusions that are meaningfully better than the simpler baseline?

If the critic or another agent does not improve results, remove or defer it.

# Stage 5 — Evaluation and Demo Hardening

## Goal

Make Trace reliable, measurable, and presentation-ready.

## Deliverables

### Benchmark suite

Expand to approximately 8–12 scenarios covering:

- Delegated authentication
- Managed platform controls
- Genuine missing controls
- Contradictory documentation
- Missing documentation
- Prompt injection
- AI-service risks
- Third-party integrations
- Duplicate threats
- Large architecture input

### Baseline comparisons

Compare Trace against:

- A single generic LLM prompt
- A structured single-pass prompt
- Trace without evidence validation
- Trace without critical review
- Trace without human context approval

### Evaluation reporting

Automatically produce a summary containing:

- Findings proposed
- Findings approved
- Findings rejected
- Findings edited
- Questions generated
- Documentation gaps
- Evidence coverage
- False positives
- False negatives
- Model calls
- Tokens
- Estimated cost
- Execution time
- Failures and retries

### Demonstration interface

Build only the interface necessary to support the demonstration clearly.

Priority views:

1. Assessment overview
2. Extracted architecture context
3. Workflow progress
4. Questions and human review
5. Findings
6. “Why was this generated?” lineage view
7. Evaluation comparison

### Demo script

Create a reliable 5–10 minute walkthrough. The script is written: [demo-script.md](demo-script.md)
stages the offline ForgeFlow run as ten timed beats with a per-beat fallback, and the recovery plan
below maps to committed artifacts.

The demonstration should show:

1. Input architecture documentation
2. Extracted context
3. Human correction or confirmation
4. Candidate threats
5. An inherited control suppressing a false positive
6. A missing fact becoming a question
7. A supported finding
8. Evidence and analysis lineage
9. Final report
10. Evaluation improvement over the baseline

### Demo recovery plan

Prepare:

- Preloaded assessment state
- Screenshots
- Backup recording
- Static report
- Known-good benchmark output

A live model or network failure should not ruin the presentation.

## Exit criteria

Stage 5 is complete when:

- The full demo works repeatedly.
- Known benchmark results are reproducible.
- Evaluation results can be explained without hand-waving.
- The demo can recover from model or network failure.
- The workflow fits within an acceptable cost and runtime.
- No confidential or employer-derived material appears.
- A technically experienced audience can understand the product thesis within several minutes.

# Stage 6 — Public Portfolio Release

## Goal

Turn Trace into a credible public career asset.

## Deliverables

### Public repository

Include:

- Clear README
- Product overview
- Architecture diagram
- Demo screenshots or recording
- Setup instructions
- Security model
- Evaluation results
- Known limitations
- Roadmap
- License
- Contribution expectations if relevant

### Portfolio narrative

The measured ablation narrative is written: [ablation-narrative.md](ablation-narrative.md) reads the
components back from the committed evaluation artifacts, weaves in the baseline and adversarial
results, and tells the DEC-016 framework story once, for the interview package.

Explain:

- The problem
- Why generic AI security analysis creates noise
- Why context and evidence matter
- How Trace separates facts, questions, and findings
- How the project is evaluated
- What remains unproven

### Public demo materials

Prepare:

- Short video
- Architecture image
- Example report
- Benchmark comparison
- “Why this finding?” screenshot
- Presentation-safe sample documents

### Interview package

Prepare stories covering:

- Why Trace exists
- Why LangGraph was evaluated and rejected (DEC-016)
- Why structured state matters
- How prompt injection is handled
- How inherited controls reduce false positives
- How evaluation changed the architecture
- What was removed because it added no value
- How the system would evolve for production

### ISC2 presentation alignment

The speaking folder should consume outputs from the Trace project:

- Slides
- Speaker notes
- Demo script
- Screenshots
- Demo video
- Handout

Trace remains the source of truth.

## Exit criteria

Stage 6 is complete when:

- A reviewer can understand and run the project from the repository.
- The project has a polished but honest README.
- A public demo is available.
- Evaluation results are reproducible or clearly described.
- Architecture and threat-model documents are shareable.
- The project supports strong interview discussion.
- The project does not imply production readiness it has not earned.

# Later Stage — Integrations and Enterprise Expansion

These capabilities should not enter the active roadmap until the MVP thesis has been demonstrated.

Possible directions include:

## Repository and developer workflow integration

- GitHub repository ingestion
- Pull-request analysis
- GitHub Actions integration
- Design-review checks
- Security guidance in developer workflows

## Continuous architecture analysis

- Change detection
- Assessment diffing
- New-risk identification
- Stale evidence detection
- Continuous control verification

## Enterprise context

- Shared platform catalog
- Organizational controls
- Control inheritance
- Approved technology patterns
- Enterprise requirements
- Risk exceptions
- Team ownership

## Evidence integrations

- Cloud configuration
- CI/CD configuration
- Source-code analysis
- Identity configuration
- Vulnerability scanners
- Asset inventory
- Ticketing systems

## Collaboration and governance

- Multi-user reviews
- Role-based permissions
- Approval workflows
- Risk acceptance
- Remediation tracking
- Reporting dashboards
- Audit exports

## Production deployment

- Cloud hosting
- Authentication
- Tenant isolation
- Secrets management
- Encryption
- Observability
- Scalability
- Data-retention controls

These possibilities belong in future features.md until promoted through an explicit decision.

# 4. Cross-Cutting Workstreams

Several workstreams continue throughout the roadmap.

## Decision records

Update the decision log when:

- A framework is accepted or rejected
- An agent is added or removed
- A major schema changes
- A control threshold changes
- A model provider is selected
- A security tradeoff is accepted
- A scope boundary changes

## Threat modeling

Update the Trace threat model whenever:

- A new external integration is added
- Agents gain new tools
- Sensitive data is introduced
- Cloud deployment begins
- Multi-user access is added
- External tracing behavior changes

## Evaluation

Every meaningful bug or false positive should become:

- A fixture
- A regression test
- An evaluation case

## Documentation

Architecture documents should describe the current system rather than an aspirational final state.

## Career assets

Capture:

- Architecture diagrams
- Before-and-after evaluation results
- Significant technical decisions
- Difficult bugs
- Simplifications
- Security tradeoffs
- Demo screenshots

These become interview and presentation material.

# 5. Prioritization Framework

Features should be prioritized using five questions.

## 1. Does it prove the product thesis?

Highest priority goes to capabilities that demonstrate context-aware, evidence-driven analysis.

## 2. Does it improve a reviewer decision?

A feature should make a decision faster, more accurate, or easier to explain.

## 3. Can its value be evaluated?

Features with measurable outcomes should be preferred.

## 4. Is it needed for the demo?

Presentation-critical capabilities may receive priority even if they are not production-ready.

## 5. Is there a simpler alternative?

Prefer the simpler implementation unless complexity produces measurable value.

# 6. Work-in-Progress Limits

To reduce distraction, Trace should use strict work-in-progress limits.

At any point:

- One active product milestone
- One primary implementation problem
- One secondary documentation or evaluation task
- No more than one experimental branch that is not tied to the active milestone

New feature ideas should go into future features.md, not immediately into implementation.

A promising idea is not automatically a current priority.

# 7. Definition of Done

A roadmap item is not complete merely because code exists.

A meaningful capability is complete when:

- The expected behavior is documented.
- The relevant data model exists.
- Inputs and outputs are validated.
- Tests cover core behavior.
- Security implications are considered.
- Evaluation fixtures exist.
- Known limitations are documented.
- Demo behavior is reliable where applicable.
- The decision log reflects consequential choices.

# 8. Stop Conditions

Pause or simplify development when:

- The workflow cannot be evaluated meaningfully.
- The fictional demo system is not sufficiently defined.
- New agents are being added without measured benefit.
- Infrastructure work is displacing the core analysis.
- The project begins incorporating confidential material.
- The demo becomes too large to explain.
- Model cost or latency prevents repeatable testing.
- The reviewer experience becomes more complicated than the manual process.
- Documentation and implementation no longer describe the same system.

# 9. Near-Term Sequence

The original nine-step sequence this section carried — documents, scenario, fixtures, catalog,
repository, environment, the evidence slice, the extraction slice, evaluation before more
agents — is delivered in full. The immediate sequence now:

1. Record the keyed measurements: the eleven-scenario live sweep with live baselines (#484),
   the prompt- and model-comparison protocols (#331, #332), and the usage backfill.
2. Record the demo video (#353), the last Stage 6 asset.
3. Execute the remaining decided items in their decided order (DEC-070's OpenAPI parser,
   DEC-072's Mermaid serializer) before opening new decisions.

The standing non-instructions hold in their original form:

Do not begin with the web interface.

Do not begin with all six agents.

Do not begin with GitHub integration.

# 10. Roadmap Success

This roadmap succeeds when Trace becomes:

- A working security-analysis system
- A measurable engineering experiment
- A reliable technical demonstration
- A public portfolio artifact
- A platform with a credible path for expansion

It does not need to become a production enterprise platform during the initial roadmap.

The first major proof point is simple:

Trace can use approved context and evidence to avoid false conclusions that a generic AI security review would produce.

Everything else should support that result.
