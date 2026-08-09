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

DEC-012 states how this is enforced: the checkpoints are workflow-graph nodes and no assessment configuration can skip one.

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

- ~~What evidence threshold converts an unverified control into a finding?~~ Resolved by DEC-013. Under the default threshold, nothing converts an unverified control into a finding; `unmet` requires evidence that describes absence or inadequacy.
- When should a documentation gap itself be considered a security finding? DEC-013 deliberately leaves this open.
- How should inherited controls be represented and validated?
- How should Trace prioritize clarifying questions?

## DEC-010: Store the requirements catalog as version-controlled YAML, one file per category

Date: 2026-08-08

Status: Accepted

Decision:

Store the requirements catalog in `requirements/` as version-controlled YAML, separate from application code.

Requirements are grouped one file per primary security category, under a directory named for the catalog version.

A `catalog.yaml` manifest lists the requirement identifiers the version contains.

`content_hash`, which DEC-006's structured-state model requires on RequirementsCatalog, is deliberately omitted until a loader exists to compute it.

Why:

The architecture already requires the catalog to be stored separately from application code and to use version-controlled structured data.

YAML matches every requirement example in the data model and the only existing domain-data file in the repository.

Category files keep a reviewable diff granularity between a single large file and one file per requirement, and they make the category taxonomy visible in the directory listing rather than only inside the data.

A hand-maintained content hash would be stale after the first edit and could not be verified against anything, because RequirementsCatalog is deferred in the data model's initial implementation priority.

Alternatives Considered:

- A single catalog file containing all requirements
- One file per requirement with a manifest
- JSON, matching the per-scenario `requirements.json` named in the evaluation plan
- Storing requirements in SQLite rather than in version control

Tradeoffs:

- Category files make the taxonomy legible but require a judgment call when a requirement spans categories, resolved by filing on primary category only.
- Splitting the catalog across a manifest and category files means the two can disagree. `tests/unit/test_requirements_catalog.py` enforces agreement, which is a test rather than a schema, so it constrains the catalog only while the catalog has no other reader.
- Omitting `content_hash` leaves the catalog without an integrity marker until the loader is built.
- YAML tolerates structural mistakes that a schema would reject. The test checks structure and citation format against the data model, but it cannot check that a cited control identifier exists in the framework it names, because the frameworks are not vendored.

Open Questions:

- Should the per-scenario `requirements.json` in the evaluation plan reference catalog identifiers rather than restate requirements?
- When should catalog version 0.1 become 0.2 rather than being edited in place?
- What computes and verifies `content_hash`, and at what point in the workflow?

## DEC-011: Record common false positives on each requirement

Date: 2026-08-08

Status: Accepted

Decision:

Add an optional `common_false_positives` field to the Requirement object.

The field records the conclusions that are wrongly drawn when a requirement is applicable but the documentation does not evidence it.

It is distinct from `non_applicable_conditions`, which states when a requirement does not apply at all.

Why:

DEC-009 establishes that missing documentation is not proof that a control is absent, but nothing in the schema carried which wrong conclusions a given requirement invites.

That knowledge existed only as prose in the demo scenario's intentional non-findings, where the application cannot reach it.

The distinction the field draws is the one the project exists to defend. A requirement about delegated authentication does not apply where a local credential store exists, which is a non-applicability condition. Where it does apply and the documentation is silent, the wrong conclusion is specifically that password policy is missing, which is a different statement and belongs in a different field.

Recording it per requirement keeps the knowledge next to the expectation it qualifies, and makes it available to the mapping step rather than depending on model judgment.

Alternatives Considered:

- Express the knowledge in `rationale` as prose
- Express it through `non_applicable_conditions`
- Defer the field until the mapping step exists and the need is demonstrated
- Hold the knowledge in the mapping prompt rather than in the catalog

Tradeoffs:

- The field is populated by hand and reflects the author's judgment, so it can encode a wrong belief as durably as a right one.
- Suppressing named false positives risks suppressing a genuine finding that resembles one, which the evaluation plan's false-negative measurement should detect.
- It adds a field to an object that is otherwise a faithful expression of a security expectation, mixing the expectation with knowledge about how it is misread.
- Nothing yet enforces that the field is consulted.

Open Questions:

- Should a suppressed conclusion be recorded as a rejected candidate for evaluation, rather than discarded silently?
- Should entries reference the context claim that makes them false, rather than being free text?
- Does this field belong on Requirement, or on a separate object relating a requirement to a known misreading?

## DEC-012: Keep checkpoint ablation out of assessment configuration

Date: 2026-08-08

Status: Accepted

Decision:

Remove `require_context_review` and `require_finding_review` from AssessmentConfiguration.

The two human checkpoints are nodes in the workflow graph, not runtime conditionals. No configuration value, environment variable, or function argument advances the pipeline past an unapproved checkpoint.

The workflow comparison in the evaluation plan's section 14 is an experiment parameter belonging to the evaluation harness, not a setting on an assessment. A run that ablates a checkpoint is recorded as non-authoritative and names the ablation it applied.

Repeatable evaluation does not require the ablation. A checkpoint answered from a recorded decision file is still a checkpoint: the node executes, the gate holds, and a ReviewerDecision is written. Replay is the mode ordinary evaluation uses, and it needs no flag.

Why:

DEC-005 states that human approval is required at two checkpoints, and both `CLAUDE.md` and `README.md` describe them as structural rather than configurable. A required boolean on the assessment's own configuration object is the definition of configurable, so the corpus asserted a constraint and supplied the switch that defeats it.

Two different things were being expressed through one field. Answering a checkpoint without a human present is a scheduling concern and is what evaluation actually needs. Removing the checkpoint is an architectural experiment about whether human review improves outcomes. Only the second changes the pipeline, and it is the one that must never be reachable from an ordinary run.

Section 14 supports this reading. The checkpoint comparison appears there alongside single agent against multi-agent, critic enabled against critic disabled, and evidence validation against no evidence validation, and the section closes by stating that the purpose is to determine whether architectural complexity improves outcomes. Those are experiments on the architecture. None of them is a per-assessment setting, and the checkpoint comparison is not one either.

Placing the ablation in the harness also makes its result legible. An ablated run produces findings that no human approved, which is exactly the output DEC-005 exists to prevent from being treated as an assessment. Marking it non-authoritative at the point of production is cheaper than inferring it later from a configuration value.

Alternatives Considered:

- Retain the fields and constrain them to true, honouring false only under an explicit evaluation mode
- Retain the fields as free configuration and amend DEC-005 accordingly
- Retain the fields and rely on documentation to discourage setting them false
- Express the ablation as a separate workflow definition rather than a harness parameter

Tradeoffs:

- Removing two documented fields is a data-model change, and section 6 was authoritative for them.
- The ablation is now further from the code that implements the checkpoint, so a future change to the checkpoint could leave the harness path stale.
- An operator who genuinely wants to skip a checkpoint has no supported way to do so and must edit the workflow, which is the intended cost but is still a cost.
- Two mechanisms now answer a checkpoint, replay and interactive review, and both must produce identical ReviewerDecision records or the reviewer metrics will disagree between evaluation and ordinary use.

Open Questions:

- Where does the non-authoritative marking live: on the assessment, on the workflow run, or on the evaluation result?
- Should an ablated run be prevented from producing a report at all, rather than producing one that is marked?
- Does the replay decision file belong with the benchmark scenario, or with the run that produced it?

## DEC-013: Define the evidence threshold for satisfaction and findings

Date: 2026-08-08

Status: Accepted

Decision:

`AssessmentConfiguration.evidence_threshold` takes one of two values.

`direct-or-confirmed` is the default and the only value permitted for an authoritative assessment.

`permissive` is reachable only from the evaluation harness. A run using it is recorded as non-authoritative, in the same way as the checkpoint ablation in DEC-012. Its purpose is to measure what a review without an evidence threshold would report, which is the baseline the evaluation plan's sections 13 and 14 compare against.

Under `direct-or-confirmed`, a `ControlMapping` may take `unmet` only when all of the following hold:

1. It cites at least one EvidenceReference.
2. At least one cited reference either describes the absence or inadequacy of the control directly, or contradicts a claim that the control exists.
3. The corresponding EvidenceAssessment carries `validation_status` of `supported` or `partially_supported`.
4. No unresolved contradiction bears on the conclusion.

Reviewer confirmation satisfies conditions 1 through 3 on its own. It is the top of the evidence hierarchy in `agent-design.md` section 14, and a reviewer stating that a control is absent is direct evidence of absence.

`satisfied` and `partially_satisfied` carry the same evidence floor. A control is not marked implemented on the strength of a requirement being applicable and nothing contradicting it. `partially_satisfied` additionally requires that the shortfall be described, since a partial satisfaction that names no gap is indistinguishable from a satisfied one.

`unverified` never produces a finding under `direct-or-confirmed`. It produces a DocumentationGap or a Question, chosen by the reclassification rules in `agent-design.md` section 16: a Question where the answer is obtainable and could materially change the assessment, a DocumentationGap where the primary issue is inability to verify.

DEC-009 lists a low-confidence candidate finding among the classifications available when documentation is missing. This decision narrows that menu at the default threshold: the classification remains defined, and is reachable only under `permissive`. A low-confidence finding built on absence is the output DEC-009 exists to suppress, and making it unreachable by default is the stronger reading of that decision.

An explicit low-confidence justification, which `data-model.md` section 21 accepts in place of evidence, is a written rationale naming what evidence would raise confidence and why the conclusion is worth surfacing before that evidence exists. It does not substitute for the `unmet` evidence rule above. It qualifies a finding that already meets the rule but whose confidence is low.

The outcome table is complete over the satisfaction and validation vocabularies:

| satisfaction_status | validation_status | Outcome |
|---|---|---|
| not_applicable | any | No output |
| satisfied | supported, partially_supported | No output |
| satisfied | unsupported, contradicted, requires_confirmation | Downgrade to unverified, then Question |
| partially_satisfied | supported, partially_supported | Provisional finding |
| partially_satisfied | unsupported, contradicted, requires_confirmation | Downgrade to unverified, then Question |
| unverified | any | DocumentationGap or Question. Never a finding |
| unmet | supported, partially_supported | Provisional finding |
| unmet | unsupported, contradicted, requires_confirmation | Downgrade to unverified, and record the downgrade |
| any | not_evaluated | No output. The mapping is incomplete, not negative |

No cell produces a finding from the absence of documentation.

Confidence does not gate the table. It is carried onto the resulting object, and a low-confidence finding requires the justification described above. Confidence is not multiplied against evidence strength; `docs/product/design-principles.md` section 15 requires the two to remain separate.

Enforcement is deterministic and happens twice. The Mapping Validation node applies the `unmet` rule and performs the downgrade, which is how `agent-design.md` section 13's requirement to prevent unverified from silently becoming unmet is met. Finding Consolidation applies the outcome table. Neither depends on a model having read a prompt instruction.

Why:

The threshold was required by `AssessmentConfiguration` and defined nowhere, and the same question was recorded as open in three places: `data-model.md` question 15, `current-architecture.md` question 7, and DEC-009's own open questions. Until it was answered, the distinction between a Finding and a DocumentationGap was enforced only by prompt wording, and `docs/product/design-principles.md` section 7 states that a rule whose violation makes the system behave incorrectly does not belong in a prompt.

The rule is expressible in the schema rather than in prose because of a property the data model already has. An EvidenceReference requires non-empty `quoted_text` drawn from a real source location, and `data-model.md` section 8 forbids modifying it after creation. There is therefore no way to construct an evidence reference that expresses the absence of a passage. Requiring evidence for `unmet` is consequently sufficient to prevent concluding absence from silence, mechanically, without any agent needing to understand DEC-009.

This also gives `EvidenceStrength` its first consumer. `data-model.md` section 4.3 defines `direct`, `indirect`, `contextual`, and `contradictory` and no object carried the type. Condition 2 above is the judgment it expresses, and the Evidence Validation agent is where it is applied.

Two values rather than a graduated scale keeps the rule explainable. `data-model.md` section 4.5 warns against an overly complex severity algorithm before the core workflow is validated, and the same argument applies here with more force, because this threshold decides whether the project's central claim holds.

Worked examples, using the ForgeFlow scenario:

**14.1, missing local password policy.** ForgeFlow uses delegated authentication and stores no local passwords, so the requirement does not apply. `not_applicable`, no output. The requirement's `non_applicable_conditions` carries the condition, and `common_false_positives` names the wrong conclusion. This never reaches the threshold rule.

**15.1, webhook authenticity language.** One document says webhook requests are validated before processing; another says the receiver validates that the request is well formed. Neither establishes whether cryptographic signature verification occurs. No evidence describes absence, so `unmet` is unavailable. The mapping is `unverified`, the answer is obtainable, and it would materially change the assessment. Outcome: a Question.

**13.1, webhook replay protection.** This case does not resolve as the scenario expects, and the disagreement is recorded rather than resolved here.

The scenario's section 19 lists FND-001 as an expected finding requiring evidence that delivery identifiers are not tracked. The input documents do not establish that. `github-integration.md` section 6 says only that incoming requests are validated before processing. `operations-guide.md` section 3 shows a delivery identifier carried in the job payload and says nothing about deduplication. `architecture-overview.md` section 26 lists webhook replay handling under Known Documentation Gaps, and states that those details are maintained elsewhere or require further clarification.

The only direct evidence available is a document stating that the topic is undocumented. Treating that as evidence of absence is the exact failure DEC-009 names, and section 26's own wording describes the inherited-or-elsewhere case that DEC-009 exists to protect. Under this threshold FND-001 is `unverified`, and resolves to a DocumentationGap together with a Question about replay handling.

Either the scenario's expected-findings list is wrong, or the input documents are missing a passage that establishes non-tracking. That is a benchmark question and belongs to the issue reconciling the expected outputs. Note that removing FND-001 from the expected findings leaves three, which is the count `structured-system-input.yaml` declared before it was relocated, so the disputed count may not be an error.

A high proportion of `unverified` mappings is the expected outcome of an assessment against ordinary architecture documentation, not a defect. `requirements/README.md` states that requirements are phrased so that absence of evidence resolves to `unverified` rather than `unmet`. Evaluation must not treat the ratio as a quality signal, and no metric should reward moving mappings out of `unverified`.

Alternatives Considered:

- A graduated numeric threshold over evidence strength and confidence
- Permitting `unmet` where documentation describes a control area specifically and omits the control, on the argument that silence within a described scope is informative
- Treating an explicit Known Documentation Gaps entry as evidence supporting `unmet`
- Keeping DEC-009's full classification menu available at the default threshold
- Leaving `evidence_threshold` as free text and encoding the rule only in the mapping prompt

Tradeoffs:

- Recall is reduced. A control that is genuinely absent and simply undocumented resolves to a documentation gap, and the assessment does not report it as a weakness. That is the intended exchange, and the false-negative rate in the evaluation plan's section 8 is the measurement that should detect it going too far.
- The rule depends on the Evidence Validation agent classifying evidence strength correctly. A model that labels a vague passage `direct` defeats condition 2, and nothing deterministic can catch that.
- Reviewer confirmation satisfying the rule on its own means a reviewer can create an `unmet` mapping the documents do not support. That is deliberate, since the reviewer may know the system, but it makes reviewer decisions load-bearing for correctness and not only for approval.
- Two threshold values give no room to tune recall against precision on a per-assessment basis, which some reviewers will want.
- The decision leaves the ForgeFlow benchmark internally inconsistent until the expected outputs are reconciled.

Open Questions:

- Should a DocumentationGap on a high-impact requirement itself be reportable as a finding of a different kind, which is DEC-009's second open question and is deliberately not answered here?
- Where is evidence strength recorded, given that `EvidenceStrength` is defined but carried by no object and EvidenceAssessment holds only a list of evidence identifiers?
- Should the downgrade from `unmet` to `unverified` be visible to the reviewer as a distinct event, rather than only as a recorded reason on the mapping?
- Does `permissive` belong on the assessment configuration at all, or should it be a harness parameter like the checkpoint ablation in DEC-012?

## DEC-014: Keep the model interface provider-agnostic, with Anthropic as the default

Date: 2026-08-08

Status: Accepted

Decision:

The application talks to a model through a provider-agnostic seam. Provider-specific code lives in an adapter behind that seam and nowhere else.

Anthropic is the default adapter and the only one implemented. The primary model is `claude-opus-5`.

`AssessmentConfiguration.model_profile` names a bundle of provider, model, and generation settings rather than a bare model identifier. `primary-development` resolves to the Anthropic adapter, `claude-opus-5`, and the generation settings the agent's declared intent maps to. This is what the field means; it was previously an example string pointing at nothing.

The seam is **capability-aware rather than lowest-common-denominator**. An adapter declares which optional capabilities it supports — prompt caching, adaptive thinking, effort levels — and the application uses a capability where it is available and proceeds without it where it is not. Which capabilities were used on a given call is recorded on the `ExecutionRecord`, so an evaluation result is interpretable against the conditions that produced it.

`agent-design.md` section 29's per-agent creativity table stays as written and is reinterpreted as **provider-neutral intent**. Each adapter maps an intent to its own controls. The Anthropic adapter maps intent to `effort` and adaptive thinking, because `temperature`, `top_p`, and `top_k` are rejected on the current Anthropic models. An OpenAI adapter would map the same intent to `temperature`. Section 29 gains a note recording that the column is an intent, not a sampling parameter.

Structured output is expressed at the seam as a target Pydantic model. The Anthropic adapter satisfies it with the SDK's schema-validated parse path. This is the same contract DEC-006 states from the data side: agents propose schema-validated objects and the application validates and persists them.

The retry budget belongs to the orchestrator, not to the adapter. An adapter makes exactly one attempt per call and returns either a validated object or a structured failure carrying the raw output, which `data-model.md` section 33 requires be preserved for debugging. No adapter may run a retry loop of its own, because a hidden loop would break the `ExecutionRecord` retry count and the cost ceiling.

Two test substitutes sit behind the same seam: a deterministic fake that returns fixed objects, and a replay transport that serves recorded responses. Neither requires a provider key, so a bare `uv run pytest` exercises every agent's prompt assembly, schema handling, and retry routing with no network call.

`instructor`, `openai`, and `langchain-openai` are removed from `pyproject.toml`. `instructor` is redundant: the Anthropic SDK validates against a Pydantic model natively, and a third layer between the application and the provider would own a retry loop this decision assigns to the orchestrator. `openai` and `langchain-openai` support an adapter that does not exist; being provider-agnostic is a property of the seam, not of the dependency list, and a declared unused SDK is the same "presence is not a choice" problem the corpus already called out. They return when an adapter is written. `langchain`, `langchain-anthropic`, and `langgraph` stay, unused, pending DEC-007.

Why:

`current-architecture.md` section 9 already required a model abstraction rather than provider calls scattered through the codebase. What was open was which provider sits behind it, and the corpus was explicit that the declared dependencies were not a choice.

Selecting a provider and selecting an architecture are separable, and conflating them is what made the question feel larger than it is. The architecture question has a clear answer: the pipeline reasons over structured objects and never over provider-shaped responses, so the provider belongs behind a seam regardless of which one is chosen. The provider question is then a default that can change without touching agent code.

A capability-aware seam rather than an intersection seam is the load-bearing part of this decision. Prompt caching is a prefix match served at a small fraction of input cost, and Trace's shape fits it unusually well: the requirements catalog and the approved context are a large stable prefix reused across every mapping call, and the evaluation plan re-runs the benchmark suite on every prompt change. A seam restricted to what every provider offers would discard that, and would do so silently, in the name of a portability that no second adapter yet exercises.

Section 29's table survives intact under this reading, which is the better outcome. The column was always an expression of how much latitude an agent should have; that it was implementable as `temperature` on the models available when it was written is incidental. Rewriting it to name one provider's control would have made the corpus less portable, not more.

Alternatives Considered:

- Select Anthropic and call the provider API directly, without a seam
- Build the seam and defer the provider, keeping only the fake
- Adopt a third-party abstraction layer such as LangChain's chat-model interface
- Restrict the seam to the intersection of provider capabilities, so every adapter is interchangeable by construction
- Rewrite section 29 to name `effort` directly

Tradeoffs:

- **A seam with one implementation is not proven agnostic.** Every abstraction written against a single provider encodes that provider's assumptions, and the shape of this one will not be tested until a second adapter exists. The claim is an intention, and the entry should not be read as evidence.
- Capability-awareness means behaviour differs by adapter, so an evaluation result is comparable only against runs with the same capabilities. Recording capabilities on `ExecutionRecord` makes that visible but does not make the results comparable.
- The seam costs indirection on every call for a portability the project does not currently need.
- Provider-neutral intent in section 29 is one more mapping to keep correct, and a wrong mapping is invisible: an agent given the wrong latitude produces plausible output, not an error.
- `claude-opus-5` is the most capable tier and the most expensive of the reasonable options. The benchmark suite re-runs on every prompt change, so cost scales with iteration speed. Prompt caching offsets this and is the reason the capability-aware seam matters, but the offset is unmeasured.
- Naming a default model dates the decision. Model identifiers change faster than architecture, and `model_profile` exists so that this is a configuration edit rather than a code change.

Open Questions:

- What is the actual cost of one ForgeFlow assessment and one full benchmark sweep at this model and effort level, and does it change the model tier?
- Does the effort level belong in `model_profile`, or per agent alongside the section 29 intent?
- Should a second adapter be written before the seam is trusted, or is that premature for a local single-user MVP?
- Which capabilities must an adapter declare for an evaluation run to be considered comparable to another?
