# Decision Log

## DEC-001: Name the project Trace

Date: 2026-08-05

Status: Accepted

Decision:

Name the project **Trace**, with the subtitle **Context-Aware Security Architecture Analysis**.

Why:

The name reflects several core capabilities of the project:

- Tracing findings to evidence
- Tracing workflow execution
- Tracing threats through a system architecture
- Tracing security requirements to controls
- Explaining how an assessment reached its conclusions

The name does not restrict the project to threat modeling or a specific AI technology.

Alternatives Considered:

- Context
- Archon
- Aegis
- Atlas
- Sentinel

Tradeoffs:

- Trace is memorable and relevant to the project’s explainability goals.
- The term is already widely used in software engineering and observability.
- Repository, domain, or package names may require a more specific variation.

Open Questions:

- What GitHub repository name should be used if trace is unavailable?
- Should the Python package use a longer name to prevent naming conflicts?

## DEC-002: Define Trace as a security architecture analysis platform

Date: 2026-08-05

Status: Accepted

Decision:

Define Trace as a **context-aware security architecture analysis platform**, rather than only an AI threat-modeling tool.

Threat modeling will be one of the platform’s initial capabilities.

Why:

The core problem is broader than threat generation. Trace is intended to support:

- Architecture analysis
- Context extraction
- Threat modeling
- Security requirement mapping
- Control analysis
- Evidence validation
- Documentation-gap identification
- Risk assessment
- Explainable security findings

This framing allows the project to expand without changing its identity.

Alternatives Considered:

- AI threat-modeling tool
- Automated application-security reviewer
- Security requirements engine
- Agentic product-security platform

Tradeoffs:

- The broader definition creates more long-term flexibility.
- A broad platform description can make the MVP appear overly ambitious.
- The project scope and demo must remain narrow despite the broader product vision.

Open Questions:

- Which capability should be treated as the primary entry point after the MVP?
- How should the project avoid becoming an unfocused collection of security features?

## DEC-003: Use a fictional GitHub-integrated developer platform as the demo target

Date: 2026-08-05

Status: Accepted

Decision:

Use a fictional GitHub-integrated developer platform as the initial system analyzed by Trace.

The fictional platform will include a modern web application, API services, repository integration, webhooks, background processing, an AI analysis service, data stores, enterprise identity, secrets management, and CI/CD workflows.

Why:

This scenario provides enough complexity to demonstrate:

- Authentication and authorization
- Third-party integrations
- Webhook security
- Secrets management
- CI/CD security
- Data flows
- Trust boundaries
- AI-specific risks
- Inherited controls
- Missing context
- Evidence-backed findings

It also aligns with the ISC2 presentation topic and the types of security-platform roles being targeted.

Alternatives Considered:

- Generic online retail application
- Financial-services application
- Healthcare application
- Simple three-tier web application
- Kubernetes-native internal platform

Tradeoffs:

- The scenario is relevant and technically rich.
- It could appear tailored to a particular employer if GitHub branding is overused.
- Too many components could make the demonstration difficult to follow.
- The platform must remain fictional and avoid reproducing former-employer intellectual property.

Open Questions:

- What will the fictional platform be called?
- Which components are necessary for the MVP demo?
- Which security control will be intentionally inherited?
- Which real vulnerability or control gap will be intentionally included?
- How much GitHub-specific functionality should appear in the scenario?

## DEC-004: Start with a local, single-user MVP

Date: 2026-08-05

Status: Accepted

Decision:

Build the initial Trace MVP as a locally operated, single-user application.

Why:

The MVP needs to prove the quality of the analysis workflow, not enterprise deployment capabilities.

A local application reduces unnecessary complexity involving:

- Cloud infrastructure
- Multi-user tenancy
- Authentication
- Role-based access control
- Distributed systems
- Production operations
- Data residency
- Enterprise integrations

This allows development effort to focus on the core differentiator: evidence-driven, context-aware security analysis.

Alternatives Considered:

- Public cloud-hosted application
- Multi-user SaaS platform
- Command-line-only application
- GitHub App
- CI/CD-native service

Tradeoffs:

- Local operation is simpler, less expensive, and easier to demonstrate safely.
- It does not demonstrate production cloud architecture or enterprise scale.
- Some future capabilities may require architectural changes.
- Local setup must be reliable enough for presentations and interviews.

Open Questions:

- Should the MVP lead with a local web interface or command-line interface?
- Should the application be containerized for repeatable setup?
- What is the minimum supported operating environment?

## DEC-005: Require human approval at major workflow checkpoints

Date: 2026-08-05

Status: Accepted

Decision:

Require human approval at two minimum checkpoints:

1. After architectural context extraction
2. Before provisional findings become final report findings

Why:

Incorrect extracted context can corrupt every later stage of analysis.

Final security findings also require professional judgment regarding:

- Accuracy
- Business impact
- Severity
- Existing controls
- Risk acceptance
- Appropriate remediation

Human review supports Trace’s role as a security-review assistant rather than an autonomous authority.

Alternatives Considered:

- Fully autonomous assessment
- Human review only after report generation
- Human review after every workflow node
- Human approval only for high-severity findings

Tradeoffs:

- Human approval improves quality and safety.
- It slows the workflow.
- Reviewer behavior can make evaluations less consistent.
- Too many review checkpoints would weaken the value of automation.

Open Questions:

- What information should be displayed at each checkpoint?
- Should low-confidence outputs trigger additional mandatory review?
- How should reviewer edits be captured for evaluation?

## DEC-006: Use structured workflow state

Date: 2026-08-05

Status: Accepted

Decision:

Use defined structured objects as the authoritative workflow state.

Agents and workflow nodes will exchange schema-validated data rather than relying on a continuously growing free-form conversation.

Why:

Structured state supports:

- Validation
- Testing
- Traceability
- Predictable workflow transitions
- Report generation
- Error recovery
- Evaluation
- Future API integration

It also reduces the risk that important facts become buried or distorted in an agent conversation.

Alternatives Considered:

- Shared conversational transcript
- Free-form Markdown state
- Agent-to-agent natural-language messaging
- One large assessment JSON object without domain separation

Tradeoffs:

- Structured state requires substantial upfront data-model design.
- Schemas may need frequent changes early in development.
- Some nuanced model reasoning may not fit cleanly into rigid structures.
- The approach makes the system easier to test and maintain.

Open Questions:

- Which objects should be stored directly in workflow state?
- Which objects should be stored in the database and referenced by ID?
- How should schema versions be managed?
- How should partially valid model output be handled?

## DEC-007: Use LangGraph as the proposed workflow orchestrator

Date: 2026-08-05

Status: Proposed

Decision:

Use LangGraph as the initial framework for orchestrating the Trace assessment workflow.

Why:

The workflow requires:

- Structured state
- Conditional transitions
- Human-review pauses
- Checkpointing
- Retries
- Workflow visualization
- Execution tracing
- Resumable assessments

LangGraph is designed for stateful workflows involving model-assisted processing.

Alternatives Considered:

- Plain Python functions
- Custom state machine
- CrewAI
- Temporal
- Prefect
- Direct LangChain chains

Tradeoffs:

- LangGraph provides useful workflow capabilities and demonstration visibility.
- It introduces framework dependency and conceptual overhead.
- The workflow could become unnecessarily complicated if every operation is modeled as an agent.
- Some functionality may be easier to implement with ordinary Python.

Open Questions:

- Does LangGraph materially improve the MVP over a simple Python workflow?
- Which activities should be graph nodes?
- How should workflow checkpoints be persisted?
- Should LangGraph remain an internal implementation detail?

## DEC-008: Use Python as the primary implementation language

Date: 2026-08-05

Status: Accepted

Decision:

Use Python as the primary implementation language for the Trace MVP.

Why:

Python has strong support for:

- AI model integrations
- LangGraph
- Pydantic
- Data processing
- API development
- Rapid prototyping
- Security automation
- Testing

It also aligns with the project’s portfolio goal of demonstrating production-oriented Python security engineering.

Alternatives Considered:

- Go
- TypeScript
- Python backend with TypeScript frontend
- Ruby

Tradeoffs:

- Python enables rapid development and has a strong AI tooling ecosystem.
- It provides weaker compile-time guarantees than Go.
- Performance may be lower for some workloads, although this is not a significant MVP constraint.
- A separate frontend language may eventually be desirable.

Open Questions:

- Will the user interface require TypeScript?
- Which type-checking tool should be adopted?
- How strict should type enforcement be in the initial repository?

## DEC-009: Do not treat missing documentation as proof of a vulnerability

Date: 2026-08-05

Status: Accepted

Decision:

When source documentation does not mention a security control, Trace will not automatically conclude that the control is absent.

The system should classify the condition as one of the following until stronger evidence exists:

- Open question
- Assumption
- Documentation gap
- Unverified control
- Low-confidence candidate finding

Why:

A major source of false positives in automated security analysis is treating missing documentation as proof that a control is not implemented.

Controls may be:

- Inherited from a platform
- Provided by a shared service
- Implemented outside the reviewed document
- Satisfied through an alternative mechanism
- Known to the organization but not repeated in every architecture artifact

Alternatives Considered:

- Generate a finding whenever a required control is undocumented
- Assume controls exist unless evidence shows otherwise
- Use only documented controls and ignore all gaps
- Apply different rules based on requirement severity

Tradeoffs:

- This approach should reduce false positives.
- It may reduce recall if genuine issues are repeatedly classified as questions.
- It increases the need for clarifying questions and human review.
- The system requires a disciplined evidence and confidence model.

Open Questions:

- What evidence threshold converts an unverified control into a finding?
- When should a documentation gap itself be considered a security finding?
- How should inherited controls be represented and validated?
- How should Trace prioritize clarifying questions?
