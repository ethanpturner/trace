# Trace — Current Architecture

**Project:** Trace

**Subtitle:** Context-Aware Security Architecture Analysis

**Architecture version:** 0.1

**Status:** Proposed

**Last updated:** 2026-08-05

## 1. Purpose

This document describes the current intended architecture for the Trace MVP.

Trace is a context-aware security architecture analysis platform. It uses a structured workflow of AI-assisted analysis steps to produce evidence-backed, explainable security assessments.

The MVP prioritizes:

- Traceability
- Evidence quality
- Structured outputs
- Human review
- False-positive reduction
- Local development
- Demonstration quality
- Clear separation between deterministic logic and model-generated analysis

This architecture is expected to evolve as implementation and evaluation reveal better approaches.

## 2. Architectural Principles

### 2.1 Evidence over assumptions

A security claim should reference supporting evidence whenever possible.

When sufficient evidence is unavailable, Trace should produce one of the following instead of presenting the claim as fact:

- An explicit assumption
- A clarifying question
- A documentation gap
- A low-confidence candidate finding

### 2.2 Context over checklists

Security requirements should not be applied mechanically.

Trace should consider:

- System architecture
- Data sensitivity
- Technology choices
- Deployment environment
- Trust boundaries
- Existing controls
- Inherited platform controls
- Compensating controls
- Business function

### 2.3 Structured state over free-form agent conversation

Workflow components should exchange validated structured objects rather than relying primarily on conversational text.

Free-form text may be used inside model prompts and reports, but workflow state should use defined schemas.

### 2.4 Human authority

Trace assists a security reviewer. It does not replace one.

The human reviewer remains responsible for:

- Confirming system context
- Accepting or rejecting assumptions
- Approving significant findings
- Adjusting severity
- Interpreting business risk
- Finalizing the assessment

### 2.5 Explainability by design

The system should preserve enough information to explain:

- What source material was used
- What context was extracted
- Why a threat was considered
- Why a requirement was applied
- What evidence supported a finding
- What workflow steps modified or rejected a finding
- Where human judgment was required

### 2.6 Deterministic where practical

Traditional software should perform tasks that do not require probabilistic reasoning.

Examples include:

- Schema validation
- Identifier generation
- Duplicate detection
- Threshold enforcement
- Relationship validation
- Report assembly
- Audit logging
- File handling

AI models should be used for tasks that benefit from semantic interpretation or security reasoning.

## 3. MVP System Context

The MVP is a locally operated application used by one security reviewer.

The reviewer supplies documentation for a fictional software system. Trace processes the material, extracts architectural context, performs threat and control analysis, validates evidence, and produces a reviewable security assessment.

### Primary actor

**Security reviewer**

The reviewer:

- Creates or selects an assessment
- Supplies architecture documentation
- Reviews extracted context
- Answers clarifying questions
- Reviews proposed findings
- Approves the final report

### External systems

The MVP may communicate with:

- A configured large language model API
- LangSmith or another tracing platform
- The local filesystem
- A local database
- A browser-based user interface

The MVP will not initially connect to:

- Enterprise wikis
- Production source-code repositories
- Ticketing systems
- CI/CD enforcement systems
- Cloud asset inventories
- Production vulnerability scanners

These may be represented by local fixtures or added after the MVP.

## 4. High-Level Architecture

flowchart TD

U[Security Reviewer]

UI[Local Web Interface or CLI]

API[Application Service]

WF[Workflow Orchestrator]

STORE[(Local Assessment Store)]

FILES[(Local Artifact Store)]

TRACE[Trace and Audit Service]

LLM[LLM Provider]

INGEST[Document Ingestion]

CONTEXT[Context Extraction]

REVIEW1[Context Review]

THREATS[Threat Analysis]

CONTROLS[Requirement and Control Mapping]

EVIDENCE[Evidence Validation]

CRITIC[Critical Review]

REVIEW2[Finding Review]

REPORT[Report Generation]

EVAL[Evaluation]

U --> UI

UI --> API

API --> WF

API --> STORE

API --> FILES

WF --> INGEST

INGEST --> CONTEXT

CONTEXT --> REVIEW1

REVIEW1 --> THREATS

THREATS --> CONTROLS

CONTROLS --> EVIDENCE

EVIDENCE --> CRITIC

CRITIC --> REVIEW2

REVIEW2 --> REPORT

REPORT --> EVAL

CONTEXT --> LLM

THREATS --> LLM

CONTROLS --> LLM

EVIDENCE --> LLM

CRITIC --> LLM

REPORT --> LLM

WF --> STORE

WF --> TRACE

REPORT --> FILES

EVAL --> STORE

## 5. Major Components

## 5.1 User Interface

The user interface allows the security reviewer to initiate and review an assessment.

Initial capabilities should include:

- Create an assessment
- Upload or select local input documents
- Enter structured system information
- Start analysis
- View workflow progress
- Review extracted architecture
- Answer clarifying questions
- Review proposed findings
- Approve or reject findings
- View evidence and reasoning traces
- Generate the final report

### Initial implementation choice

**The MVP interface is a command-line interface** (DEC-032). Earlier versions of this section
preferred a small local web application; the roadmap said the opposite in four places, and this
section was the one that was wrong.

The capability list above is the eventual interface, not the Stage 1 one. Through M4 every item is
a command: creating an assessment, adding sources, approving context, approving findings, and
assigning severity all run at the command line and write the same `ReviewerDecision` rows an
interface of any other shape would (DEC-017).

Stage 5 may add a **read-only local view** for the demonstration, rendering persisted state —
notably the lineage view. It is not a second way to drive the pipeline, and no review interaction
moves to a browser in the MVP.

Any interface, present or future, calls application services rather than containing core analysis
logic. That constraint is what makes the ordering safe: the services are built first, so a later
view is additive rather than reshaping them.

## 5.2 Application Service

The application service coordinates user-facing operations.

Responsibilities include:

- Assessment creation
- Input validation
- File registration
- Workflow initiation
- Workflow status retrieval
- Human-review submissions
- Report retrieval
- Configuration management

The application service should not contain agent prompts or substantial security-analysis logic.

## 5.3 Workflow Orchestrator

The workflow orchestrator manages the assessment lifecycle.

Orchestration is ordinary Python: a node protocol, an explicit table of permitted transitions, and
a persisted `WorkflowRun` row (DEC-016). There is no orchestration framework. The pipeline is a
fixed sequence of fourteen phases with two pause points and no analytical branching, which is the
case a graph framework helps least with, and a framework checkpointer would be a second
authoritative store alongside the domain objects DEC-006 makes authoritative.

A transition not named in the table is an error rather than an undefined behaviour. Resume is a
read of the persisted run, not a framework checkpoint restore.

Responsibilities include:

- Maintaining workflow state
- Executing analysis nodes
- Controlling transitions
- Supporting conditional branches
- Pausing for human review
- Retrying recoverable failures
- Recording node results
- Resuming interrupted assessments
- Preventing uncontrolled loops
- Enforcing execution limits

The orchestrator should treat each analysis activity as a workflow node with defined inputs and outputs.

### Proposed workflow phases

1. Assessment initialization
2. Document ingestion
3. Context extraction
4. Context validation
5. Human context review
6. Threat generation
7. Requirement and control mapping
8. Evidence validation
9. Critical review
10. Finding consolidation
11. Human finding review
12. Report generation
13. Evaluation
14. Assessment completion

## 5.4 Document Ingestion

The ingestion component converts source material into normalized document artifacts.

### MVP inputs

- Markdown
- Plain text
- JSON
- YAML

PDF, Microsoft Office, repository, and web-page ingestion are deferred unless implementation proves simple enough to include safely.

### Responsibilities

- Accept input files
- Validate supported formats
- Assign stable document identifiers
- Preserve original content
- Normalize text
- Divide long documents into addressable sections
- Preserve source locations
- Generate content hashes
- Record ingestion metadata

### What normalization does

Normalization is **line-count preserving** (DEC-015). Line *n* of the normalized artifact is line
*n* of the original.

It may convert line endings to LF, strip trailing whitespace within a line, and normalize Unicode
to NFC. It may not remove blank lines, collapse consecutive blank lines, unwrap or rewrap
paragraphs, or strip front matter.

This is what makes evidence locations unambiguous: every location field addresses the original
document, and because normalization cannot change line counts, addressing the original and
addressing the normalized artifact are the same address.

### How documents are divided

Markdown and plain text are segmented at the **shallowest heading level that occurs more than
once in that document**, determined per document rather than fixed. The corpus is inconsistent
about heading depth, so a fixed level fails in both directions: segmenting on `#` would give a
734-line document one chunk, and segmenting on `##` would give five of the seven demo documents
none. The "more than once" qualifier matters — a `#` that appears once is a title, not a section
boundary, so the shallowest level merely *present* collapses those same documents to one chunk.

JSON and YAML are addressed by JSON Pointer, carried in the evidence reference's `metadata`.

### Output

The ingestion process produces normalized evidence sources that can be referenced by later analysis.

Every extracted claim should be capable of linking back to:

- Source document
- Section or chunk
- Relevant text
- Content hash
- Ingestion timestamp

## 5.5 Context Extraction

The context extraction component converts unstructured documentation into a structured representation of the target system.

It should identify:

- System purpose
- Business capabilities
- Users and actors
- Components
- Data stores
- External dependencies
- Assets
- Data classifications
- Data flows
- Entry points
- Authentication mechanisms
- Authorization mechanisms
- Trust boundaries
- Deployment environment
- Security controls
- Uncertainties
- Contradictions
- Missing information

### Output discipline

Extracted context must distinguish among:

- Explicitly documented facts
- Reasonable interpretations
- User-confirmed facts
- Assumptions
- Unknowns

The system should not silently convert an interpretation into a confirmed fact.

## 5.6 Context Review

After extraction, the workflow pauses for human review.

The reviewer can:

- Confirm extracted facts
- Correct inaccurate facts
- Add missing context
- Resolve contradictions
- Accept or reject assumptions
- Answer prioritized questions

This review creates an approved context baseline for downstream analysis.

The threat-analysis phase should primarily reason from the approved context baseline rather than repeatedly reinterpreting all source documents independently.

## 5.7 Threat Analysis

The threat-analysis component produces candidate threat scenarios based on the approved system context.

Candidate threats should include:

- Affected asset
- Relevant component
- Threat actor or precondition
- Attack path or failure scenario
- Security impact
- Supporting context
- Applicable threat category
- Confidence
- Open questions

The initial threat methodology will likely use STRIDE as a coverage aid, but Trace should generate scenario-based threats rather than merely producing one checklist item per STRIDE category.

Example:

Weak output:

Information disclosure may occur.

Preferred output:

A compromised third-party integration token could allow unauthorized retrieval of customer repository metadata through the integration service.

The threat-analysis component produces candidate threats, not final findings.

## 5.8 Requirement and Control Mapping

This component identifies controls and security requirements relevant to each candidate threat.

It should support:

- Applicable requirements
- Existing documented controls
- Inherited controls
- Compensating controls
- Potential control gaps
- Alternative ways to satisfy a requirement
- Evidence needed to validate control implementation

The requirements catalog should be stored separately from application code and use version-controlled structured data.

A requirement should not automatically become a finding merely because the source documentation does not mention its implementation.

Absence of documentation is not automatically evidence of absence.

## 5.9 Evidence Validation

Evidence validation determines whether a proposed security conclusion is supported.

It should classify conclusions as:

- Supported
- Partially supported
- Unsupported
- Contradicted
- Requires user confirmation
- Documentation gap

A finding should generally require:

- A plausible threat scenario
- An applicable security expectation
- Evidence that the expectation is unmet or inadequately addressed
- A meaningful security impact
- Sufficient confidence for reviewer consideration

When evidence is missing, Trace should prefer a question or documentation gap over an asserted vulnerability.

## 5.10 Critical Review

The critical-review component challenges the draft analysis.

It should look for:

- Unsupported claims
- Misapplied requirements
- Ignored inherited controls
- Duplicate findings
- Exaggerated severity
- Missing attack prerequisites
- Missing business context
- Contradictory findings
- Threats disconnected from assets
- Generic recommendations
- Findings that are only documentation gaps
- Overlooked high-impact threats

The critic should not independently rewrite the entire assessment without preserving the reasons for its changes.

Its output should identify:

- The challenged object
- The criticism
- The supporting rationale
- The recommended action
- Confidence

## 5.11 Finding Consolidation

Finding consolidation converts validated analysis into a manageable review set.

Responsibilities include:

- Merge duplicates
- Link related threats
- Separate risks from documentation gaps
- Normalize titles
- Preserve evidence references
- Preserve criticism history
- Identify unresolved questions

The output remains provisional until human review.

Consolidation does **not** assign severity. Findings leave this node with
`severity: unassigned`, and the reviewer assigns it at the finding checkpoint (DEC-030).
Neither this node nor an agent has the business context severity depends on.

## 5.12 Human Finding Review

The reviewer can:

- Approve a finding
- Reject a finding
- Edit a finding
- Assign or change severity
- Request additional analysis
- Convert a finding to a question
- Convert a finding to a documentation gap
- Add reviewer notes

**Assigning severity is not optional.** Findings arrive carrying `unassigned`, and an
approval whose finding still carries it is rejected by validation (DEC-030). The reviewer
holds the business context that severity depends on; no earlier node does.

This list names actions a reviewer takes. `ReviewDisposition` in `data-model.md` section 4.6
names dispositions the system records, and **the two lists do not correspond one to one**. A
severity change is recorded as `edit` with `prior_value` and `updated_value` on
`ReviewerDecision`, per DEC-023. There is no `change_severity` disposition and adding one
would be a second way to express the same edit.

Trace should record these actions for evaluation and auditability.

Human edits are valuable evaluation data because they reveal where the workflow was inaccurate or unhelpful.

## 5.13 Report Generation

The reporting component transforms approved structured assessment data into a readable artifact.

The initial output format is Markdown, and it is the only MVP format: `future-features.md` section
13.5 defers PDF, HTML, JSON, SARIF, and audit packages.

The report has sixteen numbered sections, fixed by `templates/report-v1.md`. **Each has exactly one
owner** (DEC-035): four are prose from the Report Generation Agent, and twelve are rendered
deterministically from approved objects by the Report Rendering node. A section is never both.

| # | Section | Owner |
|---|---|---|
| 1 | Executive summary | Agent |
| 2 | Scope | Rendered |
| 3 | System overview | Agent |
| 4 | Architecture summary | Rendered |
| 5 | Assets and trust boundaries | Rendered |
| 6 | Risk summary | Agent |
| 7 | Significant threats | Rendered |
| 8 | Approved findings | Rendered |
| 9 | Documentation gaps | Rendered |
| 10 | Assumptions | Rendered |
| 11 | Open questions | Rendered |
| 12 | Existing controls | Rendered |
| 13 | Recommended actions | Rendered |
| 14 | Methodology | Rendered |
| 15 | Evidence appendix | Rendered |
| 16 | Assessment limitations | Agent |

Risk summary is the one section this list adds to the fifteen originally proposed here. It exists so
that section 7 is a rendered list of threats rather than a mixture of prose and table.

The report generator should not invent new findings during prose generation.

It should render approved structured data.

Each report is written to `outputs/report-<workflow_run_id>.md` in the assessment's artifact
directory, beside a JSON manifest carrying the report's hash, the version pins `evaluation-plan.md`
section 3 requires, and the counts. Every section is emitted whether or not it has content, using
wording authored in the template — an assessment with no approved findings is a defined outcome, and
the section that says so must not read as a failure or as an assertion that the system is secure.

## 5.14 Evaluation Component

The evaluation component measures assessment quality and workflow behavior.

Initial metrics may include:

- Finding evidence coverage
- Unsupported claim count
- Reviewer acceptance rate
- Reviewer rejection rate
- Reviewer edit rate
- Duplicate finding rate
- Clarifying-question usefulness
- Requirement-mapping accuracy
- Threat coverage
- Execution duration
- Model-call count
- Token usage
- Estimated cost
- Node failure rate

Evaluation data should be stored separately from the final user-facing report.

## 5.15 Assessment Store

The assessment store maintains structured project and workflow data.

The MVP may use SQLite.

It should store:

- Assessments
- Assessment status
- Structured context
- Workflow checkpoints
- Threats
- Requirements
- Controls
- Evidence references
- Findings
- Questions
- Human decisions
- Evaluation results
- Execution metadata

Large source files and generated reports may remain in the local filesystem, with references stored in the database.

## 5.16 Artifact Store

The MVP artifact store is a controlled local directory.

It may contain:

- Original source documents
- Normalized documents
- Generated reports
- Exported workflow state
- Evaluation fixtures
- Debug artifacts

The artifact store should use an assessment-specific directory structure and avoid mixing data between assessments.

Example:

data/

assessments/

assessment-001/

sources/

normalized/

outputs/

traces/

evaluation/

## 5.17 Trace and Audit Service

The trace and audit service captures the execution history of an assessment.

It should record:

- Workflow run identifier
- Node name
- Node version
- Prompt version
- Model configuration
- Input object references
- Output object references
- Start and completion times
- Errors
- Retry attempts
- Human interventions
- Status transitions

Sensitive prompt content and source data should not automatically be sent to an external tracing provider.

Local audit records should remain the authoritative execution record.

LangSmith may be used during development if its data-handling configuration is acceptable for the demo data.

## 6. End-to-End Workflow

### Step 1: Assessment initialization

The reviewer creates an assessment and supplies:

- Assessment name
- System description
- Input documents
- Optional structured metadata
- Analysis configuration

### Step 2: Ingestion

Trace normalizes the source documents and creates stable evidence references.

### Step 3: Context extraction

Trace identifies architectural facts, uncertainties, and missing information.

### Step 4: Context review

The reviewer approves or corrects the extracted context.

### Step 5: Threat generation

Trace generates scenario-based candidate threats using the approved context.

### Step 6: Control analysis

Trace maps threats to relevant requirements, existing controls, and inherited controls.

### Step 7: Evidence validation

Trace determines whether proposed gaps are supported by available evidence.

### Step 8: Critical review

Trace challenges the draft analysis and recommends rejection, revision, consolidation, or further investigation.

### Step 9: Finding consolidation

Trace produces a deduplicated set of provisional findings, questions, and documentation gaps.

### Step 10: Human review

The reviewer approves or modifies the assessment results.

### Step 11: Report generation

Trace produces the final Markdown assessment.

### Step 12: Evaluation

Trace records quality and execution metrics.

## 7. Workflow State

A central assessment-state object should pass through the workflow.

The state should contain references to structured objects rather than one continuously expanding block of prose.

Conceptually:

assessment:

id:

status:

configuration:

sources: []

context:

extracted:

approved:

assumptions: []

unknowns: []

threats:

candidates: []

reviewed: []

control_mappings: []

evidence_assessments: []

findings:

provisional: []

approved: []

rejected: []

questions: []

documentation_gaps: []

human_decisions: []

execution_records: []

evaluation_results: []

The authoritative schemas will be defined in data model.md.

## 8. Human-in-the-Loop Checkpoints

The MVP will include at least two explicit human checkpoints.

### Checkpoint 1: Context approval

Occurs after context extraction and before threat analysis.

Purpose:

- Prevent downstream analysis from being built on incorrect architecture assumptions
- Capture missing business and technical context
- Demonstrate the importance of human validation

### Checkpoint 2: Finding approval

Occurs before final report generation.

Purpose:

- Preserve reviewer authority
- Prevent provisional model output from becoming an official conclusion
- Capture acceptance, rejection, and editing metrics

Additional checkpoints may be added later for:

- High-severity findings
- Low-confidence analysis
- Conflicting evidence
- Unexpected cost or execution limits

### How a checkpoint pauses

The run persists itself and the process exits (DEC-017). `WorkflowRun.status` becomes `paused`,
`current_node` names the checkpoint, and `pending_human_review` names the objects awaiting a
decision. Resuming is a separate invocation that loads the run and continues once every pending
object has a `ReviewerDecision`.

Reviewer decisions reach the workflow through one interface regardless of origin. An interactive
command, a web form, and an evaluation harness replaying recorded decisions all write the same
`ReviewerDecision` rows. This is what keeps answering a checkpoint non-interactively distinct from
removing it, which DEC-012 requires.

The review package is derived from the persisted run rather than stored with it, so the mechanism
does not presuppose which interface renders it.

### How a checkpoint is passed, and what rejection does

Checkpoint 1's gate is `SystemContext.is_approved`, and it is read rather than counted: the
checkpoint node names the `SystemContext` among the objects awaiting a decision whenever
`approved_at` and `approved_by` are unset, so a run advances to threat generation only after a
reviewer approved the revision. Approval is refused while a blocking question is open or a blocking
validation error is outstanding, and the refusal names what is outstanding.

Rejection — "request re-extraction" in `agent-design.md` section 9 — stops the run and is recorded
as a `ReviewerDecision` with disposition `request_more_analysis`. It does not route the run
backwards: DEC-038 makes re-extraction the assessment's next `WorkflowRun`, so the transition table
stays a sequence and there is no edge from `human_context_review` back to `context_extraction`.

## 9. Model Interaction Architecture

Trace should use a model abstraction layer rather than calling one provider directly throughout the codebase.

The abstraction should support:

- Model selection by task
- Structured outputs
- Timeout handling
- Retry limits
- Token limits
- Cost metadata
- Provider-specific configuration
- Test substitutes
- Future multi-model evaluation

The MVP may begin with one provider and one primary model.

Different models should not be introduced merely to make the system appear multi-agent or sophisticated.

Each model call should have a clear reason.

## 10. Prompt Management

Prompts are stored as version-controlled project artifacts rather than embedded across application
code. The tree is [agent-design.md](agent-design.md) section 34's, which is authoritative for the
file names:

prompts/

shared/

source-content-boundary-v1.md

evidence-policy-v1.md

uncertainty-policy-v1.md

context/

extract-context-v1.md

threats/

generate-scenario-threats-v1.md

controls/

map-requirements-controls-v1.md

evidence/

validate-evidence-v1.md

critique/

challenge-analysis-v1.md

reporting/

generate-report-sections-v1.md

An earlier version of this section showed underscored names and a different file set. Two documents
describing one directory differently is a directory nobody can create correctly, and section 34 is
the one the loader follows.

`shared/` holds the blocks composed into agent prompts by application code rather than copied into
each one — the source-content boundary, the evidence policy, and the uncertainty policy. A copy is
the failure the composition exists to prevent, because the copy is what stops being updated.
`severity/` is absent: DEC-030 excluded the Severity Support Agent, so there is no prompt for it.

Each prompt has:

- A defined purpose
- Expected input schema
- Expected output schema
- Behavioral constraints
- Version identifier
- Evaluation examples

The composed prompt is hashed rather than the file (DEC-019), so an edit to a shared block is
visible in the hash of every prompt that includes it. Prompt versions are recorded in workflow
traces.

## 11. Error Handling

The workflow must distinguish among different failure classes.

### Validation failure

An output does not match the expected schema.

Response:

- Retry with validation feedback
- Stop after a defined retry limit
- Preserve failed output for debugging

### Model-service failure

The provider is unavailable or times out.

Response:

- Retry with bounded exponential backoff
- Allow the workflow to resume
- Do not restart the full assessment unnecessarily

### Insufficient evidence

The available information cannot support a conclusion.

Response:

- Create a question, assumption, or documentation gap
- Do not treat this as a technical execution failure

### Awaiting a reviewer decision

Not a failure mode (DEC-017).

A checkpoint pauses by persisting the run and letting the process exit. A paused run holds nothing
in memory, so waiting costs nothing and there is no timeout — a run may sit paused indefinitely.

Response:

- Persist the run with `status: paused` and the pending review block populated
- Return; the process may exit
- Resume on a later invocation, once every pending object has a reviewer decision

### Unexpected application failure

Response:

- Preserve the most recent valid checkpoint
- Record the error
- Allow controlled restart from the checkpoint

## 12. Security Boundaries

The MVP contains several important trust boundaries.

### Source-document boundary

Input documents are untrusted.

They may contain:

- Incorrect information
- Contradictions
- Embedded prompt injection
- Malicious instructions
- Sensitive information

Source content should be treated as data, not as trusted instructions to the workflow.

### Model-provider boundary

Content sent to an external model leaves the local application boundary.

The MVP must use fictional or public data and avoid confidential information.

### Browser-to-application boundary

User inputs must be validated before reaching workflow and storage components.

### Assessment-data boundary

Data from one assessment must not contaminate another assessment.

### Generated-output boundary

Model-generated content is untrusted until validated and reviewed.

Detailed risks and mitigations are maintained in [threat-model.md](threat-model.md), which covers each boundary above and names where every mitigation is enforced. The browser-to-application boundary is not present in the MVP: DEC-032 makes the interface a command line, so there is no listening port.

## 13. Deployment Model

The initial deployment model is local development on one workstation.

Proposed services:

- Local web application
- Python application service
- Workflow orchestration (plain Python; DEC-016)
- SQLite database
- Local artifact directory
- External model API
- Optional external development tracing

Containerization may be added after the basic workflow functions.

The MVP does not initially require:

- Kubernetes
- Multiple microservices
- A message queue
- A distributed database
- Cloud deployment
- Multi-user tenancy

These technologies would add complexity without proving the core project thesis.

## 14. Proposed Technology Stack

These are proposed choices, not all final decisions.

| Area | Proposed technology |
|---|---|
| Primary language | Python |
| Workflow orchestration | Plain Python: node protocol, transition table, persisted run (DEC-016) |
| Data validation | Pydantic |
| API layer | FastAPI |
| Local web interface | Lightweight Python-compatible UI or small web frontend |
| Database | SQLite |
| ORM or database layer | To be determined |
| Testing | Pytest |
| Package management | uv |
| Linting and formatting | Ruff |
| Type checking | Pyright or mypy |
| Model abstraction | To be determined |
| Development tracing | LangSmith, subject to data-handling review |
| Report format | Markdown |
| Structured configuration | YAML |
| Structured application data | JSON-compatible Pydantic models |

## 15. Repository Structure

Proposed initial repository organization:

trace/

README.md

pyproject.toml

src/

trace/

api/

application/

workflow/

nodes/

routing/

state/

domain/

models/

services/

ingestion/

evidence/

reporting/

evaluation/

infrastructure/

database/

models/

tracing/

filesystem/

prompts/

templates/

requirements/

demo/

input/

expected/

tests/

unit/

integration/

evaluation/

docs/

architecture/

project-scope.md

current-architecture.md

data-model.md

agent-design.md

threat-model.md

decision-log.md

data/

assessments/

The exact repository structure may change during implementation. The important boundary is that domain models, workflow logic, prompts, infrastructure, and user-interface code remain reasonably separated.

## 16. MVP Demo Architecture

The first demo target will be a fictional GitHub-integrated developer platform.

The fictional platform may include:

- Browser-based user interface
- REST API
- Repository integration
- Webhook receiver
- Background job worker
- AI analysis service
- PostgreSQL database
- Object storage
- Redis or a job queue
- Enterprise OIDC provider
- Secrets manager
- GitHub Actions workflow
- Administrative interface
- Third-party notification service

The input documentation will intentionally include:

- Confirmed controls
- Inherited controls
- Missing controls
- Ambiguous statements
- Contradictions
- Irrelevant details
- One or more prompt-injection attempts

This will allow the demo to show:

- Context extraction
- Trust-boundary identification
- Evidence traceability
- Clarifying questions
- Inherited-control reasoning
- False-positive reduction
- Prompt-injection resistance
- Human review
- Explainable findings

## 17. Deferred Capabilities

The following capabilities are deliberately deferred:

- Direct GitHub repository ingestion
- Automated source-code analysis
- Pull-request comments
- GitHub Actions enforcement
- Jira integration
- Enterprise wiki ingestion
- Cloud deployment
- Multi-user tenancy
- Role-based access control
- Vector database infrastructure
- Continuous security assessment
- Autonomous remediation
- Production policy enforcement
- Broad compliance-framework mapping
- Kubernetes deployment
- Large-scale document processing

Deferred capabilities may be reconsidered after the core workflow demonstrates measurable value.

## 18. Current Limitations

The proposed MVP architecture has several known limitations:

- Model outputs remain probabilistic.
- Threat coverage cannot be guaranteed.
- Evidence validation may still misinterpret documentation.
- Human review is necessary.
- The initial requirements catalog will be small.
- Local execution is not representative of enterprise scale.
- Evaluation fixtures may not fully represent real product-security reviews.
- External model usage introduces privacy and availability dependencies.
- The fictional demo will not prove production readiness.
- Multi-agent structure may add complexity without improving every task.

These limitations should be discussed openly in presentations and interviews.

## 19. Open Architecture Questions

The following questions require decisions or implementation experiments:

1. Which local web-interface framework should be used?
2. ~~Which model provider and model should be used initially?~~ Resolved by DEC-014: Anthropic as the default adapter, `claude-opus-5` as the primary model, behind a provider-agnostic seam.
3. ~~Is a separate model abstraction library needed for the MVP?~~ Resolved by DEC-014: no. The seam is the project's own; provider SDKs sit behind it in adapters.
4. ~~How should evidence chunks and source locations be represented?~~ Resolved by DEC-015.
5. ~~How should inherited controls be modeled?~~ Resolved by DEC-026.
6. How should confidence be calculated and communicated?
7. ~~What minimum evidence threshold should be required for a finding?~~ Resolved by DEC-013.
8. Which parts of the workflow require separate agents versus deterministic functions?
9. How should semantic duplicate detection work?
10. Should LangSmith be used in the public demonstration?
11. How much reasoning information should be exposed to users?
12. How should prompt injection in source documentation be tested?
13. ~~How should requirement applicability be determined?~~ Resolved by DEC-024: by the mapping agent's judgment over the whole catalog. There is no deterministic pre-filter, because `applicable_technologies` — the only structured filter field — is populated on zero requirements.
14. What data should be retained after an assessment?
15. Which evaluation dataset should be used to compare workflow versions?

Each consequential answer should be recorded in decision log.md.

## 20. Architecture Evolution

This document represents the current best architecture, not an immutable design.

It should be updated when:

- A proposed component proves unnecessary
- Implementation reveals a simpler design
- Evaluation shows a workflow step adds little value
- Security requirements change
- The demo scenario changes materially
- A major technology decision is accepted
- The system moves beyond local single-user operation

Major architectural decisions should be recorded separately in the decision log so that the reasons behind changes are preserved.
