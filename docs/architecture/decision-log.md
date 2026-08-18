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

- ~~Should the MVP lead with a local web interface or command-line interface?~~ Resolved by DEC-032: a command-line interface through M4, with a read-only view permitted in Stage 5.
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

- ~~What information should be displayed at each checkpoint?~~ Answered by DEC-017.
- Should low-confidence outputs trigger additional mandatory review?
- ~~How should reviewer edits be captured for evaluation?~~ Answered by DEC-017: as `ReviewerDecision` rows written through one interface regardless of origin. How an edit is represented on the object is DX-16 (#34).

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

Status: Rejected — superseded by DEC-016, which orchestrates with plain Python and an explicit transition table.

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

- ~~Does LangGraph materially improve the MVP over a simple Python workflow?~~ Answered by DEC-016: no, not for a fixed linear pipeline with two pause points.
- ~~Which activities should be graph nodes?~~ Moot. Every phase is a node; there is no graph framework.
- ~~How should workflow checkpoints be persisted?~~ Answered by DEC-016: as a `WorkflowRun` row. The mechanism is DX-07 (#28).
- ~~Should LangGraph remain an internal implementation detail?~~ Moot.

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

**Corroborated 2026-08-10** (issue #226, survey item A6). Three independent sources in the OWASP corpus reached the same position after this decision was recorded. ASVS 5.0 made "the documentation exists and defines X" a first-class requirement class distinct from "the control exists" — its guidance for users of 4.0 (`5.0/en/0x05-For-Users-Of-4.0.md`) describes the new `X.1 Documentation` sections as exactly that split. The GenAI LLM Top 10 2026 preface (`2026/final/LLM00_Preface.md`) argues from a 7,714-incident corpus that low signal does not indicate low risk — its "defense effect" analysis is this decision's reasoning applied to incident data rather than to documents. And TM-BOM makes `assumed` a first-class control state distinct from `active`: a control nobody has evidenced is recorded as assumed, not as absent, which is this decision expressed as a schema.

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

**Corrected 2026-08-09: the loader exists.** `src/trace_ai/services/requirements/loader.py` reads the catalog, validates every requirement against section 17, checks the manifest and the category files against each other in both directions, and computes and verifies `content_hash` per DEC-019 on every load. `requirements/catalog.yaml` carries the value, and `scripts/catalog_hash.py --write` regenerates it. Two sentences below are now historical rather than current: the catalog is no longer data that only a test reads, and the tradeoff that "the test constrains the catalog only while the catalog has no other reader" has expired — the constraint is now at load, for every reader. `RequirementsCatalog` moved from `data-model.md` section 40's deferred list to its build-first list in the same change, for the reason stated there.

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

- ~~Should the per-scenario `requirements.json` in the evaluation plan reference catalog identifiers rather than restate requirements?~~ Answered by DEC-027 by removing the file. DEC-024 puts the whole catalog in every mapping call, so a per-scenario requirement list could only narrow what the pipeline sees. A scenario pins `catalog_version` and expected control mappings reference catalog identifiers directly.
- ~~When should catalog version 0.1 become 0.2 rather than being edited in place?~~ Answered by
  DEC-057: while a version is `draft` it is edited in place; once released its directory is
  immutable and any content change is the next minor version. 0.1 releases when the recorded
  ForgeFlow fixture (#263) lands.
- ~~What computes and verifies `content_hash`, and at what point in the workflow?~~ Answered by DEC-019: one SHA-256 utility, with a stated input per object type and defined compute and verify points. The catalog's hash is computed by the loader.

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

- ~~Where does the non-authoritative marking live: on the assessment, on the workflow run, or on the evaluation result?~~ Resolved by DEC-031: on the workflow run. The assessment needs no marking because it simply cannot reach `approved`, and the evaluation result measures a run that already carries it.
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

- ~~What is the actual cost of one ForgeFlow assessment and one full benchmark sweep at this model and effort level, and does it change the model tier?~~ Estimated in `scripts/estimate_cost.py`: **$2.25 to $5.97** per assessment on `claude-opus-5` and **$27 to $72** for a twelve-scenario sweep, the range driven almost entirely by adaptive thinking depth. **It does not change the tier.** Two corrections to the reasoning above follow from it: thinking tokens billed as output are about 85% of the cost, so prompt caching saves roughly 12% rather than being the dominant lever this entry implies; and effort level, not caching or model tier, is what actually controls spend. The estimate is unmeasured — no product code exists and no `count_tokens` call was available — and should be re-run against real `ExecutionRecord` data once the pipeline runs. **Measured (DEC-092):** five completed live runs of one scenario put a run at **$6.92 ± $3.28** — above the estimate's ceiling — and the tier still does not change; `trace ledger` reads any assessment's recorded spend.
- Does the effort level belong in `model_profile`, or per agent alongside the section 29 intent?
- Should a second adapter be written before the seam is trusted, or is that premature for a local single-user MVP?
- Which capabilities must an adapter declare for an evaluation run to be considered comparable to another?

## DEC-015: Address evidence against the original document, with line-preserving normalization

Date: 2026-08-09

Status: Accepted

Decision:

**Every location field on an EvidenceReference addresses the original document, never the normalized artifact.** `start_line`, `end_line`, and `quoted_text` are all taken from the file as supplied.

**Normalization is line-count preserving by construction.** It may convert line endings to LF, strip trailing whitespace within a line, and normalize Unicode to NFC. It may not remove blank lines, collapse consecutive blank lines, unwrap or rewrap paragraphs, or strip front matter. Line *n* of the normalized artifact is line *n* of the original, always.

These two rules together are the substance of this decision. The first says which document a location means. The second makes the question unable to reappear: if normalization cannot change line counts, then addressing the original and addressing the normalized artifact are the same address, and no later reader can reintroduce the ambiguity by choosing differently. A test asserts the line counts of the original and normalized artifacts are equal for every ingested document.

`quoted_text` is verbatim from the original and is what a reviewer sees and what the report quotes. `normalized_text` is the derived form and exists for machine comparison. `content_hash` covers `quoted_text`.

**Markdown and plain text are segmented at the shallowest heading level that occurs more than once**, determined per document rather than fixed.

The qualifier is load-bearing and was arrived at by getting it wrong first. "Shallowest level present" is the intuitive statement and it fails on the corpus: two documents use `#` once as a title and `##` for every section, so the shallowest level present is `#`, which segments a 734-line document into one chunk — the exact failure this rule exists to prevent. A heading level that appears once partitions nothing. The corrected rule reads: take the shallowest level that appears at least twice.

Headings deeper than the segmenting level sit inside their chunk and do not create sub-chunks. A document with no repeated heading level is one chunk with `section_title` unset.

`section_title` is the chunk's own heading text, flattened rather than nested. `chunk_index` is contiguous from zero in document order.

**JSON and YAML are addressed by JSON Pointer** (RFC 6901), stored in `metadata` under the reserved key `json_pointer`. `section_title` carries the readable dotted-path equivalent. `start_line` and `end_line` are still populated from the parser's location information so a reviewer can find the passage in the file, but the pointer is the address. An addressable node is each top-level mapping key, and each element of a top-level sequence.

**No field is added to EvidenceReference.** `metadata` is already typed `map[string, any]` and described as "additional location details" in `data-model.md` section 8, which is exactly this. The schema is unchanged.

`page_number` remains in the schema, unpopulated, until PDF ingestion arrives. No validation rule requires it.

Why:

The question was recorded as open in three places — `data-model.md` questions 2 and 3, and `current-architecture.md` question 4 — and underneath them sat a question nobody had asked: `SourceDocument` carries both `original_path` and `normalized_path`, `EvidenceReference` carries both `quoted_text` and `normalized_text`, and nothing stated which document `start_line` indexes. If normalization changed line counts, every evidence reference in the system would be wrong by an unknown offset, silently, in the object the project's central traceability claim runs through.

Addressing the original is the right half of the choice because the original is what the reviewer opens. "Every finding is walkable back to the sentence that produced it" means a sentence in the document they supplied, not in an artifact the pipeline derived. The original is also immutable, whereas normalization rules are implementation and will change; locations bound to the original survive a normalization change, and locations bound to the normalized artifact would be invalidated by one.

Making normalization line-preserving is what turns a decision into a property. A rule that says "index the original" can be violated by a later implementer who normalizes aggressively and adjusts offsets; a normalization that cannot change line counts leaves nothing to adjust. It is also cheap here: the demo corpus contains no CRLF line endings, no trailing whitespace, no front matter, and no tabs, so the constraint currently costs nothing at all.

The per-document heading rule comes from the corpus rather than from taste, and the corpus also corrected the first version of it.

A fixed rule fails badly in both directions on the material the project already has. Segmenting on `#` gives `architecture-overview.md`, a 734-line document, exactly one chunk, because its only `#` is the document title. Segmenting on `##` gives zero chunks for five of the seven Markdown documents, which use `#` for every section. The corpus is internally inconsistent about heading depth, and any fixed rule encodes that inconsistency as a defect.

The obvious per-document rule — the shallowest heading level *present* — has the same failure for the same reason, which is easy to miss because it sounds like it addresses the problem. A `#` that appears once is a title, not a section boundary, so a document with one `#` and thirty-five `##` still collapses to one chunk under it. Requiring the level to occur more than once is what actually distinguishes a title from a partition. That correction came from running the rule against the corpus in a test rather than from reasoning about it; the wrong version was written into this entry first.

The corrected rule yields 19, 35, 17, 19, 14, 13, and 20 chunks across the seven documents, which is the intended granularity in every case.

A line range is not an address in a structured document. `- name: web` tells a reader nothing without knowing it is `components[0]`, and two list elements can be textually identical. JSON Pointer is a standard, is stable under reformatting that does not change structure, and expresses containment, which is what makes a YAML location meaningful. Keeping the line range alongside it costs nothing and preserves the reviewer's ability to open the file at the right place.

Alternatives Considered:

- Line ranges as the universal locator across all formats, with structured formats treated as text
- Chunk index as the primary address, with line ranges derived
- Addressing the normalized artifact, with a stored offset map back to the original
- Permitting normalization to change line counts and storing both sets of line numbers
- Adding a `locator` field to EvidenceReference rather than using `metadata`
- A fixed heading level for segmentation, with the corpus corrected to match

Tradeoffs:

- **Line-preserving normalization forecloses normalizations someone will eventually want.** Stripping YAML front matter, collapsing runs of blank lines, and reflowing wrapped paragraphs are all now prohibited. If one of them becomes necessary, this decision has to be revisited rather than worked around, which is the intended cost but is still a cost.
- The per-document heading rule means chunk granularity is not comparable across documents. A chunk in `architecture-overview.md` is an `##` section; a chunk in `security-overview.md` is a `#` section. They are both "one section" in their own document's terms, but nothing enforces that they are similar in size.
- A document that uses headings inconsistently within itself — a few `#` sections and then a run of `##` ones — gets segmented at `#`, and the `##` sections disappear into their parents. The corpus does not currently contain such a document.
- JSON Pointer in `metadata` is unvalidated by the schema, since `metadata` is untyped. The pointer's correctness rests on the indexing code and its tests rather than on the model.
- Storing `quoted_text` from the original means the stored evidence can contain the artifacts normalization exists to remove. That is deliberate — the reviewer should see what the document says — but it means comparison must use `normalized_text`.
- `content_hash` over `quoted_text` detects a changed passage but not a moved one. A document edited above a passage shifts its line numbers while the hash still matches.

Open Questions:

- What is the addressable-node granularity for deeply nested structured input? This decision defines it for the two-level shapes the corpus contains and does not generalize.
- Should a chunk that greatly exceeds a size threshold be subdivided, and if so does the subdivision get its own `chunk_index` or a suffix?
- When a source document is re-ingested after an edit, are existing evidence references invalidated, re-anchored, or left stale with a failing hash?
- Does `normalized_text` earn its place on every evidence reference, or only where normalization actually changed something?

## DEC-016: Orchestrate with plain Python and an explicit transition table

Date: 2026-08-09

Status: Accepted

Decision:

Reject LangGraph. The assessment workflow is orchestrated by ordinary Python: a node protocol, an explicit table of permitted transitions, and a persisted `WorkflowRun` row.

A node is a function taking typed input and returning typed output, with a name and a version. The transition table names, for each phase, the phases that may follow it. A transition not in the table is an error rather than an undefined behaviour. Resume is a read of the persisted `WorkflowRun` and its `pending_human_review` block, not a framework checkpoint restore.

The five execution ceilings in `agent-design.md` section 27 — node executions, model calls, retries, cost, duration — are enforced by the orchestrator before each step, against values on `AssessmentConfiguration`.

`langgraph`, `langchain`, and `langchain-anthropic` are removed from `pyproject.toml`. No orchestration or model-framework dependency remains; `anthropic` is the only provider SDK, behind the seam DEC-014 established.

This closes the last Proposed entry in the decision log.

Why:

DEC-007 proposed LangGraph before the workflow's shape was known. The shape is now specified, and it is the case a framework helps least with.

**The pipeline is fixed and linear.** `current-architecture.md` section 5.3 lists fourteen phases in order, with two pause points at phases 5 and 11. There is no analytical branching — the conditional routing that exists is local error handling, where a validation node routes to retry or to human review. Fourteen ordered phases and two pauses is a transition table of about twenty lines. A graph framework earns its cost on graphs whose shape is not known until runtime, and this graph is a list.

**The state design already describes a database row.** `data-model.md` section 31 states that workflow state "should primarily contain identifiers and concise routing information" and that large objects belong in the persistence layer. That is a `WorkflowRun` row. Adopting a framework whose value is managing a state object, for a state deliberately designed to hold no objects, is paying for the part that was designed out.

**A checkpointer would be a second authoritative store.** DEC-006 makes structured, schema-validated domain objects the authoritative workflow state, and the application owns them. A framework checkpointer persists its own serialized copy of whatever it is holding, on its own schedule, in its own format. Two stores of truth that can disagree is precisely the condition DEC-006 exists to prevent, and reconciling them would be ongoing work in service of a dependency rather than of the assessment.

**The limits that matter are application-domain and the framework cannot see them.** Section 27 requires ceilings on model calls, cost, and duration, and `AssessmentConfiguration` carries `maximum_model_calls`, `maximum_cost`, and `maximum_retries_per_node`. A cost ceiling is meaningless to an orchestration framework: it does not know what a model call costs, and after DEC-014 the cost metadata arrives through the seam. Those checks are written either way. What the framework would supply is the part that is already trivial.

The one capability genuinely lost is graph visualization. The README already renders the pipeline as a hand-written Mermaid diagram that is more legible than a generated one, because it distinguishes model-assisted steps, deterministic nodes, and the two human checkpoints — a distinction the framework has no concept of.

Two prior decisions point the same way. DEC-012 made the human checkpoints workflow-graph nodes rather than runtime conditionals and moved the ablation out to the evaluation harness. DEC-014 put the model behind a seam the application owns. Both moved control into the application, and a framework that wants to own the loop cuts against them.

The portfolio consideration favours this as well, and `roadmap.md` Stage 6 asks for the answer either way. "We evaluated the obvious framework, established that a fixed linear pipeline with two pause points does not need it, and removed three dependencies" is a stronger account of engineering judgment than adopting it because it is what these systems usually use.

Alternatives Considered:

- Accept LangGraph as DEC-007 proposed
- Adopt LangGraph only for the human-checkpoint interrupt mechanism, hand-rolling the rest
- A durable-execution engine such as Temporal or Prefect
- A general-purpose state-machine library rather than a hand-written transition table
- Defer again until the first checkpoint is implemented

Tradeoffs:

- **Retries, limits, resume, and visualization are now hand-written.** Each is small individually and the total is not large for this pipeline, but it is code the project owns and must test rather than inherit.
- **The decision is right for the pipeline as specified and could become wrong.** If analysis later needs genuine branching, iterative refinement loops, or parallel node execution, a hand-written orchestrator will grow toward being a worse version of a framework. The trigger to revisit is a workflow that is no longer a list.
- Rejecting the widely used framework means the project cannot lean on its documentation, examples, or the reader's familiarity, and an interviewer expecting it will need the explanation this entry provides.
- Resume across process exit is now entirely the application's problem. That mechanism is still open as DX-07 and this decision constrains it: it must work from a persisted row.
- A hand-written transition table can drift from the phases documented in `current-architecture.md` section 5.3. Nothing currently checks that they agree, and they should be checked once both exist.

Open Questions:

- Should the transition table be data or code, and if data, is it checked against `current-architecture.md` section 5.3 by a test?
- Does the orchestrator need a dry-run mode that walks the table without executing nodes, for evaluation and for verifying the graph matches the documented phases?
- At what point does a workflow stop being a list, and is that trigger observable before the orchestrator has already grown?
- Where do the five execution ceilings live — checked centrally before each step, or by each node?

## DEC-017: Pause by persisting the run and exiting; resume from recorded decisions

Date: 2026-08-09

Status: Accepted

Decision:

A checkpoint pauses by **persisting the run and letting the process exit**. Nothing is held in memory across a human review.

Reaching a checkpoint node sets `WorkflowRun.status` to `paused`, sets `current_node` to the checkpoint, and populates `pending_human_review` with the checkpoint type and the identifiers of the objects awaiting a decision. The invocation then returns. A paused run is a complete, self-describing record on disk.

Resuming is a separate invocation. It loads the run, verifies the checkpoint's completion condition, and continues from the node after the checkpoint. The completion condition is that **every object named in `pending_human_review` has a `ReviewerDecision`**. Partial progress is allowed and persisted; a run with some objects decided stays paused.

**Reviewer decisions reach the workflow through one interface regardless of where they came from.** A decision writer validates a disposition against `ReviewDisposition`, records `prior_value` and `updated_value`, and persists a `ReviewerDecision`. An interactive command, a web form, and an evaluation harness replaying recorded decisions all call the same writer and produce identical rows. Replay is therefore not a test affordance bolted onto an interactive design; it is the same path with a different caller, which is what DEC-012 requires when it says an ablated run and a replayed run are different things.

**`WorkflowRun.checkpoint_reference` is removed.** Its stated purpose was a persistence reference to a framework checkpoint, and DEC-016 removed the framework. `current_node` says where the run stopped and `pending_human_review` says what it is waiting for; a third field pointing at a checkpoint object that no longer exists is vestigial.

**There is no human-review timeout.** `current-architecture.md` section 11 lists one as a failure mode whose response is to pause, preserve state, and resume. Under this decision that is not a failure mode at all — it is the normal state of a paused run, which waits indefinitely because waiting costs nothing when nothing is resident. Section 11's entry is rewritten to say so.

The **review package** is derived from the persisted run rather than stored with it, so it can be rendered by whatever interface DX-17 selects without the pause mechanism presupposing one. Every package carries the objects pending decision, the evidence supporting each with quoted text and source location, the validation results, the human-review triggers that fired, and the open questions with blocking ones first.

Checkpoint 1 additionally carries the extracted architecture — components, actors, assets, data flows, trust boundaries — with each claim's status and confidence, and any contradictions surfaced during extraction. Checkpoint 2 additionally carries, per provisional finding, its severity and confidence, its validation status, both supporting and contradictory evidence, the originating threat and control mapping, its assumptions and limitations, and the critiques raised against it. This closes DEC-005's open question about what is displayed at each checkpoint.

Why:

The alternative that a local single-user application invites is a blocking interactive prompt inside one long-running process. It is the simplest thing that works on a developer's machine and it fails three ways that matter here.

It cannot survive process exit, and DEC-004 makes this a local application a reviewer steps away from. A checkpoint that requires the process to stay alive means reviewing findings is bounded by the terminal staying open.

It is unscriptable, which would force evaluation runs to bypass the checkpoint. DEC-012 draws the distinction between *answering* a checkpoint non-interactively and *removing* it, and holds that only the second is an ablation. A blocking prompt makes them the same thing, because the only way to run unattended is to skip the node. That would quietly undo DEC-012.

And it puts the reviewer's decision in memory rather than in a `ReviewerDecision` row. `data-model.md` section 2.5 requires reviewer actions to be recorded rather than silently overwriting generated content, and the evaluation plan makes reviewer acceptance and edit rates primary metrics. A decision that exists only as a keystroke is not measurable.

Persisting and exiting is also what DEC-016 already implies. Having rejected a framework checkpointer, resume is a database read; a mechanism that resumes from a read is one that can be interrupted arbitrarily, and a process that can exit at a checkpoint is one whose state is genuinely complete on disk. The two decisions want the same shape.

Removing `checkpoint_reference` follows the precedent DEC-012 set with the two configuration booleans: a field whose referent no longer exists is not harmless, because a later implementer will find a use for it and that use will not be the one the schema documents.

Deleting the human-review timeout is the pleasant consequence. A pause that costs nothing to hold does not need a deadline, and the failure mode disappears rather than being handled.

Alternatives Considered:

- A blocking interactive prompt inside a single long-running process
- A file-based review artifact the reviewer edits, read back on resume
- A polling loop that keeps the process alive and watches for a decision record
- Keeping `checkpoint_reference` and redefining it as the review-package identifier
- Storing the review package with the run rather than deriving it

Tradeoffs:

- **Two invocations where a prompt would be one.** Running an assessment now means running it, reviewing, and running it again — which is more ceremony than a demonstration wants, and the demo script has to account for it.
- Deriving the review package on demand means it is recomputed on every render, and a package that is expensive to build makes the review step feel slow. Nothing measures that yet.
- Removing `checkpoint_reference` is a data-model change to a field nothing uses, which is cheap now and would not have been later.
- The completion condition — every pending object decided — is strict. A reviewer with fifty provisional findings must decide all fifty before the run advances, and there is no supported way to say "approve the rest as-is" without recording fifty decisions. That is deliberate, because those decisions are the evaluation data, but it will feel like friction.
- A paused run waiting indefinitely means abandoned runs accumulate with no expiry. Nothing cleans them up.
- The decision assumes the reviewer and the pipeline share a filesystem and a database. That holds under DEC-004 and would not survive the application becoming multi-user.

Open Questions:

- Does a partially-decided checkpoint need to be visible as such, or is "paused with *n* of *m* decided" derivable from the decision rows alone?
- Should resume verify that the objects pending decision still exist and are unchanged since the pause, and what happens when they are not?
- ~~Where does the reviewer identity on a `ReviewerDecision` come from under DEC-004, where there is no authentication?~~ Answered by DEC-023: a configured local string defaulting to the OS username, recorded for evaluation attribution and explicitly not authentication.
- Does an abandoned paused run need an expiry, or is accumulation acceptable for a local single-user application?

## DEC-018: Assign prefixed sequential identifiers at persistence, scoped per assessment

Date: 2026-08-09

Status: Accepted

Decision:

There are **two classes of identifier**, and they follow different rules.

**Authored identifiers** are written by hand and carry meaning. `req-` is the only authored prefix currently in use, in the requirements catalog's `req-AUTH-001`: the prefix names the object type, the middle segment names the category, and the number is assigned by the author. (This sentence originally read "the only class currently in use", which was inaccurate when written: `requirements/catalog.yaml` already called itself `cat-core`. DEC-034 settles that value and states which objects the scheme governs.) They are globally unique, stable across catalog versions, and are the only identifiers a benchmark expected-output file may reference.

**Generated identifiers** are minted during an assessment. They take the form `<prefix>-<NNN>` — `thr-007`, `evd-014`, `fnd-003` — using the prefixes listed in `data-model.md` section 2.1, zero-padded to three digits and widening beyond three when a sequence exceeds 999. They are **unique within their assessment**, not globally; `thr-007` in one assessment and `thr-007` in another are different objects, and an identifier is fully qualified only by `(assessment_id, id)`.

**A generated identifier is assigned by the persistence layer at insert**, from a counter kept per `(assessment_id, prefix)`. It is not assigned at construction. Counters are monotonic: a deleted object's number is never reused.

Identifier generation is therefore a store operation rather than a pure function. That is not a cost this decision introduces — it is already required. Agents return proposal objects that structurally cannot carry an identifier, because `agent-design.md` section 22 forbids an agent minting one and the proposal models omit the field. The application assigns the identifier when it takes ownership of a proposed object, which is a write. Making that assignment sequential costs nothing beyond a counter read in a transaction that was happening regardless.

**No generated identifier appears in a benchmark expected-output file.** Expected outputs reference authored catalog identifiers and match on content — the requirement, the affected components — not on generated identity. This is what frees the scheme from reproducibility pressure: a re-run may number the same logical threat differently, and nothing downstream cares.

`data-model.md` section 2.1's statement that "UUIDs may be used internally, with readable prefixes added for debugging and demonstration" is removed. It described a second scheme alongside the first and the two are not compatible.

Why:

Section 2.1 offered two incompatible schemes in adjacent sentences and every example in the document used the sequential one. The apparent conflict was between readability and reproducibility: sequential identifiers are order-dependent, so a re-run that produces objects in a different order renumbers them, which would break anything holding a stored identifier across runs.

Separating the two classes dissolves it. The thing that would have needed stable identifiers is the benchmark truth set, and it does not use generated identifiers at all — it references catalog identifiers, which are authored and stable, and matches produced objects on requirement and affected component rather than on identity. Once that is stated, order-dependence costs nothing, and the readability argument wins uncontested.

Readability is worth more here than it usually is. Section 2.1 says the prefixes exist "for debugging and demonstration," and this is a project whose output a reviewer reads and whose demonstration is a deliverable. `thr-007` in a report, a log line, or a validation error is legible; `thr-9f2c8a1e-4b21-...` is not, and a reader cannot hold it in mind long enough to match two mentions of it.

The counter objection — that sequential identifiers need per-assessment state and therefore a persistence dependency — is real but already paid. The proposal pattern means the application assigns identifiers during a write no matter which scheme is chosen. A UUID would avoid the counter read and nothing else.

Per-assessment rather than global uniqueness follows the assessment-data boundary in `current-architecture.md` section 12. An identifier that means nothing outside its assessment is one that cannot accidentally address another assessment's object, and every object already carries `assessment_id`.

Alternatives Considered:

- Prefixed UUIDs, as section 2.1's second sentence allowed
- A prefixed short random suffix, avoiding the counter while staying readable
- Content-derived identifiers, stable across re-runs for identical content
- Globally unique sequential identifiers, with one counter per prefix across all assessments
- Assigning identifiers at construction, with the counter held in workflow state

Tradeoffs:

- **Identifier generation cannot be tested as a pure function.** It needs a store, so the unit tests for anything that mints an identifier need one too, in-memory or otherwise.
- Order-dependence means two runs over identical input produce different numbering for the same logical objects. That is harmless under this decision and would stop being harmless the moment something outside the assessment stores a generated identifier — a saved reviewer bookmark, an external tracker reference, a cached report link.
- Per-assessment uniqueness means a bare identifier in a log line is ambiguous without its assessment. Logs and error messages have to carry both.
- Zero-padding to three digits is a guess at scale. Widening past 999 is defined but produces mixed-width identifiers within one assessment, which sorts badly in a lexical sort.
- Monotonic counters mean the numbering has gaps wherever an object was rejected or deleted, and a reader may read a gap as a missing object rather than a discarded one.

Open Questions:

- Does the counter live in its own table, or is it derived from the maximum existing identifier per prefix at insert time?
- Should a rejected proposal consume a number, or should numbers be assigned only to objects that survive validation?
- Do authored identifiers need a validation rule beyond the prefix, given that the catalog's `req-CATEGORY-NNN` shape is currently convention rather than schema?

## DEC-019: Compute content hashes with SHA-256 over a stated input per object type

Date: 2026-08-09

Status: Accepted

Decision:

`content_hash` is **SHA-256**, rendered as `sha256:` followed by 64 lowercase hexadecimal characters. One utility computes and verifies every hash in the system.

The input differs by object type, deliberately, and each is stated:

| Object | Hashed input | Computed | Verified |
|---|---|---|---|
| `SourceDocument` | The original file's **raw bytes**, before any normalization | At ingestion | On re-read, to detect an edited source |
| `EvidenceReference` | The UTF-8 bytes of `quoted_text` | At evidence indexing | By the evidence resolver, before evidence reaches an agent |
| `PromptDefinition` | The UTF-8 bytes of the **composed** prompt, after shared blocks are merged in | At prompt load | At prompt load |
| `RequirementsCatalog` | A canonical re-serialization of the parsed catalog: keys sorted, comments and formatting discarded | At catalog load | At catalog load |
| `Finding` (added by DEC-066) | Sorted `requirement_ids` plus sorted, normalized affected-component names | At creation; recomputed when an identity input changes | By longitudinal consumers |
| `DocumentationGap` (added by DEC-066) | The requirement reached through its mapping, plus that mapping's normalized component names | At creation; recomputed when an identity input changes | By longitudinal consumers |

A source document is hashed over raw bytes rather than normalized text because its hash exists to detect that the file changed, and normalization would mask exactly the changes it is meant to catch. Evidence is hashed over `quoted_text` because DEC-015 makes that field the verbatim excerpt from the original and forbids modifying it after creation. A prompt is hashed after composition because the composed text is what the model receives; hashing the file alone would miss a change to a shared block, which is the change most likely to alter behaviour without anyone noticing.

The catalog is hashed over a canonical re-serialization rather than file bytes so that reformatting, comment edits, and key reordering do not change it. A catalog hash that churns on whitespace reports change where there is none, and a hash that reports change constantly is one nobody reads.

`requirements/catalog.yaml` gains its `content_hash` once the loader exists. DEC-010 omitted it deliberately, on the grounds that no loader existed to compute it; this decision states what the loader computes.

Why:

`content_hash` is required on four objects and DEC-010 left open what computes it and when. A hash over an unstated input is not verifiable: two implementations can both be correct and disagree, and a mismatch cannot be distinguished from a bug.

The single utility matters more than the algorithm choice. Four call sites hashing four kinds of content will drift if each is written where it is needed, and the drift is silent — a hash computed slightly differently still looks like a hash.

Per-object inputs rather than one uniform rule follow from what each hash is for. They are not four conventions but one principle applied four times: hash the thing whose change you want to detect. That is raw bytes for a file, the excerpt for an evidence reference, the composed text for a prompt, and the meaning rather than the formatting for a catalog.

The `sha256:` prefix comes from `data-model.md` section 8's own example, which reads `content_hash: sha256:example`. Fixing it as the format makes it one thing rather than a convention, and leaves room for a second algorithm without ambiguity.

Alternatives Considered:

- One uniform input rule — hash the file bytes — for every object type
- Hashing normalized text for source documents, for consistency with evidence
- Hashing the prompt file rather than the composed prompt
- Hashing the catalog's file bytes, accepting churn on formatting
- A bare hex digest with no algorithm prefix
- Deferring the catalog hash indefinitely, as DEC-010 did

Tradeoffs:

- **Four different inputs is four things to get right**, and the failure mode is quiet: a hash computed over the wrong input verifies against itself forever and only fails when something else changes.
- Canonical re-serialization of the catalog means the hash covers the parsed meaning, so a change that YAML parses identically — a comment carrying real guidance, for instance — does not register. `requirements/README.md` treats prose in the catalog as meaningful, and this hash does not see it.
- Hashing composed prompts means the hash changes when a shared block changes, which is correct and will look alarming: one edit to `evidence-policy-v1.md` changes the hash of every prompt that composes it.
- A source document's hash detects that the file changed but says nothing about where, so a one-character edit invalidates the document's hash while every evidence reference into it still verifies individually. Reconciling those two signals is not specified here.
- As DEC-015 noted, an evidence hash detects a changed passage but not a moved one: an edit above a passage shifts its line numbers while the hash still matches.

Open Questions:

- When a source document's hash no longer matches, are its evidence references invalidated, re-anchored, or left with their own hashes still passing?
- Should the catalog hash cover comments, given that the catalog carries authored prose the parser discards?
- Does anything need to verify a hash on a schedule, or only on read?

## DEC-020: Persist generated objects as JSON payloads in SQLite, keyed by identity and routing columns

Date: 2026-08-09

Status: Accepted

Decision:

**Three stores, split on whether an artifact is authored or generated**, not on whether it is large or small.

**Version-controlled files** hold what a person writes and a reviewer reads in a diff: the requirements catalog, prompt files, and benchmark expected outputs. These are inputs to an assessment, edited in pull requests, and their history belongs in git.

**SQLite** holds everything an assessment generates: assessments, context objects, threats, controls, mappings, findings, questions, documentation gaps, reviewer decisions, workflow runs, execution records, and evaluation results.

**The local filesystem under `data/`** holds generated files too large or too binary for a row: original documents, normalized artifacts, reports, debug artifacts, and traces, in the per-assessment layout of `current-architecture.md` section 5.16, with references and content hashes in the database. `data/` is not version-controlled.

That answers `data-model.md` open question 13. The axis is authorship, not size: a requirement is a file because a person wrote it and a reviewer reviews it, and a threat is a row because a run produced it.

**Objects are stored as JSON payloads with identity and routing lifted into columns.** One table holds every generated object type, keyed by `(assessment_id, id)`, with `object_type`, `status`, and `created_at` as columns and the validated object serialized into a payload column. Pydantic is the only schema; SQLite stores no field definitions.

Adding, removing, or retyping a field is therefore a Pydantic change and not a database migration. That matters because the schema is still moving: DEC-012 removed two fields, DEC-015 constrained three, DEC-017 removed one, DEC-018 rewrote the identifier scheme, and DEC-019 redefined four field descriptions — five schema-affecting decisions in two days, with `data-model.md` section 39 still carrying open questions that will produce more.

**Referential integrity lives in application code**, which is where the corpus already put it. The Context, Threat, and Mapping validation nodes each confirm that referenced objects exist; a foreign-key constraint would duplicate that check in a second place and in a second vocabulary, and the two would disagree the first time a validation rule changed.

**Identifier counters get their own table**, keyed by `(assessment_id, prefix)`, incremented in the same transaction as the insert that consumes the number. DEC-018 requires assignment at persistence, so the counter is a store concern.

**A repository is scoped to one assessment.** Every read is qualified by `assessment_id`, and there is no interface for a cross-assessment query outside the evaluation harness. The assessment-data boundary in `current-architecture.md` section 12 is thereby structural rather than a rule each query must remember.

**Schema versioning refuses rather than migrates.** Every assessment records `data_model_version`. Loading one written by an incompatible version fails with a message naming both versions; there is no migration machinery. That answers open question 17 for early development.

Re-running is cheaper than migrating, and now measurably so: DEC-092's measurement puts a live assessment at $6.92 ± $3.28 (the earlier `scripts/estimate_cost.py` figure was $2.25 to $5.97). Regenerating an assessment costs a few dollars and no engineering time; writing a migration for a schema still under active decision costs hours and produces code that will itself need maintaining. The trigger to add migrations is the point at which an assessment becomes expensive or irreplaceable — real rather than fictional source material, or a benchmark run whose provenance matters.

**Evaluation results and the longitudinal record are additionally written as version-controlled artifacts.** `evaluation-plan.md` section 17 requires every release to record its evaluation summary and known regressions, and section 16 wants metrics compared across versions. If assessments become unloadable after a schema change, a database-only evaluation history would break exactly when the comparison is most interesting. Writing the summary to a file keeps the history readable independent of whether the assessments behind it still load.

Why:

The corpus had already made most of this decision. Section 35 lists what goes in SQLite and what goes on the filesystem, and section 5.15 says the same. What was open was the mapping between Pydantic objects and rows, and the two questions section 39 records.

The mapping question turns on one observation: **the schema is the least stable thing in the project right now.** Five decisions in two days changed it, and the ones still open — severity, contradictions, reviewer edits, confidence — will change it further. An ORM that mirrors the object model in table definitions converts each of those into a migration, and migrations written against a model that is still being decided are work that is thrown away.

A JSON payload keyed by identity and routing columns costs almost nothing to change and serves every query the corpus actually asks for: by identifier, by assessment, by type, by status, and the identifier-following walks that section 32's lineage chain requires. Nothing in the MVP needs to query inside an object.

The corpus also already declined the main argument for a relational schema. Referential integrity is checked by validation nodes in application code, deliberately, because the checks are semantic — a mapping must reference a threat *in the same assessment*, a documented claim must carry evidence — and a foreign key expresses only the first half. Adding constraints would not replace those nodes; it would duplicate part of them.

DEC-004 removes the other argument. A local single-user application, whose process exits at every checkpoint under DEC-017, has no concurrency for a relational engine to arbitrate.

Refusing to load rather than migrating is the same trade in a different place, and the cost estimate is what makes it defensible rather than merely convenient. Before that estimate this would have been an assertion that regeneration is cheap; now it is a figure.

Alternatives Considered:

- SQLAlchemy Core with a hand-written relational schema and Pydantic as a separate domain layer
- SQLModel, fusing the domain object and the table definition
- Filesystem only, one JSON or YAML document per assessment
- One SQLite database per assessment rather than one database with `assessment_id` on every row
- Relational tables for the few objects with stable shapes, JSON payloads for the rest
- Alembic migrations from the first schema

Tradeoffs:

- **The database will accept anything the application writes.** With no column types and no constraints, a bug that writes a malformed object produces a row that loads back as a validation error rather than failing at write time. Pydantic validates on the way in, so this depends entirely on nothing bypassing the repository.
- **A new query axis needs a new indexed column**, which is a migration after all — a cheap one, but the claim that schema changes are free holds only for changes to object *shape*, not to how objects are searched.
- Objects of every type share one table, so a corrupt or oversized payload of one type sits alongside every other. Nothing partitions blast radius.
- **Refusing to load old assessments discards evaluation history at every schema change.** Writing summaries to version-controlled files mitigates this and does not remove it: the underlying assessments are gone, so a result cannot be re-examined, only re-read.
- One database for all assessments makes the assessment-data boundary a property of the repository rather than of the storage. A query written outside the repository can cross it.
- JSON payloads are opaque to database tooling. Inspecting state means loading it through the application, which is a real loss when debugging.
- The decision is shaped by the schema being unstable, and that is temporary. Once `data-model.md`'s open questions close, the reasoning weakens, and this should be revisited rather than assumed.

Open Questions:

- At what point does the schema count as stable enough to revisit this — a closed section 39, a shipped MVP, or the first assessment worth keeping?
- Should the payload column store the object's `data_model_version` alongside it, so a mixed-version database can report precisely which rows are unreadable?
- Does the evaluation harness get a cross-assessment read interface, and if so what prevents it being used from the pipeline?
- Does anything need to detect that `data/` and the database have diverged — an artifact referenced by a row but missing from disk?

## DEC-021: Represent contradictions and injection attempts as one SourceObservation object

Date: 2026-08-09

Status: Accepted

Decision:

Add one object, **`SourceObservation`**, prefix `obs-`. It records something observed **about the source material**, as distinct from an assertion about the reviewed system.

It has a `kind` discriminator with two initial values:

- **`contradiction`** — two or more passages that disagree. Requires at least two evidence references.
- **`injection_attempt`** — a passage that attempts to instruct the reader rather than describe the system. Requires at least one.

Fields: `id`, `assessment_id`, `kind`, `summary`, `evidence_ids`, `subject_claim_ids` (optional, the context claims the observation bears on), `status`, `generated_by`, `reviewer_notes`, `created_at`.

A `SourceObservation` carries **no severity and never becomes a Finding**. A Finding asserts a weakness in the reviewed system; an observation asserts something about a document. Collapsing them would be the DEC-009 failure in a new place.

**A contradiction does not resolve itself.** `forgeflow-scenario.md` section 16.1 states that Trace must not silently choose the safer statement, so the workflow surfaces the disagreement and, where the answer would materially change the assessment, raises a `Question` alongside it. The observation records that the documents disagree; the question asks which is true.

**`ContextClaim` gains no field.** Its `contradicted` status now has a defined meaning: a `SourceObservation` of kind `contradiction` references this claim in `subject_claim_ids`. The reference is one-directional, from observation to claim, so a claim does not need to know what contradicts it and the two cannot disagree about whether they disagree.

`data-model.md` section 2.1 gains the `obs-` prefix. Section 38's deferred-objects list is unchanged; this object is not on it.

Why:

Two open questions asked the same thing twice. `agent-design.md` section 7 lists "contradiction records or flagged claims" as an extractor output and no object represents one. Section 25 says the workflow "may create a ContextClaim or security event indicating that injection-like content was detected" — and no security-event object exists anywhere in the data model, including in section 38's list of things deliberately deferred, which makes it an omission rather than a deferral.

Both are load-bearing rather than hypothetical. The ForgeFlow scenario contains two deliberate contradictions in section 16 and a planted injection payload in section 17, and the benchmark's expected outputs count both. The system is required to surface things it currently cannot represent.

**Neither belongs on `ContextClaim`, and the reason is categorical.** A context claim asserts something about the reviewed system: authentication is delegated, the API is internet-accessible. Its shape — `subject_type`, `subject_id`, `predicate`, `value` — is built for that. A contradiction asserts something about the documentation, and forcing it into that shape leaves no sensible answer to what the subject is or what the value asserts. The `contradicted` status exists precisely because someone noticed the gap and reached for the nearest field.

**One object rather than two** because the two kinds share everything that matters. Both reference source passages, both must reach the reviewer at the context checkpoint, both are counted by the evaluation harness, both are produced by context extraction, and neither is a Finding, a Question, or a DocumentationGap. What differs is the number of evidence references and whether a Question usually accompanies it, which is a validation rule rather than a different object.

Two near-identical objects would also cut against the model's stated instinct. Section 38 defers eighteen object types and section 40 limits the initial implementation set; adding two where one serves is the kind of expansion those sections exist to resist.

The discriminator leaves room for the observations that will follow — a document that appears to describe a different system, a section internally inconsistent with itself — without another object each time.

**One subtlety the ForgeFlow fixture surfaces.** Its injection payload sits in a document that, within the fiction, is a ForgeFlow engineer's repository notes. Detecting it is a Trace behaviour and produces a `SourceObservation`. But the *existence* of injectable content in repository data is also evidence for THR-001, the scenario's own "repository prompt injection manipulates AI output" threat about ForgeFlow. One fixture, two distinct outputs: an observation about the document Trace was given, and evidence for a threat about the system Trace is reviewing. Conflating them would produce a finding about ForgeFlow every time Trace reads a document containing an injection, regardless of whether ForgeFlow is exposed to one.

Alternatives Considered:

- A `ContextClaim` with a dedicated predicate such as `suspicious_instruction_detected`
- Two separate objects, `Contradiction` and `SecurityObservation`
- Adding `contradicts_id` or `conflicting_claim_ids` to `ContextClaim`
- Reusing `Critique` with a `contradictory_analysis` type
- Representing an injection attempt as a `DocumentationGap`
- Recording both only in `ExecutionRecord` metadata, with no first-class object

Tradeoffs:

- **One object with a discriminator means validation is conditional on `kind`**, and conditional validation is where schema bugs live. A contradiction with one evidence reference and an injection attempt with two are both structurally valid until a rule checks them.
- The two kinds may diverge. If contradictions later need a resolution state and injection attempts need a severity, the shared object becomes a union of fields where half are always null — the shape this decision avoided by not creating two objects in the first place.
- `summary` is free text, so counting contradictions in evaluation depends on the extractor producing one observation per disagreement rather than one per document or one per pair of passages. Nothing enforces the granularity.
- The observation-to-claim reference being one-directional means finding what contradicts a given claim requires scanning observations. With the volumes involved that is fine and it is still a scan.
- Adding an object to a model that deliberately limits them needs to stay justified. If neither kind is ever produced outside the demo fixture, this is a schema paying rent for a test.

Open Questions:

- Does a reviewer disposition on a contradiction — confirming which passage is correct — belong on the observation, on the `Question`, or on the `ContextClaim` it resolves?
- Should an injection attempt observed in a source document ever be admissible as evidence for a threat about the reviewed system, or must that always be a separate reviewer judgment?
- What granularity counts as one contradiction when three documents disagree pairwise?
- Does `SourceObservation` need a `status` of its own, given that it records an observation rather than a proposal a reviewer accepts or rejects?

## DEC-022: Confidence is categorical; evidence strength is relational; inferred claims carry a rationale

Date: 2026-08-09

Status: Accepted

Decision:

**`confidence_score` is removed from `ContextClaim`.** Confidence is categorical — `low`, `medium`, `high` — and nothing numeric is stored alongside it. Section 4.2's sentence permitting a numeric score is removed with it.

**`EvidenceStrength` gains a home.** `EvidenceAssessment` gains `evidence_strengths`, a map from evidence identifier to `EvidenceStrength`, covering the references in `evidence_ids`. The type has been defined since the model was written and carried by no field; this is where it belongs.

It belongs there rather than on `EvidenceReference` because **strength is relational, not intrinsic**. The same passage can be direct evidence for one claim and merely contextual for another; a sentence describing an identity provider is direct evidence about authentication and contextual evidence about session handling. A field on the reference would have to pick one.

**`ContextClaim` gains a required-when-inferred `rationale`.** `agent-design.md` section 7 requires inferred claims to carry "a concise rationale" and the object had nowhere to put one — `reviewer_notes` is the reviewer's field, not the agent's. The field is required when `status` is `inferred` or `assumed`, and optional otherwise.

**"Enforce confidence ranges" now means one thing.** `agent-design.md` section 8 gives the Context Validation node that responsibility without saying what it checks. With no numeric score, it checks that `confidence` is a member of `ConfidenceLevel` — nothing more. There is no range, no consistency check between two representations, and no arithmetic.

Why:

Design principle 15 supplies its own decision test: "Does this score help the reviewer make a decision, or merely make the output look precise? Remove metrics that do not improve judgment." Applied to `confidence_score`, the answer is available rather than debatable.

The field appears **exactly once in the entire corpus** — `ContextClaim`'s field table — and is consumed by nothing. No threshold reads it, and after DEC-013 none will: that decision made every threshold a deterministic rule over `satisfaction_status` and `validation_status`, categorical values compared by membership rather than by magnitude. A number that no rule can consume and no reviewer can calibrate is precision with no referent.

Keeping it would also violate the principle it sits under twice over. Principle 15 says to avoid treating confidence as probability, and a decimal from 0 to 1 alongside a three-value enum invites exactly that reading. It says to separate evidence strength from model confidence, and a single score conflates them — a claim can be confidently inferred from weak evidence, or tentatively drawn from strong evidence, and one number cannot say which.

**That separation is what wires up `EvidenceStrength`.** The corpus has both halves of the distinction principle 15 demands and neither was connected: categorical `confidence` sits on objects and means model confidence, while `EvidenceStrength` was defined in section 4.3 and carried nowhere. DEC-013 already relies on the judgment it expresses — its second condition for `unmet` requires knowing whether a cited reference describes absence *directly* or merely *contradicts* a claim of existence — and had to describe that in prose because no field held it.

The rationale field closes the third orphan in the same area. Principle 15's engineering implications list five things, and "require rationales for high-impact uncertain conclusions" is one of them; `agent-design.md` section 7 states the requirement for inferred claims specifically. The object simply lacked the field, which is why the M2 backlog research flagged it.

Alternatives Considered:

- Keep `confidence_score` as optional and never read it
- Keep it but forbid thresholds from consuming it, enforced by review
- Put `EvidenceStrength` on `EvidenceReference` as an intrinsic property
- Change `EvidenceAssessment.evidence_ids` to a list of objects carrying identifier and strength
- Remove `EvidenceStrength` entirely as vestigial
- Reuse `reviewer_notes` on `ContextClaim` for the agent's rationale

Tradeoffs:

- **Removing a documented field is a schema change**, and any reader who had planned on a numeric score loses it. That is the intent, but the field had been in the model since it was written and its absence will surprise someone.
- Three categories is coarse. A reviewer sorting forty claims by confidence gets three buckets, and within `medium` there is no ordering. That is the honest position and it is less useful than a score would *appear* to be.
- `evidence_strengths` as a map keyed by identifier can drift from `evidence_ids` — an entry for an identifier not in the list, or a listed identifier with no strength. Nothing structural prevents it; a validation rule must.
- Making strength relational means the same evidence reference carries a different strength in each assessment that cites it, so "how strong is this passage" has no answer outside a context. That is correct and it complicates any future evidence-quality metric.
- A rationale required only for `inferred` and `assumed` claims means a `documented` claim gets no explanation of why the evidence supports it. The evidence is supposed to speak for itself there, and sometimes it will not.
- Nothing yet consumes `evidence_strengths` either. It is wired to DEC-013's rule, which is written but unimplemented, so this replaces one unused field with another until the mapping validation node exists.

Open Questions:

- Should `EvidenceAssessment.confidence` and the per-evidence strengths be checked for coherence — a `supported` status resting entirely on `contextual` evidence, for instance — or is that the agent's judgment to make?
- Does `Threat`, `ControlMapping`, or `Finding` need per-evidence strength too, or is recording it once at evidence validation sufficient for everything downstream?
- Is `rationale` required for `unknown` and `contradicted` claims as well, or only where the claim asserts something?
- Does removing the numeric score leave the evaluation plan's reviewer-agreement metrics with enough resolution to be meaningful?

## DEC-023: Mutate objects in place, record the delta on ReviewerDecision, version only SystemContext

Date: 2026-08-09

Status: Accepted

Decision:

**Three mechanisms, for three distinct causes.** The corpus already contained all three; they had never been distinguished.

**A reviewer edit mutates the object in place and writes a `ReviewerDecision`.** The decision carries `prior_value` and `updated_value` holding **only the fields that changed**, before and after — not the whole object. `data-model.md` section 25 calls these "relevant prior state," and keeping them to the delta is what makes reviewer edit rate computable per field rather than per object.

**`supersedes_id` records a generated object replacing a prior generated object**, not a human edit. Its case is re-extraction: DEC-017 lists "request re-extraction" as a reviewer action, and the claims that come back supersede the ones they replace. The reviewer's decision to request re-extraction is a `ReviewerDecision`; the claims that result carry `supersedes_id`.

**`SystemContext` is the only versioned object.** Its integer `version` increments on approval, alongside `approved_at` and `approved_by`. It is versioned because it is the approved baseline that every later stage reasons from, and because `current-architecture.md` section 5.6 requires threat analysis to work from that baseline rather than reinterpreting source documents.

History is reconstructed by **replaying decisions in order** against an object's generated state. That satisfies section 2.6's requirement that significant changes remain traceable without the machinery it declines.

`reviewer_id` is a **configured local string**, defaulting to the operating-system username, recorded so evaluation can attribute decisions when more than one person reviews the same benchmark. It is not authentication and must not be treated as such; DEC-004 has no authentication to draw from. This closes DEC-017's open question about where reviewer identity comes from.

Why:

Open question 10 asked whether reviewer edits create new object versions or update the current object with decision history. The corpus answers it in two places that had not been read together.

**Section 2.6 states that "the MVP does not need full event sourcing."** Immutable objects with `supersedes_id` chains on everything is event sourcing in effect, whatever it is called — every read resolves a chain to a head, and every write appends. That option is ruled out by a sentence already in the model.

**`supersedes_id` exists on exactly two objects**, `ContextClaim` and `Requirement`, and `Requirement`'s serves catalog versioning across published catalog versions, which is authored rather than reviewed. If the model intended immutable-with-supersedes as its edit mechanism, the field would be on every object that a reviewer can touch. It is on one.

Meanwhile `ReviewerDecision` carries `prior_value` and `updated_value` — fields whose only purpose is recording what an edit changed. They exist for precisely the mechanism this decision adopts, and would be dead weight under an immutable scheme, where the prior value is simply the superseded object.

Section 2.5's wording is the third confirmation. It says reviewer actions should be recorded "rather than silently overwriting generated content." The load-bearing word is *silently*. Overwriting is acceptable when it is recorded; what is forbidden is losing the fact that a human changed something.

`SystemContext` earns its exception because it is the only object whose *whole* state is approved as a unit. Everything else is approved or edited individually, so a per-object version number would count edits rather than mark a baseline. A context version is meaningful — analysis was performed against version 2 — in a way that a claim version would not be.

Making the delta rather than the whole object the recorded value matters for evaluation. Reviewer edit rate is a primary metric, and "the reviewer changed this finding" is much less useful than "the reviewer changed its severity and left everything else." A whole-object snapshot pair makes that a diff computed after the fact, over objects whose schema may since have changed.

Alternatives Considered:

- Immutable objects with `supersedes_id` chains on every reviewable object
- Whole-object snapshots in `prior_value` and `updated_value`
- Versioning every object with an integer, as `SystemContext` does
- A separate revision table, decoupled from `ReviewerDecision`
- Deriving history from `ExecutionRecord` alone, with no per-object trail

Tradeoffs:

- **Reconstructing an object's history means replaying decisions**, so there is no single query that returns its state at a past moment. For a local single-user MVP with tens of objects that is fine, and it stops being fine at a scale this project is not designed for.
- Recording only the changed fields means a decision is only interpretable against the schema in force when it was written. DEC-020 already refuses to load assessments across incompatible model versions, so the two decisions fail together — but it does mean an old decision cannot be read even in isolation.
- The reviewer sees current state, not generated state, so "what did the model originally say" requires walking back. That is the intended trade for a simple read path, and it makes the lineage view — a Stage 5 deliverable — do real work rather than a straight read.
- Three mechanisms for three causes is more to explain than one uniform rule, and a future implementer may reach for `supersedes_id` when editing, or write a decision when superseding. The distinction is by cause, which is a judgment, not a type.
- `reviewer_id` defaulting to an OS username is trivially forgeable and looks like identity in a data model that also records approvals. Nothing enforces that it is not read as authentication.

Open Questions:

- Should a reviewer edit that reverts an earlier edit be recorded as a new decision or as a retraction of the prior one?
- Does `Finding` need `supersedes_id` for re-consolidation, in the way `ContextClaim` has it for re-extraction?
- When a reviewer edits an object that a later stage has already consumed, does anything invalidate the downstream work?
- Is per-field delta granularity sufficient for a nested field, or does an edit inside `metadata` need its own path notation?

## DEC-024: Pass the whole catalog to one mapping agent; there is no deterministic pre-filter

Date: 2026-08-09

Status: Accepted

Decision:

**Requirement and Control Mapping is one model-assisted agent**, as `agent-design.md` section 12 defines it. There is no separate deterministic requirement matcher.

**The whole requirements catalog is passed on every mapping call.** At 23 requirements and roughly 12,600 tokens it fits comfortably, and DEC-014's capability-aware seam makes it a stable cacheable prefix across the ten or so mapping calls in an assessment.

**A requirement is evaluated only through a threat.** `ControlMapping.threat_id` is required and stays required. The consequence is stated rather than left implicit: **a requirement that applies to the system but that no threat reaches is never evaluated and appears nowhere in the assessment.** Coverage is therefore bounded by threat generation, and the evaluation plan's false-negative rate is what detects a systematic miss.

**The discrimination constraint is satisfied at the output, not the input.** `agent-design.md` section 12 prohibits applying every catalog requirement to every component and makes undiscriminated applicability a failure condition. Those constrain what the agent *concludes*, not what it is *shown*. Every mapping carries a non-empty `applicability_reason`, and a mapping run in which no requirement is marked `not_applicable` or `conditionally_applicable` is flagged by the Mapping Validation node.

Why:

The issue that framed this recommended a deterministic requirement pre-filter with the mapping agent behind it. **That recommendation was written before checking whether the filter fields carry data, and they do not.**

`applicable_technologies` is the only structured filter field in the section 17 schema. It is populated on **zero of the twenty-three requirements**. There is nothing to filter on.

The remaining candidates fail for their own reasons. `applicable_conditions` and `non_applicable_conditions` are populated on every requirement — 48 and 46 entries — and are free text, deliberately: `requirements/README.md` records that no controlled vocabulary was introduced so the vocabulary could be observed before being fixed. Free text is model-readable and not filterable. Category is the only structured axis with data, at 17 distinct values, but filtering on it requires deriving a category from a threat, and that derivation is a judgment. Implementing it as a hand-written table from threat type to requirement category would reproduce exactly the mechanical checklist behaviour `current-architecture.md` section 2.2 rejects; implementing it with a model makes it a second model-assisted step, which is the seventh agent the cap exists to prevent.

So a deterministic pre-filter is not merely unnecessary here — it has no input. Recording that plainly matters more than the conclusion, because the recommendation reads plausibly and the data contradicting it is one query away.

Passing the whole catalog is affordable and becomes more so under caching. The catalog is the single largest stable prefix in the pipeline, reused across every mapping call, which is exactly the shape prompt caching serves.

The confusion the section 12 prohibition invites is worth naming. "Apply every catalog requirement to every component" describes an output in which everything is marked applicable. It does not describe an input. Reading it as an instruction to narrow the input is the likely implementation error, and it would produce a system that silently never considers most requirements — a false-negative machine whose failure is invisible because the requirement never appears at all.

How this scales, when it stops:

The escalation path is stated here so the next person is not choosing under pressure.

**First, partition and fan out deterministically.** Split the catalog into a handful of domains and run the mapping agent once per threat *per domain*, so each call sees a fraction of the catalog. Discrimination improves because the input is narrower, and **nothing is excluded**, because every partition runs for every threat. There is no filtering judgment to get wrong, which is what separates this from a pre-filter: an excluded requirement produces no mapping to inspect, and a partitioned one produces the same mappings in more calls.

The cost is not where it appears. Caching makes the input roughly equivalent either way — five partition writes plus forty-five reads comes to about what ten full-catalog calls cost. What multiplies is the call count, and `scripts/estimate_cost.py` found thinking to be roughly 85% of spend. Each partitioned call should think less, having fewer requirements to weigh, so the increase is not proportional to the call count, but it is real and currently unmeasured.

**Then, structured applicability.** Requirements gated by a small set of system-level questions answered once per assessment — whether the system processes customer data, whether it delegates authentication — so whole groups become inapplicable on evidence rather than on a guess. That is `data-model.md` question 5, deliberately left open so the vocabulary could be observed rather than imposed, and the catalog is where the observation happens: the 48 `applicable_conditions` and 46 `non_applicable_conditions` entries written so far are its raw material. Twenty-three requirements are not enough signal to derive it from; somewhere before two hundred there will be.

Populating `applicable_technologies` is the weakest of the three. It is hand-authored, drifts as technologies are renamed, and reintroduces the invisible-exclusion failure this decision avoided.

Alternatives Considered:

- A deterministic pre-filter on `applicable_technologies`, once populated
- A category filter driven by a hand-written threat-to-category table
- A model-assisted retrieval step, accepting a seventh agent
- Semantic retrieval over requirement text, once vector infrastructure exists
- Batching requirements across several calls per threat
- Making `threat_id` optional so requirements can be evaluated against the system directly

Tradeoffs:

- **This does not scale with the catalog**, and what breaks first is not what it looks like. Cost and context are not the constraint: at two hundred requirements the catalog is roughly 110,000 tokens, which under DEC-014's caching costs about a dollar per assessment and occupies a tenth of the context window. **Discrimination quality is the constraint.** Section 12's failure condition is undiscriminated applicability, and the wider the input the likelier it becomes. It degrades continuously rather than at a threshold, so the trigger is measured applicability precision — which `evaluation-plan.md` section 7 already tracks as correct and incorrect applicability under Requirement Mapping — not a token count.
- Passing everything means the agent sees requirements that are obviously irrelevant, and every one is an opportunity to mark something applicable that is not. The discrimination requirement is enforced downstream rather than prevented upstream.
- **Threat-gating leaves a real coverage gap.** A whole category of requirement can go unevaluated because threat analysis did not produce a threat that reaches it, and nothing in the assessment says so. Populating `applicable_technologies` would not close it either; only a system-level applicability pass would.
- The output-side enforcement — requiring at least one `not_applicable` mapping — is a heuristic. A threat that genuinely implicates most of a small catalog would trip it.
- Caching the catalog makes the prefix sensitive to catalog edits: changing one requirement invalidates the cached prefix for every mapping call in every subsequent assessment until it is rewritten.

Open Questions:

- What applicability-precision figure is low enough to trigger partitioning, and over how many assessments must it hold before the trigger fires?
- Partitioning trades money for discrimination at an unmeasured exchange rate. How much less does a call over a fifth of the catalog think, and is the total increase closer to 2x or 5x?
- Does the coverage gap from threat-gating need a system-level applicability pass, and would that be a seventh agent?

## DEC-025: Record suppressed conclusions on the mapping that suppressed them

Date: 2026-08-09

Status: Accepted

Decision:

When a mapping declines a negative conclusion because a `common_false_positives` entry applies, the `ControlMapping` records it. Two fields are added:

- **`suppressed_conclusion`** — the conclusion not drawn, in the agent's words.
- **`suppressed_by`** — the `common_false_positives` entry that applies.

**Suppression is never silent.** DEC-011 records that nothing enforces the field is consulted, and asks whether a suppressed conclusion should be recorded rather than discarded. It should. `evaluation-plan.md` section 8 makes false-negative rate a primary metric and DEC-011 names over-suppression as the field's principal risk; a suppression that leaves no trace is invisible to exactly the measurement meant to catch it.

**Enforcement is a deterministic check that does not require semantic matching.** The Mapping Validation node rejects a mapping that proposes `unmet` against a requirement carrying `common_false_positives` entries unless the mapping states why those entries do not apply. The check is structural — does the mapping address the field — rather than an attempt to decide whether an entry matches, which free text cannot support.

The distinction DEC-011 draws stays load-bearing and is restated where an implementer will meet it: **`common_false_positives` is not `non_applicable_conditions`.** The latter says the requirement does not apply at all. The former says the requirement *does* apply, the documentation is silent, and a particular conclusion is still wrong.

Why:

The field was added by DEC-011 and its own Tradeoffs section states the problem: "Nothing yet enforces that the field is consulted." It is populated on all 23 requirements with 51 entries and read by nothing.

Recording rather than discarding is the answer to DEC-011's first open question, and the argument is a measurement one. The catalog encodes fifty-one specific wrong conclusions that should not be drawn. If suppressing one leaves no record, then a catalog entry that is too aggressive — suppressing a conclusion that was actually correct — produces a false negative that no metric can attribute. The false-negative rate would move and nothing would say why.

Putting the record on the `ControlMapping` rather than in a new object keeps it where the decision happened. A suppressed conclusion is not a free-standing thing; it is a property of one requirement-threat-control evaluation, and it is meaningless detached from that. DEC-021 added an object for observations about *source material*, and this is deliberately not that — it is an observation about the analysis.

The structural enforcement is the part that can actually be built. Deciding whether a free-text `common_false_positives` entry matches a proposed conclusion is a semantic judgment, and a validation node that attempted it would be a model call in a deterministic node. Requiring the mapping to *address* the field is checkable without judgment, and it converts the failure mode from "the agent never looked" to "the agent looked and said why" — which is the difference DEC-011 was reaching for.

Alternatives Considered:

- A separate `SuppressedConclusion` object
- Recording suppressions only in `ExecutionRecord` metadata
- Extending `SourceObservation` with a third kind
- Semantic matching in the validation node, deciding whether an entry applies
- Leaving suppression silent and relying on the false-negative rate alone

Tradeoffs:

- **Two more fields on an object that is already the most complex in the model.** `ControlMapping` carries the threat, requirement, control, both status vocabularies, and the applicability reason; this adds to that.
- The structural check verifies that the mapping addressed `common_false_positives`, not that it addressed them *correctly*. An agent can satisfy it with a plausible sentence about why the entries do not apply while being wrong.
- `suppressed_by` referencing a free-text entry means the reference is by content rather than by identifier, so an edit to the catalog breaks the link in stored mappings.
- Requiring the check only for `unmet` leaves `partially_satisfied` unguarded, and a partial satisfaction is a negative conclusion too.
- Recording suppressions makes them countable, which invites optimizing for the count. A low suppression rate is not obviously better than a high one.

Open Questions:

- Should `common_false_positives` entries carry identifiers so `suppressed_by` can reference them stably?
- Does `partially_satisfied` need the same check as `unmet`?
- Is a suppression the reviewer disagrees with a reviewer decision on the mapping, or something that should feed back into the catalog?

## DEC-026: Express inherited-control scope with the fields Control already has

Date: 2026-08-09

Status: Accepted

Decision:

**`Control.inheritance_scope` is removed.** Scope is expressed by fields the object already carries:

- **`provider_component_id`** — who provides the control.
- **`protected_component_ids` and `protected_asset_ids`** — what it covers.
- **`limitations`** — where the coverage stops.

Together those say what a free-text scope string was trying to say, in a form that can be validated, queried, and compared against the architecture.

**Two states are distinguished by existing field combinations**, and the distinction is the one the ForgeFlow scenario turns on:

| Situation | `control_type` | `implementation_status` | Evidence | Outcome |
|---|---|---|---|---|
| The platform provides it and the documentation says so | `inherited` | `implemented` | present | Control is satisfied |
| The platform probably provides it and nothing says so | `inherited` | `claimed` | absent | A `Question` requesting confirmation |

The second **never resolves to `absent`**, and by DEC-013 never to `unmet`. That is `forgeflow-scenario.md` section 14.2 — managed database encryption, which the application documentation does not describe — and it is one of the scenario's named intentional non-findings.

Why:

`inheritance_scope` was a free string, and `data-model.md` question 6 and `current-architecture.md` question 5 both asked how inherited-control scope should be modelled. The answer is that it already is.

`provider_component_id` names the provider. The protected component and asset lists name the coverage. `limitations` names the boundary. A free-text scope field sits alongside those describing the same thing in prose, which means it can disagree with them, and when it does nothing says which is right. Removing it is the third field removed for this reason — after `checkpoint_reference`, whose referent had gone, and `confidence_score`, which nothing consumed.

The structured form is also the only one the metric can use. "Inherited-control recognition" is a named evaluation criterion in `agent-design.md` sections 12 and 32 and `evaluation-plan.md` section 7. Measuring it means comparing what the assessment concluded against what the scenario says is true, and a free-text scope string cannot be compared to anything. Structured provider and coverage references can.

The two-state distinction matters more than the field removal. ForgeFlow contains six inherited or shared controls, and the scenario's intentional non-findings turn on treating undocumented-but-inherited correctly. The failure mode is not concluding the wrong scope; it is collapsing "inherited and documented" into "inherited, therefore fine" or collapsing "undocumented" into "absent." Expressing both as combinations of `control_type` and `implementation_status` makes the difference checkable rather than a matter of the agent's phrasing.

Alternatives Considered:

- Keep `inheritance_scope` as free text and let the agent populate it
- Give `inheritance_scope` a controlled vocabulary
- Add a structured `inheritance` sub-object carrying provider, coverage, and limits together
- Add an `inheritance_confidence` field distinct from `validation_status`
- Model inherited controls as a separate object type

Tradeoffs:

- **Removing a documented field is a schema change**, and an implementer who expected somewhere to put "the platform encrypts data at rest in this region only" now puts it in `limitations`, which is a list of strings and is a slightly worse fit than a dedicated field would be.
- Expressing scope through references means an inherited control cannot describe coverage the architecture does not model. If the platform protects something Trace never extracted as a component or asset, there is nowhere to say so.
- The two-state table is a convention over two independent enums rather than a single state. Nothing structurally prevents `inherited` with `implementation_status: absent`, which is a combination that should not occur.
- `limitations` now carries two kinds of thing: where an inherited control's coverage stops, and known weaknesses of an implemented one. Those read differently and share a field.
- Six inherited controls in one scenario is a small sample to design a representation against.

Open Questions:

- Should the `inherited` and `absent` combination be rejected by validation, or is there a case for it?
- When an inherited control's provider is a component Trace did not extract — a platform outside the reviewed system — what does `provider_component_id` reference?
- Does distinguishing inheritance from a compensating control need more than `control_type`, given that both reduce a requirement's applicability by pointing elsewhere?

## DEC-027: Derive the benchmark scenario layout from the object model; ForgeFlow keeps its location

Date: 2026-08-09

Status: Accepted

Decision:

**The two layout specifications were never competing.** `evaluation-plan.md` section 5 describes a whole scenario directory and `forgeflow-scenario.md` section 25 describes only its expected subdirectory. They overlap on three files — `expected-context.yaml`, `expected-threats.yaml`, `expected-findings.yaml` — and agree on all three. What looked like a conflict is one list of inputs and one list of outputs, written in different documents without either naming which half it covered.

**A scenario directory has two subdirectories:**

```
<scenario>/
  input/                     the material supplied to Trace
  expected/                  the truth set, never supplied to Trace
    expected-*.yaml
    reviewer-notes.md
    evaluation-contract.yaml
```

**The expected file list is derived, not enumerated.** There is one `expected-*.yaml` per domain object type the pipeline produces and the benchmark grades, plus `expected-rejections.yaml` for the negative set. Enumerating the list in prose is what produced this issue: DEC-021 added `SourceObservation` and no document was updated, so the contract counts contradictions and an injection fixture that section 25's seven files have nowhere to hold.

Under the current object model that is: `expected-context.yaml`, `expected-threats.yaml`, `expected-control-mappings.yaml`, `expected-findings.yaml`, `expected-questions.yaml`, `expected-documentation-gaps.yaml`, `expected-observations.yaml`, `expected-rejections.yaml`. **`expected-observations.yaml` is new here** and covers both `kind` values DEC-021 defined, because they are one object type and get one file.

**The filename is `reviewer-notes.md`.** `evaluation-plan.md` section 5's `review-notes.md` is corrected. The corpus uses "reviewer" as the actor noun throughout — reviewer acceptance rate, reviewer edit rate, reviewer notes on the domain objects — and consistency with that is the only thing distinguishing the two spellings.

**`requirements.json` is dissolved rather than resolved.** It predates the requirements catalog, and DEC-024 removed the role it would have had: the whole catalog is passed on every mapping call, so a per-scenario requirement file could only narrow what the pipeline sees, which is the pre-filter DEC-024 rejected. What it was reaching for is a version pin, so the scenario records `catalog_version` in `evaluation-contract.yaml` and expected control mappings reference catalog identifiers directly. **This answers DEC-010's first open question** — not by making the file reference identifiers, but by removing the file.

**ForgeFlow stays at `demo/forgeflow/`; `benchmarks/<slug>/` holds scenarios two onward.** The split is by role and it is real. ForgeFlow is the demo *and* benchmark scenario one, and the demo half is `forgeflow-scenario.md` — a 40,000-character narrative that exists to be read by a person and feeds roadmap Stage 6. Scenarios two through twelve have no such document and exist only to be measured. Both use the layout above.

**The harness discovers scenarios from `benchmarks/scenarios.yaml`, never by globbing a directory.** This is the part that makes two locations safe. A registry naming each scenario and its path makes the benchmark set a stated fact; directory discovery would make it a fact about the filesystem, and two discoverable homes would reproduce the specified-twice failure this entry exists to remove.

`CLAUDE.md`'s repository layout records the split.

Why:

Reconciling the two lists by picking a winner would have discarded correct information from whichever lost. Section 5 is the only place that says a scenario carries its own inputs; section 25 is the only place that says the expected files must never be supplied to Trace. Both are right about the half they describe.

The derivation rule matters more than the list it currently produces. An enumerated list is a second source of truth about the object model, and it drifts the moment the model changes — which is not hypothetical here, it is the state the corpus was found in. Deriving the list means a new object type produces a new expected file by construction, and the layout cannot silently fall behind `data-model.md`.

Keeping ForgeFlow in place is also the cheap answer, and that is worth stating plainly rather than dressing up: the path appears 153 times across 46 files outside `demo/`, and in 29 open issue bodies that cannot be rewritten as easily as a document can. But the role split is what makes it correct rather than merely convenient. If ForgeFlow were only a benchmark, it would move.

Alternatives Considered:

- Pick section 5 or section 25 as authoritative and correct the other
- Move ForgeFlow to `benchmarks/forgeflow/` and leave `demo/` holding only the narrative
- Keep everything in `demo/` and delete `benchmarks/`
- Enumerate the expected files in `evaluation-plan.md` and update it when the object model changes
- Keep `requirements.json` as a per-scenario catalog subset
- Discover scenarios by globbing `benchmarks/*/` and `demo/*/`

Tradeoffs:

- **Two homes for one kind of artifact is a smell.** The registry makes the set stated rather than discovered, and `tests/unit/test_benchmark_layout.py` asserts that every directory under `benchmarks/` is registered and that every registry entry resolves to a directory holding `input/` and `expected/`. What remains a convention is the layout rule itself: nothing prevents a scenario whose expected files are named something else, because the expected files do not exist yet to be checked against.
- The derivation rule means adding a domain object type adds a benchmark file, including for object types the benchmark has no useful expectation about. `expected-observations.yaml` is well motivated; a future object may not be.
- Dissolving `requirements.json` ties the scenario to `catalog_version` as its only requirement-side pin. If a scenario ever needs a requirement the catalog does not contain, there is now nowhere to put it, and the answer would be to add it to the catalog.
- `evaluation-contract.yaml` sits inside `expected/`, so the whole directory is what must never be supplied to Trace. That is a simpler rule than a per-file one, and it means the contract cannot be read by anything that legitimately reads inputs.
- Correcting `review-notes.md` to `reviewer-notes.md` is a coin flip dressed in a consistency argument. It is recorded so it is only decided once.

Open Questions:

- Does the demo-versus-benchmark split survive scenario two, or does ForgeFlow's narrative turn out to be something every scenario wants?
- `architecture-overview.md` section 26 lists source-artifact retention as a known documentation gap while `operations-guide.md` states a 30-day period affirmatively. Is that a third intentional contradiction, or an authoring slip in the fixture?

## DEC-028: The expected set is enumerated; the contract declares no counts

Date: 2026-08-09

Status: Accepted

Decision:

**`evaluation-contract.yaml` declares no expected-output counts.** The `expected_outputs` block and the `disputed` block are both removed. The contract keeps `benchmark_version`, gains `catalog_version` per DEC-027, and otherwise holds grading policy rather than grading targets.

**The expected set is the enumerated content of the `expected-*.yaml` files.** A count is `len()` of a file, derived when a report needs one, and stored nowhere.

**This resolves the count conflict by removing the thing that could conflict.** Three findings against four, and five questions against ten, were disagreements between a declared number and an enumerated list. A declared count that can disagree with its own enumeration is a second source of truth, which is the same defect DEC-027 removes from the layout.

**Matching is semantic, not numeric.** Expected-to-actual matching is on requirement and affected component, as established when the identifier scheme was settled in DEC-018; it was never a count comparison.

Why:

A declared count is a finding quota with a different name. `design-principles.md` section 9 and `evaluation-plan.md` section 20 both state that Trace must not optimize for finding volume, and `CLAUDE.md` lists it as a binding constraint. Issue #18 removed exactly this data from the input fixture because holding it there handed the pipeline its own target. Moving it out of the input made it unable to reach the pipeline; removing it makes it unable to become the metric.

The counts were also wrong, which is a weaker argument but a real one. DEC-029 finds three findings rather than four, and four documentation gaps rather than three, and both numbers move again the first time a fixture document is edited. A number that has to be maintained in parallel with the thing it describes will fall behind it.

Section 20's selection rule — questions prioritized by their ability to change findings — is a better specification of the expected question set than any count, because it states what makes a question expected. Ten candidates and a target of five never said which five, and the rule does.

Alternatives Considered:

- Correct the counts to 3 findings and 6 questions and keep them declared
- Keep counts as an assertion checked against the enumeration by a test
- Keep counts only in the scenario document, not in the contract
- Declare ranges rather than exact counts

Tradeoffs:

- **A count is a cheap smoke test and it is gone.** An assessment producing thirty findings against an expected three is obviously broken, and a declared number would catch that before any semantic matching runs. The enumerated set still catches it, but only after the matcher runs.
- The enumerated files do not exist yet, so the contract currently declares less than it did and the expected set is nowhere. That is a real regression in what is written down, held until the M3 and M4 authoring issues land.
- Removing the `disputed` block removes a record of the conflict. It is preserved here and in the journal instead, which is the right place, but the fixture no longer carries its own warning.
- Deriving counts on demand means two reports can disagree about how many findings a scenario expects if the files change between them. Version control makes that answerable rather than preventing it.

Open Questions:

- Should a scenario declare an expected *order of magnitude* — a handful, not thirty — as a cheap guard that is not a quota?
- `evaluation-plan.md` section 19 question 1 asks how expected findings are established. This entry says how they are stored and matched, not how they are decided. Who authors a truth set, and does a second reviewer confirm it?

## DEC-029: ForgeFlow expects three findings; FND-001 is a documentation gap and FND-004 is its own finding

Date: 2026-08-09

Status: Accepted

Decision:

**FND-001, webhook replay protection, is not a finding.** It is a `DocumentationGap` and a `Question`. `forgeflow-scenario.md` section 19 is corrected and section 21 gains **GAP-004**.

DEC-013 forces this. Section 19 requires evidence establishing that "delivery identifiers are not tracked", and no document establishes it: `github-integration.md` section 6 says only that webhook requests are validated, `operations-guide.md` section 3 shows a delivery identifier in the job payload without mentioning deduplication, and `architecture-overview.md` section 26 lists **"Webhook replay handling"** under Known Documentation Gaps. The only direct evidence is a document stating the topic is undocumented, and treating that as evidence of absence is the DEC-009 failure exactly.

**FND-003 survives the same test, and the contrast is the point.** Retention is also listed as a section 26 gap, but `operations-guide.md` states a 30-day period affirmatively. FND-003 rests on a positive statement; FND-001 rests on silence. Two neighbouring subjects falling on opposite sides of the DEC-009 line is worth more as a benchmark than either alone.

**FND-004 is a separate finding from FND-002, resolving `forgeflow-scenario.md` open question 8.** Section 19's own consolidation test is whether "the remediation and impact are substantially related". They are related and not the same: FND-002 needs a human approval gate before external publication, FND-004 needs isolation of untrusted repository content from model instructions. Either can be fixed without the other, and fixing only one leaves a real exposure. Trace consolidating them at runtime remains defensible behaviour; the truth set does not pre-consolidate them.

**The expected findings are FND-002, FND-003, FND-004 — three.** The number the contract recorded was right and the scenario document's four was right about the candidates. What drops out is FND-001, not FND-004, so both documents were partly correct and the disagreement was never about the number.

Per DEC-028 the count is not declared anywhere; it is what the enumerated file will contain.

Why:

The webhook case is the most valuable single item in this benchmark. A generic security review reports an undocumented control as a missing control, and section 26 is a document *volunteering* that a topic is not covered here. A system that concludes "no replay protection" from that sentence has committed the failure this project exists to avoid, and it will do so confidently, because the sentence is about the right subject.

Keeping FND-001 as an expected finding would have graded that failure as correct.

Splitting FND-002 and FND-004 is the less certain call. Section 19 explicitly permits consolidation, so a truth set that expects two must not penalize a system that produces one well-reasoned combined finding. That is a matching-policy consequence rather than a reason to expect one: the expected set records the finer decomposition because it can be collapsed by a matcher, and a coarser one cannot be split.

Alternatives Considered:

- Add a passage to the input fixture affirmatively establishing that delivery identifiers are not tracked
- Keep FND-001 as a low-confidence finding rather than a gap
- Consolidate FND-004 into FND-002 and expect two findings
- Expect four findings and let the matcher accept three

Tradeoffs:

- **Removing FND-001 makes the scenario slightly easier to score well on and harder to score correctly on.** A system that reports nothing at all about webhook replay now scores the same on findings as one that correctly raises a gap and a question — the distinction only appears in the gap and question metrics.
- Expecting three findings where the scenario document promised four invites the reading that Trace under-reports. The scenario document has to say why, at the point where the finding was.
- The FND-002 and FND-004 split depends on a matcher that can accept one combined finding against two expected. That matcher does not exist and this entry assumes it will.
- GAP-004 makes four documentation gaps where the contract recorded three. Under DEC-028 no count needs correcting, but any prose quoting "three gaps" does.
- Section 20's candidate question 2 — whether delivery identifiers are stored and checked — becomes load-bearing rather than optional, since it is the question GAP-004 must raise.

Open Questions:

- Does GAP-004 need its own entry in section 21, or is a documentation gap that a source document self-declares a different category worth naming?
- How does the matcher score one combined finding against two expected ones — full credit, partial, or a separate consolidation metric?
- Section 22 lists ten rejected findings. Should "ForgeFlow lacks webhook replay protection" join them, given that it is now the most likely wrong conclusion in the scenario?

## DEC-030: The reviewer assigns severity; there is no Severity Support Agent

Date: 2026-08-09

Status: Accepted

Decision:

**The MVP has six model-assisted agents. The Severity Support Agent is not built.** It is not deferred pending evidence; it is excluded because four of its six specified outputs already exist as required `Finding` fields produced by other agents.

`agent-design.md` section 17 lists the agent's outputs as recommended severity, impact rationale, likelihood rationale, confidence, factors that could increase or decrease severity, and missing information. Against the `Finding` schema:

| Section 17 output | Already exists as |
|---|---|
| Impact rationale | `Finding.impact`, required |
| Likelihood rationale | `Finding.likelihood` |
| Confidence | `Finding.confidence`, required |
| Missing information | `Finding.limitations` and `Finding.assumptions` |
| Factors that raise or lower severity | nothing |
| Recommended severity | `Finding.severity` |

**The pipeline already produces the reasoning severity rests on.** A seventh agent would re-derive it from the same inputs and add one enum value. That is not the specific quality gap section 36 requires before an agent is added; it is a second pass over work already done.

**The reviewer assigns severity at checkpoint 2.** `current-architecture.md` section 5.12 already lists changing severity as a reviewer action, so this makes an existing authority the origin rather than a correction. Findings are created with `severity: unassigned`.

**Finding Consolidation does not assign preliminary severity.** The bullet is removed from `current-architecture.md` section 5.11. A deterministic node has the same problem the agent has and less judgment to apply.

**`unassigned` cannot survive approval.** A validation rule at checkpoint 2 rejects an approval whose finding still carries `unassigned`. This is the load-bearing half of the decision: without it, reviewer-assigned severity degrades into nobody assigning severity, and the report is a list of findings with no ordering.

**A severity change is recorded as `edit`, with `prior_value` and `updated_value` on `ReviewerDecision`.** No `change_severity` disposition is added. DEC-023 settled the mechanism, and a second way to express an edit would be a second source of truth about what the reviewer did.

`current-architecture.md` section 5.12 lists "Change severity" alongside "Edit a finding", which reads like a conflict and is not one. **Section 5.12 lists actions a reviewer takes; `ReviewDisposition` lists dispositions the system records.** Those are different lists and do not need to correspond one to one. The section is annotated to say so, because the next reader will otherwise resolve the apparent mismatch by adding an enum value.

**Benchmark expected severities are reviewer guidance, not graded output.** `forgeflow-scenario.md` section 19 states an expected severity per finding. Severity is not a pipeline output, so it is not scored; the value exists so that whoever plays the reviewer in a benchmark run does not introduce variance between runs. `evaluation-plan.md` never measured severity and gains no metric here.

Why:

**Severity is the one required `Finding` field that the source documents cannot answer.** Every other judgment in the pipeline is an evidence judgment — does the documentation support this conclusion — and DEC-009, DEC-013 and DEC-022 all draw that line deliberately. Severity is a risk judgment in business context: what an outage costs, what the data is worth, what this organization tolerates. Architecture documents do not contain it.

An agent asked for severity would therefore produce a fluent answer from documents that do not contain the answer. That is the DEC-009 failure relocated into a different field, and it would be harder to detect there, because a severity label carries no evidence reference and nothing in the schema would show it was unsupported.

The reviewer is already at checkpoint 2 examining each finding, and already holds the context severity depends on. Assigning it is not additional work imposed on them; it is the judgment they are there to make.

The cap argument reaches the same conclusion and is weaker, so it is recorded second. Section 36 requires a specific quality gap identified by evaluation before an agent is added, and the evidence cannot exist before the agent does. Left undecided, the agent would have been built because it is the most completely specified component in the corpus — ten evaluation factors, six outputs, five prohibited operations — and specification completeness is not evidence of need.

A deterministic heuristic was the other real candidate, and design principle 7 favours it. It fails on data. The fields a rule would use — `internet_exposed`, `business_criticality`, the confidentiality, integrity and availability impact fields, `data_classification` — are all optional, and most are free-text strings with no controlled vocabulary. `data-model.md` section 4.5 warns against a complex severity algorithm before the core workflow is validated, and a simple one over optional free text would be arbitrary rather than simple.

Alternatives Considered:

- Build the Severity Support Agent and record a cap change to seven
- Build it behind a flag, off by default, and evaluate it later
- A deterministic heuristic in Finding Consolidation from asset and exposure fields
- A deterministic floor only — a rule that constrains the range without picking a value
- Leave `severity` at `unassigned` through approval and let the report omit ordering
- Add `change_severity` to `ReviewDisposition`

Tradeoffs:

- **This makes the reviewer's job at checkpoint 2 strictly larger**, and checkpoint 2 is already the heaviest step in the workflow. Every approved finding now requires a severity decision that was previously going to arrive pre-filled. For an assessment with many findings that is real friction, and it is the most likely reason this decision gets revisited.
- **A blank field is a worse prompt than a wrong one.** A proposed severity gives the reviewer something to disagree with, and disagreement is faster than origination. That is the strongest argument for the agent and it is not answered here, only outweighed.
- Excluding the agent removes `agent-design.md` section 17's evaluation criteria — reviewer severity agreement, overstatement rate, understatement rate — which cannot be measured without a proposal to compare against. Those were among the more concrete metrics in the corpus.
- **Nothing now measures severity at all.** `evaluation-plan.md` mentions it zero times, and this entry does not add a metric. Severity quality is unobserved, so a reviewer assigning severity badly would leave no trace.
- The "factors that could increase or decrease severity" output has no home in the schema and is simply lost. It was the one genuinely new thing section 17 offered.
- `current-architecture.md` section 5.13 notes that additional checkpoints may later be added for high-severity findings. A workflow gate keyed on severity would then depend on a field assigned by hand at the checkpoint before it, which is workable but not obviously the right ordering.

Open Questions:

- Should severity carry a rationale field of its own, or is `Finding.impact` sufficient given the reviewer wrote the severity?
- If checkpoint 2 becomes the workflow's bottleneck, is the answer a severity proposal, a smaller finding set, or a different checkpoint shape?
- Is there a metric for reviewer-assigned severity that does not require a second reviewer — consistency across similar findings within one assessment, perhaps?
- Section 17 stays in `agent-design.md` as a specification of something not built. Should deferred-agent specifications live in section 37's list instead, so the document describes only what exists?

## DEC-031: `Assessment.status` is the deliverable lifecycle; workflow progress stays on the run

Date: 2026-08-09

Status: Accepted

Decision:

**One axis per object.** `WorkflowRun.status` answers *where is the pipeline*. `Assessment.status` answers *may these conclusions be used, and may work continue*. The two never describe the same thing, and neither is derived from the other.

`Assessment.status` uses **four of the seven `ObjectStatus` members**. Section 4.1 already permits a subset: "not every object needs every status."

| Status | Meaning |
|---|---|
| `draft` | Work in progress. The conclusions are not authoritative. Any number of runs, at any stage. |
| `pending_review` | Blocked on a human. No automated progress is possible. |
| `approved` | The pipeline completed and the reviewer approved the findings at checkpoint 2. The conclusions are the reviewer's. |
| `archived` | Retired. Read-only. |

`pending_review` says *that* a human is required, never *which* checkpoint. `WorkflowRun.current_node` says which, and DEC-017 already makes a paused run self-describing.

**Five transitions, each with exactly one writer.**

| From | To | Written by | On |
|---|---|---|---|
| `draft` | `pending_review` | the checkpoint node | reaching either checkpoint |
| `pending_review` | `draft` | the resume invocation | every pending object having a `ReviewerDecision` |
| `draft` | `approved` | the terminal node | the run completing |
| `approved` | `draft` | the run initiator | a new run beginning against an approved assessment |
| any of the three | `archived` | a person | retiring the assessment |

`archived` is terminal. There is no `pending_review` to `approved` edge: resuming from checkpoint 2 returns the run to `running`, and report generation and evaluation still follow, so the assessment returns to `draft` and reaches `approved` when the pipeline finishes.

**Four rules that are not transitions, and matter more than the edges.**

**The status and the run status are written in one transaction.** `pending_review` is set in the same transaction that sets `WorkflowRun.status` to `paused`, and cleared in the same transaction that resumes. Two independent writes are what would let them disagree; one transaction removes the failure mode rather than documenting it.

**A failed run does not fail its assessment.** `WorkflowRun.status` becomes `failed` and the assessment stays `draft`. There is no failed-shaped assessment status, because an assessment with a failed run is an assessment someone may run again. `data-model.md` section 26 already permits multiple runs per assessment; this states what that means for the parent.

**An assessment completed by a non-authoritative run may not reach `approved`.** DEC-012 records an ablated run as non-authoritative and `evaluation-plan.md` section 14 ablates checkpoints. Findings that no human approved becoming an approved assessment is precisely what DEC-005 exists to prevent.

**A person may perform only the transition to `archived`.** Every other edge is written by a workflow node. A user-settable `approved` is a checkpoint bypass with extra steps.

**This answers DEC-012's first open question.** The non-authoritative marking lives on the **workflow run**. It is not needed on the assessment, because the assessment's inability to reach `approved` is the consequence that matters, and it is not needed on the evaluation result, which measures a run that already carries it. One marking, one place, with its effect expressed as a rule rather than as a second field.

**Three members are excluded**, and the reasons differ:

- `candidate` describes an object proposed by an agent and awaiting validation. An assessment is created by a person and is never proposed.
- `rejected` conflates two different things. An assessment whose findings were all rejected is a *completed* assessment with zero findings, and "a successful assessment may produce no significant findings" is a binding constraint. An abandoned assessment is `archived`.
- `superseded` belongs to re-generation. DEC-023 puts `supersedes_id` on exactly two objects and reserves it for a generated object replaced by a later generated one. A re-assessment is a new run or a new assessment, not a supersession.

Why:

The field was required by section 5 and defined nowhere. Section 5's example shows `pending_review` and that is the only statement about it in the corpus, while both neighbouring status fields — `WorkflowRun.status` and `ExecutionRecord.status` — carry explicit vocabularies and explicit scopes.

Issue #50 needed a table to build the service and shipped one, recorded in the code as invented. It was wrong in a way worth keeping in the record, because the same mistake is available to anyone filling this gap: it made `pending_review` mean "at a checkpoint". There are two checkpoints, so that value is ambiguous between them, and it duplicates `WorkflowRun.status == paused` plus `current_node`, which DEC-017 already establishes as the record of a pause.

Duplication is the actual problem rather than ambiguity. A stored status that can disagree with the runs it summarizes is a second authoritative answer to one question — the failure DEC-016 cites when rejecting a framework checkpointer whose state would sit alongside the domain objects, and the one DEC-028 cites when refusing a declared count that can disagree with its own enumeration. Three decisions now reject the same shape.

Section 26 is what forces the axis apart: an assessment may have multiple workflow runs, for retries, revisions, or evaluations. A status that mirrored a run would have to choose which run, and every answer to that is wrong for some case.

The four rules carry the weight because the edges alone permit a correct-looking implementation that still diverges. Writing the pair in one transaction is what makes divergence structurally impossible; DEC-017 already has the checkpoint node persisting the run, so there is a transaction to join and the rule costs nothing.

Excluding `rejected` is the one exclusion with a real argument against it, since a reviewer who rejects every finding has plainly not produced a useful assessment. The design principle settles it: a run that surfaces no defensible findings has done its job, and a status meaning "the answer was no" would be read as failure by everything that displays it.

Alternatives Considered:

- Three values, dropping `pending_review`, leaving a pure deliverable lifecycle with nothing that can diverge
- Deriving the status from the assessment's runs rather than storing it
- Mirroring the run, adding `running`, `paused`, and `failed` to `ObjectStatus`
- Keeping #50's table, which additionally allowed `approved` to `pending_review`
- A separate `blocked_on_human` boolean beside the status, rather than a status value

Tradeoffs:

- **`pending_review` is denormalized and can still be wrong** if a node sets it outside the transaction that pauses the run. The rule makes that a defect rather than a race, but nothing in the schema enforces it; the enforcement lives in the checkpoint node's implementation, which is not built.
- Dropping `pending_review` entirely would have removed that risk. It was kept because "which of my assessments are waiting on me" is the question a local single-user tool is most often asked, and answering it otherwise means loading every run.
- **The `approved` gate depends on information the assessment does not hold.** Whether the completing run was authoritative is a property of the run, so the service takes it as an argument until `WorkflowRun` exists. An argument is weaker than a lookup and will be replaced by one.
- Five named transitions rather than one status setter is more surface, and a sixth event will want a sixth verb. That is the intended cost: a generic setter re-admits the ambiguity this decision removes.
- `approved` to `draft` means an approved assessment silently stops being approved when someone starts a new run. That is correct — the conclusions no longer describe the current state — but it discards the record that it *was* approved, which only the `ReviewerDecision` rows retain.
- Nothing detects an assessment stuck in `pending_review` whose run was deleted or whose decisions were never recorded. DEC-017 makes a paused run wait indefinitely by design, and this inherits that.

Open Questions:

- Should reaching `approved` be recorded as an event as well as a state, so a revision does not erase the fact that an earlier run was approved?
- Does `archived` need to prevent writes to the assessment's objects, or is it a label until retention (section 36) gives it teeth?
- When a run is ablated, should the assessment be prevented from *starting* it rather than only from reaching `approved`?
- Is `pending_review` worth the denormalization once a run listing exists, or should it be reconsidered when the CLI is built?

## DEC-032: The command line is the interface through M4; `argparse`, no dependency

Date: 2026-08-09

Status: Accepted

Decision:

**The reviewer's interface is a command-line interface through M4.** `current-architecture.md` section 5.1 is corrected: it was the document that was wrong.

Stage 5 may add a **read-only local view** for the demonstration — the lineage view that section 5.1 and the roadmap both want to show. It is a rendering of persisted state and not a second way to drive the pipeline. **No review interaction moves to a browser in the MVP.** Approving context, approving findings, assigning severity, and answering questions are command-line operations backed by the decision writer DEC-017 defines.

**The CLI uses `argparse` from the standard library.** No dependency is declared.

The Stage 1 command surface is confirmed, with two additions that decisions since the roadmap require: `trace assessment list`, because a reviewer needs to find an identifier the store allocated, and `trace assessment archive`, because DEC-031 makes archiving the one status transition a person performs.

Why:

The corpus contradicted itself and the contradiction was lopsided. Section 5.1 states a preference for a local web application once. The roadmap states the opposite four times — Stage 1 delivers "a simple CLI before building the full interface", Stage 1's non-goals forbid a polished web interface, Stage 5 says to "build only the interface necessary to support the demonstration", and section 9 says flatly "do not begin with the web interface." A single sentence against four is a stale sentence, not a live disagreement.

**DEC-017 removed the strongest argument for leading with a web interface.** The open question this decision inherited asked whether the checkpoint mechanism needs an interactive interface. It does not. A checkpoint pauses by persisting the run and letting the process exit, and reviewer decisions reach the workflow through one writer regardless of caller — an interactive command, a web form, and an evaluation harness replaying a decision file all produce identical `ReviewerDecision` rows. Review is therefore not a thing a browser is needed for; it is a thing a browser would be one caller of.

**Repeatable evaluation wants a scriptable interface.** `evaluation-plan.md` section 3 requires repeatability, and DEC-012 requires that answering a checkpoint non-interactively is not an ablation. A web-first interface would leave evaluation either driving a browser or bypassing the interface entirely — and bypassing it means the measured path is not the path a reviewer uses, which is the thing evaluation exists to avoid.

**Section 5.1 names the CLI as the demo-recovery path if the web interface fails.** A recovery path that has not been built is not a recovery path. If exactly one interface exists, it should be the one that is also the fallback.

**Choosing the CLI removes a trust boundary rather than mitigating one.** DEC-004 makes this a local single-user application with no authentication and no RBAC. A local web application introduces a browser-to-application boundary — a listening port, a server process holding assessment data, and request forgery from any page the reviewer has open — for a single user on their own machine. The threat model issue lists that boundary as conditional on this decision; it is now conditional on nothing, because it does not exist.

**The cost of getting the order wrong is asymmetric.** Section 5.1 already requires the web interface to call application services rather than contain analysis logic. Building the services first, which M1 is doing, makes a later interface additive. Building the interface first shapes the service layer around a rendering concern, and that shaping is not visible until something else needs the same services.

`argparse` rather than a declared dependency, for three reasons. The command surface is seven commands, which is within what `argparse` expresses without strain. (It is thirteen as of the M2 context slice — `context extract`, `show`, `review`, and `approve` joined it, and `review` carries seven flags. The revisit trigger below has not fired: the help is still readable and the argument handling is still declarative. It is closer than it was.) Every declared dependency is a supply-chain surface on a project whose subject is architectural risk, and five commands do not pay for one. And the claim that `typer` was already available transitively — which the issue recorded — is no longer true: DEC-016 removed the orchestration packages that carried it, and the declared runtime dependencies are down to five. Adopting it now would be adding a dependency, not using one already present.

This is the kind of choice worth revisiting rather than defending. The trigger is command count or help quality: when subcommand help, completion, or argument validation start being hand-written in ways a framework provides, the framework has become cheaper than the code avoiding it.

Alternatives Considered:

- A local web application first, following section 5.1
- A CLI plus a read-only local web view built in parallel through M1 to M4
- Both interfaces over a shared application service, built together
- `typer` or `click` as a declared dependency
- A text user interface, avoiding both a browser and bare `argparse`

Tradeoffs:

- **The review experience is worse.** Checkpoint 2 asks a reviewer to read findings with their evidence, and a terminal is a poor medium for that. The review package DEC-017 derives is rendered as text, and a reviewer will read some of it in a pager.
- Section 5.1's capability list — view workflow progress, view evidence and reasoning traces — is genuinely better served by a browser, and this decision defers all of it to Stage 5 rather than answering it.
- **Deferring the web interface risks it never being built**, and with it the lineage view that is a Stage 5 deliverable and part of the portfolio argument.
- `argparse` produces help text that is adequate rather than good, and no shell completion. That is a visible quality gap in a project whose demonstration is a deliverable.
- Choosing the standard library now means a later migration to a framework rewrites the command layer rather than extending it. The layer is thin by design, which is what makes that acceptable.
- A read-only Stage 5 view still needs a way to render persisted state, so the work is deferred rather than avoided; only the review interaction is settled here.

Open Questions:

- Does the Stage 5 read-only view render from the database directly, or through the same application services the CLI uses?
- Is the checkpoint review package rendered as text, as a file the reviewer opens in an editor, or as both?
- At what command count or help-quality threshold is a CLI framework worth the dependency?
- Does a text user interface become attractive for checkpoint 2 specifically, without becoming a second interface for everything else?

## DEC-033: `IngestionStatus` has three values; the failure reason lives on the ExecutionRecord

Date: 2026-08-09

Status: Accepted

Decision:

`data-model.md` section 7 requires `ingestion_status` and enumerates nothing. The vocabulary is
**three values**:

| Value | Meaning | Requires |
|---|---|---|
| `registered` | Recorded and preserved. Its bytes are stored and hashed; nothing has read them. | `ingested_at` and `normalized_path` unset |
| `ingested` | Normalized, segmented, and indexed. | both set |
| `failed` | Ingestion was attempted and did not complete. | `normalized_path` unset |

`registered` is the default. A document exists before anything reads it, which is why section 7
makes `ingested_at` optional, and that optionality is exactly what would otherwise let a document
claim it was ingested while carrying nothing an evidence reference could point at. The consistency
rule is enforced on the model.

**The success value is `ingested`, not `normalized`.** Section 7's field is `ingested_at`, described
as the successful-ingestion timestamp, and `current-architecture.md` section 5.4 calls the whole
component ingestion, of which normalization is one of nine responsibilities. Naming the state
`normalized` would give one event two vocabularies.

**There is no separate `indexed` state.** Section 5.4 lists normalizing, dividing into addressable
sections, preserving locations, and generating hashes as responsibilities of one component, and the
milestone builds them as one node. A state between them would describe a moment no code can be
interrupted at.

**A failed ingestion says that it failed and not why.** The reason belongs on the `ExecutionRecord`
for the ingestion node, which section 27 already gives `error_type` and a safe `error_message`.
Recording it on `SourceDocument` as well would be two records of one event, and they would disagree
the first time one was written and the other was not.

Why:

Section 7 leaves the field required and undefined, which is the shape that produces a vocabulary
invented separately at each call site — three spellings of "ok" and no agreement on what failure
looks like. Settling it with the object costs one entry and removes that.

The distinction that has to exist is registration from ingestion, and the corpus already implies it
twice: `ingested_at` is optional while `created_at` is required, and the artifact store's `sources/`
and `normalized/` directories are separate places written at separate times. A document whose bytes
are stored but not yet read is a real state, not an edge case — it is what exists between
`trace source add` and the ingestion node running.

Adding states was the temptation and the corpus argues against it. Every additional value has to
correspond to a moment the system can actually be observed in, and a status the code never writes
is worse than absent: someone will eventually branch on it.

Alternatives Considered:

- `pending`, `processing`, `complete`, `failed`, mirroring a generic job lifecycle
- Separate `normalized` and `indexed` states, following section 5.4's responsibility list literally
- A `partially_ingested` state for a document that normalized but failed segmentation
- A boolean `ingested` flag with the failure recorded only on the `ExecutionRecord`
- An `error_message` field on `SourceDocument`, alongside the status

Tradeoffs:

- **A failed document requires a join to explain itself.** Reading why ingestion failed means
  finding the `ExecutionRecord` for that node, which is more work than reading a field. That is the
  intended cost of one record per event, and it is only payable once the execution ledger exists
  (#57) — until then, a failed document is a state with no accessible reason.
- `processing` is absent, so a document being ingested is indistinguishable from one that was never
  attempted. DEC-017 makes runs pause by exiting rather than holding state, so nothing is
  concurrently in flight, but a crashed run leaves documents at `registered` that were mid-ingest.
- Three values will not survive PDF ingestion unchanged if page extraction becomes a separate,
  separately-failing step.
- Enforcing the consistency rule on the model means a caller must set `ingested_at`,
  `normalized_path`, and the status together. That is correct and it is three things to remember at
  one call site.

Open Questions:

- Does a crashed run need a way to distinguish "never attempted" from "attempted and interrupted",
  or is re-ingesting a `registered` document always safe?
- When re-ingestion produces different normalized output, does the document keep its identity, or
  does DEC-023's supersession apply?
- Should `failed` carry the identifier of the `ExecutionRecord` that explains it, which is a
  reference rather than a duplicate?

## DEC-034: The identifier scheme governs assessment data; configuration objects are named, not identified

Date: 2026-08-09

Status: Accepted

Decision:

`data-model.md` section 2.1 never said which objects the identifier scheme governs. It governs
**objects an assessment produces**, and nothing else.

An object is inside the scheme when all three hold: it is scoped to one assessment, it is persisted
by the assessment store, and something else refers to it by identifier. Those objects carry an `id`
of one of DEC-018's two forms, drawn from the prefix registry in section 2.1. The one authored
exception is `Requirement`: it is written by hand rather than produced by a run, but assessment
objects reference it by identifier — a `ControlMapping` names `req-AUTH-001` — so it is inside the
scheme and keeps its `req-` prefix.

**`RequirementsCatalog` and `PromptDefinition` are outside it.** They are authored configuration:
not scoped to an assessment, not minted by the persistence layer, and referenced by *version* rather
than by identifier. `Assessment.requirements_catalog_version` records a version, `PromptDefinition`
is cited in generation metadata as `extract-context-v1`, and DEC-027 pins `catalog_version` in a
benchmark scenario. Nothing anywhere joins on either object's `id`.

Their `id` is therefore a **name**: a lowercase slug, stable across versions, unique among objects of
its kind, carrying no prefix and no number. Identity is `(id, version)` — the slug names the family,
the version names the edition.

`requirements/catalog.yaml` changes from `cat-core` to `core`. The `cat-` prefix was imitation: it
made a name look like an identifier from a registry that does not contain it, which is the reading
that has to be prevented rather than the value that has to be preserved.

Section 2.1's prefix list was also incomplete against the rule this entry states. Three
assessment-scoped objects carry an `id` and had no prefix, and this entry adds them:

| Prefix | Object | Defined in |
|---|---|---|
| `act` | Actor | `data-model.md` section 13 |
| `eas` | EvidenceAssessment | section 20 |
| `crq` | Critique | section 24 |

The registry is now twenty-three. `SystemContext` (section 9) has no `id` field and needs no prefix:
it is keyed by `(assessment_id, version)`, which DEC-023 makes the versioned object it is.

DEC-018's "the requirements catalog's `req-AUTH-001` is the only class currently in use" is
corrected. It was inaccurate when written — `cat-core` was already in the same directory — and the
sentence is replaced with one that says `req-` is the only authored *prefix*, which is what was
meant and is true.

Why:

The question the issue asks — what to do about one value in one file — is not the question worth
answering. `cat-core` is a symptom of the omission in section 2.1: a document that lists prefixes
without saying what the list is for invites every object with an `id` field to acquire one by
resemblance. That is exactly how the value was produced, and fixing the value alone would leave the
next authored object to make the same mistake.

Stating the boundary answers the issue's own decision criteria in one move. Does anything join on
`RequirementsCatalog.id`? No — `catalog_version` is the real key, in the evaluation contract, in
`Assessment`, and in every requirement file's `catalog_version` field. Would a benchmark expected
file reference a catalog identifier? It references the version, which DEC-027 settled. Is a third
identifier form worth explaining? Not when the object needing it turns out not to need an identifier
at all.

`PromptDefinition` is the evidence that this is a class rather than one stray value. It has an `id`,
it has no prefix, it is cited everywhere as `extract-context-v1`, and nobody has ever proposed
`prm-`. The catalog and the prompt behave the same way, and a rule covering one covers both. That is
the difference between a rule and an exception.

Adding the three missing prefixes is part of the same decision rather than a separate cleanup.
`Actor`, `EvidenceAssessment`, and `Critique` are inside the scheme under the rule stated here, so
leaving them unlisted would publish a rule the registry contradicts, and would leave three
in-progress issues each free to invent a prefix. A closed registry only works if it is complete.

Alternatives Considered:

- Add `cat` to section 2.1 and admit a third identifier form, `<prefix>-<name>`
- Rename the catalog's identifier to a registered prefix, in one of the two existing forms
- Drop `RequirementsCatalog.id` entirely, since `version` is the real key
- State the boundary but leave the catalog's value as `cat-core`, treating the shape as harmless
- State the boundary and defer the three missing prefixes to the issues implementing those objects

Tradeoffs:

- **Two kinds of `id` field now exist in one data model**, and the type does not distinguish them.
  `RequirementsCatalog.id` and `Finding.id` are both `string` and only the section tells a reader
  which rules apply. A `CatalogName` annotated type would say so in the schema; there is no loader
  to put it on yet.
- The rule is stated in prose and enforced by nothing for configuration objects. A future authored
  object can still acquire a prefix by imitation, and the only thing standing in the way is a reader
  of section 2.1.
- Renaming `cat-core` to `core` changes a value in a version-controlled catalog. Nothing reads it,
  so the change is free today and would not have been once a loader existed.
- Three prefixes are now registered for objects that do not exist. If `Critique` is built and turns
  out not to need an identifier — it is always reached through the object it critiques — `crq` is a
  registered prefix naming nothing.
- `eas` and `eval` are close enough to misread at a glance, and they name unrelated objects.
- Requiring authored configuration to be unique "among objects of its kind" is unenforced: two
  catalogs both named `core` at the same version would collide, and nothing checks.

Open Questions:

- When a catalog loader exists, should `RequirementsCatalog.id` become an annotated slug type, so
  the schema rejects a prefixed value rather than a convention doing it?
- Does `PromptDefinition.id` hold the slug (`extract-context`) with `version` separate, or the
  composed `extract-context-v1` the corpus writes in metadata? The corpus shows the composed form
  and section 29 requires both fields.
- Is `Requirement` the only authored object that will ever be inside the scheme, or does a future
  shared threat-pattern library create a second?

## DEC-035: Sixteen report sections, four written by the agent; the renderer owns the document

Date: 2026-08-09

Status: Accepted

Decision:

The MVP report has **sixteen numbered sections**, fixed by `templates/report-v1.md`, and every one
of them has exactly one owner. Markdown is the only output format, as `future-features.md` section
13.5 defers PDF, HTML, JSON, SARIF, and audit packages.

| # | Section | Anchor | Owner | Content |
|---|---|---|---|---|
| 1 | Executive summary | `s01-executive-summary` | Agent — `executive_summary` | What was assessed, what was concluded, what was not determined |
| 2 | Scope | `s02-scope` | Rendered | `Assessment`, `AssessmentConfiguration`, and the source documents ingested |
| 3 | System overview | `s03-system-overview` | Agent — `system_overview` | Narrative of the approved `SystemContext` |
| 4 | Architecture summary | `s04-architecture-summary` | Rendered | `Component`, `Actor`, and `DataFlow` tables |
| 5 | Assets and trust boundaries | `s05-assets-and-trust-boundaries` | Rendered | `Asset` and `TrustBoundary` tables |
| 6 | Risk summary | `s06-risk-summary` | Agent — `risk_summary` | What the approved findings amount to together |
| 7 | Significant threats | `s07-significant-threats` | Rendered | Validated `Threat` objects |
| 8 | Approved findings | `s08-approved-findings` | Rendered | `Finding` objects approved at checkpoint 2 |
| 9 | Documentation gaps | `s09-documentation-gaps` | Rendered | Approved `DocumentationGap` objects |
| 10 | Assumptions | `s10-assumptions` | Rendered | `ContextClaim` with status `assumed` or `inferred`, with the DEC-022 rationale |
| 11 | Open questions | `s11-open-questions` | Rendered | `Question` objects with status `open` |
| 12 | Existing controls | `s12-existing-controls` | Rendered | `Control` objects whose `validation_status` is `supported` |
| 13 | Recommended actions | `s13-recommended-actions` | Rendered | `Finding.recommendation` and `acceptance_criteria`, by severity then identifier |
| 14 | Methodology | `s14-methodology` | Rendered | Fixed template text and the version pins |
| 15 | Evidence appendix | `s15-evidence-appendix` | Rendered | Every `EvidenceReference` cited above, with `quoted_text` and location |
| 16 | Assessment limitations | `s16-assessment-limitations` | Agent — `limitations` | One entry per limitation the assembler requires |

The list is `current-architecture.md` section 5.13's fifteen with one addition. **Risk summary** is
new, and it exists so that section 7 does not have to be half prose and half table: the model's
synthesis of what the findings mean together is a section of its own rather than a paragraph
interleaved into a rendered one.

**Four sections are model-written and twelve are rendered.** The rule that produced that split is:
*anything that restates an approved object is rendered; only prose that adds no fact is written by
a model.* A section is never both.

**The agent's output is a named structure of sections, not a document.** `ReportSections` carries
four fields and the shared response metadata of `agent-design.md` section 6:

| Field | Type | Constraint |
|---|---|---|
| `executive_summary` | string | Prose only. No headings, no Markdown tables, no links, no anchors |
| `system_overview` | string | Same |
| `risk_summary` | string | Same |
| `limitations` | list of `{limitation_id, text}` | Exactly one entry per `required_limitation` in the input; no more, no fewer, no invented identifier |

The agent no longer writes per-object prose. Section 19's responsibility list included finding
descriptions, threat summaries, gap summaries, assumption summaries, and a recommended-priority
narrative; all five are rendered from the objects instead. A `Finding.description` is text a
reviewer approved, and often edited, at checkpoint 2. Regenerating it would put model prose where
reviewer-approved text belongs and make "only approved content appears in the report" unverifiable.

**Limitations are the exception that proves the split, and they are handled structurally.** The
assembler computes a `required_limitations` list — one entry per limitation the run's own state
implies, such as documents that failed ingestion, unanswered blocking questions, findings resting on
inferred claims, a non-authoritative run under DEC-012, or an empty finding set — and hands the
agent the identifier and the facts for each. The agent writes the words; the validator checks the
set by identifier. That is why omission is a schema failure rather than a judgment call, and it is
the only place a required-by-identifier list is used.

**Numbering and anchors are fixed by the template.** Section numbers are literal, not computed from
how many sections have content, and every section is emitted even when empty. Anchors are written as
explicit `<a id="...">` elements rather than left to heading-derived anchors, which differ between
Markdown renderers and change whenever a title is reworded. Object anchors are the object's own
identifier lowercased — `fnd-003` — which is stable within its assessment, the scope a report is
read in.

**Output location and naming.** The report is written through the `ArtifactStore` to the assessment's
`outputs/` area, named for the run that produced it:

```
data/assessments/<assessment_id>/outputs/report-<workflow_run_id>.md
data/assessments/<assessment_id>/outputs/report-<workflow_run_id>.manifest.json
```

Naming per run rather than `report.md` is required rather than tidy: the artifact store refuses to
overwrite a stored file with different content, so a second run over the same assessment would fail
on a fixed name. `Assessment.final_report_path` holds the path **relative to the assessment root** —
`outputs/report-run-003.md` — and names the report of the run whose findings were approved. A
relative path keeps the value valid when the data directory moves, which an absolute one would not.

**The output manifest is JSON**, one per report, carrying what a later reader needs to know that two
reports are comparable:

| Field | Content |
|---|---|
| `manifest_version` | Version of this manifest's own shape |
| `assessment_id`, `workflow_run_id` | What produced the report |
| `generated_at` | Render timestamp |
| `report.path`, `report.content_hash`, `report.format`, `report.template_version` | The artifact, hashed per DEC-019, and the template it was rendered from |
| `versions.architecture`, `versions.data_model`, `versions.workflow` | From `Assessment` |
| `versions.requirements_catalog` | Catalog version, per DEC-034 the way a catalog is referenced |
| `versions.prompts` | Every prompt version used in the run, by name |
| `versions.model`, `versions.model_profile`, `versions.model_configuration` | DEC-014's bundle |
| `counts.*` | Approved findings, findings by severity, documentation gaps, open questions, assumptions, confirmed controls, threats, evidence references |
| `authoritative`, `ablations` | Whether the run applied a DEC-012 ablation, and which |

The six version fields `evaluation-plan.md` section 3 requires are all present. JSON rather than
YAML because nothing authors this file by hand and DEC-020 already makes JSON the machine format;
the manifest sits beside the report so a report cannot be found without it.

**No machine-readable sidecar is emitted.** `data-model.md` section 37's export package —
`findings.json`, `report.md`, `evidence/` — stays deferred. The manifest describes the report; it
does not contain the assessment's objects, and adding a second serialization of objects that already
live in the assessment store would be a second authoritative copy for no MVP consumer.

**Zero approved findings is a defined outcome with authored wording.** The template's
`empty.findings` text states that no candidate weakness reached the assessment's bar, that this is
not a statement that the system is secure, and where to read what could not be determined. Every
rendered section that can be empty has wording of its own, written the same way, and no empty
section is omitted: a section that disappears reads as one that was never considered.

Why:

Two documents disagreed about how many sections the report has — fifteen in `current-architecture.md`
section 5.13, four in `agent-design.md` section 19 — and the disagreement was never about counting.
Section 5.13 lists sections of a document; section 19 lists keys of an agent's output. They can both
be right only once someone says which sections the agent writes, and nobody had.

That question is the one that matters, because it decides what the agent can get wrong. A model that
returns a document can put a fabricated fact anywhere in it, and validating that requires reading
every sentence against every object. A model that returns four prose fields, none of which is
allowed to contain a heading, a table, a link, or an identifier the input did not carry, can be
checked. The renderer owns the document; the model owns four passages inside it.

Rendering per-object text rather than having the model rewrite it is the same argument applied to
the checkpoint. The reviewer approves finding text at checkpoint 2 under DEC-023, editing it where
needed. If the report regenerates that text, the reviewer approved one thing and the report says
another, and the guarantee that only approved content appears becomes unverifiable in the exact
place it is most load-bearing. Rendering also makes the empty case free: a table with no rows is a
defined state, while prose about nothing is a prompt for invention.

The template being a specification rather than an engine template follows the same reasoning as
DEC-032. A templating library is a dependency, a syntax, and a second place for logic to hide, in
exchange for string substitution that Python does natively. What the artifact is actually needed for
is to make the report's shape editable and reviewable in one file, and comparable against what the
renderer emits — which a test can do against a specification just as well as against a live
template.

The fixed section numbering exists for the same reason the anchors do. This is a document a reviewer
reads, quotes in a ticket, and links a colleague to. If section numbers shift because one assessment
had no findings, then "section 12" means different things in two reports of the same system, and
every link into the previous one silently points somewhere else.

Alternatives Considered:

- Have the agent return one Markdown document, with the renderer only writing files and the manifest
- Keep section 19's four keys as the whole prose surface and drop Risk summary, folding it into the
  executive summary
- Let the agent write per-object prose — finding descriptions, threat summaries — as section 19
  originally specified
- Render the limitations section deterministically from structured facts, with no model involved
- Number sections dynamically, skipping empty ones
- Rely on heading-derived Markdown anchors rather than explicit anchor elements
- Adopt Jinja2 and make `report-v1.md` a real engine template
- Emit `findings.json` beside the report, bringing section 37's export forward into the MVP
- Name the report `report.md` and overwrite it on each run

Tradeoffs:

- **Twelve rendered sections is a lot of rendering code**, and every one of them is a place where a
  table can be built wrong. The failure is at least visible: a broken table looks broken, where a
  fabricated sentence does not.
- The report will read as two registers — synthesized prose in four places, structured output
  everywhere else. That is honest about what wrote what, and it is not what a human-written
  assessment reads like.
- `required_limitations` is a mechanism that exists for one section. It is a real cost: the
  assembler has to derive the list, the schema has to carry the identifiers, and the validator has to
  check them, all to protect one section from omission.
- Fixed section numbering means a report about a system with no data flows still contains a section
  saying so. Some readers will read that as padding.
- Naming the report per run means an assessment with several runs accumulates several reports in
  `outputs/`, and only `final_report_path` says which one is current.
- The manifest duplicates counts that can be derived from the assessment store. If a reviewer edits
  an approved finding after the report is rendered, the manifest is stale and nothing detects it.
- A sixteen-section report is long for a system with three findings. Nothing in this decision
  shortens it, and the MVP has no reduced or summary variant.
- Explicit anchor elements are inline HTML in a Markdown document. Renderers that strip HTML lose
  every anchor, and the report degrades to unlinkable.

Open Questions:

- Does the evidence appendix quote every cited `EvidenceReference` in full, or excerpt long ones?
  DEC-015 forbids modifying `quoted_text`, so excerpting would have to render a truncation rather
  than a shortened quote.
- Should the manifest carry the report's section-by-section ownership, so a reader can tell which
  passages a model wrote without consulting the template?
- Is `risk_summary` distinguishable from `executive_summary` in practice, or will the two converge
  and one of them stop earning its section?
- When a reviewer edits a finding after rendering, is the report re-rendered under a new run, or
  amended in place with the manifest updated?

## DEC-036: Type fields are open vocabularies, normalized; `direction` is closed

Date: 2026-08-09

Status: Accepted

Decision:

`data-model.md` lists values under four headings ending in "examples" — component types, asset
types, actor types, boundary types — and types every one of those fields `string`. Those fields are
**open vocabularies**: any term is accepted, and the corpus's lists are documentation.

**A term is normalized before it is stored.** `Web Application`, `web-application`, and
`WEB_APPLICATION` all become `web_application`: whitespace, hyphens, slashes, and dots collapse to
single underscores and the result is lowercased. A value that does not reduce to lowercase words
joined by underscores is refused, because normalization exists to remove incidental variation rather
than to accept anything at all.

**A field is closed when the document enumerates rather than illustrates.** The signal is in the
description: "Service, datastore, external system, etc." names examples, and "One-way or
bidirectional" names the values. `DataFlow.direction` is therefore a closed enum, and it gains a
third member, `unknown`, alongside the document's two.

The `KNOWN_*` constants in each object module record the terms the corpus already uses. They
validate nothing.

Two `DataFlow` fields carry the `unknown` rule explicitly. `encryption_in_transit` and
`authentication` default to the string `unknown` rather than to absence, and a boolean in either is
refused by name.

Why:

A closed `component_type` enum would reject Trace's own benchmark.
`demo/forgeflow/input/structured-system-input.yaml` uses seven component types and section 11 lists
one of them; the other six — `web_application`, `managed_database`, `managed_cache`,
`managed_storage`, `managed_security_service`, `internal_application` — appear nowhere in the
document. The scenario was written to be assessed, so a schema that refuses it is wrong about
itself rather than strict.

The deeper reason is what these fields are for. The extractor reads architecture documents written
by people who did not know Trace's vocabulary, and DEC-009's discipline is that Trace records what
the documentation supports. A closed enum makes the model's list an authority over the document, and
the failure is quiet: the nearest allowed value gets chosen, and a managed database becomes a
`data_store` with the "managed" part — the part that decides whether encryption at rest is inherited
— silently discarded. That is the same argument `requirements/README.md` makes about
`acceptable_implementations`, which is non-exhaustive by construction for the same reason.

What genuinely goes wrong with free text is drift, and drift is a spelling problem rather than a
vocabulary problem. Three spellings of one type make the report's counts wrong, make two components
of the same kind look different, and make a benchmark comparison meaningless. Normalizing fixes all
three without deciding what a type may be.

`direction` is the counter-example that keeps the rule honest. If every string field were open, an
extractor could write `inbound`, `outbound`, `duplex`, and `two-way` for two states, and nothing
downstream could ask "does this flow cross the boundary in both directions". The document names both
values, so the enum is a reading of the document rather than an addition to it. `unknown` is an
addition, and it is the same one section 14 already makes for encryption: `direction` is required,
and a required field with no honest value is one that gets guessed. A guessed `one_way` removes a
threat nobody ruled out.

Alternatives Considered:

- A closed enum per type field, extended with the six types the ForgeFlow fixture uses
- Free strings with no normalization, leaving spelling to whatever produced the value
- An open vocabulary with a warning logged for an unknown term
- A registry file of permitted types, versioned like the requirements catalog
- Making `direction` open too, for one uniform rule across every vocabulary field
- Omitting `unknown` from `FlowDirection`, since the document names two values

Tradeoffs:

- **Nothing catches a typo.** `manged_database` normalizes cleanly and is stored as a new type. The
  drift this decision prevents is between spellings of the same intent; it does nothing about a
  misspelling, and the first place it will show is a report counting two kinds of database.
- The `KNOWN_*` constants will be read as authoritative by someone, because a list of values in code
  looks like a validation rule whatever its docstring says.
- Normalization is lossy in one direction: `data-store` and `data_store` become one term, and if a
  document ever meant them differently, that distinction is gone with no record it existed.
- The open/closed rule depends on how a field's description is worded. `etc.` is a reliable signal in
  the current document and is not a property anyone was maintaining deliberately, so a future field
  can land on the wrong side of the rule by accident.
- Defaulting `encryption_in_transit` to `unknown` means a caller who forgets the field gets a valid
  object that asserts nothing. That is the safe direction, and it is still a default doing work a
  required field would have made explicit.
- Evaluation across catalog or scenario versions has no way to tell that `managed_database` and
  `data_store` refer to the same component if a later extraction spells it differently.

Open Questions:

- Should an unknown term be recorded somewhere a reviewer sees, so a vocabulary growing by accident
  is visible rather than silent?
- Does `Actor.trust_level` want the same treatment? It is free text today and describes a small,
  repeating set of levels in practice.
- Is there a case for normalizing at the seam that receives agent output instead, so the raw term the
  model produced is preserved alongside the canonical one?

## DEC-037: Actor is a first-class context object; `SystemContext` gains `actor_ids`

Date: 2026-08-09

Status: Accepted

Decision:

`Actor` is a first-class object in the context baseline, and `SystemContext` gains an `actor_ids`
field pointing at the actors an assessment extracted. Section 40's implementation-priority list
gains `Actor`, after `Asset` and before `DataFlow`.

`data-model.md` section 39's open question 4 — whether actors should be first-class objects in the
MVP — is answered by this entry rather than left open.

`Actor` still carries no `status` field, because section 13's table has none. Every other object in
the context baseline has one, and adding it here would be a data-model change; this entry does not
make it.

Why:

The corpus was split, and it was split lopsidedly. `agent-design.md` section 7 lists Actor objects
among the Context Extraction Agent's outputs, `docs/product/roadmap.md` lists Actor in Stage 1 and
again in Stage 2, and section 2.1 assigns actors a prefix. Against that: section 40 omitted Actor
from a list written before several of those, and section 39 asked a question nobody had answered.
An omission and an open question are not an argument for removal; they are the absence of one.

The deciding consideration is the one the issue phrased: an extracted actor that nothing references
is worse than an absent one. `SystemContext` is the versioned baseline a reviewer approves, and it
holds identifier lists for claims, components, assets, data flows, and trust boundaries. An actor
outside that list would be extracted, persisted, and invisible to the approval — approved by nobody
and reachable by nothing — which is the worst of both designs. So either the field exists or the
object does not, and three documents say the object exists.

Threat analysis is the downstream reason to keep it. Threats are proposed against the approved
context, and a threat needs someone to be the adversary and someone to be harmed. Deferring Actor
would push that into free text on `Threat`, where nothing can check it against the architecture and
nothing can ask whether an actor's documented capabilities support the threat.

DEC-034 is the smaller consistency argument. It registered `act` as a prefix on the grounds that
Actor is an assessment-scoped object carrying an `id`, and recorded as a tradeoff that a prefix
naming nothing would be the cost of getting that wrong. Deferring Actor now would realize exactly
that cost.

Alternatives Considered:

- Defer `Actor` out of M2 and let threat analysis carry actors as free text
- Keep `Actor` without adding `actor_ids`, leaving actors outside the approved baseline
- Fold actors into `Component` with a component type of `actor`, as some threat-modeling tools do
- Add `status` to `Actor` for symmetry with the other four context objects

Tradeoffs:

- **`SystemContext` grows a sixth identifier list**, and every one of them is a place where the
  baseline can reference an object that was later rejected. The Context Validation node has one more
  list to check.
- Actor without `status` is asymmetric, and the asymmetry is now permanent until someone changes the
  document. Code that iterates the context objects generically has to special-case it.
- Actors are the context object a design document says least about. Most of what an assessment knows
  about them will be inferred, which means `ContextClaim` rationales and low confidence rather than
  quoted evidence — and an object that is mostly inference is one a reviewer has to check hardest.
- Adversarial actors (`external_attacker`, `malicious_insider`) sit in the same object as legitimate
  ones, so any consumer counting "the system's users" has to filter by type.

Open Questions:

- Does an adversarial actor belong in the *approved context* at all, or is it a threat-analysis
  object that happens to share a shape with a legitimate actor?
- Should `SystemContext.actor_ids` be required-but-possibly-empty, like the other lists, or optional?
  The other five are required in section 9, and this entry follows them.

## DEC-038: Re-extraction is the assessment's next workflow run, not a backward transition

Date: 2026-08-09

Status: Accepted

Decision:

"Request re-extraction", which `agent-design.md` section 9 lists among the reviewer's actions at
checkpoint 1, is a **new `WorkflowRun` for the same assessment**. It is not a transition from
`human_context_review` back to `context_extraction`, and no such edge is added to the transition
table.

The reviewer's rejection is recorded as a `ReviewerDecision` against the `SystemContext` with
disposition `request_more_analysis`, carrying a required rationale. That row is what connects the
two runs: the second run is a re-extraction because a decision on the first one says so, not
because the orchestrator routed backwards.

The transition table therefore stays a sequence — every phase names exactly one successor, and
`successor()` keeps returning a single value.

Why:

Three decisions already made settle this, and the only reason it looked open is that the phrase
"the re-extraction path" appears in an issue without appearing anywhere in the corpus.

**DEC-016 declares the pipeline as an ordered table with no analytical branching.** An edge from
`human_context_review` to `context_extraction` would give one phase two successors, which is the
one shape `successor()` refuses to resolve — it raises rather than choosing. Every consumer of the
table would gain a branch, and the branch would exist to serve a case that happens rarely and
costs a process restart when it does.

**`agent-design.md` section 27 requires the orchestrator to prevent uncontrolled loops**, and a
backward edge is the loop: extraction, validation, review, extraction. Bounding it would mean a
re-extraction ceiling, which is a fourth kind of limit alongside node executions, model calls, and
cost — invented to make a transition safe that nothing needed.

**DEC-017 already says a rejected review is a stopped run.** Pausing is stopping: the state is
written, the process exits, and resuming is a read in a new process. A rejection arrives after the
process that produced the context is gone, so there is nothing to route; what happens next happens
in a new invocation either way. Making that invocation a new run rather than a resumed one costs
nothing and says what actually occurred.

**DEC-031 already allows for it.** `Assessment.status` is the deliverable's lifecycle and
`WorkflowRun.status` is the pipeline's position, and an assessment may have several runs. A
re-extraction is the plainest example of why that separation exists: the assessment is one
deliverable being worked on twice, and a failed or rejected run leaves its assessment in `draft`.

The alternative that looks tidier — reusing the run and stepping it backwards — also loses the
record. A run that visited `context_extraction` twice has one `WorkflowRun` row whose counters are
the sum of two attempts, and the evaluation question "how often does a reviewer reject an extracted
context" becomes unanswerable from the ledger. Two runs answer it by counting.

`SystemContext.next_version()` and DEC-023's `supersedes_id` do the rest without a transition: the
second run's context is version 2, its claims supersede version 1's, and both revisions stay in the
store.

Alternatives Considered:

- Add `human_context_review -> context_extraction` to `TRANSITIONS` and bound it with a
  re-extraction ceiling
- Add the edge and let `agent-design.md` section 27's node-execution ceiling bound it implicitly
- Treat re-extraction as a resumed run that rewinds `AssessmentState.current_phase`
- Leave the action unimplemented until M4, when the finding checkpoint needs the same shape

Tradeoffs:

- **A reviewer rejecting a context has to start a run rather than press continue.** The command-line
  surface has to make that obvious, or it will read as the rejection having done nothing.
- The connection between the two runs is a `ReviewerDecision` row rather than a workflow edge, so
  anything reconstructing the history has to read decisions as well as runs. A single run with a
  backward edge would have carried it in one place.
- Two runs mean two sets of execution records for one assessment, and a cost report that sums runs
  will show the rejected attempt. That is accurate and is also the first time a reader will notice
  that a rejected extraction was paid for.
- `ReviewDisposition.REQUEST_MORE_ANALYSIS` now carries two meanings across the two checkpoints —
  re-extraction here, further analysis of a finding at checkpoint 2. The disposition vocabulary
  names what the system records rather than what the reviewer said, so the subject type
  distinguishes them, but a reader counting dispositions across an assessment has to split by
  subject.

Open Questions:

- Should the second run's extraction receive the rejection rationale as input? The retry rule in
  section 26 says a repeated attempt carries feedback or it is a repetition, which argues yes; but
  the rationale is reviewer-authored text entering a prompt, which is a trust question the
  untrusted-source boundary does not currently cover.
- Does a rejected run's `Assessment` need a status distinct from `draft`? DEC-031 gives four values
  and a failed run leaves its assessment in `draft`; a rejected review is not a failure, and it is
  not obvious the two should look identical.

## DEC-039: The five architecture objects carry `source_origin`

Date: 2026-08-09

Status: Accepted

Decision:

`Component`, `Asset`, `Actor`, `DataFlow`, and `TrustBoundary` gain a required `source_origin`
field, typed `SourceOrigin` and added to their field tables in `data-model.md` sections 11 to 15.
The extractor's conversion sets `uploaded_document`; a reviewer adding a missing object at
checkpoint 1 sets `reviewer_edit`.

It is required rather than defaulted. A default would make the extractor's provenance the answer
given when nobody supplied one, and the case that matters — an object a person created — is the one
that would then have to be remembered at the call site.

Why:

Section 4.4 says `SourceOrigin` "identifies where information originated", and it was carried by
exactly two objects: `EvidenceReference` and `ContextClaim`. That looked like a pattern — the
objects that carry an *assertion* record where the assertion came from, and a component is a
structural fact rather than an assertion — and it is a defensible reading. It stops being defensible
at the checkpoint, where a reviewer adds a component the extractor missed.

**A reviewer-added object was indistinguishable from a generated one.** Nothing in `Component`
records who created it. `generated_by` is on `ContextClaim` and `Question` and not here, and
`ObjectStatus` describes lifecycle rather than origin. So the only record of the addition would be
the `ReviewerDecision` naming it — and `ReviewDisposition` has no member meaning "added". An
addition would have to be recorded as an approval, which is exactly what approving an *extracted*
object also produces. The two would be the same row.

That matters beyond tidiness. `docs/product/roadmap.md` makes reviewer correction rate a primary
evaluation metric and `data-model.md` section 2.5 says reviewer edits "are the evaluation signal
that shows where the workflow was inaccurate". "The reviewer had to add three components the
extractor missed" is the sharpest form of that signal, and it was not computable from the objects.

The alternative — adding a `ReviewDisposition` member for additions — was rejected because section
4.6's vocabulary names what the *system records* about an existing object, and an addition is not a
disposition toward anything. DEC-030 made the same distinction for severity and DEC-023 for
re-extraction: the reviewer's action vocabulary and the system's disposition vocabulary do not
correspond one to one.

Alternatives Considered:

- Leave the field off and record additions as `ReviewerDecision` rows with disposition `approve`
- Add a `ReviewDisposition` member meaning "added by the reviewer"
- Add `generated_by` to the five objects instead, matching `ContextClaim`
- Make `source_origin` optional with a default of `system_generated`

Tradeoffs:

- **Required means every construction site must state it**, including tests. Five models, one
  conversion function, and five test modules changed in the commit that introduced it, and every
  future fixture has to carry a field that is almost always `uploaded_document`.
- `Actor` now has `source_origin` and still no `status`, so the asymmetry DEC-037 left is still
  there and is now one field narrower, which reads as an oversight rather than as the deliberate
  omission it is.
- `source_origin` on a `Component` says where the *object* came from, not where each of its fields
  came from. A component the extractor created and a reviewer then corrected still reads
  `uploaded_document`, and the correction is only in the decision log. The field answers "who
  created this" and not "who last touched it", and nothing in the name says so.
- Two objects now carry provenance twice over: a `ContextClaim` about a `Component` has its own
  `source_origin`, and so does the component. They can disagree, and neither is wrong when they do.

Open Questions:

- Should `Threat`, `ControlMapping`, and `Finding` carry it too, for the same reason at checkpoint 2?
  M4 will meet the identical problem.
- Does a reviewer-corrected object need a separate marker from a reviewer-created one, or is the
  decision log the right place for that distinction to stay?

## DEC-040: Approval mints the revision; reviewer edits mutate in place

Date: 2026-08-09

Status: Accepted

Decision:

DEC-023 says `SystemContext.version` "increments on approval, alongside `approved_at` and
`approved_by`". This entry states what that means in code, because the sentence admits a looser
reading that the first implementation took.

**`approve_context` mints the next revision.** It calls `SystemContext.next_version()`, stamps
`approved_at` and `approved_by` on the successor, and saves it. The revision the extractor produced
is left exactly as it was and stays retrievable. So version 1 is always the generated baseline and
is never approved; version 2 is the baseline the reviewer approved.

**The new revision's identifier lists are recomputed from the store**, not copied from the previous
revision. They name every context object in the assessment whose status is not `rejected`. A
reviewer-added object therefore reaches the approved baseline, and a reviewer-rejected one does not.

**Nothing else is versioned.** A reviewer edit to a `Component`, a `ContextClaim`, a `Question`, or
a `SourceObservation` mutates the object in place under the same identifier and records its delta on
a `ReviewerDecision` (DEC-023's first mechanism). `supersedes_id` stays reserved for re-extraction.

**A reviewer's re-extraction rationale may reach the next run's prompt**, in the trusted region and
outside the source-content fence. This closes DEC-038's open question.

Why:

The looser reading was that approval stamps whatever revision is current, and that a new version
appears only when a reviewer's edits change the baseline's membership. It fails on its own terms:
an edit that changes a claim's text changes no membership list, so an assessment could be reviewed,
edited, and approved with exactly one revision in the store — and "leave the prior revision
retrievable" would be satisfied by there being nothing to retrieve. Two revisions, always, is both
simpler to state and the only version that keeps the generated baseline intact next to the approved
one. The difference between them is the reviewer's work, readable by diff.

**Recomputing membership rather than copying it** is what makes rejection mean something.
`current-architecture.md` section 5.6 says threat analysis reasons from the approved baseline
rather than reinterpreting the documents; a component the reviewer rejected sitting in that
baseline would be reasoned from anyway, and the rejection would be a row nothing consulted.

**On the reviewer's rationale reaching a prompt**: DEC-013's trust levels already answer it. The
corpus divides origins into material under review and everything else — `uploaded_document` and
`structured_input` are untrusted; `reviewer_edit` and `requirements_catalog` are not. A reviewer is
the operator of the tool, not a document being assessed, so their text belongs in the trusted half
alongside the assessment name and the precedence rule. Putting it inside the fence would tell the
model to treat the operator's instruction as data, which is the opposite of the distinction the
fence exists to draw. `agent-design.md` section 26 supplies the reason it must be carried at all: a
repeated attempt carries feedback or it is a repetition.

Alternatives Considered:

- Stamp approval on the current revision and mint a new one only when membership changes
- Mint the revision on the reviewer's first mutating action rather than at approval
- Copy the previous revision's identifier lists and edit them as the reviewer works
- Keep rejected objects in the approved baseline and let downstream nodes filter by status
- Withhold the re-extraction rationale from the prompt and let the reviewer re-word the documents

Tradeoffs:

- **A reviewer who approves without changing anything still produces version 2**, identical to
  version 1 but for the approval fields. That is a row that carries no information about the
  reviewer's work, and someone will read the version number as an edit count.
- Version numbers advance by one per approval, so an assessment that goes through re-extraction
  twice ends at version 3 or 4 with no obvious mapping back to "how many times was this reviewed".
- Recomputing membership means the approved revision reflects the store at the moment of approval,
  including any object written between the package being built and the approval being made. For a
  local single-user MVP there is no concurrency to worry about, and that stops being true the moment
  there is.
- Rejected objects stay in the store and out of the baseline, so `assessment_ids()` counts and
  baseline counts disagree. Anything reporting "components found" has to say which it means.
- Carrying reviewer text into a prompt puts human-authored free text into a model request with no
  boundary around it. The trust argument is sound and the blast radius is a bad extraction rather
  than an escalation, but it is the first place operator text and model input meet.

Open Questions:

- Should the approved revision record *which* run approved it, beyond the `ReviewerDecision`'s
  `workflow_run_id`?
- If a reviewer rejects every component, the approved baseline is empty and threat analysis has
  nothing to reason from. Is that a refusal condition at approval, or a legitimate outcome?

## DEC-041: Threat categories are an open vocabulary; `threat_methodology` stays free text

Date: 2026-08-09

Status: Accepted

Decision:

`agent-design.md` section 11 requires the Threat Validation node to "Confirm threat categories use
permitted values", and no document says what the permitted values are. This entry says.

**`Threat.category` is an open vocabulary, normalized, and never rejected for being unfamiliar.**
It is the DEC-036 treatment, reached by DEC-036's own stated test: `data-model.md` section 16 types
the field `list[string]` and *illustrates* two values in its worked example rather than enumerating
a set. `KNOWN_THREAT_CATEGORIES` in `domain/threat.py` records STRIDE in the snake_case spelling
that example uses, plus four categories named from OWASP Top 10 for LLM Applications 2025. It is
documentation and validates nothing.

**An uncategorisable threat is recorded uncategorised.** `category` stays optional, as section 16
has it. Nothing forces a threat into the nearest STRIDE bucket, because a category that does not
fit is read downstream as one that does.

**"Permitted values" is satisfied by normalization, not by a whitelist.** What the validation node
checks is that a category is a well-formed vocabulary term and that the spellings do not drift --
`Elevation of Privilege`, `elevation-of-privilege`, and `elevation_of_privilege` are one category
written three ways, and three spellings make a coverage count wrong and a benchmark comparison
meaningless. An unfamiliar term is recorded, not refused.

**`AssessmentConfiguration.threat_methodology` stays free text for the MVP.** No registry, no enum.

Why:

**STRIDE has no category for the threat ForgeFlow is built around.** `demo/forgeflow/forgeflow-scenario.md`
section 18's first expected threat is THR-001, repository prompt injection manipulating AI output.
THR-005 is over-disclosure of source content to a model provider and THR-006 is unreviewed model
output being published. `agent-design.md` section 10 requires AI-specific threats "where
applicable". A closed STRIDE enum would reject or mis-bucket the single most important expected
threat in the demo scenario, and the mis-bucketing is the worse outcome of the two: it is silent.

This is the same failure DEC-036 documents for `component_type`, where a closed enum would have
rejected six of the seven types `structured-system-input.yaml` uses. The catalog's
`acceptable_implementations` is the third instance of one principle: a list of examples treated as
the set of allowed values decides cases it was never shown.

**Adding the AI categories to a closed set would not fix it either.** The set would then be
whatever taxonomy was current when this was written, and the next scenario outside it fails the
same way. The names here are cited rather than invented -- LLM01, LLM02, LLM05, LLM10, from a
framework `requirements/README.md` already adopts -- which makes them a good starting list and
still not a rule.

**"Generic STRIDE labels are rejected" is a different check.** `agent-design.md` section 39 lists it
among the fixture tests, and it is about *specificity*: a threat titled "Tampering" with a
description restating the category is a checklist item, not a scenario. Section 10 says the same
thing directly -- the agent "should not produce six generic threats merely to satisfy each STRIDE
category". That check belongs to the Threat Validation node and tests the threat, not the
vocabulary. Enforcing it through a category whitelist would not catch it, because the label on a
generic threat is a perfectly valid STRIDE category.

**On `threat_methodology`**: `data-model.md` section 6 types it `string` and one value exists,
`stride-scenario-based`. A registry with one entry validates nothing and would have to be edited
before the second methodology could be tried, which inverts the point of the field being
configuration. `current-architecture.md` section 15 says the initial methodology "will likely use
STRIDE", which is not the language of a fixed set.

Alternatives Considered:

- A closed STRIDE enum, with AI threats mapped onto the nearest STRIDE category
- A closed enum of STRIDE plus the OWASP LLM categories
- An open vocabulary with a warning recorded when a term is outside the known set
- A required `category`, so every threat carries at least one
- A registry of known values for `threat_methodology`, validated at assessment creation

Tradeoffs:

- The validation node's category check is weaker than section 11's wording suggests. It catches
  drift and malformed terms, not an invented taxonomy. What stops a threat being labelled badly is
  the specificity check and the reviewer at checkpoint 2, not the schema.
- Coverage metrics over an open vocabulary are harder to compute: "did we cover all six STRIDE
  categories" needs `STRIDE_CATEGORIES` explicitly rather than iterating an enum. That constant is
  exported for exactly this.
- `KNOWN_THREAT_CATEGORIES` will drift from what the corpus actually uses unless something watches
  it. Nothing does today.
- Free-text `threat_methodology` means two assessments can record `stride` and `stride-scenario-based`
  and compare as different. For a single-user MVP with one methodology this costs nothing, and it
  will cost something the first time results are compared across assessments.

Open Questions:

- ~~Should the Threat Validation node record an observation when a category falls outside
  `KNOWN_THREAT_CATEGORIES`, so the drift is visible without being refused?~~ Answered by
  DEC-063: yes — an observation, warn-only, never an error.
- At what point does `threat_methodology` need a registry — a second methodology, or the first
  cross-assessment comparison?

## DEC-042: Threat analysis runs once per assessment, over the whole approved context

Date: 2026-08-09

Status: Accepted

Decision:

`agent-design.md` section 38 question 2 asks whether threat generation should run once for the
system or separately by trust boundary. It runs **once per assessment**, over the whole approved
context, in a single model call.

The approved baseline is assembled in full: every component, actor, asset, data flow, trust
boundary, and context claim the approved `SystemContext` names, plus the evidence the caller
selects. Nothing is partitioned and nothing is dropped. Only evidence is subject to the input
budget, and an excluded excerpt is named rather than truncated.

**How this scales, and when it stops.** The trigger is the input budget, not the object count: when
the assembled architecture no longer leaves room for the evidence behind it, the successor is
deterministic partition fan-out over **connected component groups** — subgraphs joined by data
flows — with every partition run for the same assessment and the results merged by the validation
node. It is not partition by trust boundary. Section 38 question 2 is resolved by this entry.

Why:

**A per-boundary call cannot see a cross-boundary threat.** Four of ForgeFlow's ten expected
threats span boundaries. THR-001 has repository content reaching a model provider and model output
returning to a pull-request comment, which crosses three. THR-004 is a cross-tenant authorization
failure, and tenancy is not a boundary in the architecture at all. An agent shown one boundary at a
time is structurally unable to describe any of them, and the failure is silent: each call returns
plausible threats about the slice it was given, and nothing reports what could not be seen from
there.

**Partitioning multiplies the failure section 10 warns about.** The section says the agent "should
not produce six generic threats merely to satisfy each STRIDE category". A call that sees one
boundary has little architecture to reason from and the same coverage checklist, which is exactly
the condition under which category-filling is the easiest way to answer. Six boundaries then
produce six near-identical sets, and the duplicate detection in the validation node inherits a
problem that the invocation shape created.

**Section 23's context minimisation is satisfied by object selection, not by fan-out.** The section
asks for the smallest *useful* context, and it names what this agent receives: approved context,
relevant architecture objects, selected supporting evidence. The package already excludes the
source documents, the ingestion records, the requirements catalog, and every object a reviewer
rejected. For ForgeFlow that is a small architecture. Splitting it further trades the thing the
agent is for — seeing how the parts connect — for tokens it is not short of.

**One call is also the cheaper one.** `scripts/estimate_cost.py` assumes a per-assessment threat
call. Per-boundary invocation multiplies the architecture context by the number of partitions,
because each call needs enough surrounding architecture to be coherent, and the shared prefix stops
being shared.

This is the same shape as DEC-024, reached from the other direction: send the whole thing, and when
it stops fitting, partition without excluding rather than filter.

Alternatives Considered:

- One invocation per trust boundary, as section 38 question 2 proposes
- One invocation per bounded group of components, chosen deterministically
- One invocation per externally reachable entry point
- Two passes: a per-boundary pass for depth and a whole-system pass for cross-boundary scenarios

Tradeoffs:

- One call means one failure. A schema failure loses the whole threat set rather than one
  partition's, and the retry re-sends the whole architecture. The retry budget is two, and the
  cost of a repeated call is the cost this decision already accepted.
- Depth per component is lower than a focused call would give. A threat agent looking at one
  component in isolation would notice more about it; the judgment here is that noticing how
  components connect matters more for an architecture review, which is what this project is.
- The approved context has to fit one request. It does for ForgeFlow and for anything of that size,
  and the expiry trigger above is the point at which it stops being true.
- Coverage is unmeasurable per boundary. Nothing reports "these two boundaries produced no
  threats", because there is no per-boundary unit of work to report on. If that turns out to
  matter, it is a coverage-metadata output on the proposal, not a change to the invocation shape.

Open Questions:

- Should the node record which architecture objects no threat referenced, as a coverage signal for
  the reviewer at checkpoint 2?
- Does re-running threat analysis after a context revision need to see the previous run's threats,
  or is a fresh pass plus duplicate detection the better shape?

## DEC-043: Duplicate threats are found by deterministic feature comparison and proposed, never merged

Date: 2026-08-09

Status: Accepted

Decision:

`agent-design.md` section 38 question 7 asks whether duplicate detection should use embeddings, a
model, deterministic features, or a combination. For the MVP: **deterministic features**, scored,
with the outcome recorded as a proposal.

Three features, weighted, summing to one:

| Feature | Weight | What it compares |
|---|---|---|
| Title | 0.50 | Jaccard overlap of normalized title tokens, minus a short stop list |
| Targets | 0.35 | Jaccard overlap of affected component and asset identifiers, as one set |
| Category | 0.15 | Jaccard overlap of the category lists |

A pair scoring above **0.75** is proposed as a duplicate. Two empty sets score 0.0 rather than 1.0.

**The output is a `MergeProposal`, and nothing merges.** It carries both threat identifiers, the
score, and which features matched. Section 11 requires the merge decision to stay explicit and
traceable, and section 16 assigns the merge itself to Finding Consolidation in M4. A merge proposal
does not block the threat set from reaching control mapping: two overlapping threats are still two
threats worth mapping, and collapsing them first would lose whichever the merge did not keep.

**When this is revisited.** Two triggers, either one sufficient. First, a benchmark duplicate rate
that this misses — `agent-design.md` section 10 lists duplicate rate as an evaluation criterion, so
the number exists to check against. Second, vector infrastructure arriving for another reason;
`current-architecture.md` section 17 defers it, and if it stops being deferred, an embedding
comparison becomes cheap enough to add as a *second* signal alongside these features rather than in
place of them. The pairwise comparison is quadratic, which is free at tens of threats and worth
revisiting past a few hundred.

Why:

**An embedding approach has no substrate.** `current-architecture.md` section 17 defers vector
infrastructure. Adding an embedding model for this one comparison would mean a second provider
dependency, a second thing to cache, and a similarity threshold tuned against nothing — the
benchmark that would tune it is the same one that has not run yet.

**A model-assisted comparison would put a model call in a deterministic node.** `agent-design.md`
section 4 classifies this node as deterministic, and the six-agent cap in section 36 is on
model-assisted agents. A comparison call is arguably not an agent, which is exactly the argument
that erodes a cap. It is also the wrong shape: a model asked whether two threats are the same
returns a judgment with no features attached, and section 11 requires the decision to be traceable.

**The weights follow from what a duplicate actually is.** Two threats are the same threat when they
describe the same thing happening to the same objects. Title carries the most weight because it is
the only field that summarises the scenario, and targets carry nearly as much because a title can
be reworded while the objects cannot. Category is a coverage label rather than a description, so it
breaks ties and does not decide.

**0.75 is where identical-alone stops being enough.** A pair with identical titles and no shared
target scores 0.50; identical targets and no shared title scores 0.35. Either is a real possibility
— two different scenarios against one component, or one scenario written twice about different
components — and neither should be proposed on its own. A pair matching strongly on both crosses.
The number is a starting point with a stated meaning rather than a tuned value, because there is
nothing yet to tune it against.

**Two empty sets score 0.0, not 1.0.** The convention matters more than it looks: DEC-041 makes
`category` optional, and a Jaccard implementation returning 1.0 for two empty sets would make every
pair of uncategorised threats look identical on that feature.

Alternatives Considered:

- Embedding similarity over threat descriptions, with a vector store
- A model-assisted pairwise comparison, prompted to answer "same threat or not"
- Exact match on normalized title only, as `workflow/context_validation.py` does for components
- Deterministic features first, escalating to a model call for pairs in an uncertain band
- Merging automatically above a higher threshold and proposing between the two

Tradeoffs:

- Rewording defeats it. Two threats describing one scenario in different words, against different
  components, are not detected. That is the case an embedding would catch and this does not, and
  it is the reason the revisit trigger is a measured duplicate rate rather than a date.
- The threshold is asserted, not derived. Until the benchmark runs, nobody knows whether 0.75 is
  generous or strict, and the failure directions are asymmetric: too low produces proposals a
  reviewer dismisses, too high produces duplicates nobody sees.
- Stop words are a small English list. A title in another language tokenizes worse, which does not
  matter for a local single-user MVP assessing English documentation and would matter later.
- Proposals do not block, so a run can reach control mapping with two near-identical threats and
  map both. That is the intended behaviour and it costs a mapping call.

Open Questions:

- Should the merge proposal survive into checkpoint 2's review package, or is it consumed by
  Finding Consolidation and never shown?
- Does a proposal need a recommended survivor — the more specific threat, the one with more
  evidence — or is that the merging step's judgment?

## DEC-044: Two nodes create controls, both record which; `Control` gains provenance

Date: 2026-08-09

Status: Accepted

Decision:

No document said which node creates a `Control`. Three places imply they exist — Context Extraction
identifies "Existing controls" (`agent-design.md` section 7), the Mapping Agent outputs "New or
refined Control objects" (section 12), and Mapping Validation must "Confirm control identifiers
exist" (section 13) — and section 18 carried no field recording which of them was responsible.

**Two nodes create controls, and a reviewer is the third origin.**

| Origin | `generated_by` | When |
|---|---|---|
| Context Extraction | `context-extraction-v1` | The documentation describes a safeguard while the architecture is being read |
| Requirement and Control Mapping | `mapping-v1` | A requirement is evaluated and a control bearing on it is found described |
| Reviewer | `reviewer_edit` | A person adds one at a checkpoint |

**A control claimed during context extraction becomes a `Control` row at conversion**, alongside
the components and claims from the same response, with `validation_status: not_evaluated`. It does
not wait for the mapping step. A safeguard the documentation describes is a fact about the
architecture, the reviewer approves it at checkpoint 1 with everything else, and the mapping step
then references it by identifier through `existing_control_ids` rather than re-proposing it.

**`Control` gains `generated_by` and `created_at`.** Both required. `data-model.md` section 18 is
updated, which is what makes this a design change rather than an implementation detail.

**An asserted implementation status cites evidence.** `implemented`, `partially_implemented`, and
`absent` require at least one `EvidenceReference`. `claimed` and `unknown` do not. A `planned` or
`recommended` control is exempt whatever its status.

**`ControlMapping` keeps the mirrored rule.** `satisfied`, `partially_satisfied`, and `unmet`
require evidence; `unverified` does not.

Why:

**Provenance was unrecoverable, and this is the one object where three answers were possible.**
Every other object the pipeline produces carries `generated_by` or `source_origin` or both. A
control could have come from the extractor, the mapper, or a person, and the record could not say
which — which matters directly for evaluation, because "did the extractor recognise the inherited
managed-database encryption" and "did the mapper infer it while evaluating a requirement" are
different results with different fixes.

**Creating extraction-found controls at conversion keeps checkpoint 1 meaningful.** The alternative
— the extractor notes controls in prose and the mapper creates the rows later — puts a class of
architectural fact outside the baseline the reviewer approves. DEC-040 recomputes approved
membership from the store, so a control created after checkpoint 1 would never be in an approved
revision at all, and the reviewer would first see it inside a mapping.

**The evidence rules are one rule from two ends, and both ends are named failure conditions.**
Section 12 lists "unverified controls are marked implemented" as a failure of the mapping step;
section 19 says a high proportion of `unverified` mappings "is the expected result of assessing
ordinary architecture documentation" and "must not be treated as a defect". A schema requiring
evidence everywhere would force every honest silence into a status that asserts something, which is
the DEC-009 collapse. A schema requiring it nowhere would leave section 12's failure entirely to
instruction. Requiring it for exactly the statuses that assert something is the only split that
serves both.

`unmet` cannot be reached by silence for a structural reason section 19 already gives: an
`EvidenceReference` quotes real source text, so an absence has nothing to cite.

Alternatives Considered:

- Only the mapping step creates controls; extraction records them as context claims and the mapper
  converts them
- Only extraction creates controls; the mapper may reference but never propose
- No `generated_by`, with provenance recovered from the `ExecutionRecord` that produced the object
- `source_origin` instead of `generated_by`, matching the five context objects DEC-039 covers
- Require evidence for every implementation status, and record undocumented controls as `unknown`

Tradeoffs:

- Two creating nodes means duplicate controls are possible: the extractor records a safeguard and
  the mapper proposes the same one under a different name. `existing_control_ids` is the mechanism
  that should prevent it, and nothing enforces that the mapper uses it. The Mapping Validation node
  is where that check belongs.
- `generated_by` and `created_at` widen section 18 beyond what the corpus originally specified.
  Every field added to a data-model object is a field an agent might try to set, and both are
  absent from `ControlProposal` for that reason.
- The evidence rule is structural and says nothing about evidence *quality*. A control citing a
  passage that does not actually describe it passes here; that is the Evidence Validation step's
  question, and `validation_status: not_evaluated` at promotion is what records that it has not
  been asked yet.
- `source_origin` is not added, so a control does not record whether the underlying material was an
  uploaded document or structured input the way DEC-039's five context objects do. `generated_by`
  names the node, and the node's `ExecutionRecord` names what it consumed.

Open Questions:

- Should the extractor's control-recognition be a separate evaluation metric from the mapper's,
  given they are now distinguishable?
- When the mapper proposes a control the extractor already created, is that a duplicate to merge or
  a refinement to apply? Section 12 says "new or refined", and refinement has no mechanism yet.

## DEC-045: A documentation gap's severity rates the gap, is proposed, and is never `unassigned`

Date: 2026-08-10

Status: Accepted

Decision:

`DocumentationGap.severity` reuses section 4.5's `Severity` vocabulary for a different quantity than `Finding.severity` carries, and the two are governed by opposite rules.

**It rates the gap, not a weakness.** The value answers how much the inability to verify impedes the assessment — whether a reviewer should chase the missing documentation before relying on the result. It does not say a control is absent, and nothing downstream may read it as though it did. `data-model.md` section 23 already names the field "Importance of documentation gap"; this states the consequence.

**The node that raises the gap assigns it, and `DocumentationGapProposal` carries the field.** DEC-030 removed severity from every agent's output and made the reviewer its origin. That decision is about `Finding` and stays that way.

**A `DocumentationGap` may not carry `unassigned`.** `DocumentationGap` refuses the value in a validator rather than defaulting to it.

Why:

DEC-030's mechanism does not reach this object, and the gap is structural rather than an oversight. Findings arrive `unassigned` because checkpoint 2 exists to resolve it: `current-architecture.md` section 5.12 lists "Assign or change severity" among the reviewer's actions, and DEC-030 makes an approval carrying `unassigned` a validation failure. Both halves are about findings. **Section 5.12 lists no action on a documentation gap at all** — the reviewer's gap-shaped action there is converting a *finding* into one.

So a gap created with `unassigned` would keep that value through the entire pipeline and render into report section 9 with it. That is not a field awaiting a decision; it is a decision nobody is ever asked to make, displayed as though someone declined to make it. Refusing the value is what makes the difference visible at the point of construction rather than in the report.

DEC-030's substantive argument also fails to transfer, which is why the different rule is not merely a workaround for a missing checkpoint. Severity on a finding is a business-risk judgment — what an outage costs, what the data is worth — and architecture documents do not contain it, so an agent asked for it produces a fluent answer from material that cannot support one. The importance of a documentation gap is a judgment about the *assessment*: which requirement could not be evaluated, which threat it bore on, how much of the analysis rests on the unknown. Every input to it is in the pipeline's own state, and the mapping step holds all of it at the moment it raises the gap. This is an evidence judgment in DEC-009's sense, not a risk judgment.

The two fields sharing a vocabulary is the residual hazard, and it is accepted rather than solved. A separate `GapImportance` enum was the alternative, and it would make the distinction unmissable at the cost of contradicting section 23's field table, which types the field `Severity`. `data-model.md` is authoritative for types (`CLAUDE.md`), and `tests/unit/test_data_model_conformance.py` would fail on the change. Defending the distinction in the model docstring, the proposal docstring, and the validator's error message is weaker than a type would be, and it is what the authoritative document permits.

Note that `importance` — required, free text, section 23 — is the field a reviewer actually reads. `severity` orders the list; `importance` says why the entry is on it. A gap carrying a severity and no importance would be a label with no argument behind it, which is why the schema requires both.

Alternatives Considered:

- Create gaps with `unassigned` and add a gap-severity action to checkpoint 2
- A separate `GapImportance` enum, contradicting section 23's field table
- Drop `severity` from `DocumentationGapProposal` and derive it deterministically from the mapping
- Make `severity` optional on `DocumentationGap` and let the renderer omit it
- Treat `importance` as the only rating and remove `severity` from the object

Tradeoffs:

- **One vocabulary now means two things**, and the object that carries the ambiguous field is the one whose whole purpose is to not be read as a finding. A reader scanning report section 9 beside section 8 sees `high` in both and has no visual cue that they are different quantities.
- The mapping agent proposes a value with no evidence reference attached, which is the property DEC-030 objected to. The defence is that the inputs are pipeline state rather than business context, and it is a defence rather than a disproof.
- Refusing `unassigned` means a node that genuinely cannot rate a gap has to pick a value anyway. `informational` is the honest floor and nothing enforces its use over `medium`.
- Gap severities are unmeasured, in the same way DEC-030 leaves finding severities unmeasured. Nothing in `evaluation-plan.md` scores them.
- If checkpoint 2 later gains gap review, this decision has to be revisited rather than extended: the reviewer would be editing a value an agent proposed, which is DEC-023's edit path and not DEC-030's assignment path.

Open Questions:

- Should the reviewer be able to edit a gap's severity at checkpoint 2, given that gaps appear in the review package but carry no approval action?
- Does report section 9 need to state that gap severity and finding severity are different quantities, or does the section's own framing carry it?
- Is a deterministic floor available — a gap on a requirement no threat could evaluate is at least `low` — or is that the same optional-free-text problem DEC-030 found?

## DEC-046: The downgrade is recorded on the mapping; two of DEC-013's four conditions wait for Finding Consolidation

Date: 2026-08-10

Status: Accepted

Decision:

**`ControlMapping` gains `downgraded_from` and `downgrade_reason`.** When the Mapping Validation node lowers a proposed `unmet` to `unverified`, it records the status it lowered *from* and the DEC-013 condition that failed. Both fields are present or both absent, and a downgrade whose recorded origin equals its current status is refused.

**A downgrade is not a suppression.** DEC-025's `suppressed_conclusion` and `suppressed_by` stay for what they were added for: the *agent* declining a negative conclusion because a `common_false_positives` entry applies. A downgrade is the *application* refusing one the agent drew. The four fields are not merged.

**The node applies the two DEC-013 conditions that can be checked where it runs.** DEC-013 states four conditions for `unmet`. Conditions 1 and 4 — at least one cited `EvidenceReference`, and no unresolved contradiction bearing on the conclusion — read only the mapping, the catalog, and the `SourceObservation` records, all of which exist at this phase. Conditions 2 and 3 read `EvidenceAssessment`: whether a cited reference is `direct` or `contradictory` rather than merely `contextual`, and whether the assessment's `validation_status` is `supported` or `partially_supported`.

**`EvidenceAssessment` does not exist yet when this node runs**, and that is the pipeline's order rather than an implementation gap. `current-architecture.md` section 5.3 puts Evidence Validation *after* Requirement and Control Mapping. So DEC-013's "enforcement happens twice" is narrowed here: Mapping Validation enforces conditions 1 and 4 and performs the downgrade for them; Finding Consolidation applies the outcome table, including conditions 2 and 3, and performs any further downgrade at that point. DEC-025's structural check — an `unmet` against a requirement carrying `common_false_positives` entries must say why none applies — is enforced here too, because it reads only the catalog.

Why:

The record had to live somewhere and DEC-013 already implied where. Its own open questions ask whether the downgrade should be "visible to the reviewer as a distinct event, rather than only as a recorded reason **on the mapping**", which takes the mapping as the baseline and asks whether more is needed. This decision answers only the baseline; the distinct-event question stays open.

Reusing DEC-025's two fields was the obvious shortcut and it destroys the measurement both records exist for. `evaluation-plan.md` section 8 makes false-negative rate a primary metric, and the two records answer different questions about a rising rate. A high suppression count with a low downgrade count means the *catalog* is suppressing too much — DEC-011 names over-suppression as `common_false_positives`'s principal risk. A high downgrade count with a low suppression count means the *agent* is reaching for negative conclusions the evidence does not carry. One pair of fields would show a single number that could not distinguish a catalog problem from a model problem, which is exactly the attribution DEC-025 was written to preserve.

Recording rather than silently lowering follows the same argument the issue makes: a silent downgrade is as invisible to evaluation as a silent upgrade. It also keeps the node honest about what it did — `agent-design.md` section 8 and section 11 both make the validators report rather than correct, and this node is the one place a validator *does* change its input. DEC-013 sanctions that specific change and no other; the record is what keeps the exception legible as an exception.

The split across two nodes deserves recording because the alternative reading is available and wrong. One could implement conditions 2 and 3 here against a *missing* `EvidenceAssessment` and treat absence as failure, which would downgrade every `unmet` mapping in every run, unconditionally, and look like a very strict evidence rule rather than like a node reading a field that is not populated yet. Nothing would fail; the assessment would simply never report an unmet requirement, and the false-negative rate would move with no attributable cause.

Alternatives Considered:

- Reuse `suppressed_conclusion` and `suppressed_by` for the downgrade
- A `Downgrade` object of its own, linked to the mapping
- Record downgrades only in `ExecutionRecord` metadata
- Move Evidence Validation before Requirement and Control Mapping so all four conditions are checkable at once
- Treat a missing `EvidenceAssessment` as failing conditions 2 and 3
- Perform the whole DEC-013 rule in Finding Consolidation and leave Mapping Validation reporting only

Tradeoffs:

- **Two more optional fields on the most complex object in the model.** `ControlMapping` now carries four fields about conclusions that were not drawn, which is more space given to negative space than to the mapping itself.
- The reviewer sees `unverified` with a note, not the `unmet` the agent proposed. Whether that is enough visibility is DEC-013's open question and is still open.
- **DEC-013's enforcement is now genuinely partial at this node**, and a reader of section 19 could reasonably expect the whole rule to run here. The document says which half runs where; a reader who skips that will over-trust this node.
- Splitting the rule across two nodes means the second half has no implementation yet — Finding Consolidation is M4 — so between now and then an `unmet` resting on purely contextual evidence survives to the checkpoint. The reviewer is the backstop in the meantime, which is weaker than the decision intends.
- `downgraded_from` is a status the mapping never had persisted, so an audit reading only stored states sees `unverified` and a claim that it used to be something else. There is no `ExecutionRecord` of the intermediate object.

Open Questions:

- Should Finding Consolidation append to `downgrade_reason` or overwrite it when it applies conditions 2 and 3 to an already-downgraded mapping?
- Does a downgrade belong on the checkpoint 2 review package as its own line, or is the mapping's status enough?
- Should the ratio of downgrades to suppressions be an evaluation metric in its own right, given that this decision argues the two numbers mean different things?

## DEC-047: `EvidenceAssessment` carries the recommendation; the evidence hierarchy is a vocabulary, not a score

Date: 2026-08-10

Status: Accepted

Decision:

**`EvidenceAssessment` gains `recommendation`**, a closed vocabulary of five values: `continue`, `revise`, `stop`, `downgrade_to_question`, `documentation_gap`. `agent-design.md` section 14 lists "recommendations to continue, revise, or stop a candidate conclusion" among the agent's outputs and adds the two DEC-009 outlets under its allowed operations. Section 20's field table had nowhere to put any of them, so the field is added and `data-model.md` section 20 records it.

**It is a recommendation and not an action.** DEC-013's outcome table decides what a conclusion becomes, deterministically, from `satisfaction_status` and `validation_status`. The agent's recommendation is stored beside that so the two are comparable rather than so one is obeyed. The agent creates no `Question`, creates no `DocumentationGap`, and approves nothing.

**Section 14's evidence hierarchy is an ordered vocabulary and nothing converts it to a number.** `EVIDENCE_HIERARCHY` is a tuple of seven labels a rationale cites by name. No function ranks two levels, no field stores a position, and no rule combines a level with a confidence.

**`subject_type` is a closed enum over section 20's own five**: `context_claim`, `control`, `control_mapping`, `threat`, `finding`. `documentation_gap` is not among them.

Why:

The recommendation had to be persisted or discarded, and discarding it removes the only signal that would show the agent and the deterministic rule disagreeing. `evaluation-plan.md` section 7 measures classification accuracy against a truth set; the cheaper and earlier signal is internal — an assessment recommending `stop` on a conclusion the outcome table carries forward is a case worth a person's attention, and it is invisible if the recommendation lives only in a proposal object that promotion drops. This is the same argument DEC-025 made for suppressions and DEC-046 for downgrades, and adding the field follows DEC-044's precedent of giving a named output a home rather than letting it evaporate at the boundary.

Making it advisory rather than executive is what keeps DEC-005 and DEC-013 intact. A recommendation the pipeline obeyed would be an agent deciding a candidate's fate, and DEC-013 deliberately made that determination a deterministic table precisely so no prompt instruction could move it.

The hierarchy is the more consequential half of this entry, because encoding it as a score is the natural implementation and it contradicts the document in one line. Section 14 says the hierarchy "is guidance, not a universal scoring formula". A rank function would make that sentence false: as soon as levels compare, a downstream rule will compare them, and the result is a number that looks like a measurement of evidence quality while actually being the position of a label in a list somebody wrote once. `design-principles.md` section 15 asks whether a score helps a reviewer decide or merely makes the output look precise, and applied here the answer is available rather than debatable — the reviewer wants to know *why* a passage is direct evidence, which is the rationale, not that it scored 2.

`subject_type` is closed for the reason a free string here is worse than a free string elsewhere: an assessment whose subject type does not match its subject identifier is unjoinable to the thing it assesses, and nothing downstream can detect it. DEC-036's test applies cleanly — section 20's purpose *names* the five rather than illustrating them — so the prefix check has something to check against. `documentation_gap` is excluded because section 14 lists gap candidates among the agent's outputs rather than among what it evaluates, and an assessment of a gap would be an evaluation of whether the evidence supports the claim that there is no evidence.

Alternatives Considered:

- Keep `recommendation` on the proposal only, consumed by the validating node and discarded
- A separate `Recommendation` object linked to the assessment
- Let the recommendation drive the outcome, and make DEC-013's table the fallback
- Add a numeric `evidence_level` field ranking each reference on the hierarchy
- A `rank()` helper that compares two hierarchy levels without storing a number
- Leave `subject_type` a free string, as section 20's table types it
- Include `documentation_gap` in `SubjectType`

Tradeoffs:

- **A field the pipeline does not act on.** `recommendation` is written and, until Finding Consolidation exists, read by nothing. That is one more thing to keep correct with no test downstream of it that would notice if it were wrong.
- Storing an advisory recommendation beside a deterministic outcome invites a future reader to wire the first into the second. Nothing structural prevents it; this entry is the only thing that does.
- **Refusing a rank function makes some legitimate work harder.** "Is this evidence stronger than that evidence" is a question a reviewer will ask, and the answer is now prose rather than a comparison. That is the intended exchange and it is a real cost.
- The seven hierarchy levels are carried as a vocabulary nothing validates against: no field stores a level, so an agent citing one in a rationale can cite it wrongly and no schema notices.
- Closing `subject_type` means an object type added later is a schema change rather than a value. `Finding` is in the enum before the model exists, which is a value nothing can currently produce.
- Excluding `documentation_gap` means a gap's own evidential basis is never assessed. If gaps later need validating, this decision has to be revisited rather than extended.

Open Questions:

- When Finding Consolidation lands, should a disagreement between `recommendation` and DEC-013's outcome be a human-review trigger, or only an evaluation metric?
- Should `evidence_strengths` and the hierarchy be reconciled — `EvidenceStrength` has four values and the hierarchy seven levels, and neither maps onto the other?
- Does `Finding` belong in `SubjectType` before `Finding` exists, or should the enum grow with the models?

## DEC-048: Evidence validation gets a deterministic node; `agent-design.md` section 3's diagram should be amended

Date: 2026-08-10

Status: Accepted

Decision:

**A deterministic node is built behind the Evidence Validation agent**, at `workflow/evidence_assessment_validation.py`, even though `agent-design.md` section 3's workflow overview does not draw one.

**Section 3's omission is an omission, not an intent**, and the diagram is amended to show the node. That edit has since been made, together with the section 4 classification row and the `NODES_BY_PHASE` entry, and the diagram carries a sentence saying why both nodes arrived late.

**The same correction applies to the Critique Validation node**, which section 3 did not draw either and which `agent-design.md` section 15 and section 22 require for the same reasons. It was built under the same argument and is now drawn. That answers this entry's second open question: two nodes were missing, not one, and every reasoning agent is now followed by a deterministic node.

**This node owns the write, and it is the only validator for which that is literally true.** `workflow/evidence_validation.py` contains no store write — no `objects.save`, no `.transaction()`, no `allocate(` — and a test asserts it. Persistence of an `EvidenceAssessment` is unreachable except through validation. The other three validators check objects their agents already persisted.

**Four of section 14's six failure conditions are checked here**: evidence references that do not exist, unsupported claims marked supported, model-generated text treated as source evidence, and contradictions present in the input and absent from the output. Misquotation is checked at the agent node, where the raw output still exists to preserve in `traces/`. "Evidence quantity is mistaken for evidence quality" is checked nowhere, because it is a judgment about reasoning.

**Validation-status transitions are a permitted set.** `not_evaluated` may move anywhere, a status may be re-applied unchanged, and `requires_confirmation` may move anywhere. A settled classification moving to a different settled one is an error, not a write.

**This node corrects nothing.** DEC-013 authorises Mapping Validation to downgrade an unsupported `unmet`; nothing here has an equivalent authority, and a failing assessment is refused rather than adjusted.

Why:

Two rules in the corpus outrank a diagram, and both apply directly. `data-model.md` section 33 requires validation after model-generated structured output without conditioning it on a node being drawn. `agent-design.md` section 22 states that agents never write authoritative records — so if no node exists, either the agent writes, which section 22 forbids, or nothing writes, which loses the output section 14 specifies. Section 4 also classifies every other reasoning agent as needing deterministic follow-up, and there is no property of this agent that would exempt it; if anything the case is stronger, because its failure conditions are the most mechanically checkable in the corpus.

The asymmetry is worth recording rather than silently fixing, because the next reader will meet the diagram before the code and conclude one of them is wrong. It is the diagram.

**Making this node the sole write path is the part that is more than tidiness.** For the other three agents, section 22's write model is a statement about who decides, enforced by convention: the agent node persists, having validated first, and nothing structural stops a future edit from persisting before validating. Here the agent module has no persistence code in it at all, so the rule is a property of the import graph. That is the strongest form of section 22 available, and it arrived because the split was forced — `NodeResult` carries identifiers and counts and never an object (section 31's state-design rule), so the proposal had to travel to the validator some other way, and the way that worked put the write on the far side.

The transition table exists because "updated validation statuses" is the one thing this node changes on an object it did not create. Without a table the node would be a general-purpose status setter driven by model output, which is DEC-006's authoritative-state rule leaking. With one, a reversal is an event someone has to decide on. `requires_confirmation` moving freely is the case the table exists to permit rather than to catch: it means the documents could not settle the question and a person could, so a later answer resolving it is the designed path and not an anomaly.

Refusing to correct is the same reasoning `agent-design.md` section 8 applies to the Context Validation node, stated for a different object. A node that re-labelled a `supported` assessment as `unsupported` to make it pass would produce a conclusion nobody asserted with a clean validation record, and the reviewer would never learn that the agent had claimed more than the evidence carried.

`persist_assessments` refuses outright rather than writing the assessments that passed. A partial write leaves the run reporting a mixture nobody decided on, and the retry that follows would re-propose the failed assessments against a store already holding their siblings — which is a duplicate set with no way to tell which pass produced which.

Alternatives Considered:

- No node: let the Evidence Validation agent persist its own output, as the other three do
- A node that corrects a failing assessment down to the strongest status its evidence supports
- Amend `agent-design.md` section 3 in this change rather than recording that it should be amended
- Allow any validation-status transition and record the previous value, as DEC-046 does for downgrades
- Write the assessments that validated and report the rest as errors
- Fold the checks into the agent node, keeping one module per step

Tradeoffs:

- **The code and the authoritative document now disagree**, deliberately, until section 3 is amended. Anyone reading the diagram alone will believe evidence validation has no follow-up node.
- The split makes this step two modules where every other step is one, and a reader comparing them will see an inconsistency before they see the reason for it.
- **The transition table is strict in a way that will be inconvenient.** A second run that genuinely reaches a different conclusion — new evidence, a reviewer answer, a corrected document — hits an error rather than an update. Whether re-running should relax it is unanswered.
- Only `Control` carries a `validation_status`, so the transition machinery applies to one of the five subject types and is inert for the rest. That is correct today and looks over-built.
- Refusing the whole set on any failure means one malformed assessment blocks four good ones. The retry re-proposes all five, which costs a call and re-derives work that was already right.
- The model-generated-text check keys on `EvidenceReference.source_origin`, so it catches a citation to a system-produced reference and not a rationale that paraphrases an earlier analysis in its own words. The second is the likelier form and nothing detects it.

Open Questions:

- Should a re-run be allowed to move a settled validation status, and if so does it need DEC-046's from/reason record?
- ~~Does `agent-design.md` section 3's diagram need any other node it does not draw, or is this the only one?~~ Answered: two were missing, this one and Critique Validation. Both are drawn, and section 4's table lists both.
- Should the other three agents adopt the same arrangement — no write in the agent module — or is the convention enough where the node already validates first?

## DEC-049: The critic reviews one threat's lineage, its vocabularies are closed, and it proposes no missing threats

Date: 2026-08-10

Status: Accepted

Decision:

**The critic's unit of work is one threat and everything downstream of it.** The review group is a threat, the `ControlMapping` objects that cite it, the `Control` objects those mappings reference, the `EvidenceAssessment` objects over any of them, and the `DocumentationGap` objects raised alongside. That is `agent-design.md` section 23's "bounded group of related objects" made specific, and it is the same chain `data-model.md` section 32 calls object lineage.

**`Critique`'s three prose vocabularies become closed enumerations.** `CritiqueSubjectType` has six values — `threat`, `control`, `control_mapping`, `evidence_assessment`, `documentation_gap`, `finding`. `CritiqueType` has eleven, section 24's twelve less one. `RecommendedAction` has section 24's five.

**`missing_high_impact_threat` is excluded, and the critic proposes no missing threats.** Section 15 lists both among the critic's concerns and outputs; both are dropped for the MVP.

**A severity critique needs a severity that someone assigned.** `severity_overstated` and `severity_understated` are refused against `unassigned` and against a subject that carries no severity at all. `DocumentationGap` is where the pair is genuinely reachable in M3, because DEC-045 has the mapping step assign a gap's rating and forbid `unassigned`.

Why:

**The unit of work follows from what a critique has to be able to say.** Section 15's twelve concerns are almost all comparisons — an ignored inherited control compares a mapping against a control, a duplicate compares two threats, a mislabelled documentation gap compares a mapping's conclusion against its evidence. None of them can be made from a single object, and all of them can be made from one threat's downstream chain. A smaller group makes the comparison impossible; a larger one is section 15's "unrestricted second full assessment" prohibition, which is a statement about scope rather than about volume.

The per-threat shape also matches what the pipeline already does. DEC-024 makes mapping per-threat for its own reasons, so the mappings, controls, and assessments belonging to one threat are already a natural set, and no new grouping rule is invented to produce it.

**Closing the vocabularies is where section 15's two structural failure conditions live.** "Critiques lack target objects" and "critiques lack actionable recommendations" are the only two of its six that a schema can refuse, and a free-text `subject_type` or `recommended_action` gives it nothing to refuse. Section 24 types them as strings and then names the values in prose — `recommended_action` is described as "Keep, revise, reject, merge, investigate", which is DEC-036's naming case rather than its illustrating case. `critique_type` is headed "Critique-type examples", which reads like the illustrating case and is treated as the naming case anyway, because the alternative is a critique type nobody can route on and section 15's last failure condition is precisely output that cannot be traced to specific issues.

`CritiqueSubjectType` has six values where section 24's purpose names three — "a generated threat, mapping, or finding" — because section 15's own responsibilities need more targets than its purpose sentence allows. A critique about a mislabelled documentation gap has a gap as its natural target, and one about an unsupported claim often has an evidence assessment. Reading the purpose sentence as exhaustive would force those critiques onto the nearest permitted object and lose which thing was actually wrong.

**Excluding missing-threat proposals resolves a contradiction inside section 15 rather than overriding it.** The section lists "missing high-impact threats" among what the critic looks for and "candidate missing-threat proposals" among its outputs, and it also makes "critiques lack target objects" invalid output. A missing threat has no target object by definition. One of those three statements has to give, and the failure condition is the one that is structurally enforceable and that the whole object model is built around.

Section 27 settles it from the other direction, with a worked example that is exactly this case: "The critic may recommend that a threat be reconsidered. It may not automatically start an unlimited threat-generation and criticism loop." A critic-proposed threat is a threat generated outside the single call DEC-042 specifies, from different inputs, with the Threat Validation node already several phases behind it. There is nowhere for it to be validated and no phase for it to be generated in.

Roadmap Stage 4's decision gate — "if the critic or another agent does not improve results, remove or defer it" — argues for the narrowest useful version. Missing-threat proposals are the widest thing section 15 asks for and the least verifiable; building them before the gate is passed is building the feature most likely to be removed.

**The severity rule exists because the two severity critique types are almost unreachable and the reason is easy to miss.** Critical review runs before checkpoint 2, where DEC-030 has the reviewer assign a finding's severity. So on a `Finding`, severity is `unassigned` everywhere the critic can see it, and `severity_overstated` against `unassigned` is a critique of a default value nobody chose. Refusing it by name, citing DEC-030, is what stops the pair being used as a general-purpose "I disagree with the emphasis" type. `DocumentationGap` keeps them honest: DEC-045 makes a gap's severity a real judgment made by a real step, so disagreeing with it is a real critique.

Alternatives Considered:

- Review the whole assessment at once, as one call
- Review one object at a time, with no group
- Group by component rather than by threat
- Leave `critique_type` open, since section 24 heads its list "examples"
- Keep `missing_high_impact_threat` and let it target the `SystemContext` version or an unreached `Component`
- Keep missing-threat proposals behind a bounded budget, per section 27's loop rules
- Drop `severity_overstated` and `severity_understated` entirely until `Finding` exists

Tradeoffs:

- **A real capability is gone.** Section 15 asks the critic to notice missing high-impact threats, and it now cannot. The false-negative rate in `evaluation-plan.md` section 8 and the human at checkpoint 2 are the only things left that would catch a whole missing threat, and neither is as targeted as an agent looking for one.
- The per-threat group means a critique that spans two threats — "these two are the same scenario" — is only available when both are in one group, which they never are. Duplicate detection across threats stays DEC-043's deterministic comparison, and the critic's `duplicate` type is left able to see only duplicates within one chain.
- **Per-threat grouping multiplies calls.** Ten threats is ten critic calls where one call over everything would be one, and the critic is the agent whose value is least established. If the Stage 4 gate is failed on cost rather than on quality, this decision is part of why.
- Closing `critique_type` over eleven values means a challenge that fits none of them has to be forced into `contradictory_analysis` or dropped. Section 24 called them examples and this treats them as a set.
- Six subject types where section 24's purpose names three is a departure the document does not sanction; section 24 now records it, which is a document edit made on the strength of section 15 rather than of section 24.
- The severity rule is enforced by a method the validating node has to call rather than by a validator, because the subject's severity is not on the critique. A caller that forgets to call it gets no error.

Open Questions:

- If the Stage 4 gate is passed, does missing-threat proposal come back as a bounded re-invocation, or as a separate deterministic coverage check over components no threat reaches?
- Should the review group include the questions raised alongside a threat, which section 15 lists among its inputs and which the per-threat chain does not obviously contain?
- Is `contradictory_analysis` doing too much work as the catch-all, and would the accepted-critique rate show it?

## DEC-050: `Finding` gains a low-confidence justification; two of section 21's worked values were unbuildable

Date: 2026-08-10

Status: Accepted

Decision:

**`Finding` gains `low_confidence_justification`**, required when `confidence` is `low` and refused otherwise. `data-model.md` section 21 records the field.

**It qualifies rather than substitutes.** `evidence_ids` stays required whatever the confidence. Section 21's minimum-validation rules read "Evidence or an explicit low-confidence justification", and the wording is corrected to "Evidence, and an explicit low-confidence justification where confidence is `low`".

**DEC-013's outcome table is implemented once, in `domain/outcomes.py`, and `Finding` consults it.** The set of validation statuses a finding may carry is *derived* from the table rather than restated: `supported` and `partially_supported`, which are the two the table's four finding-producing cells use.

**Where two of DEC-013's rows overlap, `any / not_evaluated` wins.** The pair `unverified` and `not_evaluated` matches both that row and `unverified / any`, and the table does not say which applies. The outcome is no output.

**Section 21's worked example carried two values the schema now refuses**, and both are corrected: `severity: high` on a candidate becomes `unassigned`, and `validation_status: requires_confirmation` becomes `partially_supported`.

Why:

The justification had nowhere to live. DEC-013 describes it in detail — "a written rationale naming what evidence would raise confidence and why the conclusion is worth surfacing before that evidence exists" — and section 21's field table has no column for it. This is the fourth time the same shape has come up, after DEC-044, DEC-046, and DEC-047: the corpus names an output, the field table has no home for it, and the answer is to add the field rather than let the value evaporate. Treating that as the default is now warranted.

**Reading the minimum rule as an either-or would have been the more serious error**, and it is the reading section 21's own wording invites. DEC-013 settles it in one sentence — the justification "does not substitute for the `unmet` evidence rule above. It qualifies a finding that already meets the rule but whose confidence is low" — and the consequence of getting it wrong is precise: an unevidenced finding would be constructible, which is the DEC-009 collapse arriving through a field added to prevent a different problem. Requiring evidence unconditionally is what keeps the structural argument intact, and the structural argument is the one that matters: an `EvidenceReference` quotes real source text and cannot express an absence, so requiring one makes concluding a weakness from silence impossible rather than discouraged.

**Deriving the permitted statuses rather than restating them is the point of putting the table in code.** A hardcoded set on `Finding` would be a second opinion about when a finding is reachable, and DEC-013 already exists because two opinions about that is how the separation stops holding. The derivation also makes the table's own claim testable over its whole cross product rather than over the rows somebody remembered to write down.

**The row precedence is a real ambiguity and not a reading error.** Both rows are in the table, both match, and neither is qualified. The tiebreak is the reason the `not_evaluated` row gives for itself: the mapping is incomplete, not negative. A documentation gap asserts that Trace could not determine whether a control exists; a mapping nobody evaluated has not established that, it has established nothing. Emitting a gap there turns an unfinished run into a reported conclusion, which is a worse failure than emitting nothing, because nothing is visibly nothing.

**The worked example is the same failure the identifier examples had.** An example is read as a template. Section 21's carried `severity: high` on a candidate, which DEC-030 forbids — findings are created `unassigned` because the reviewer assigns severity at checkpoint 2 — and `validation_status: requires_confirmation`, which DEC-013's table produces no finding from at all. Both predate the decisions that govern them. Left there, the document would specify an object nobody can build, and the more likely outcome is that somebody relaxes the schema to make the example pass.

Alternatives Considered:

- Read section 21's minimum rule as an either-or and allow an unevidenced finding with a justification
- Put the justification in `limitations` or `assumptions` rather than adding a field
- Hardcode the permitted validation statuses on `Finding` and skip the table module
- Resolve the overlapping rows the other way, emitting a gap for an unevaluated mapping
- Leave section 21's example alone and note the divergence in a comment
- Require `confidence` to be other than `low` on a finding at all

Tradeoffs:

- **A field required by one enum value is easy to forget.** Nothing prompts a caller to write a justification until validation fails, and the failure arrives at construction rather than where the confidence was decided.
- The reverse rule — a justification on a non-`low` finding is refused — will annoy someone who wants to explain a `medium`-confidence conclusion. `limitations` and `assumptions` are where that goes, and the distinction is not obvious.
- **`Finding` now imports the outcome table**, so a domain object depends on a module encoding a decision. That is the intent, and it means the table cannot be changed without considering every object that consults it.
- Deriving `FINDING_VALIDATION_STATUSES` at import time means a change to the table silently changes what `Finding` accepts. That is correct and it is also action at a distance.
- **Correcting the worked example changes a document readers may have copied from.** Anyone who built a fixture from it has an object the schema now refuses, which is the intended outcome and still a break.
- The row precedence is recorded here rather than in DEC-013, so a reader of DEC-013's table alone still meets the overlap unresolved.

Open Questions:

- Should DEC-013's table itself be amended to state the precedence, rather than leaving it recorded here?
- Does `low_confidence_justification` belong on `DocumentationGap` and `Question` too, or is a finding the only object where low confidence needs defending?
- Is there a case for requiring the justification to name the evidence that would raise confidence in a structured way, rather than as prose nothing can check?

## DEC-051: Conversions across the outcome boundary carry `converted_from_id`; the source is superseded, not deleted

Date: 2026-08-10

Status: Accepted

Decision:

**`Finding`, `DocumentationGap`, and `Question` gain `converted_from_id`.** It names the object a conversion produced this one from, and it is cross-type: a plain identifier rather than a typed alias, because a finding may have been a gap and a gap may have been a finding. `data-model.md` sections 21, 22, and 23 record it.

**A conversion supersedes its source rather than deleting it.** The source moves to `ObjectStatus.SUPERSEDED` and stays retrievable. Both objects come back from the helper and the caller persists both.

**A conversion never fabricates a required field.** Every field the target requires and the source does not carry is a keyword argument with no default, and a blank one is refused by name.

**Converting *to* a `Finding` runs the full minimum criteria and DEC-013's outcome table.** The helper is a thin wrapper over `Finding.model_validate` and gains no privileges from being one.

Why:

DEC-023 gives three mechanisms for three causes — a reviewer edit mutates in place with a `ReviewerDecision`, a regenerating node sets `supersedes_id`, an approved baseline increments `SystemContext.version` — and a conversion is a fourth cause none of them covers. `supersedes_id` is the closest and it is same-type by construction: `ContextClaim.supersedes_id` is a `ContextClaimId`. Reusing it would mean typing it as a bare string on three objects to accommodate one case, which loses the checking everywhere else to gain it here.

A separate `ConversionRecord` object was the alternative and it fails DEC-025's test: the record is a property of the converted object rather than a thing in its own right, and detached from it means nothing. The same reasoning put suppressions on the mapping that suppressed them.

**Fabrication is the failure mode a conversion helper invites**, which is why the signature is the enforcement rather than a rule. `DocumentationGap.importance` and `Question.rationale` are required and a `Finding` carries neither, so a helper that wanted to be convenient would write "converted from fnd-001" into them and produce an object whose required fields say nothing. Making them arguments means the caller states them; refusing a blank one closes the other half, which is passing `""` to satisfy the signature.

**Severity is the case worth stating separately**, because it looks inheritable and is not. A `Finding` has a severity, so carrying it into the gap seems obviously right — but findings are created `unassigned` (DEC-030) and a gap may never be `unassigned` (DEC-045). The value would move a field meaning "nobody has decided yet" into a field where nobody ever will, and DEC-045's whole argument is that a gap's severity has no later step to resolve it. The reverse direction has the same shape for a different reason: a gap's severity rates the gap and a finding's rates a weakness, so a gap converted forward starts `unassigned` whatever it rated itself.

**The escape-hatch risk is the reason `documentation_gap_to_finding` is deliberately unhelpful.** A gap records that something could not be determined. Converting one forward means somebody determined it, which requires evidence the gap did not have — so `evidence_ids` is a parameter rather than inherited, since a gap's evidence shows ambiguity or contradiction and a finding's has to support the weakness. Building through `model_validate` means DEC-013's table applies, and a gap cannot become a finding on a validation status the pipeline could not have reached one from.

Alternatives Considered:

- Widen `supersedes_id` to a bare string on the three outcome objects
- A `ConversionRecord` object with its own identifier prefix
- Record conversions only on `ReviewerDecision`, using the two existing dispositions
- Delete the source object, since the converted one carries its content
- Let the helpers derive `importance` and `rationale` from the source's `description`
- Inherit severity across the conversion in both directions

Tradeoffs:

- **Three objects now carry a field only conversions set**, and nothing prevents a caller writing an unrelated identifier into it. The chain walk raises on one that does not resolve, which catches the accident and not the deliberate misuse.
- Recording conversions on the object rather than on `ReviewerDecision` means a reviewer-driven conversion is recorded twice — once as a disposition and once as a field — and nothing checks the two agree.
- **`conversion_chain` raises rather than returning a partial walk**, so a single broken link makes the whole history unreadable rather than mostly readable. That is the intended exchange and it will be inconvenient.
- The helpers take a long argument list, and a long keyword-only signature is easy to call wrongly in ways the type checker catches and a reader does not.
- Superseding rather than deleting means an assessment accumulates objects nothing reports. The review package and the renderer both have to filter on status, and neither is written yet.
- `Question` carries one `related_object_id`, so a conversion from a finding keeps the threat and loses the requirement and mapping references except through the chain. Section 22's shape is the constraint and this decision does not change it.

Open Questions:

- Should a reviewer-driven conversion assert that its `ReviewerDecision` disposition and the `converted_from_id` on the result agree?
- Does `Question` need the fuller lineage a finding carries, or is one related object plus the chain enough?
- Should `conversion_chain` have a lenient variant for a report that would rather show a partial history than nothing?

## DEC-052: Finding duplicates are detected on shared identifiers, merged by the node, and every merge persists a record

Date: 2026-08-10

Status: Accepted

Decision:

**Duplicate detection over provisional findings is deterministic and reads identifiers, not prose.** Two provisional findings are duplicates when they share at least one threat identifier *and* at least one requirement identifier. A shared control mapping implies both, because a mapping names one threat and one requirement. Shared affected components and shared affected assets are corroborating features — recorded on the merge when present, deciding nothing on their own. One component hosting two distinct weaknesses is the ordinary case, not a duplicate.

**The node performs the merge; it does not stop at proposing.** This is the half DEC-043 assigned forward: `agent-design.md` section 16 makes "merge duplicate issues" a Finding Consolidation responsibility, and by this phase merging loses no downstream analysis — mapping and evidence validation have already run. The survivor is the earliest-allocated finding (lowest identifier), which is stable across runs and favors nothing else. The survivor takes the union of the evidence, threat, requirement, control-mapping, affected-component, and affected-asset references of everything merged into it, losing none. Every merged finding is retained with `duplicate_of_id` set to the survivor; nothing is deleted.

**`FindingMergeRecord` is a persisted object** — `data-model.md` section 21a, prefix `mrg`. It names the survivor, the merged identifiers, the features that matched, a `decision` of `structural` or `model_assisted`, and a human-readable detail. Section 11's constraint is that the merge decision stays explicit and traceable, and a record that lives only in a node's return value is not traceable after the process exits.

**A model-assisted comparison, if one is ever wired in, proposes candidate pairs and nothing else.** Its proposals are recorded as proposals on the node outcome, are never merged by the node, and reach a merge only through a reviewer decision — which reuses the same merge operation and records `model_assisted`. The MVP wires no model here, for DEC-043's reasons: the node is classified primarily deterministic, and the six-agent cap is not eroded by comparison calls that are "arguably not an agent". The seam exists so the decision to add one later is a wiring change, not a redesign.

**A `Finding` and a `DocumentationGap` are never merged.** They are different conclusions about different things (DEC-009), and the schema is the enforcement: `FindingMergeRecord`'s identifier fields are `FindingId`-typed, so a record naming a gap fails validation, and the merge operation refuses non-`Finding` input before that.

Why:

**The detection rule differs from DEC-043's because the substrate differs.** A threat is prose — a title, a category list — so DEC-043 scores weighted token overlap. A provisional finding is built from identifiers: it names its threats, requirements, and mappings outright. Where the identifiers agree, the two findings assert the same shortfall against the same scenario, and a similarity score over their derived titles would be a noisy proxy for an exact question the objects already answer. The conjunction — threat *and* requirement — is the narrowest rule that merges what consolidation actually produces twice: two mappings of the same requirement to the same threat, through different controls.

**Merging here rather than proposing here is DEC-043's own assignment.** Its record says section 16 assigns the merge itself to Finding Consolidation, and its reason for not merging threats — collapsing before mapping would lose whichever threat the merge did not keep — does not apply after mapping has run and the references are unioned onto the survivor.

**The record is an object rather than fields on the survivor** because the survivor cannot carry it honestly. The merged identifiers are derivable from `duplicate_of_id`, but the matched features and the decision mode are not derivable from anything, and `duplicate_finding_rate` (`data-model.md` section 28) needs to count merges after the fact. DEC-025's locality test — a record detached from its object means nothing — cuts the other way here: a merge concerns several findings at once, so it has no single object to live on.

**Earliest-allocated survivor rather than most-evidenced.** The union makes the survivor's evidence identical whichever member survives, so the tiebreak only chooses which title, summary, and description persist. Earliest allocation is deterministic, cheap to explain, and does not smuggle in a quality judgment no rule defines. DEC-043's open question about a recommended survivor is answered for findings by making the choice not matter.

Alternatives Considered:

- Score weighted feature overlap with a threshold, as DEC-043 does for threats
- Propose merges to the checkpoint 2 reviewer and merge nothing automatically
- Record merges as fields on the surviving finding
- Record merges only in `ExecutionRecord` metadata
- Select the survivor by evidence count, or by lowest `confidence`, rather than by allocation order
- A model-assisted comparison for pairs the structural rule misses

Tradeoffs:

- **Rewording does not defeat this rule, but disjoint lineage does.** Two findings describing one weakness through different threats and different requirements are not detected. That is the case a semantic comparison would catch, and the revisit trigger is the same as DEC-043's: a measured `duplicate_finding_rate` this rule misses.
- The conjunction is strict. Two findings sharing a requirement across two related threats stay separate, which can read as noise to a reviewer; the checkpoint reviewer can merge them, and the operation is built to be reused there.
- A twenty-fourth prefix and a twenty-seventh documented object, for a record type that most assessments will produce zero of.
- Merged findings stay `candidate` with `duplicate_of_id` set, so every consumer of the provisional set — the review package, the renderer, the metrics — must filter on `duplicate_of_id` rather than getting a pre-filtered set.

Open Questions:

- Should the checkpoint 2 review package show merge records alongside the findings they merged, and DEC-043's threat merge proposals with them?
- When a reviewer rejects a survivor, what happens to the findings merged into it — do they stay duplicates of a rejected finding, or return to the provisional set?

## DEC-053: Consolidation applies forward critique recommendations; a deterministic revision adds and never rewrites

Date: 2026-08-10

Status: Accepted

Decision:

**Finding Consolidation applies the critique recommendations that route forward, and only those.** `workflow/critique_validation.py` already splits the recommendations: `revise` and `investigate` against a threat, control, mapping, or evidence assessment re-enter a passed phase and are the orchestrator's budget-gated concern, while everything else "is applied going forward, by Finding Consolidation or the reviewer". This decision settles the going-forward half, per action:

- **`keep`** — recorded, nothing changes.
- **`reject`** — the candidate moves to `rejected`, leaves the provisional set, and is retained with the critique identifier as its stated reason. Never deleted.
- **`revise`** — the candidate is rebuilt with the critique's description appended to `limitations` under the critique's identifier, and the critique's cited evidence unioned into `evidence_ids`. Nothing else changes. The pre-revision state is preserved on the application record, DEC-023's `prior_value` pattern applied to a node.
- **`merge`** — deferred to the DEC-052 merge operation; consolidation's critique step performs no merge of its own, so one recommendation cannot merge through two doors.
- **`investigate`** — deferred to the checkpoint 2 reviewer, whose vocabulary has "request more analysis". A deterministic node cannot investigate.

**A `documentation_gap_only` critique outranks its own `recommended_action`.** Whatever the critic recommended doing with the finding, the type asserts the finding should not exist as one — so the candidate routes through DEC-051's `finding_to_documentation_gap`, with the critique's rationale as the gap's importance and the source finding superseded, never through an ad hoc edit that softens a description. The precedent is the contradiction rule in the same node: a structural signal outranks an advisory one.

**No critique path can produce an approved object.** Approval is the checkpoint's (DEC-005); the application writes `rejected`, `superseded`, and revised candidates, and nothing else. A critique that resolves to no candidate, or to one already rejected or converted, is reported as unapplied with the reason — never silently dropped.

**The lineage surface is a query, not a stored structure.** `services/findings/lineage.py` walks section 32's chain backward from a finding — critiques, mappings, evidence assessments, threats, context claims, evidence references, source documents — resolving every referenced identifier and raising on one that does not resolve. Nothing new is persisted for it; the chain is already on the objects, which is what DEC-006 buys.

Why:

**The revision rule is the decision that needed making**, because "apply critique recommendations" (`agent-design.md` section 16) collides with two other rules the moment the action is `revise`: the node is deterministic and cannot write prose, and section 15 forbids rewriting objects without preserving lineage. Appending the critique's own words to `limitations` threads it: the text is agent output that already passed schema validation and the critique validation node, the field means exactly "analysis limitations", the entry carries the critique identifier so the change records its cause on the object itself, and nothing the earlier pipeline asserted is altered. A revision that *rewrote* `description` or `impact` deterministically would have to fabricate, and fabrication under a validation-shaped name is the section 26 failure.

**Rejection is consolidation's to perform** because section 16 already gives this node "use no output when" rules and section 18 keeps rejected candidates available rather than deleted. The critic still decides nothing: the recommendation is applied by deterministic logic the same way an `unverified` mapping is routed by the outcome table — section 2.5's "agents propose; deterministic logic and humans decide" with the deciding logic in the application, not the agent.

**The type-outranks-action rule closes the softening path.** A `documentation_gap_only` critique answered with a revision would produce exactly what the issue names as the failure: a finding with a softened description that still asserts a weakness the evidence does not carry. Routing through the DEC-051 helper means the minimum criteria, the severity rules, and the lineage field all apply, and the source survives as `superseded`.

Alternatives Considered:

- Have the revision lower `confidence` to `low` with the critique's rationale as the justification
- A `supersedes_id` on `Finding`, minting a new finding per revision (DEC-023's regeneration mechanism)
- A persisted `CritiqueApplication` object with its own prefix
- Apply `documentation_gap_only` only when `recommended_action` agrees
- Let consolidation perform `merge` recommendations directly

Tradeoffs:

- **A rejected candidate's stated reason lives on the application record, not on the object** — `Finding` has no rejection-reason field and this decision adds none. Retention and the persisted linkage for rejections are #103's; until then the reason survives the run only in the outcome the caller holds.
- `limitations` now serves two writers: the consolidation build and the critique application. An entry is attributable only because the application prefixes the critique identifier, which is a convention, not a schema rule.
- Deferring `merge` and `investigate` means two of the five actions produce no change here, and a reader of "apply critique recommendations" may expect more. The alternative was a node that merges through a second door and "investigates" by guessing.
- The revision unions the critique's evidence into the finding's. Critique evidence shows what the criticism rests on, which is not always evidence *for* the finding; the union is honest about provenance only because `EvidenceReference` records what each excerpt is.

Open Questions:

- Should the application records be persisted alongside #103's retained rejections, so a resumed run can re-state why a candidate is absent?
- When a revised candidate is later rejected by the reviewer, is the pre-revision state part of what checkpoint 2 shows, or only the revised object?

## DEC-054: The finding checkpoint reuses the shared machinery; a reviewer merge is an edit plus the record; a blocking question pauses nothing

Date: 2026-08-10

Status: Accepted

Decision:

**Checkpoint 2 is the shared `CheckpointNode`, configured for `human_finding_review`, waiting on the provisional findings.** Its subjects are the state's `candidate_finding_ids`; it advances only when every one has a `ReviewerDecision`, and there is no flag, configuration field, or argument that changes the condition (DEC-005, DEC-012). Pause and resume are DEC-017's, unchanged. An assessment in which the reviewer approves nothing passes the checkpoint: rejection is a decision, and an empty approved set is a valid outcome.

**There is no `merge` disposition, and none is added.** The `ReviewDisposition` gap against `agent-design.md` section 18 is resolved the way DEC-030 resolved severity: section 18 names actions a reviewer takes, section 4.6 names dispositions the system records, and the two do not correspond one to one. A reviewer merge is recorded as what it does — an `edit` per merged finding whose delta is `duplicate_of_id`, an `edit` on the survivor when the union changed it — plus **the same `FindingMergeRecord` the automatic path writes** (DEC-052), so `duplicate_finding_rate` counts both paths from one table.

**`MergeDecision` gains `reviewer`, amending DEC-052's two values.** DEC-052 named `structural` and `model_assisted` and defined `model_assisted` as a reviewer merging from a model-proposed pair — which left a reviewer merging on their own judgment, the checkpoint's ordinary case, unrepresentable. Three values now: `structural` (the identifier rule decided), `model_assisted` (a reviewer decided from a model proposal), `reviewer` (a reviewer decided unprompted). `matched_features` may be empty **only** on a reviewer merge: the rule's reason is its features and a record of it without them is a record of nothing, while a reviewer's reason lives in the `ReviewerDecision` rationale.

**A blocking `Question` pauses nothing; it is surfaced first at the next structural checkpoint.** Section 22 described `blocking` as "whether workflow should pause", which contradicts DEC-005's two structural checkpoints — a field that could pause the pipeline anywhere would be a third checkpoint nobody decided to add, configurable per question by whatever writes the field. The field's real meaning is priority of a specific kind: the assessment cannot conclude soundly without the answer, so the question leads the review package (`order_for_review` already puts blocking first) and the reviewer — who can defer every finding the question touches — decides what it holds up. Section 22's description and `domain/question.py`'s docstrings are corrected.

**An approval whose finding carries `severity: unassigned` is refused at this node** (DEC-030's load-bearing half, landing where that entry said it would). So is approving a finding already merged into a survivor — the canonical finding is the one to decide.

**Reviewer identity stays DEC-023's convention.** Every checkpoint-2 decision carries `reviewer_id`, a configured local string defaulting to the operating-system username. No authentication, role, or tenancy is introduced (DEC-004).

Why:

**Recording a merge as edits keeps the audit trail one mechanism.** DEC-023 gives reviewer changes exactly one shape — mutate in place, record the delta — and a merge *is* a set of field changes: `duplicate_of_id` on the merged, unions on the survivor. A `merge` disposition would record the same facts a second way, and every consumer of decisions would need to understand both. The merge-specific facts that edits cannot carry — the survivor, the set merged, what matched — already have a persisted home in DEC-052's record, built for exactly this reuse.

**The blocking-question resolution follows from where answers come from.** A question is answered by a person. Between consolidation and checkpoint 2 no person is present, so a pause anywhere but a checkpoint would stop the process where nobody is looking at it; DEC-017's pause already waits indefinitely at the place the reviewer *is* looking. Surfacing first at the checkpoint is the whole enforceable content of "this must be resolved before conclusions rest on it".

Alternatives Considered:

- Add `merge` to `ReviewDisposition` and record one decision per merge
- Record a reviewer merge as a single `edit` on the survivor only, with the merged identifiers in the rationale
- Reuse `model_assisted` for reviewer-initiated merges
- Let a blocking question pause the run where it is raised, as section 22's description implied
- Gate checkpoint completion on every blocking question being answered

Tradeoffs:

- A reviewer merge of N findings writes N+1 or N+2 rows (edits plus the record), which is chattier than one `merge` decision; the compensation is that no consumer needs a second vocabulary.
- `matched_features` empty-only-for-reviewer is a conditional constraint on a schema field, which is harder to state than `min_length=1`; the validator names the condition.
- A blocking question that the reviewer overlooks holds up nothing mechanically. The checkpoint surfaces it first and counts it, but "blocking" is enforced by the reviewer's judgment, not the application — deliberately, and weaker than the old description promised.
- Checkpoint completion requires a decision per provisional finding with no bulk approve (DEC-017's stated friction), and this decision does not soften it.

Open Questions:

- Should a checkpoint-2 approval write `Assessment.approved_by`, or does `Assessment.status` stay the deliverable's lifecycle only (DEC-031) with attribution living on the decisions?
- Does the review surface need to show, per finding, the blocking questions that touch it as a refusal-shaped warning rather than a list entry?

## DEC-055: Consolidation's downgrade appends to the reason and never overwrites; approval runs a deterministic gate with a recorded override

Date: 2026-08-10

Status: Accepted

Decision:

**`downgrade_reason` is appended to, never overwritten, and `downgraded_from` is written once.** This answers DEC-046's open question. When Finding Consolidation applies DEC-013's conditions 2 and 3 — the two that read `EvidenceAssessment` and could not run at Mapping Validation — it lowers the mapping to `unverified` and records why as a new entry appended to `downgrade_reason`, each entry prefixed with the node that wrote it and joined with `"; "`. `downgraded_from` keeps its existing value when one is present: it records the status the *agent proposed*, and a second downgrade does not change what was proposed.

**Consolidation now performs the downgrade DEC-046 assigned to it.** The `downgrade_only` and `question_after_downgrade` cells of the outcome table rebuild the mapping to `unverified` with the record, and the run's outcome carries the downgraded mappings so persistence writes them under their identifiers. A `question_after_downgrade` cell produces the question the table names; a `downgrade_only` cell produces nothing further, and the retained rejected-candidate entry states why.

**Approval runs a deterministic gate, and the override path is explicit.** `approve_finding` refuses, in addition to DEC-030's severity rule: a finding whose `validation_status` is not `supported` or `partially_supported` — approvable only with an explicit `override_rationale`, which is stored on the `ReviewerDecision` with the rationale prefixed `override:` so overrides are retrievable by inspection — and, outright, a finding with no evidence citation or no actionable remediation (no recommendation and no acceptance criteria). The refused conditions are already unreachable through the schema for objects built normally; the gate is the last enforcement point before a conclusion becomes official, and it does not assume the schema was upstream of every caller. **The issue's premise for the override is stale and is recorded as such**: it predates DEC-013 and DEC-050, under which a finding carrying `unsupported` or `contradicted` is unconstructible — `Finding` refuses every validation status the outcome table produces no finding from. The gate's refusal is exercised against a validation-bypassing construct, and an override that passes the gate still meets the schema at persistence, which refuses the object; the override machinery exists so that if the table ever widens, approving a non-carried status is loud and recorded rather than silent.

**One accessor owns the approved set.** `services/findings/approved.py` is the only module that queries findings by approved status; report generation, rendering, and evaluation consume it, and a source-scan test holds every other module to that. Rejected, deferred, and superseded candidates are retained and queryable through `retained_candidates`, each with its stated reason — the reviewer's rationale where a decision exists, the rejecting critique's description where consolidation applied one (DEC-053's deferred linkage, landing here).

**Checkpoint completion moves the assessment through the existing verb.** `conclude_finding_review` verifies every provisional finding has a `ReviewerDecision` and calls `AssessmentService.resume_from_review` — DEC-031's verb for a completed checkpoint, returning the assessment to `draft` while the run continues to report generation. `approve` stays the pipeline-completion verb. No new status and no setter.

Why:

**Append preserves the attribution DEC-046 exists for.** Its whole argument is that a downgrade count must distinguish a catalog problem from a model problem from an application correction. Two nodes can each lower a conclusion for different reasons across a revision cycle, and overwriting would leave the record claiming the second node's reason was the only one — a silent erasure inside the field that exists to prevent silent changes. Node-prefixed entries keep each reason attributable at the cost of a delimiter convention.

**`downgraded_from` is first-writer because it answers a different question.** The reason accumulates because "why is this not what the agent said" can have several answers; the origin does not accumulate because "what did the agent say" has one.

**The override is a prefix convention rather than a field** because `ReviewerDecision` (section 25) has no override column and the delta fields carry field changes, not judgments about conditions. A prefix on `rationale` is retrievable with a string match, costs no schema change, and keeps the record readable as a sentence. If overrides become an evaluation metric, a field is the successor and this entry is where the convention is recorded.

Alternatives Considered:

- Overwrite `downgrade_reason` with the latest node's reason
- A list-valued `downgrade_reasons` field on `ControlMapping`
- Advance `downgraded_from` to the pre-downgrade status at each downgrade
- An `override` boolean on `ReviewerDecision`
- Enforcing the approved-set rule at the store layer rather than by source scan

Tradeoffs:

- A delimiter convention inside a free-text field is parsing by agreement; a consumer that wants the entries separately splits on `"; "` and trusts writers to have used the prefix.
- The gate re-checks conditions the schema already guarantees, which is redundant until the day an object reaches it another way — the redundancy is the point, and it costs a few comparisons.
- The `override:` prefix makes the rationale slightly less natural to read and is the kind of convention that erodes without the test that greps for it.
- The accessor rule is enforced by source scan, which a sufficiently creative query evades; the store cannot enforce it without knowing who is asking, which DEC-004 declines to model.

Open Questions:

- Should overrides be counted as their own evaluation metric, and does that justify promoting the prefix convention to a field on `ReviewerDecision`?
- When a revision run re-proposes a previously downgraded mapping, does the new mapping inherit the old downgrade record or start clean with `supersedes_id` carrying the history?

## DEC-056: Benchmark matching is structural through the contract's fields, and a consolidation scores full credit per matched expectation

Date: 2026-08-10

Status: Accepted

Decision:

**An expected finding matches an approved finding when the finding cites the expected `requirement_id` and names an affected component whose name matches the expected `affected_component`.** The contract already fixes the fields (`matching.findings_match_on`); this decision fixes the mechanics: component matching goes through the run's own `Component` objects — identifier to name, compared case-insensitively after whitespace normalization — because generated identifiers are run-scoped (DEC-018) and names are what the truth set can carry. Title wording is never compared. `expected-findings.yaml` gains the `affected_component` field the contract's rule requires.

**A consolidated finding scores full credit for every expected entry it matches.** DEC-029 enumerates FND-002 and FND-004 separately and states that one well-reasoned combined finding is defensible rather than wrong; `allow_consolidation: true` is the contract's word for it. This closes DEC-029's open question: no partial credit, no penalty fraction — a defensible consolidation scored at half would be a penalty wearing a measurement's name, and the metric it would depress is the false-negative rate, exactly the number the scenario exists to keep honest. The consolidation is *observable* instead: the evaluation records how many expected entries resolved onto fewer produced findings, so drift toward over-merging shows up as a count rather than as a hidden discount.

**An expected documentation gap matches a produced gap through the requirement it bears on.** `expected-documentation-gaps.yaml` gains `requirement_id`, and a produced gap reaches a requirement through its related mapping (consolidation writes `related_object_ids` as threat and mapping). Gap wording is never compared, for the same reason as titles.

**`EvaluationResult` is promoted from section 40's deferred list**, which this issue's metrics make unavoidable: a metric with no persisted object is a print statement. Section 40 records the promotion; `PromptDefinition` stays deferred.

Why:

**Structural matching is the only kind that cannot be gamed by prose.** A matcher over titles rewards the run that words its findings like the truth set, which is a copying test, not a correctness test. Requirement and component are the two fields DEC-029's analysis actually used to decide what was distinct, and both survive rewording.

**Full credit follows from what the truth set records.** The finer decomposition exists because a matcher can collapse two entries onto one finding and cannot split one entry across two (DEC-029's own words). If collapsing is an accepted mechanic of the matcher, penalising the run for triggering it is incoherent — the score would depend on an authoring choice the run cannot see.

Alternatives Considered:

- Match findings on normalized title overlap, DEC-043-style
- Partial credit (half per expected entry) for a consolidated match
- A separate `consolidation_penalty` metric subtracted from coverage
- Matching gaps on subject keywords rather than through a requirement
- Leaving `EvaluationResult` deferred and writing metrics only to a JSON file

Tradeoffs:

- Component names in the truth set must stay aligned with `expected-context.yaml`'s names; a rename there silently breaks matching here, and only a benchmark run notices.
- Full credit means a run that merged everything into one mega-finding could still score zero false negatives if the structure matched; the volume principle and the reviewer are the backstops, and the recorded consolidation count is the tell.
- Requirement-mediated gap matching cannot match a gap raised outside any mapping; such a gap scores as unexpected even when reasonable. The precision metric therefore reads best alongside the reviewer notes, not alone.

Open Questions:

- Should the consolidation count become a named metric with a target, or stay metadata on the false-negative computation?
- When scenario two arrives, does component-name matching survive a scenario whose truth set names components differently from its own context file?

## DEC-057: Catalog versions are immutable once released; lifecycle is minor-or-major, retirement is a status, and cross-version fates are authored data

Date: 2026-08-10

Status: Accepted

Decision:

**A catalog version is `<major>.<minor>`, and there is no patch level.** The classes of change are
two. A *minor* version may add requirements, revise wording, and retire entries; every identifier
that exists in the prior version is either present or accounted for, and no identifier is renumbered
or reused. A *major* version may renumber, and a fate map is then mandatory. The class ASVS calls
patch — edits compatible with an existing assessment — is empty here by construction: DEC-019's
content hash covers the parsed catalog, so any change a parser can see moves the hash and breaks
verification against recorded runs. The version semantics ratify what the hash already enforces;
a fix, however small, is a new minor version.

**A released version directory is immutable, and the freeze is enforced at PR time.** A version is
`draft` until released and may be edited in place freely — which answers DEC-010's open question
about when 0.1 becomes 0.2: while 0.1 is `draft`, edit it; after release, any content change is
0.2. Version 0.1 releases when the recorded ForgeFlow fixture (#263) lands, because a replayable
recorded run is the first artifact whose requirement references outlive an edit. On release, CI
fails any pull request that touches a file under that version's directory (the AISVS `LOCKED`
pattern): the loader's hash check refuses a drifted catalog at read time, but the CI guard fails
at review time and documents the freeze in-repo rather than in a stack trace.

**Governance metadata lives outside the frozen, hashed content.** A top-level
`requirements/versions.yaml` records, per version: lifecycle status (`draft`, `active`,
`retired`), maintainer, release date, and last-reviewed date (RaD-TM's "owned, not orphaned"
fields). It sits outside the version directories and outside the content hash, so retiring a
version does not alter content whose hash a recorded assessment verifies. The manifest keeps its
section 30 shape; the loader sources lifecycle status from the registry when both exist, and the
mechanics land with the 0.2 implementation.

**A requirement retires by status, never by deletion, within a major lineage.** The next minor
version ships the entry in its category file with `status: retired` (section 17 already carries
the vocabulary; pytm's `DEPRECATED` marker maps onto it and no new marker is invented), so old
assessment references resolve for the lineage's lifetime. Removal happens only at a major
version, recorded as a fate.

**Cross-version fate maps are authored data, shipped with the newer version.** When 0.2 ships,
`requirements/mappings/0.1-to-0.2.yaml` records one fate per 0.1 identifier — `unchanged`,
`revised`, `retired`, and at a major boundary also `moved_to`, `merged_to`, `split_to`, and
`deleted` with a reason (ASVS's mapping-file vocabulary). Tests hold it referentially complete in
both directions: every old identifier has a fate, every named target exists. The loader never
reads it; its consumers are people and the longitudinal tooling the cross-run finding-identity
decision (#236) reaches toward.

Why:

**The content hash cannot express change-compatibility, only change.** DEC-010 and DEC-019 pin
what a version contains; nothing stated which kinds of change are compatible with an assessment
already made against it. Version pinning (`load_catalog(version)`) protects an in-flight run;
this contract protects everything downstream of a finished one — recorded runs, benchmark truth
sets that pin `catalog_version` (DEC-027), and any report citing a requirement identifier.

**Immutability-at-PR-time fails faster than immutability-at-read-time.** The hash already makes
silent in-place edits unreadable, but the failure surfaces at the next load, in whatever process
happens to load it, with a hash mismatch as the only message. A CI guard names the violation at
the moment someone proposes it.

Alternatives Considered:

- Three-part semver with in-place patch releases, hash regenerated each time
- Editing a released 0.1 in place with `catalog_hash.py --write` as the ritual
- A `deprecated` boolean or marker field alongside `status`, per pytm's convention
- Keeping governance fields inside the hashed manifest
- OpenCRE identifiers as renumbering-proof anchors instead of fate maps

Tradeoffs:

- A new directory per fix is heavier than a patch: every minor version copies eleven-plus files.
  The cost buys the property that a version, once cited, means one thing forever.
- Fate maps are authored, so they can be wrong in ways referential-integrity tests cannot see; a
  `revised` that should have been `split_to` misleads exactly the tooling it exists to serve.
- The CI guard binds the repository, not a local clone; a locally edited released catalog still
  fails only at load. The two guards are complementary, not redundant.
- `versions.yaml` is a second file that can disagree with the manifests it describes; the same
  both-directions test posture that holds `catalog.yaml` to the category files applies.

Open Questions:

- Does the maintainer field carry weight while DEC-004's single-user scope holds, or is it a
  placeholder for the multi-user future?
- What first forces a major version — a category taxonomy change, or an identifier-scheme change?

## DEC-058: Catalog 0.2 provenance — AISVS and the AI Exchange are adopted with stated caveats, the 2026 LLM Top 10 identifiers are used, and `source_frameworks` stays strings

Date: 2026-08-10

Status: Accepted

Decision:

**AISVS 1.0 is adopted as a citable framework for catalog 0.2's agentic and AI categories**, cited
as `"OWASP AISVS: v1.0-C9.4.3"` — the reference form AISVS itself prescribes, framework segment
unversioned, exactly parallel to the ASVS rule `requirements/README.md` already records. The
caveat is binding, not advisory: AISVS wording is runtime-test phrased ("Verify that X is
enforced") with near-zero documentation-assessable wording, so a Trace requirement grounded in C9
(Orchestration/Agentic) or C10 (MCP) adopts the *substance* and is rewritten into the
documentation register, so that silence resolves to `unverified`. A requirement that imports AISVS
phrasing unrewritten is a DEC-009 violation whatever it cites. AISVS is CC BY-SA 4.0 like ASVS:
cited by identifier, wording never reproduced.

**The OWASP AI Exchange is citable as a living document, and the accessed date is mandatory.**
It has no versioned releases, so permalink-plus-accessed-date is the only stable handle:
`"OWASP AI Exchange: <topic anchor>, accessed YYYY-MM-DD"`. It may stand as a requirement's sole
citation — refusing that would only push authors to launder the same grounding through a versioned
framework that fits worse — but the date makes the staleness visible rather than silent.

**Catalog 0.2 cites the LLM Top 10 under the 2026 release**, as `LLMxx:2026` with the GenAI
Security Project as publisher, applying the renumbering (Improper Output Handling LLM05:2025 →
LLM10:2026; Unbounded Consumption LLM10:2025 → LLM06:2026). Version 0.1's 2025-pinned strings
remain correct archived provenance and are not edited — DEC-057 freezes them anyway once 0.1
releases.

**OpenCRE identifiers are rejected as citation anchors.** The argument for them is renumbering
resistance; the observed state is the caution — their public ASVS mapping still resolves to
v4.0.3, one major version behind what this catalog cites. An anchor whose own mappings lag is a
crosswalk liability wearing a stability costume, and `requirements/README.md` already forbids
sourcing ASVS crosswalks through it.

**`source_frameworks` stays `list[string]` for 0.2.** The structural alternative —
`{framework, version, source_url, accessed}` objects, per the 2026 release's mapping sidecars —
is rejected for now: section 17 is authoritative and implemented, the string grammar
`<framework>: <version-qualified reference>` is parsed and tested, the one new need (an accessed
date) fits the grammar, and the field has no machine consumer — compliance mapping is deferred,
and provenance's readers are a person and the citation test. The revisit trigger is named: the
first machine consumer, which the interop-export decision (#231) would supply if a serializer
wants structured citations.

Why:

**Each source earns its place by covering ground the current three do not.** AISVS C9/C10 covers
agentic orchestration and MCP, which the 2025 LLM Top 10 predates; the AI Exchange feeds ISO/IEC
27090 and covers AI-specific ground between releases. Adopting them as provenance keeps 0.2's new
requirements grounded in public work rather than invented, which is the entire function of the
field.

**The register caveat is the decision's load-bearing half.** Every surveyed verification standard
phrases for a running system; Trace assesses documentation. The difference is exactly DEC-009 —
absence of evidence must resolve to `unverified` — and it is easier to import a phrasing violation
than to notice one.

Alternatives Considered:

- Adopting AISVS wording as-is and accepting the runtime register
- Refusing living documents as sole citations
- Keeping 2025 LLM identifiers in 0.2 for continuity with 0.1
- OpenCRE ids as primary anchors with framework citations secondary
- Graduating `source_frameworks` to structured objects now, ahead of a consumer

Tradeoffs:

- An accessed-date citation is honest about staleness but does not prevent it; nothing re-checks
  the Exchange's content against the date.
- Staying with strings means a future structured consumer parses the grammar out of prose; the
  grammar is tested, so the parse is stable, but it is still a parse.
- Skipping OpenCRE keeps the catalog ahead of the mapping ecosystem at the cost of doing its own
  crosswalk maintenance forever, one fate map at a time (DEC-057).

Open Questions:

- Does the citation test vendor an AISVS export for resolution, as #221 did for ASVS, or accept
  unresolved AISVS identifiers the way it accepts NIST ones?

## DEC-059: Catalog 0.2 gains a cloud-operations category mined from Cumulus, adapted under CC BY 4.0 with attribution

Date: 2026-08-10

Status: Accepted

Decision:

**Catalog 0.2 adds a cloud-operations primary category**: file `cloud-operations.yaml`, identifier
prefix `req-OPS-`. Its ground is mined from OWASP Cumulus, whose 55 cards name operational
security expectations the current catalog does not cover: separation between backup access and
delete permissions, cost-anomaly alerting, environment separation including indirect connection
through CI/CD, visibility of pipeline definition changes, and alert actionability against alert
fatigue. Each phrases naturally in the documentation register — silence resolves to `unverified`
— which is the admission test DEC-009 sets. The exact requirement set and count are authoring
work in the 0.2 implementation, guided by this named ground; this decision fixes the category,
the prefix, and the source posture.

**The licensing posture differs from ASVS and AISVS, and both postures are stated side by side.**
Cumulus content is CC BY 4.0 (the GitHub license API misreports it as null because of the REUSE
layout), so wording may be *adapted with attribution* — unlike the CC BY-SA sources, which are
cited by identifier with wording never reproduced. `requirements/README.md` records the two
postures adjacently so the share-alike rule is not accidentally applied to Cumulus or, worse, the
adaptation freedom accidentally applied to ASVS.

**Citations use the version-in-framework-segment form**, since Cumulus prescribes no reference
format: `"OWASP Cumulus <release>: <card identifier>"`, with the concrete release pinned against
the source as fetched when 0.2 is authored.

**This is minor-version content under DEC-057** — a new category and new requirements, no
renumbering — and the provenance table gains its row under DEC-058's process.

Why:

**The gap is real and the source is apt.** The current catalog is application- and
architecture-shaped; nothing in it asks whether backups can be deleted by the credentials that
write them, whether cost anomalies alert anyone, or whether a pipeline change is visible. These
are architecture-level, documentation-assessable questions — precisely Trace's register — and
Cumulus is the one surveyed source that treats operations as first-class threat-modeling ground.

**Stating the licensing posture now prevents the quiet failure later.** The catalog's standing
rule is written for share-alike sources. A future author extending the cloud-ops category who
applies that rule to Cumulus loses harmless freedom; one who assumes Cumulus's freedom applies to
ASVS creates a licensing obligation. The pair is only safe when both are explicit.

Alternatives Considered:

- Folding the operational requirements into existing categories (cicd-trust, logging) rather than
  adding one
- Citing Cumulus by card identifier only, share-alike style, ignoring the adaptation freedom
- Deferring cloud-ops entirely until a scenario demands it
- A broader `operations` category not scoped to cloud

Tradeoffs:

- A new category built from one source starts single-sourced; ASVS and NIST cross-citations will
  be thinner here than elsewhere in the catalog, and the provenance table will show it.
- Card names are not stable identifiers the way `v5.0.0-2.1.1` is; a Cumulus release that renames
  cards strands the citations, mitigated by pinning the release in the framework segment.
- Requirements this operational sit at the edge of "assessable from design documentation"; the
  authoring test is whether ForgeFlow-class input can evidence them, and some candidates will
  fail it and be dropped.

Open Questions:

- Which scenario exercises the category first — none of the four seeded benchmarks is
  operations-heavy, and a requirement no scenario can exercise is exactly what DEC-010's
  "small on purpose" posture argues against shipping.

## DEC-060: The reviewer may assign a risk treatment at checkpoint 2; `accept` requires a rationale, and treatment never blocks approval

Date: 2026-08-10

Status: Accepted

Decision:

**`Finding` gains a reviewer-assigned risk treatment.** Three fields, specified here; the table
rows and code land together in the implementing change:

- `risk_treatment` — a **closed** vocabulary: `undecided`, `mitigate`, `accept`, `transfer`,
  `avoid`. Closed in the DEC-036 sense that the values are named rather than illustrated, like
  `DataFlow.direction`; extending it is a design change. Findings are created `undecided`.
- `treatment_rationale` — required when `risk_treatment` is `accept`; optional otherwise. For
  accepted risk it is the residual-risk statement: what remains exposed and why that is
  tolerable.
- `treatment_review_by` — an optional date, meaningful for `accept`; DEC-061 gives it semantics.

**The reviewer assigns treatment at checkpoint 2, and no node proposes one** — DEC-030's
philosophy applied to the neighbouring judgment. Treatment is a risk decision in business
context; the documents under review do not contain it, and an agent asked for it would produce a
fluent answer from sources that cannot answer.

**Unlike severity, treatment never blocks approval.** `undecided` may survive checkpoint 2.
Severity is the reviewer's own security judgment and orders the report, so DEC-030 makes it
mandatory; treatment is frequently the system owner's decision to make after reading the report,
and a gate would manufacture defaults — a forced treatment is a fabricated business decision,
which is DEC-009's failure relocated into a reviewer field. The gate that does exist: **an
approval whose finding carries `accept` with no `treatment_rationale` is refused**, by the same
mechanism as the severity gate.

**Assignment is recorded as `edit`.** No `ReviewDisposition` value is added; `prior_value` and
`updated_value` carry the change per DEC-023, exactly as severity does. Section 4.6's note
generalizes.

**The report renders treatment deterministically inside the existing findings sections.** An
`accept` renders its rationale and review-by date with the finding. No section is added, no
ownership changes, and the sixteen-section contract (DEC-035) is untouched; the Report Generation
agent's `risk_summary` may reference treatment outcomes and never rewrites them.

Why:

**Five surveyed projects independently model a treatment outcome** — Threat Dragon's status
vocabulary, pytm's `Finding.response`, the Threat Modeling Cheat Sheet's "each threat must have a
response", ThreatAtlas's acceptance-with-approver-and-date, the playbook's residual-risk
statement — which is the strongest convergence signal in the survey. A finding whose fate is
recorded is a decision; a finding whose fate is a conversation after the report is a loose end.

**The vocabulary is present-tense choice, not past-tense completion.** Threat Dragon's
`Mitigated`/`Eliminated` describe work already done, which a documentation review cannot witness;
Trace's values name the *chosen response*. There is no `eliminated`: a weakness that no longer
exists produces no finding.

Alternatives Considered:

- Threat Dragon's five past-tense statuses verbatim
- Requiring a treatment at approval, symmetrical with the severity gate
- A new `accept_risk` disposition on `ReviewDisposition`
- Recording treatment on `ControlMapping` rather than `Finding`
- Leaving treatment entirely to post-report tooling

Tradeoffs:

- An approved report may carry findings with no treatment story. That is deliberate — honesty
  over completeness theatre — but it will read as unfinished to audiences expecting a risk
  register, and the report's authored wording should frame `undecided` as "not yet decided by the
  system owner" rather than leaving the cell blank.
- The `accept`-requires-rationale rule is a two-field validation coupling that the checkpoint
  gate must enforce with the same care as the severity gate, and it is easier to forget because
  it fires rarely.
- Treatment on `Finding` means a merged finding (21a) carries one treatment for what were two
  candidates; the merge record preserves lineage, but a treatment assigned before a merge is not
  automatically revisited.

Open Questions:

- Does `transfer` need a named counterparty to be meaningful, or is that the rationale's job?
- Should the report's deterministic findings sections group accepted-risk findings separately so
  residual risk is legible at a glance?

## DEC-061: Revisit is episodic — assumed claims are standing revisit subjects, and an expired acceptance re-routes to checkpoint 2 at the next run

Date: 2026-08-10

Status: Accepted

Decision:

**Nothing watches a clock.** DEC-004's system runs locally and episodically; re-check semantics
attach to the triggers that already exist — the start of a new `WorkflowRun` on the assessment,
and `begin_revision` (DEC-031's verb, DEC-038's mechanism). Display never triggers anything:
`trace assessment status` may list overdue dates read-only, and nothing fires from being looked
at.

**Assumptions carry no date.** A `ContextClaim` with status `assumed` is a *standing* revisit
subject: at the next revision's checkpoint 1 it is re-presented flagged with the `revisit_due`
routing reason (DEC-062) rather than buried among unchanged claims. No `review_by` field is added
to `ContextClaim`, because an assumption's shelf life is driven by landscape change rather than
calendar, and an authored date would be a guess wearing a deadline's costume. The OWASP umbrella
definition asks that assumptions be checkable or challengeable in the future; the status already
makes them findable, and this makes them presented.

**Accepted risk carries the one authored date.** `treatment_review_by` (DEC-060) passing changes
nothing at rest. At the first run or revision that begins after the date, the finding routes back
to checkpoint 2 as a review subject with reason `revisit_due`. **The prior decision is never
reverted silently**: `accept` stands, with its recorded rationale, until the reviewer re-decides
— a new `edit` on a new `ReviewerDecision`. An expiry that flips a field nobody touched would be
the silent overwrite DEC-023 exists to prevent, performed by a calendar.

Why:

**Re-check semantics have to fit the execution model or they are theatre.** ThreatAtlas's expiry
works because ThreatAtlas is a running service; Trace is a process that exits (DEC-017 — pausing
is stopping). A review-by date in an episodic system can only mean "surface this when someone is
next here," and saying so plainly is better than implying monitoring that does not exist.

**The two outlets age differently.** An accepted risk was a *decision* with an owner who can
name their own confidence horizon — a date is theirs to author. An assumption is a *gap* nobody
chose; it has no owner to pick a date, and every revision is the right time to challenge it.

Alternatives Considered:

- A scheduler or daemon watching review-by dates
- `review_by` on `ContextClaim`, symmetrical with accepted risk
- Auto-expiring acceptance: `risk_treatment` reverts to `undecided` when the date passes
- A single assessment-level review date instead of per-object semantics

Tradeoffs:

- An expired acceptance can sleep indefinitely if nobody starts a run — the honest cost of an
  episodic tool, stated rather than hidden. The status display is the mitigation, and it is only
  a display.
- Re-presenting every assumed claim at every revision scales checkpoint-1 load with assumption
  count; for a system whose assumptions grow, the reviewer pays for this decision each revision.
  The routing reason at least makes the pile legible.
- Two different revisit mechanisms (standing status versus authored date) is more to explain
  than one; the difference is by cause, like DEC-023's three mechanisms.

Open Questions:

- Should `archive` — the one human-performed lifecycle verb — warn when overdue review-by dates
  exist, or is archiving precisely the moment such warnings stop mattering?

## DEC-062: Checkpoint subjects carry typed routing reasons, derived at package-build time from persisted state

Date: 2026-08-10

Status: Accepted

Decision:

**Every review-package subject may carry routing reasons from a closed `ReasonCode` vocabulary,
at both checkpoints.** A subject may carry several; the initial vocabulary is `low_confidence`,
`contradicted`, `no_evidence`, `injection_flag`, and `revisit_due`. Extending it is a design
change, and each code's exact derivation — which persisted fields produce it — is fixed in the
implementing change under one rule: **a code is a deterministic function of persisted state**,
never a judgment made at build time. `injection_flag` derives from a recorded observation about a
cited source (#274 implements the surfacing); `revisit_due` is DEC-061's.

**Reasons are derived when the review package is built, never stored.** The package is derived
from the run and never stored in it (DEC-005, DEC-017); reasons are part of the package. Nothing
on validation output, the run, or the subject records a reason code.

**Two guards are part of the decision, not the implementation.** First, reasons triage attention
and never filter: every subject still requires a `ReviewerDecision` before the checkpoint
advances (DEC-005), and a subject with no reasons is routine, not exempt. Second, a reason is a
routing aid, not a verdict: the Context Validation node's report-and-route remit
(`agent-design.md` section 8) is unchanged, and no node gains authority from a code.

Why:

**Derivation from persisted facts gets auditability without a second store.** The question the
issue poses — derived and cheap, or recorded and auditable — is a false choice here, because the
inputs to every code are already persisted domain data (a confidence field, a contradicted flag,
an observation, a date against a run timestamp). A deterministic function of stored state is
re-derivable at any time, which *is* the audit; storing its output would be a second copy of
authoritative data, the exact shape section 31's state-design rule and DEC-016's
checkpointer rejection both refuse, and the copy could drift from the fields it summarizes.
OpenCRE's Librarian stores its reason codes because its review queue is its authoritative store;
Trace's package is a view over one.

**The reviewer should triage by machine-stated reason rather than re-deriving it.** The fields
are all present on the objects, but "this claim is here because it is contradicted" currently
has to be reconstructed by reading the object against the vocabulary in the reviewer's head.
ThreatAtlas's defined-semantics confidence pill is the presentation-layer proof that stating the
reason changes review behaviour.

Alternatives Considered:

- Recording reason codes on validation output as data, OpenCRE-Librarian style
- Free-text reasons authored by the validation node
- Separate vocabularies per checkpoint
- A confidence pill in the CLI with no typed codes underneath

Tradeoffs:

- The vocabulary is bounded by what persisted fields can express. A reason like "the reasoning
  seems thin" cannot be a code without a model call, so codes will under-describe why some
  subjects deserve attention — and the absence of a code must not read as a clean bill, which is
  why the never-filters guard is part of the decision.
- Derivation logic lives in package assembly and grows with the vocabulary; each new code adds a
  function that must stay deterministic and tested.
- Deriving at build time means a reason reflects state at package construction; a reviewer
  looking at a stale package sees stale reasons. Packages are rebuilt on resume (DEC-017), which
  bounds the staleness to one pause.

Open Questions:

- Should the checkpoint CLI order subjects by reason, and if so in which precedence?
- Do reason frequencies belong in the evaluation metrics as a reviewer-attention calibration
  signal?

## DEC-063: Threat Validation gains a warn-only coverage baseline from authored applicability data; nothing retries or quotas against it

Date: 2026-08-10

Status: Accepted

Decision:

**Per-element-kind category applicability becomes authored data**, the Threat Dragon and OdTM
convention: spoofing applies to actors and processes and never to flows or stores, tampering to
stores and flows, and so on. The table keys on element kinds — `process`, `data_store`,
`external_actor`, `data_flow`, `trust_boundary` — with a conservative classification from the
open `component_type` vocabulary to a kind. It ships beside `STRIDE_CATEGORIES` as authored
constants and covers only the categories it names; the open vocabulary (DEC-041) is untouched.
A component whose type does not classify is `unclassified` and is *presented* as unclassified —
where absence would read as an answer, say `unknown` explicitly (DEC-036); an unclassifiable
component must never render as "no gaps".

**The table has exactly two uses, both warn-only.**

1. **Plausibility observations from the Threat Validation node.** A threat whose category and
   affected elements the table calls inapplicable — spoofing whose only affected component is a
   data store — is flagged as an observation, never rejected. The node also records an
   observation when a category falls outside `KNOWN_THREAT_CATEGORIES`, which answers DEC-041's
   open question: drift becomes visible without being refused. An observation is not an error:
   it never enters the retry taxonomy and never routes anywhere.
2. **A coverage listing in the checkpoint 2 review package**: per component, the applicable
   categories in which zero threats name it. It is derived at package-build time from persisted
   threats, the approved context, and the table — DEC-062's posture; nothing stores it.

**The listing informs the reviewer and is structurally nothing else.** Zero threats in an
applicable category is a legitimate outcome. A coverage gap is not an error class, so the
orchestrator cannot retry the threat agent against it — retrying it would be retrying a
conclusion (`agent-design.md` section 26), and an agent retried until a category is populated
will populate it, which is the checklist failure sections 2.2 and 10 exist to prevent. It is
also not an evaluation metric target: the volume principle holds, and no score improves by
filling a cell.

Why:

**It converts an unverifiable model property into a checkable one at zero model cost.** "Did the
agent cover the obvious structural threats" is today a question the reviewer answers by
re-deriving STRIDE-per-element in their head across the whole context. The table is small,
public, stable knowledge — both surveyed encodings agree on it — and checking against it is
arithmetic.

**Warn-only is what keeps it compatible with everything already decided.** Enforced
applicability would close the vocabulary DEC-041 opened; a retry loop would manufacture threats;
a metric would optimise for finding count. The one safe consumer of a checklist is the human it
informs.

Alternatives Considered:

- Enforcing applicability: rejecting a spoofing threat against a data store
- Feeding coverage gaps back to the threat agent as retry feedback
- A per-category coverage metric in the evaluation plan
- Leaving coverage entirely to the reviewer's unaided judgment

Tradeoffs:

- The kind classification is a judgment compressed into a lookup, and the open `component_type`
  vocabulary guarantees unclassifiable components; the listing under-covers exactly the exotic
  components where threats are least obvious, and says so via `unclassified` rather than hiding
  it.
- The baseline is STRIDE-shaped. No per-element applicability data exists for the AI-specific
  categories, so the listing is silent about the categories ForgeFlow's most important threats
  use; a reader who treats it as total coverage inverts its meaning. The package labels it as a
  structural baseline, not a coverage claim.
- The reviewer now sees a per-component grid at checkpoint 2, which is more to read; the
  alternative was deriving the same grid mentally or not at all.

Open Questions:

- Does the plausibility observation ever earn a routing reason code (DEC-062) of its own, or
  would that promote a heuristic to an authority?

## DEC-064: Rationale-bearing dismissals feed the critic as marked context; matching is deterministic and scoped to the assessment

Date: 2026-08-10

Status: Accepted

Decision:

**The Critical Review input package gains a precedent block**: prior findings from the same
assessment that a reviewer dismissed — disposition `reject`, `convert_to_question`, or
`convert_to_documentation_gap` — **with the reviewer's recorded rationale**, matched to the
lineage under review deterministically: the precedent shares a `requirement_id` with the
lineage's mappings, or names an affected component whose name matches one of the lineage's,
under DEC-056's normalization (identifier resolved to name, case-insensitive, whitespace
normalized). No model call and no embedding computes similarity; a hidden model call here is the
seventh agent the cap refuses.

**Only rationale-bearing decisions qualify.** The question the block puts to the critic is "this
was dismissed for reason X — does X apply here?", and a bare rejection supplies no X.
`ReviewerDecision.rationale` is optional by schema; a dismissal without one is simply not
precedent.

**Precedent is context, never subject.** DEC-049 fixes the critic's unit of work as one threat's
lineage, and this decision does not reopen it: precedent appears in a distinct, labelled package
block, the critic may cite a precedent's rationale in a critique's explanation, and a critique
may still target only the lineage's own subjects. The block is capped; when the cap excludes
precedent, the package names what was excluded rather than truncating silently, the same rule
the evidence fence follows.

**Scope is the assessment.** Prior runs and revisions of the same assessment are readable
through the scoped repository; other assessments are not — the `AssessmentHandle` boundary
exists so one assessment's code cannot reach another's, and a cross-assessment precedent ledger
would carve through it. That carve-out is deferred, not decided: appsec-agent's global ledger is
the shape it would take, and the cross-run finding-identity decision (#236) is where the
identity half lands.

**Dismissal patterns are not distilled.** appsec-agent's second mechanism — summarising
dismissals into reusable guidance — is a model call whose output becomes standing instruction,
unreviewed authority in exactly the place agent output must stay challengeable. Raw precedent
with a human's own words is the version of this that carries no invented generalisation.

Why:

**The data is already persisted and already trustworthy.** Every `ReviewerDecision` carries
disposition and rationale (DEC-023); the rationale is the one text in the pipeline written by
the human whose judgment the critic is meant to anticipate. Feeding it back is reading the
record, not building a new mechanism.

**The critic is the right consumer.** It already judges whether a finding survives challenge;
"the reviewer dismissed the sibling of this for reason X" is exactly a challenge. Consolidation
is mechanical and the checkpoint is the human's own view; neither benefits.

Alternatives Considered:

- Embedding or model-assisted similarity matching
- Distilling dismissal patterns into reusable prompt guidance, appsec-agent style
- A cross-assessment precedent ledger through a deliberate scoping carve-out
- Feeding precedent to Finding Consolidation instead of the critic

Tradeoffs:

- Within-assessment scope makes the block empty until an assessment has revision history, so
  the mechanism is dormant in every first run; its value arrives with longitudinal use.
- Deterministic matching misses paraphrased precedent — a dismissal whose finding cited a
  different requirement for the same underlying concern will not surface.
- Precedent bias is real: a wrongly-dismissed finding now argues for dismissing its successor.
  The mitigations are structural — the critic tests whether the rationale applies rather than
  inheriting the verdict, and the reviewer at checkpoint 2 sees any critique that leaned on
  precedent.

Open Questions:

- What is the right cap for the precedent block — and should recency or match tightness order
  it?

## DEC-065: A credible concern no requirement covers becomes a catalog-gap candidate, routed to the catalog owner and never into the assessment's conclusions

Date: 2026-08-10

Status: Accepted

Decision:

**`domain/proposals/` gains `CatalogGapCandidateProposal`, and the Threat Analysis and Mapping
agents may return it.** The RaD-TM discipline, transplanted: never stretch the nearest
requirement to cover a concern it does not cover, and never drop the observation — flag it as
catalog-maintenance input. The proposal carries the concern, the evidence local keys that ground
it, a suggested category, and — the quality gate — **the nearest requirements considered and why
each does not fit**. DEC-024's whole-catalog posture is what makes "no requirement covers this"
a claim the agent can actually make; the named-nearest-requirements field is what makes it
falsifiable. Proposal rules apply unchanged: local keys, nothing authoritative, `extra="forbid"`.

**A validated candidate persists with the assessment and is not a conclusion.** It is converted
and allocated like any proposal (DEC-018), with provenance to the run that produced it. No
report section renders it — the sixteen-section ownership table is unchanged, which is the
structural guarantee that a candidate cannot become a finding-shaped object. It is not a
checkpoint subject and requires no `ReviewerDecision`; it appears in the checkpoint 2 package as
an informational block, because under DEC-004 the reviewer and the catalog owner are the same
person.

**The candidate feeds the next catalog version through a human.** DEC-057's lifecycle is the
receiving end: a candidate is raw material for a 0.2 authoring decision, carrying no authority.
Aggregating candidates across assessments stays manual — the scoped-repository boundary is not
carved for this either (the DEC-064 posture).

**This is not a seventh agent.** No new model call exists; two existing agents gain an optional
output type. The cap inventory is unchanged.

Why:

**Both failure modes it replaces are silent.** An agent that stretches `req-AUTH-001` over an
uncovered concern produces a mapping whose wrongness only a careful reviewer catches; an agent
that drops the concern produces nothing at all. The typed channel makes the third path cheaper
than either: flagging is easier than stretching, and the catalog grows from ground the analysis
actually met — which is how a 23-requirement catalog scoped to one scenario gets honest
extension pressure rather than invented breadth.

**The DEC-009 pressure point is answered structurally, not by instruction.** A candidate is
about the *catalog's* coverage, not the system's controls. Its schema carries no severity, no
validation status, and no finding-shaped field, and no report section can render it; the shape
that must not happen is unrepresentable rather than discouraged.

Alternatives Considered:

- The status quo: nearest-requirement stretching or silent drops
- Filing uncovered concerns as low-confidence findings
- A repo-side maintenance queue the agent writes directly (agents have no filesystem)
- A standalone catalog-maintenance review agent

Tradeoffs:

- Candidates are model prose reaching a human with less validation pressure than findings get;
  the volume principle applies and nothing rewards count, but junk candidates cost the catalog
  owner reading time. The nearest-requirements justification is the filter, and an empty one is
  a validation failure.
- An informational block at checkpoint 2 is easy to skim past; a candidate nobody reads is a
  dropped observation with more steps. The block is small and the alternative was a decision
  burden on objects that need none.
- Per-assessment persistence means the catalog owner assembles the cross-assessment picture by
  hand until a deliberate aggregation surface exists.

Open Questions:

- Does the candidate deserve its own identifier prefix, and which — the prefix registry is
  DEC-018's to extend?
- Should `trace assessment show` grow a flag that lists candidates, ahead of any aggregation
  surface?

## DEC-066: `Finding` gains a structural content fingerprint for cross-run identity, alongside the allocated identifier and never instead of it

Date: 2026-08-10

Status: Accepted

Decision:

**`Finding` gains `content_fingerprint`**: SHA-256 through DEC-019's single utility, rendered
`sha256:<hex>`, computed by the application when the finding is created and recomputed whenever
an identity input changes. The DEC-019 table gains the row, because a hash over an unstated
input is not verifiable. The stated input: the sorted `requirement_ids`, plus the sorted
affected-component *names* resolved from `affected_component_ids` and normalized under DEC-056's
rule — case-insensitive, whitespace-normalized. Nothing else: no title, no description, no
evidence text.

**The tuple is structural because the fingerprint exists to survive rewording.** appsec-agent
hashes cwe + file + normalized snippet, which is right for a code scanner — the snippet is the
location. Trace's findings are prose over architecture; the excerpt an extraction cites flickers
across runs and document edits, and DEC-056 already established that requirement and component
are the fields that survive rewording. The fingerprint is DEC-056's benchmark matching rule
promoted to an object property, so evaluation matching and longitudinal identity cannot drift
apart. Requirement identifiers are stable across catalog versions (DEC-057) and component names
are the cross-run handle because DEC-018 identifiers are run-scoped.

**Reviewer edits change identity only when they change identity fields.** An edit to
description, severity, or treatment leaves the fingerprint alone; an edit that changes the
affected components or cited requirements recomputes it, because it is then a claim about
different ground. The fingerprint is derived, so recomputation is a rebuild, not a mutation
with history.

**`DocumentationGap` gets the same treatment**: a fingerprint over the requirement it bears on
— reached through its related mapping, DEC-056's own path — plus the normalized component names
of that mapping. The implementing change fixes the exact resolution; the principle fixed here is
structural fields only, no prose.

Why:

**DEC-018 identifiers cannot answer "same finding, still open."** They are per-assessment and
allocation-ordered, so a re-assessment after revision re-mints everything and the longitudinal
question has no handle. Every consumer that wants one — the run-diff in the harness decision
(#255), precedent maturation beyond DEC-064's within-assessment scope, a future "resolved since
last assessment" view — needs the same identity, and computing it ad hoc in each place is how
three subtly different identities happen.

Alternatives Considered:

- Including a normalized evidence excerpt in the tuple, appsec-agent style
- Title-similarity identity, DEC-043-style normalization
- No stored fingerprint: compute structural matches ad hoc where needed
- Letting the reviewer assign a stable cross-run key by hand

Tradeoffs:

- The identity is deliberately coarse: two genuinely distinct weaknesses citing the same
  requirements against the same components share a fingerprint. DEC-056 accepted the same
  coarseness for scoring, and the consumers here want "the same ground re-examined," which
  coarse identity serves; anything finer re-imports prose.
- A component rename between runs silently breaks identity — DEC-056's recorded tradeoff, now
  inherited by every longitudinal consumer. The fate-map convention (DEC-057) covers
  requirement renames; nothing yet covers component renames.
- A recomputed-on-edit fingerprint means longitudinal tooling must treat identity as
  time-varying, not immutable.

Open Questions:

- Should `EvaluationResult`'s run-diff persist fingerprint pairs (prior, current) so identity
  changes are themselves observable?

## DEC-067: `ExecutionRecord` accounts cache tokens as their own spans, and `estimated_cost` weights them at the profile's rates

Date: 2026-08-10

Status: Accepted

Decision:

**`ExecutionRecord` gains `cache_read_tokens` and `cache_creation_tokens`**, optional integers,
provider-neutral names at the seam; `WorkflowRun` gains the matching rollups
`total_cache_read_tokens` and `total_cache_creation_tokens`. The adapter maps its provider's
usage report into them and omits them where the capability is unused or unreported — absent
means "not reported," and the capability record DEC-014 already keeps on `ExecutionRecord` says
which.

**The three input spans are disjoint.** `input_tokens` means uncached input actually processed
at the full rate; cache reads and cache writes are their own counts, never folded in. Folding
them in is exactly how "cost and tokens described different spans of work."

**`estimated_cost` is the weighted sum**, with the weights owned by the model profile: cache
reads at the provider's discounted rate, cache creation at its premium, uncached input and
output at list. The cost ceiling and the `WorkflowRun` totals compare against this
billed-equivalent number, not against raw token counts.

**The table rows land with the implementing change**, per the conformance test's
both-directions rule; the fields and their semantics are fixed here.

Why:

**The design leans on caching on purpose, so the divergence lands exactly where the system
works hardest.** DEC-024 passes the whole catalog on every mapping call *because* it is a
stable cacheable prefix; a cost ceiling that prices those tokens at the full input rate
overstates spend most on the runs the design optimizes, and a ceiling comparing against the
wrong number either trips early or licenses overruns. appsec-agent retrofitted the same fields
in v3.7.0 for the same reason; the retrofit is cheaper before the numbers exist.

**Profile-owned weights keep the seam provider-agnostic.** Rates are a property of the
provider-model bundle, which is what a `model_profile` already names (DEC-014). The adapter
reports counts; the profile prices them; nothing behind the seam does arithmetic the
application owns.

Alternatives Considered:

- Folding cache reads into `input_tokens` at a discount factor
- A single `cached: boolean` per call instead of counts
- Pricing inside the adapter, next to the provider that knows its rates
- Leaving the divergence until live runs make it measurable

Tradeoffs:

- Two more optional fields whose absence is meaningful ("not reported") — readable only
  alongside the capability record, which is one join more than obvious.
- Profile-owned rates go stale when a provider reprices; `estimated_cost` is named *estimated*
  for exactly this, and the profile is one file to update.
- Rollups on `WorkflowRun` widen an already-wide totals row; the alternative of computing them
  by summing records on read was rejected once already for the other totals.

Open Questions:

- Should `scripts/estimate_cost.py` grow the same weighting so pre-run estimates and recorded
  spend stay comparable?

## DEC-068: Context-model extensions — one pass: sensitivity vocabulary, at-rest placement, personas, entry points, and an access-model claim; no trust-zone object

Date: 2026-08-10

Status: Accepted

Decision:

One pass over the five surveyed extensions, three adopted as fields, one adopted as a check, one
rejected. Every adopted field lands with its implementing change, document and registry first,
conformance test holding both directions.

**No named trust-zone object, and no per-component zone field beyond what exists.** The context
model already says where a component runs (`deployment_zone`, open vocabulary) and which
boundaries separate what (`TrustBoundary` inside/outside sets, `DataFlow.crosses_trust_boundary_ids`).
A first-class zone object would be a third representation of the same fact, and two
representations of containment already have to agree; adding a reconciliation problem to gain a
name is TM-BOM's shape, not Trace's need. What the survey actually wants from zones — boundary
crossings as the highest-signal threat locations — is adopted as a **Context Validation
cross-claim check**: a flow between components whose `deployment_zone` values differ and that
crosses no declared boundary yields a warn-only observation. Report-and-route holds; nothing is
corrected.

**`Asset` gains a sensitivity vocabulary and an at-rest split.** `data_classification` stays
free text but normalizes against a new `KNOWN_DATA_CLASSIFICATIONS` vocabulary (`pii`, `phi`,
`financial`, `credentials`, `intellectual_property`, `telemetry`, `public`, and peers) — the
DEC-036 treatment, explicitly against TM-BOM's closed enum, for DEC-036's reasons. `Asset` also
gains optional `stored_in_component_ids`: `component_ids` keeps meaning "holds or processes,"
and the subset that *stores at rest* is where encryption-at-rest and retention requirements
attach; without the split, every at-rest mapping over-applies to processors.

**`Actor` gains persona fields**: optional `skill_level` and `access_level`, open vocabularies
normalized through `domain/vocabulary.py`, with `KNOWN_*` starting sets (`opportunist`,
`skilled`, `organized_group`; `anonymous`, `authenticated`, `privileged`, `physical`). Their
purpose is auditability: a threat's free-text preliminary likelihood becomes checkable against
who it presumes — a threat presuming an organized attacker with physical access should read
differently from one an opportunist can execute.

**`Component` gains `entry_point_types`**: an optional list, open vocabulary (`login`,
`admin_interface`, `file_upload`, `webhook`, `api`, `inter_system_interface`, and peers),
normalized. With it comes the **privilege-extremes check**: when the approved context
represents no anonymous-or-external actor, or no administrative-or-privileged one, Context
Validation emits a Question — the attack surface's extremes are where analysis most often goes
silent, and a Question is the DEC-009 outlet for exactly that silence.

**`SystemContext` gains `access_model`**: a **closed** enum — `deny_by_default`,
`allow_by_default`, `mixed`, `unknown` — required, defaulting to `unknown`. Closed because the
values are named rather than illustrated, like `DataFlow.direction`; `unknown` because an
authorization posture nobody stated must never be readable as an answer (the never-`False`,
never-`None` rule applied to the single highest-leverage authorization fact).

Why:

**One pass, because five drive-by field additions would each re-litigate the same principles.**
Every choice above is an existing principle applied: open-vocabulary-with-normalization where
the document illustrates (DEC-036), closed where it names, `unknown` where silence would read
as an answer, warn-only observation where a check could otherwise become a corrector, and a
Question where absence needs a human. The survey's value is naming the ground; the corpus
already owned the rules.

Alternatives Considered:

- A first-class TrustZone object with per-component zone assignment, TM-BOM style
- TM-BOM's closed sensitivity enum
- A first-class EntryPoint object with counts, per the Attack Surface cheat sheet
- Making `access_model` an open vocabulary like its neighbours
- Deferring all five until the threat agent demonstrably misses what they would carry

Tradeoffs:

- The zone-crossing check keys on `deployment_zone` string equality after normalization; two
  spellings of one zone that normalization does not unify yield a false observation. Warn-only
  makes that annoying rather than wrong.
- `stored_in_component_ids` as a subset of `component_ids` is an invariant validation must
  hold, and a modeling question ("does a cache store?") the extraction agent will answer
  inconsistently; the reviewer sees both lists at checkpoint 1.
- Persona fields on `Actor` invite exactly the pseudo-precision DEC-030 refused for severity;
  they are inputs a human audits a likelihood narrative against, never factors anything
  computes with, and no scoring formula may consume them.
- The privilege-extremes Question fires on legitimate single-privilege systems (a batch
  pipeline with no anonymous surface); a Question is answerable and closes, which is the cost
  of a check that cannot be silenced.

Open Questions:

- Does the zone-crossing observation deserve promotion to a DEC-062 routing reason once it has
  run against real extractions?
- `data-model.md` question 5 (structured applicability) may eventually want
  `KNOWN_DATA_CLASSIFICATIONS` as one of its axes; nothing here commits that.

## DEC-069: A model profile may carry a per-agent overlay; resolution fails at load, and attribution rides the existing snapshot

Date: 2026-08-10

Status: Accepted

Decision:

**A `ModelProfile` may map agent names to model-and-settings overrides.** The overlay is
optional; a profile without one behaves exactly as today. Keys are the six agent names the cap
pins (`tests/unit/test_agent_cap.py`'s inventory); an overlay naming anything else — a
misspelling, a deterministic node, a seventh agent — is a configuration error refused when the
profile resolves, at load, not mid-run. Deterministic nodes make no model calls and can carry
no override.

**Nothing else moves.** The seam is untouched: resolution happens in
`infrastructure/model/profiles.py` before a call reaches an adapter, and the adapter still sees
one resolved bundle. The agent cap is untouched: six agents with different models are six
agents. `ExecutionRecord.model_name` already snapshots the resolved model per call, so
attribution and evaluation interpretability survive without a schema change. `Creativity`
stays per-agent provider-neutral intent, orthogonal to the overlay: the profile says which
model and limits; the intent maps to that model's controls inside the adapter.

**The default profiles stay uniform.** No shipped profile routes agents to different models
until the evaluation harness can measure what a cheaper model costs in quality — the ablation
machinery (#256's baseline protocol is the nearest instrument) is where an overlay earns its
values. The mechanism lands decided so that the measurement, when it runs, is a config edit
rather than a design change.

Why:

**The cost case is real and the shape is small.** lets-threat-model routes triage to a cheap
model and analysis to a strong one, and the win in their demos is genuine. Trace's version is a
closed six-key map resolved in one module — deciding it now costs a page; retrofitting it after
`model_profile` strings leak into recorded runs and evaluation baselines would cost a
migration.

**Fail-at-load is the part worth writing down.** An overlay error surfacing mid-run — after
checkpoint 1, three agents in — wastes a run and a reviewer's time; profiles are configuration,
and configuration errors belong at the moment configuration is read (the loader's own posture,
applied to profiles).

Alternatives Considered:

- Per-agent `model_profile` on `AssessmentConfiguration` instead of an overlay inside the profile
- Free-form overlay keys, validated only against "is a known agent" at call time
- Extending the overlay to deterministic nodes for symmetry
- Shipping a cost-optimized default profile now, ahead of measurement

Tradeoffs:

- A run's `WorkflowRun.model_profile` no longer implies one model for every call; anything that
  assumed so must read `ExecutionRecord.model_name`, which was always the honest source.
- Six keys is a small closed surface, but it is coupled to the agent inventory; renaming an
  agent now touches profiles, and the load-time check is what turns that from silent to loud.
- Deferring shipped overlays means the mechanism carries no default benefit; it is
  infrastructure for a measurement not yet run, and infrastructure ahead of measurement is the
  pattern DEC-030 warns about — mitigated by the mechanism being configuration rather than a
  component.

Open Questions:

- When the measurement runs, is the right comparison per-agent model ablation against the
  uniform baseline, or a small set of curated mixed profiles?

## DEC-070: Machine-readable artifacts may be parsed deterministically into documented claims; parser output enters the same proposal path, and compose manifests come first

Date: 2026-08-10

Status: Accepted

Decision:

**The capability is adopted, post-MVP.** A deterministic parser may derive context claims from a
machine-readable artifact — a container-compose manifest, an OpenAPI description, an IaC plan —
each claim carrying a verifiable excerpt hash into the artifact, exactly as document-cited
evidence does. A claim derived mechanically is *documented* evidence: the artifact states the
port, the volume, the dependency, and the excerpt proves it. This shrinks the DocumentationGap
surface at zero model cost, which is DEC-009 served directly.

**Parser output enters the pipeline as proposals, not as authority.** Parsed objects go through
the same conversion, the same Context Validation, and the same checkpoint 1 as agent-extracted
ones; determinism earns no bypass, because a parser can be wrong about meaning while right about
syntax (a compose port exposed to a host network is not thereby internet-accessible). The
Context Extraction agent receives parser-derived claims as existing context so it extends rather
than re-derives — the division of labor: parsers own what the artifact states, the agent owns
what the documents mean.

**Provenance rides the existing vocabulary.** Parser-derived objects carry
`source_origin: structured_input`, whose meaning section 4.4 widens to "parsed
deterministically from a machine-readable source"; `generated_by` names the parser. No new
`SourceOrigin` value — the distinction that matters, mechanical versus model-extracted, is
exactly the one `structured_input` already draws against `uploaded_document`.

**The untrusted-source rules apply unchanged.** A compose file is attacker-authorable text; its
excerpts live inside the fence like every other excerpt, and nothing a parser reads becomes an
instruction. Parsers are the one place this is easy to forget, because their input looks like
configuration rather than prose.

**Priority order: compose manifests, then OpenAPI, then IaC.** Compose is OdTM's proven ground
and yields the topology objects (components, flows, ports) with the least ambiguity. OpenAPI
yields entry points — feeding `entry_point_types` (DEC-068) — and authentication declarations.
IaC is the largest surface with the hardest semantics and waits. Cross-claim consistency checks
(a flow naming HTTP implies its endpoints speak HTTP) accrue to Context Validation as warn-only
observations, the DEC-063 posture.

Why:

**The pipeline's scarcest resource is verifiable ground, and machine-readable artifacts are
made of it.** Every claim a parser derives arrives with evidence that re-verifies forever, at
no model cost, in exactly the format the evidence resolver already checks. The alternative is
a model reading the same artifact and paraphrasing what a parser could quote.

Alternatives Considered:

- Parser output bypassing checkpoint 1 on the grounds that it is deterministic
- A new `SourceOrigin` value for parser-derived objects
- Letting the extraction agent alone read machine-readable artifacts, unassisted
- OpenAPI first, on the strength of the DEC-068 entry-point synergy

Tradeoffs:

- Two producers of context objects means duplicate-shaped claims when the agent re-derives
  what a parser stated; feeding parser claims into the agent's package mitigates, and the
  validation node's duplicate detection is the backstop.
- A parser is a maintenance surface tracking a moving format; dormant-project history (OdTM
  itself) shows these rot quietly. Each parser needs its own fixture corpus.
- `structured_input` now covers both authored structured input and parsed artifacts; anyone
  needing the finer distinction reads `generated_by`, which is one hop less obvious.

Open Questions:

- Does the roadmap give parsers their own stage, or do they ride the first post-MVP scenario
  that supplies machine-readable input?

## DEC-071: Every source document lands in exactly one coverage bucket, rendered in the report's methodology section

Date: 2026-08-10

Status: Accepted

Decision:

**The report renders a per-source coverage ledger, and section 14 (Methodology) owns it.** No
new section; the ledger is deterministic content in an existing rendered section, so the
sixteen-section contract (DEC-035) is untouched. Every source document supplied to the
assessment appears in exactly one bucket, each entry with its stored justification:

- `reviewed` — ingested, and its evidence was available to every stage
- `reviewed_with_exclusions` — reviewed, but the evidence budget excluded named excerpts; the
  ledger names them, the fence rule's naming obligation carried through to the reader
- `could_not_process` — supplied but not ingestable (format, corruption), with the error class
- `excluded_by_rule` — deliberately out of scope, with the rule stated

**The ledger is derived at render time from persisted state.** Ingestion already records what
could not process; package assembly already names budget exclusions; scope rules are
configuration. The implementing change fixes the carriers; the decision fixes that every
disposition must be persisted somewhere derivable, because a ledger with a memory hole is worse
than none.

**The limitations section may interpret the ledger and never restates it.** Section 16 is agent
prose; the ledger is rendered fact. The Report Generation agent receives the ledger as input so
its limitations prose can bound blind spots honestly, and DEC-035's no-rewriting rule keeps the
authoritative table the rendered one.

Why:

**A reader cannot weigh conclusions without knowing what was never read.** lets-threat-model's
ledger is the survey's most honest mechanism because it converts the invisible failure — a
document silently dropped — into a visible row. Trace already does the hard half (naming budget
exclusions at package-assembly time, DEC-025's fence rule); this decision is where that
information stops dying inside the run and reaches the person the report is for.

**Methodology is the right owner.** The ledger answers "what did the analysis actually
consume," which is a methodology fact. The evidence appendix describes what *was* cited;
limitations interprets; neither states coverage.

Alternatives Considered:

- A seventeenth section owning coverage, amending DEC-035
- Rendering the ledger in section 15 (Evidence appendix)
- Limitations-only: the agent describes coverage in prose from run data
- Per-excerpt rather than per-document granularity throughout

Tradeoffs:

- Exactly-one-bucket forces a call on partially processed documents; `reviewed_with_exclusions`
  absorbs the budget case, but a document half-parsed by a failing converter still needs one
  honest bucket, and `could_not_process` with a partial-evidence note is the least-bad answer.
- The ledger's completeness depends on every exclusion path persisting its reason; a new
  exclusion path added without a recorded justification silently produces an unlisted document.
  The renderer should refuse to render a ledger that does not account for every
  `SourceDocument` — a loud failure over a quiet omission.
- More rendered content in section 14 lengthens every report, including clean ones.

Open Questions:

- Should the JSON manifest beside the report carry the ledger too, for machine consumers ahead
  of the export formats (DEC-072)?

## DEC-072: Interop exports are a post-MVP serializer family, not report formats — TM-BOM first, SARIF second, Mermaid third, CycloneDX deferred

Date: 2026-08-10

Status: Accepted

Decision:

**Exports are deterministic serializers over approved objects, and they are not reports.**
DEC-035's "Markdown is the only MVP output format" governs the *report*; an export is a
different artifact family — no prose, no model call, approved objects only, written to the
assessment's `outputs/` beside the same version-pin manifest discipline. The distinction is
recorded so the report contract and the export family never blur.

**The family and its order:**

1. **TM-BOM** — the OWASP Threat Model Library schema, a near-superset of Trace's approved
   context with first-class assumptions, and Threat Dragon's declared future primary format.
   Approved context, threats, and findings serialize; Trace-specific fields ride the schema's
   namespaced extensions block. This is the ecosystem door: diagramming and GRC tooling reads
   it with no Trace UI built.
2. **SARIF 2.1.0** — approved findings as code-scanning alerts. Two hard rules from the trap
   lets-threat-model demonstrated: only *approved* findings serialize, and the only severity
   ever written is the reviewer-assigned one — a model-derived rating rendered by GitHub as
   authority is the exact failure DEC-030 exists to prevent, exported.
3. **Mermaid DFD** — rendered deterministically from approved `Component` and `DataFlow`
   objects, never model-drawn. A standalone artifact in `outputs/`; it does **not** embed in
   the MVP report, so the sixteen-section contract and `templates/report-v1.md` stay untouched.
4. **CycloneDX for the catalog** — same family, no demonstrated consumer; deferred
   indefinitely rather than ordered.

**All post-MVP**, sequenced after assembly (M6); nothing here enters a current milestone.

Why:

**Ordering by who consumes, not by ease.** TM-BOM has a named consumer ecosystem and carries
the most of Trace's structure; SARIF has the single highest-adoption surface (a repository's
security tab) and the sharpest misuse trap, which is why its rules are fixed at decision time;
the DFD is a rendering convenience. Deciding the order now prevents the easiest one (Mermaid)
from shipping first because it is easiest.

Alternatives Considered:

- Treating exports as report formats and amending DEC-035's format list
- SARIF first, for the adoption surface
- Embedding the Mermaid DFD in the report's architecture section
- Committing to all four with milestones now

Tradeoffs:

- TM-BOM is itself pre-1.0; serializing to a moving schema means tracking it, and the
  extensions block is the hedge — Trace-specific content survives schema drift there.
- SARIF's consumers will display findings next to static-analysis results with numeric
  confidence; Trace's reviewer-severity-only rule will read as missing data in that UI, which
  is correct and will still generate questions.
- A deferred CycloneDX row is a standing invitation to implement it anyway; the deferral names
  the missing prerequisite (a demonstrated consumer) so the invitation has a test.

Open Questions:

- Does the TM-BOM serializer round-trip — can Trace *read* a TM-BOM file as structured input
  (DEC-070's family) — or is export one-way?

Amendment (2026-08-17, #503): **Mermaid is built**, third in the order as decided, closing the
family's build-out (CycloneDX stays deferred until a consumer exists). The constraints held as
written: deterministic from approved `Component` and `DataFlow` (plus approved actors as
external entities and trust boundaries as subgraphs over their inside components), never
model-drawn, a standalone content-addressed `.mmd` in `outputs/`, and not embedded in the
report. Labels are escaped so an approved name cannot become diagram syntax, and an `unknown`
flow direction renders undirected — a directed arrow would draw a claim nobody made. This also
discharges future-features 13.2 (Architecture Visualization): the visualization reflects
reviewer-approved state because it is derived from nothing else.

Amendment (2026-08-17, #487): **SARIF is built**, second in the order as decided, and its
mapping decisions are recorded here rather than in a fresh entry because the decision — the
family, its order, its post-approval rule — was already made. An approved `Finding` is a result
whose `level` follows the reviewer-assigned severity (critical/high → `error`, medium →
`warning`, low/informational → `note`; `unassigned` cannot appear, the approval gate refuses
it). A `DocumentationGap` is a result of `kind: "review"` at `level: "none"` — SARIF's own
vocabulary for "a human should evaluate this" — never an error or a warning, which keeps
DEC-009 structural in the export. Cited requirements become rules titled from the assessment's
pinned catalog version, degrading to bare identifiers rather than dropping or guessing;
locations come from the evidence chain (stored filename, line span) plus logical locations for
affected components; `EvidenceReference` and DEC-066 fingerprints ride `partialFingerprints`.
Approved text serializes verbatim, the export refuses an unapproved context, and the artifact
is content-addressed into `outputs/` like TM-BOM's.

## DEC-073: The harness is a caller of the ordinary pipeline — registry-driven, offline through replay, one authoritative results home, per-item run diffs

Date: 2026-08-10

Status: Accepted

Decision:

**The evaluation harness executes a registered scenario by driving the ordinary pipeline.** It
reads `benchmarks/scenarios.yaml` and never discovers scenarios by scanning (DEC-027's
registry). It is a caller of `AssessmentService` — not a second orchestrator, not a parallel
code path: the same nodes run, the same transition table routes, the same stores persist. A
harness that re-implements the pipeline evaluates the re-implementation.

**A harness run is offline by construction.** Model calls come from the replay adapter serving
recorded responses; reviewer decisions come from a recorded decision file replayed at both
checkpoints — the node executes, the gate holds, a `ReviewerDecision` is written, and no switch
exists because replay is not an ablation (DEC-012). CI can therefore run the harness with no
provider key, which the CI constraint already requires.

**Ablations are applied harness-side, as run construction.** The harness builds the ablated
`WorkflowRun`, marks it non-authoritative, and names the ablation (DEC-012, DEC-031); no
assessment configuration is touched, and an ablated run's assessment can never reach `approved`.

**Results have one authoritative home and one derived feed.** `EvaluationResult` objects
persist with the assessment through the ordinary stores — they are domain objects (DEC-056
promoted them) and get no exemption. The harness additionally exports a metrics-only feed,
keyed by scenario, condition, and commit, into a repo-side results tree for the scorecard
(DEC-076) and CI; the feed is derived, regenerable from the stores, and never authoritative —
the DEC-062 posture applied to evaluation output.

**The run diff is per-item, not two aggregate scores.** Comparing a run against a named prior
run classifies each expected item as matched, missed, spurious, or changed, using the DEC-056
structural matcher and DEC-066 fingerprints. Two runs can hold the same F1 while disagreeing on
half their items; the per-item diff is what makes a regression a list rather than a delta.

Why:

**Everything downstream of measurement inherits the harness's honesty.** Baselines (DEC-074),
adversarial conditions (DEC-075), the scorecard (DEC-076), and stability (DEC-077) are all
harness runs; a harness that bypassed a checkpoint, skipped a node, or kept private state would
quietly change what every one of them measures. Making it a caller of the real pipeline is the
one design that cannot drift from what it evaluates.

Alternatives Considered:

- A standalone runner that invokes nodes directly, skipping the orchestrator
- Results written only to a repo-side tree, keyed by scenario and commit
- Results written only to the assessment stores, with the scorecard reading SQLite
- Aggregate-score comparison between runs, with diffs computed ad hoc when needed

Tradeoffs:

- Driving the real pipeline means harness runs pay full pipeline overhead per scenario; at
  five scenarios and a handful of conditions this is minutes, and the alternative is measuring
  something else.
- Two result homes can disagree; the feed being regenerable-by-command is the repair, and any
  disagreement is a bug in the export, never in the stores.
- Replayed reviewer decisions freeze the human at recording time; a pipeline change that
  produces genuinely better candidates still gets the old reviewer's answers until decisions
  are re-recorded. The reviewer-facing metrics say when re-recording is due.

Open Questions:

- Does the results tree live under `benchmarks/results/` in-repo, or stay untracked until the
  scorecard needs CI history?

Amendment (2026-08-17, #505): **Any scenario may pin its offline replay, and the harness
verifies it.** `recorded/report-hash-offline.txt` pins the harness's own replay of a scenario;
a completed run compares the rendered bytes and `HarnessOutcome.report_hash_verified` carries
the verdict — `None` when no pin exists (absence of a pin is not a pass), `False` on drift,
which the CLI answers as exit 3, the same answer `trace verify` gives a drifted report
(DEC-088). The pin is deliberately distinct from `report-hash.txt`, the capture-conditions pin
`scripts/replay_forgeflow.py` checks: the two replay paths stamp different model profiles into
the report, so one pin cannot serve both; each file names its replay path. ForgeFlow and
rag-support-bot ship offline pins. And **the evaluation pages are CLI-reachable**:
`trace evaluate --report scorecard|comparison|ablation [--out PATH]` runs the same sweep and
renders the same pages the build scripts write, to stdout or a named file — the committed pages
under `docs/eval/` remain the scripts' deliberate step, with the DEC-081 history snapshotting
and the CI currency check staying theirs alone.

## DEC-074: Baselines run through the same seam, emit the same schemas, and see the same inputs — with ties resolved against Trace; the external comparable stays in the portfolio

Date: 2026-08-10

Status: Accepted

Decision:

**The baseline set is roadmap Stage 5's, unchanged**: a single generic prompt, a structured
single-pass prompt, and the ablation family (Trace minus evidence validation, minus critical
review, minus context approval — DEC-012 machinery). Nothing is added or dropped.

**The two prompt baselines are harness runs through the seam.** Their prompts live in
`prompts/`, versioned and hashed like agent prompts (DEC-019); their calls go through
`StructuredModel`, are recorded, and replay. A baseline that cannot be re-run is the
unverifiable vendor self-comparison the ecosystem is rightly criticized for, and the protocol's
whole point is that anyone can re-execute the comparison from the repository.

**Baseline output is schema-forced, never hand-normalized.** Both baselines emit the same
target schemas Trace's agents emit, through the same structured-output contract, and are scored
by the same structural matcher (DEC-056). There is no free-text normalization step to tune in
either direction; a baseline that fails to produce valid schema output has that recorded in its
schema-validity rate, which is itself a reported result, not an excuse.

**Fairness limits, with ties resolved against Trace.** Baselines receive the same source
documents — never the curated, approved context — and they *do* receive the requirements
catalog, because the matcher scores on requirement citations and a baseline that cannot cite
requirements would lose on plumbing rather than analysis. Where an input choice favors a side,
it goes to the baseline. One asymmetry is structural and stated rather than papered over:
Trace's scored output passed human checkpoints and the baselines' did not; the
checkpoint-ablated run is the like-for-like comparator, and the full-pipeline comparison
measures the system as actually operated.

**STRIDE GPT is scored in the portfolio write-up, not in-repo.** It cannot run through the seam,
and a wrapper would measure the wrapper. The portfolio comparison uses its published behaviour
on the public scenario inputs, dated, with its version pinned — the scenario inputs are
synthetic and public (design-principles section 19), so nothing leaks by feeding them to an
external tool.

Why:

**The comparison is the project's central claim, so its protocol carries the burden of proof.**
Roadmap Stage 4's decision gate asks whether the multi-stage workflow beats the simpler
baseline; an unfair or unrepeatable protocol converts the answer into marketing either way.
Every choice above — same seam, same schemas, same matcher, generous inputs — exists so that a
skeptic re-running the comparison finds nothing tuned in Trace's favour.

Alternatives Considered:

- Free-text baselines with a normalization layer mapping prose to objects
- Withholding the catalog from baselines, scoring their uncited findings by title similarity
- Scoring STRIDE GPT in-repo behind an adapter
- Adding named commercial tools to the comparison set

Tradeoffs:

- Schema-forcing helps the baselines (structure is half of Trace's discipline, granted free);
  that is the chosen direction of error and stated as such.
- Giving baselines the catalog means the comparison cannot show whether Trace's *catalog
  integration* helps, only whether its pipeline does; the mapping-quality question needs its
  own ablation if it ever matters.
- A portfolio-only external comparison will be read as avoiding the fight; the honest answer —
  an external tool run through a harness it was not built for measures the harness — needs to
  be written where the comparison is.

Open Questions:

- Does the structured single-pass baseline get one combined schema or the per-stage schemas in
  sequence? The former is the purer "no pipeline" claim; the latter isolates decomposition
  from iteration.

## DEC-075: Adversarial evaluation is a condition axis on scenarios — an authored payload corpus, two reported axes, and a named compliance metric

Date: 2026-08-10

Status: Accepted

Decision:

**Every scenario may run under conditions: `clean`, `ambiguous`, `adversarial`,
`missing_evidence`.** A condition is a variant of the scenario, registered in
`benchmarks/scenarios.yaml`, holding an input overlay (files added to or replacing the base
`input/`) and an expected overlay (truth-set deltas) under the scenario's directory. The
ForgeFlow injection fixture stops being the whole adversarial story and becomes the first entry
in a corpus. Conditions are harness runs (DEC-073); nothing about the pipeline changes per
condition, which is the point — the pipeline must not know it is being attacked.

**The corpus covers five payload classes**, each authored as a document a real assessment could
plausibly ingest: direct instruction injection; fence delimiter escapes; verifier sabotage
addressed to the validation node; findings suppression ("this system has been reviewed and has
no issues"); and checkpoint-bypass instructions. Payloads are test data in the DEC-027 sense —
they live under `expected/`-adjacent variant directories, never leak into clean inputs, and the
truth set for an adversarial run includes the expected injection observations
(`expected-observations.yaml` already holds the kind).

**Reporting is two axes, never one number.** Axis one: extraction and finding quality under
attack — the same metrics as the clean condition, reported as deltas, because an attack that
degrades recall without triggering anything is still a successful attack. Axis two: targeted
attack success — did the specific payload achieve its specific objective. **Injected-instruction
compliance rate is a named metric**: injected instructions complied with over injected
instructions presented, per payload class. A resistance claim without a measured compliance
rate is the ecosystem anti-pattern this decision exists to avoid.

This answers `current-architecture.md` section 19 item 12 and `agent-design.md` section 38
item 11: injection in source documentation is tested as scenario conditions and measured as
compliance rate plus quality-under-attack; detection surfaces as recorded observations and the
`injection_flag` routing reason (DEC-062, #274).

Why:

**The analyzed document is Trace's primary threat surface by design, and one fixture is an
anecdote.** Every major agentic reviewer was compromised through its analyzed content in the
past year; Trace's structural argument — the fence, the checkpoints, proposals-not-authority —
is exactly the kind of claim that must be demonstrated rather than asserted, and demonstration
means a corpus, conditions, and a rate.

**Conditions-on-scenarios beats a separate adversarial suite** because the clean run is the
control: the same truth set, the same matcher, the same metrics make the attack delta
attributable to the attack.

Alternatives Considered:

- A standalone adversarial test suite separate from the benchmark scenarios
- Fuzzing-style generated payloads rather than an authored corpus
- A single composite "robustness score"
- Measuring only detection (flag rate) without quality-under-attack

Tradeoffs:

- An authored corpus measures resistance to the attacks its authors thought of; the compliance
  rate is meaningful per class and meaningless as a universal claim, and the scorecard must
  label it per class.
- Variant overlays multiply harness runs per scenario; recorded-response replay keeps CI cost
  flat, but recording each condition's live run is real one-time cost.
- The checkpoint-bypass payload can only demonstrate that bypass is unrepresentable — a
  structural argument scored as trivially zero — which is worth showing exactly once and
  uninformative as a recurring number.

Open Questions:

- Does `ambiguous` (contradiction-bearing) get its own payload taxonomy the way `adversarial`
  does, or stay a single authored variant per scenario?

## DEC-076: The scorecard is static, deterministic, metrics-only, and never contains assessment content

Date: 2026-08-10

Status: Accepted

Decision:

**A static HTML scorecard is generated deterministically from the harness's results feed
(DEC-073) — no model call, no prose generation.** It shows, per scenario and condition:
precision, recall, and F1 per truth-set field class; schema-validity rate; injected-instruction
compliance rate per payload class (DEC-075); run-to-run variance (DEC-077); and cost, including
the cache-aware spend (DEC-067). It is regenerated by CI from recorded runs only — the CI
key constraint holds — and lives as a committed artifact published via GitHub Pages from the
repository, so the page's history is the git history.

**The scorecard never contains assessment content.** No finding text, no claim text, no
evidence excerpt, no document fragment — metrics and identifiers only. This is the DEC-035
boundary stated for a new artifact: the scorecard is not the report and cannot drift toward
being one. It is also a security property, not just a taxonomy: adversarial-condition results
summarize runs whose inputs are attack payloads, and a scorecard that quoted content would
republish the corpus to a public page.

**The boundary with DEC-032's read-only demonstration interface is recorded**: the scorecard
shows measurements of the system; the demo interface shows an assessment's content locally.
Neither absorbs the other.

Why:

**Public, re-runnable, per-pipeline evaluation is rarer than it should be, and rare is
visible.** The survey found closed self-reported comparisons to be the commercial norm; a
scorecard whose every number regenerates from recorded runs in CI is the most credible artifact
the evaluation work can produce, and credibility is the project's currency.

**Deterministic generation is what makes publication safe.** A model-written summary of results
would need its own review cycle; a rendered table from persisted metrics is auditably boring.

Alternatives Considered:

- GitHub Pages generated from CI artifacts without committing the rendered page
- A scorecard with model-written narrative summaries per scenario
- Extending the Markdown report to include evaluation results
- A live dashboard (future-features 9.1's fuller shape) instead of a static page

Tradeoffs:

- A committed rendered artifact churns the diff on every regeneration; the feed being the real
  input keeps the churn reviewable as numbers.
- Metrics-only means the scorecard cannot show *why* a number moved; the per-item diffs
  (DEC-073) hold that answer and stay local, one link the reader cannot follow from the page.
- Publishing variance and compliance rates publicly commits the project to numbers that may be
  unflattering; that is the differentiator working as intended, and the alternative reads as
  hiding.

Open Questions:

- Does the scorecard page get versioned per release (DEC-057's registry pattern) or show only
  the current commit's numbers with history left to git?

## DEC-077: Stability is measured — n live runs, replay-matched decisions, per-item agreement retained — and gates nothing

Date: 2026-08-10

Status: Accepted

Decision:

**The protocol: n live runs per scenario, n = 5 as the working default, identical input, same
recorded reviewer decisions.** Live runs are manual and never CI — CI stays on recorded
responses — and the operator sees the cost estimate before starting (the DEC-067-weighted
number). The runs are ordinary runs under DEC-031, not a new kind.

**Recorded decisions apply across runs by structural match.** A recorded decision names its
subject; in a fresh live run the subjects are re-generated, so replay matches them by content
fingerprint (DEC-066) and the DEC-056 rules. A subject with no matching recorded decision gets
the run's named default policy — approve-as-generated, recorded as such — because pausing five
runs for a human would re-introduce the reviewer variance the protocol holds constant. A run
containing defaulted decisions says so in its results.

**Variance and agreement are reported per metric and per object class, and the per-item
agreement sets are retained.** Which expected items appear in all n runs, which flicker, and
which appeared in none — persisted with the `EvaluationResult`, because "F1 σ = 0.04" cannot be
diagnosed and "THR-007 matched in 2 of 5 runs" can. The scorecard (DEC-076) shows the variance;
the retained sets stay local.

**Stability gates nothing.** It is a reported measurement, not a threshold: no release gate, no
harness failure, no retry-until-stable. A stability gate creates pressure to reduce *measured*
variance, and the cheapest reductions — prompts that hedge toward the truth set, matchers
loosened until runs agree — reduce the measurement, not the instability.

Why:

**Run-to-run instability is a documented, named weakness of LLM threat-modeling tools, and
almost nobody reports variance at all.** Reporting it — whatever the number — is a
differentiator precisely because it is honest; the moment it gates something, the incentive
inverts and the number stops being honest. Evaluation-plan section 18 listed consistency as
future research; this makes it protocol.

Alternatives Considered:

- Stability as a release gate with a variance threshold
- Deriving stability from recorded-replay runs (free, and measures nothing — replay is
  deterministic by construction)
- Fresh human review per run instead of replay-matched decisions
- Reporting aggregate variance only, without per-item agreement sets

Tradeoffs:

- Five live runs per scenario is the single most expensive measurement in the plan; it is
  manual, bounded by the operator, and priced up front — and it will therefore be run rarely,
  so the numbers will age between measurements.
- Fingerprint-matched replay under-matches when a run words the same finding onto different
  components; a defaulted decision then substitutes for the human's recorded one, and the
  defaulted count is part of the result so the substitution is visible.
- n = 5 bounds what agreement can mean (an item in 4 of 5 runs is one flicker from
  unanimous); the protocol reports counts, not confidence intervals, and pretends otherwise
  nowhere.

Open Questions:

- Should the flickering-item set feed the prompt-evaluation loop (section 12) as its highest-
  value regression fixtures?

## DEC-078: The Stage 5 read-only view is stdlib `http.server`, localhost-only, GET-only, and read-only — re-introducing the browser boundary bounded, not defended

Date: 2026-08-11

Status: Accepted

Decision:

**The demonstration view (`trace view`) is a local HTTP server built on Python's stdlib
`http.server`, and no web framework is adopted.** This answers `current-architecture.md` section
19 question 1 — "which local web-interface framework should be used?" — with *none*, consistent
with DEC-016's no-orchestration-framework stance and the same supply-chain reasoning DEC-032
applied to the CLI. `fastapi`, `flask`, `django`, `starlette`, and `uvicorn` stay undeclared, and
`tests/unit/test_interface_decision.py` fails if one appears.

**The view is read-only by construction, and read-only is enforced as a discipline the tests
audit, not a file mode.** SQLite offers no read-only handle here, so the guarantee is that the
`trace_ai.interface` package calls no store write method — `save`, `allocate`, `transaction`,
`delete` — asserted by scanning the package source. The view consumes the section 32 lineage walk
and the persisted objects; it drives no phase and holds no checkpoint interaction. Reviewer
decisions stay on the command line (DEC-032): the browser reads, the CLI writes.

**Shipping it re-introduces the browser-to-application boundary that DEC-032 had removed, and the
threat model records it as present rather than absent.** `threat-model.md` section 5 is rewritten
from "this boundary does not exist" to a mitigation table: the server binds `127.0.0.1` only
(DEC-004); every method other than `GET` is refused with `405`, so the request-forgery threat has
no state-changing endpoint to forge against; every source-derived value is HTML-escaped on render,
because a browser is not the inert terminal and an untrusted excerpt must not inject markup; and
responses carry `X-Frame-Options: DENY`. The review trigger in section 9 fired exactly as written,
and this is its resolution.

Why:

**A rendering surface over persisted objects needs neither routing, templating, nor an ASGI
server, and each of those would be a dependency on a project whose subject is architectural risk.**
The seven views are static HTML the store already has the data for; `http.server` plus a pure
render module is the whole stack, and the render module is testable without binding a port. The
differentiating view — the lineage walk from a finding back to its hashed evidence — is the reason
the view exists at all, and it is pure computation over the object model, not a UI framework's
concern.

**Making the request-forgery mitigation structural rather than a token means it cannot be edited
away.** A read-only surface has nothing to forge; that is a property of what the view *is*, not a
check bolted onto a mutable endpoint. It is the same move DEC-005 makes for checkpoints — the unsafe
state is unrepresentable rather than guarded against.

Alternatives Considered:

- A local web framework (FastAPI/Flask): more machinery than a read-only view needs, and a
  dependency and supply-chain surface DEC-016 and DEC-032 both argue against.
- A static-site export instead of a server: loses the lineage view's live navigation over a real
  store, and would need a separate render path from the one the CLI already exercises.
- Leaving the boundary "absent" in the threat model and treating the view as out of scope: the view
  ships, the port listens, and a threat model that denied it would be false.
- A read-only SQLite handle to enforce read-only at the storage layer: not available through the
  store's open path here, so the discipline is enforced by the package-scan audit instead.

Tradeoffs:

- `http.server` is single-threaded and unhardened; it is acceptable only because DEC-004 bounds it
  to one local reviewer on `127.0.0.1`, and it must never be exposed off the machine.
- Read-only is enforced by a source scan rather than the type system or a file mode, so a write
  method reached through an alias the scan does not spell would slip past — the mitigation is that
  the package is small and the scan is part of the suite.
- The store opens read-write, so a bug elsewhere in a shared process could write; the view itself
  does not, and the audit pins that.

Open Questions:

- If the view ever needs to trigger a re-render of the scorecard or a verify pass, does that cross
  into "driving the pipeline", and does it therefore belong on the CLI rather than a POST route?

## DEC-079: Revisit re-prompts by scoping a checkpoint's completion to the current run; a revisit subject with only prior-run decisions re-enters, its prior decision standing until re-decided

Date: 2026-08-11

Status: Accepted

Decision:

DEC-061 decided that an expired accepted risk "re-routes to checkpoint 2 at the next run" and that
the prior `accept` decision "is never reverted silently." It did not say how a subject that already
carries a `ReviewerDecision` re-enters a checkpoint whose completion condition (DEC-005) is a
decision per subject — an already-decided subject would be skipped. This decides the mechanism.

**A checkpoint's completion is scoped to the current run.** A subject is satisfied when it carries a
`ReviewerDecision` whose `workflow_run_id` is the run now executing, or a decision with no
`workflow_run_id` at all — the run-less form recorded replays and file-applied decisions write, kept
current so those paths are unaffected. A decision made in a *different* run no longer satisfies the
checkpoint. This changes nothing for an ordinary subject: a candidate object is generated fresh each
run and decided within it, and a paused run resumes under the same run identifier, so its
before-pause decisions still count. It changes exactly one thing: a subject carried over from a
prior run, whose only decisions belong to that prior run, is not treated as decided.

**A revisit subject is added to the checkpoint's subject list, and re-prompts by that scoping.** At
the finding phase, an approved `Finding` whose `treatment_review_by` (DEC-060) falls on or before the
run's date joins `candidate_finding_ids`. It is already approved, so its only decision is the prior
run's `accept`; the current-run scoping means it re-enters checkpoint 2 rather than passing as
decided. The same holds at checkpoint 1 for a context subject carried across a revision.

**The prior decision is never reverted.** The finding stays `approved` with its recorded `accept`
and rationale; re-deciding writes a new `ReviewerDecision` in the current run (a new edit or
approval, DEC-023). Nothing a calendar touches flips a field a person set — the expiry only
re-presents.

**Every revisit subject carries the `revisit_due` reason (DEC-062).** The reason is derived at
package-build time: a finding whose `treatment_review_by` has passed, and an assumed `ContextClaim`
carried across a revision (one already bearing a `ReviewerDecision` and still `assumed`). The reason
triages attention and never filters; the completion scoping is what makes the subject re-enter.

Why:

**The alternative — a global "any decision ever" rule with a separate re-open marker — needs new
state on every pause and a second place the completion condition is evaluated.** Run scoping is one
rule in one place, and it reads naturally: a checkpoint is about *this* run's decisions, and a
decision from a run that has since been revised is history, not a standing answer. Keeping run-less
decisions current means the recorded-replay path, which never sets a run identifier, is untouched.

**Expiry is evaluated when the finding phase builds its subjects, not by a clock.** DEC-061 already
settled that nothing watches time in an episodic local tool (DEC-004, DEC-017); this places the one
evaluation at the point the run assembles what the reviewer will see, against the run's own date.

Alternatives Considered:

- A global "any decision ever" completion rule plus a `revisit_object_ids` marker on the pause state
- Reverting `risk_treatment` to `undecided` when the date passes (rejected by DEC-061 already)
- A scheduler evaluating review-by dates between runs (rejected by DEC-061 already)
- Scoping completion by decision timestamp rather than run identifier

Tradeoffs:

- Run scoping means a decision genuinely made in a prior run never counts toward a later run's
  checkpoint. For ordinary subjects this is invisible (they are regenerated per run); the one place
  it bites is intentional — the revisit.
- A revisit subject that no reviewer ever re-decides keeps the checkpoint open, which is the point:
  an expired acceptance surfaces and stays surfaced until a person acts, the honest episodic cost
  DEC-061 named.
- Run-less decisions counting as current means a file-applied decision cannot itself be revisited by
  run; no path needs that today, and the recorded-replay compatibility is worth more.

## DEC-080: The precedent block holds at most ten dismissals, ordered by match tightness then decision recency, and the cap names what it excluded

Date: 2026-08-12

Status: Accepted

Decision:

DEC-064 decided that rationale-bearing dismissals feed the critic as a capped, marked block, and
left open what the cap is and whether recency or match tightness orders the block. This decides
both, for the implementing change.

**The cap is ten precedents per review group.** The block exists to put "this was dismissed for
reason X — does X apply here?" in front of the critic, and ten rationales is already more standing
challenge than any one lineage can absorb; past that the block stops being precedent and starts
being a second corpus. The number is a constant in `services/critique/precedent.py`, not
configuration — DEC-012's reasoning: a knob nobody has evidence to turn is a knob that will be
turned without evidence.

**Match tightness orders first, recency second.** A precedent sharing a `requirement_id` with the
lineage's mappings is a tighter match than one matching only on an affected component's name — the
requirement is the claim's ground, the component is its neighbourhood — so requirement-sharing
precedents precede name-only ones. Within each class, the most recent dismissal decision comes
first, because the latest expression of the reviewer's judgment is the one the critic should meet
first when the cap bites. Ordering is deterministic: decision timestamp, then decision identifier.

**The cap names what it excluded.** When more than ten precedents match, the block carries the
excluded findings' identifiers — the same rule the evidence fence follows under DEC-064: silent
truncation reads as "this is everything" when it is not.

Why:

**The open question had to close for the block to be buildable**, and both halves close on
grounds already in the corpus: the cap follows DEC-012's no-ungoverned-knobs posture, the naming
of exclusions follows DEC-064's own budget rule, and tightness-first follows from what the block
is for — the critic tests whether a rationale applies, and a rationale about the same requirement
applies more often than one about the same component.

Alternatives Considered:

- A character budget instead of a count (the evidence fence's mechanism)
- Pure recency ordering
- A configurable cap on `AssessmentConfiguration`

Tradeoffs:

- Any fixed count is arguable; ten is a judgment, not a measurement, and the Stage 4 critic gate
  is where evidence about it would surface.
- Tightness-first means a very recent name-only dismissal can be displaced by an old
  requirement-sharing one. That is intended — but it does mean recency is not a reliable reading
  of the block's order across match classes.
- A count cap ignores rationale length, so ten long rationales cost more context than ten short
  ones. The package's character metadata still reports the real size.

## DEC-081: Scorecard history is committed, append-only, written deliberately, and keyed by git ref, prompt digest, and catalog version

Date: 2026-08-12

Status: Accepted

Decision:

**Scorecard builds can be retained as snapshots in `docs/eval/history.jsonl`, a committed
append-only JSON-lines file, and the scorecard page renders the retained history alongside the
current table.** A snapshot holds one build's rows and three identifiers naming what produced
them: the short git ref the sweep ran on, a digest over the prompt tree, and the
requirements-catalog version. Evaluation-plan sections 16 and 17 ask for metrics viewable across
versions; this is the mechanism.

**A snapshot is written deliberately — `build_scorecard.py --snapshot YYYY-MM-DD` — never as a
side effect of a build.** A plain build reads the history and never writes it. The DEC-076 drift
check depends on this: a page that stamped the current git ref on every regeneration would
change on every commit, and the check would either fail permanently or stop meaning anything.
The operator states the snapshot date rather than the script reading the clock, for the same
reason the page's generation date is pinned.

**Appending a snapshot whose version key equals the last one's is refused.** Equal git ref,
prompt digest, and catalog version mean the same build re-run, and retaining both would leave
two records nothing distinguishes. Any two retained snapshots therefore differ in what produced
them, which is the property that makes the history a history.

**The prompt identifier is a digest over the prompt tree's files, path-keyed, not a DEC-019
composed hash.** DEC-019 hashes each composed prompt, and composition needs per-agent
substitutions a version key should not depend on. Hashing every file under `prompts/` — shared
blocks included — moves the digest on any edit that could move any composed hash, which is the
property the key needs.

**The DEC-076 content boundary applies to the history file unchanged**: metrics and identifiers
only, no finding text, no claim text, no document fragment. The file is committed to a public
repository; a snapshot that quoted content would republish it. The page's history section pools
precision, recall, F1, and cost over each snapshot's authoritative rows — baselines and
ablations are retained in the rows but stay out of the pooled line, because the history tracks
the pipeline.

Why:

**The scorecard is regenerated in place, so the git history of the page answers "what changed"
only one diff at a time.** Sections 16 and 17 want the longitudinal question answered directly:
how a metric moved across prompt revisions, catalog versions, and code changes. A retained
record keyed by those versions answers it without archaeology.

**Append-only and committed beats a database or a CI artifact.** The history is small, one-line-per-snapshot
diffs review cleanly, the CI key constraint is untouched, and the same skeptic who can
re-run the scorecard can read every retained number in the repository.

Alternatives Considered:

- Stamping every build with its git ref and letting the page churn (breaks the drift check)
- Deriving history from the git log of `scorecard.html` (archaeology, and unkeyed by prompt or
  catalog version)
- A separate history page rather than a section on the scorecard
- Retaining pooled numbers only, without per-row detail

Tradeoffs:

- The snapshot's git ref names the commit the sweep ran on; the commit that adds the snapshot is
  that ref's child, so the ref is one commit behind the history file's own history. Provenance,
  not a checkout target.
- A deliberate step can be forgotten. Nothing prompts for a snapshot; a release checklist is the
  natural place for it, and section 17's release record is the natural trigger.

## DEC-082: Approval is a person's sign-off on the rendered deliverable; phase fourteen stays a terminal marker

Date: 2026-08-12

Status: Accepted

Decision:

**The `draft` to `approved` transition is performed by a person, through `trace assessment
approve`, and DEC-031's table is amended: the writer of that edge is the person, not the
terminal node.** Phase fourteen (`assessment_completion`) declares no node and stays what it
is today — the orchestrator's terminal marker. A completed run leaves its assessment in
`draft`, which is what the driver test has asserted since the phase landed.

**The verb is a sign-off, not a status setter, and the service enforces the difference.**
`AssessmentService.approve()` refuses unless three facts hold: the assessment carries a
rendered report (`final_report_path`); the run that rendered it — named by the report's
filename, not whichever run is latest — completed; and that run is authoritative
(DEC-012's rule, kept from the original verb). Each refusal names what is missing.
`run_is_authoritative` is no longer caller-supplied: the run exists now, and a boolean the
caller asserts is a bypass one keyword away.

Why:

**DEC-031's table and the implementation disagreed, and the implementation had the better
argument.** The table assigned `draft → approved` to "the terminal node"; the code left phase
fourteen empty and `tests/unit/test_driver.py` asserted that a completed run leaves `draft`,
annotated "approval is a person's verb, not a run's". The contradiction sat unresolved
because nothing drove the final verb at all — `approve()` had no caller in `src/` and its
docstring still claimed `WorkflowRun` did not exist.

**The terminal node cannot make the judgment approval records.** Checkpoint 2 approves
findings before the report exists; report generation and rendering follow it. `approved`
means "the conclusions are the reviewer's" (DEC-031) — and the conclusions a customer reads
are the rendered document, which nobody has confirmed reading at the moment the run
completes. An automatic terminal approval would mark the deliverable usable on the strength
of a review that predates it.

**Offering the verb on the surface is not the bypass DEC-031 rejected.** DEC-031 refused a
user-settable `approved` as "a checkpoint bypass with extra steps" — correctly, for a bare
setter. The guarded verb cannot bypass anything: no report exists without passing both
checkpoints (DEC-005 makes them structural), so the earliest moment the verb succeeds is
after every gate DEC-031 protects has held.

Alternatives Considered:

- A phase-fourteen node writing `approved` on completion, per DEC-031's table as written
- Keeping `run_is_authoritative` caller-supplied and adding only the CLI verb
- A separate `sign_off` verb beside `approve`, leaving DEC-031's table untouched

Tradeoffs:

- An operator can now forget the sign-off, leaving a finished assessment in `draft`
  indefinitely — visible in `trace assessment status`, and preferable to an approval nobody
  performed.
- Binding the sign-off to the run named by the report means a later failed run does not
  block approving the earlier finished one; whether that is generosity or correctness
  depends on why the later run failed, and the reviewer holding the report is the right
  judge of that.

## DEC-083: A proposed claim's value is a scalar or a list of scalars; `JsonValue` stays on the domain side

Date: 2026-08-13

Status: Accepted

Decision:

**`ProposedContextClaim.value` is typed `str | int | float | bool | None`, or a list of those,
and no longer `JsonValue`.** The domain object is unchanged: `ContextClaim.value` remains
`JsonValue`, and every value a proposal can carry converts into it losslessly.

**Mappings are excluded from the proposal shape deliberately, not provisionally.** A claim that
wants to assert a mapping asserts one claim per key instead — the subject-predicate-value shape
already carries that decomposition.

Why:

- The proposal schema crosses the wire and the domain schema does not. The provider's
  structured-output format refuses the unconstrained `{}` that `JsonValue`'s recursion collapses
  to in a JSON Schema export, so a proposal carrying it cannot be requested at all — the first
  live context-extraction call fails before a request is sent (#412). Nothing offline noticed,
  because the deterministic model never serializes a schema for the wire.
- A mapping arm would be worse than absent. The provider's schema strictifier rewrites an open
  mapping into an object that accepts only `{}`, while the prompt substitutes the application's
  own untransformed export — so the prompt would teach a shape the wire grammar forbids, which
  is an instruction to fail.
- Every claim value in every committed recording and truth set is a plain string. The union is
  headroom, not a migration.

Tradeoffs:

- The proposal and domain types now differ where they used to coincide, and the difference has
  to be explained wherever a reader would expect symmetry. Both modules carry the explanation.
- A future agent with a genuine need for structured values needs a schema change and a DEC
  entry rather than finding the latitude already present. That is the correct friction: the
  wire shape is part of what the prompt teaches, and it should not widen silently.
- Section 39's open question 1 — whether claims should keep the subject-predicate-value shape
  at all — stays open. This entry narrows a field's wire type; it does not answer that.

## DEC-084: The retries ceiling is enforced in the node's attempt loop with the budget's value; the execution record carries the retries consumed

Date: 2026-08-13

Status: Accepted

Decision:

**`AssessmentConfiguration.maximum_retries_per_node` reaches the attempt loop through the
budget.** `Budget.retry_policy()` derives the `RetryPolicy` from the configured value, and an
agent node given a budget and no explicit policy runs under it (`resolve_retry_policy`). An
explicitly supplied policy still wins, because a test that says "no retries" means it.

**The budget does not *check* retries, and `LimitKind` carries no retries member.**
`Budget.check_retry` and `LimitKind.RETRIES` are removed: a retry decision is made between a
classified failure and the next attempt, inside the node, where the orchestrator never stands —
and a run stopped by exhausted retries is classified by the failing attempt's error class with
the attempt count (section 26), not by the ceiling that stopped the retrying.

**One `ExecutionRecord` per node execution, whose `retry_number` is the retries consumed.** The
attempt loop sets it as it runs, so a clean first attempt records zero and a recovery after one
failure records one, on the success and failure paths alike. Per-attempt detail stays in the
record's `attempt_N` metadata and the preserved outputs under `traces/`.

Why:

- The previous arrangement enforced the ceiling nowhere (#397): `Budget.check_retry` had no
  callers, every node constructed the default policy, and configuring zero retries still
  produced three attempts. A configuration field that governs nothing is worse than absent,
  because it reads as control.
- `retry_number` was structurally zero (#398): no caller ever passed it, and the evaluation's
  retries metric summed the constant. A metric that reads as measured and is not commits the
  failure this project exists to criticize.
- One record per node execution is the shape the ledger already has, the counters already count,
  and the committed evaluation feeds already assume. A record per attempt would have moved
  model-call accounting and the drift-checked pages for no reader's benefit — the per-attempt
  story is already told by the metadata and the preserved outputs.

Tradeoffs:

- `agent-design.md` section 27 reads "the orchestrator should enforce ... maximum retries", and
  the enforcement point is now the node's loop rather than the orchestrator's. The value still
  lives in the one budget the orchestrator owns; what moved is the check, to the only place a
  retry decision exists. This entry records that reading rather than leaving it implicit.
- A closed `LimitKind` lost a member. Nothing ever raised or persisted it, so no stored run can
  reference it, but any external reader that enumerated the vocabulary sees four kinds now.

## DEC-085: Section 29's "low to moderate" rows resolve to moderate for critical review and low for report generation; the enum member goes

Date: 2026-08-13

Status: Accepted

Decision:

**The critical review agent runs at `moderate` creativity and the report generation agent at
`low`.** `agent-design.md` section 29's table is corrected to say so, replacing its two "low to
moderate" rows. **`Creativity.LOW_TO_MODERATE` is removed from the seam**, together with the
adapter's `xhigh` effort tier it mapped to; the mapping is now `low` to effort `high` and
`moderate` to effort `max`.

Why:

- The split reading has been the implemented behavior since the two nodes landed, reasoned only
  in module docstrings and pinned by tests — a silent divergence from the corpus, which this
  project's own discipline says needs a decision entry, not improvisation (#402). The reasoning
  those docstrings carried is sound and is adopted here: the critic is a search — imagining how
  a conclusion fails benefits from the same breadth as proposing threats — while report
  generation is a restatement of approved objects, and a restatement takes the conservative
  reading.
- An enum member no node can reach is a claim the seam makes and nothing keeps. Nothing
  persists the value — no recording, no profile, no feed carries `low_to_moderate` — so removal
  breaks no stored data, and the seam's docstring stops describing an assignment the table no
  longer makes.
- The side effect the audit flagged is corrected with it: `threat_analysis.py` claimed to hold
  "the one non-`low` creativity setting in the MVP", which the critic's `moderate` made false.

Tradeoffs:

- The Anthropic effort ladder loses its middle rung: two intents, two tiers. A future agent
  with a genuinely intermediate need reintroduces a value through a decision entry, which is
  the correct friction — an intent is part of what section 29 promises about an agent's
  behavior, and it should not widen silently.
- The table's history is less visible: a reader of section 29 no longer sees that two rows
  were once broader. The note under the table names this entry, which is where the history
  belongs.

## DEC-086: Validator retry instructions feed the re-extraction prompt; the four downstream validators drop the surface; the analysis error classes stay as vocabulary

Date: 2026-08-13

Status: Accepted

Decision:

**The Context Validation node's retry instructions are consumed by the re-extraction path.**
`re_extraction_feedback` appends the validator's per-correctable-error instructions to the
reviewer's rationale, and the extraction node already carries that feedback into its prompt.
Re-extraction is the one path on which a generating agent runs again, so it is the consumer
`agent-design.md` section 8's "retry instructions" output describes.

**The four downstream validators — threat, mapping, evidence-assessment, and critique — lose
their `retry_instruction`/`retry_instructions` surface.** No path re-runs their agents: a
blocking validation failure stops the run under its own error class, the transition table has
no backward edge, and section 26 forbids retrying a conclusion. The actionable content lives on
the `ValidationError` itself, where the run's stop reporting reads it. Section 8 specifies the
context validator; the other four surfaces were symmetry the corpus never asked for, produced
by nothing-consumed-by-nothing since they landed.

**`ErrorClass.INSUFFICIENT_EVIDENCE` and `ErrorClass.UNRESOLVED_CONTRADICTION` stay, without
producers.** The pipeline expresses both conditions as the Question, gap, or observation they
resolve to (DEC-009, DEC-021), so nothing is left to raise — a property of the routing, not an
oversight. The members remain because the taxonomy is section 26's vocabulary: the non-retryable
rule is stated where retry decisions read it, and a future producer inherits the classification
instead of inventing one. Their docstrings now say so.

Why:

- The audit (#409) found the feedback loop produced twice and consumed never: five aggregate
  methods with no caller, and two error classes no code constructs. A mechanism the docs
  describe as active and nothing exercises is debt in the shape of a feature.
- Wiring beats deleting exactly where a consumer exists with clear semantics. The re-extraction
  prompt previously carried only the reviewer's reason; a reviewer who writes "the extraction
  missed the queue" is not going to restate the validator's finding that a claim cites
  unresolvable evidence, and the next attempt benefits from both.

Tradeoffs:

- The five validators are no longer shaped identically. Symmetry was the reason the dead
  surface existed; the asymmetry is now the accurate statement of which agent can be re-run.
- A future decision to re-run a downstream agent (a DEC-level routing change) reintroduces the
  surface for that validator deliberately, with its consumer, rather than finding it waiting.

## DEC-087: No open mapping crosses the model wire; proposal fields are typed pair lists

Date: 2026-08-14

Status: Accepted

Decision:

**A proposal schema field is never a dict with arbitrary keys.** A per-identifier association —
evidence strengths, quoted passages — is a list of typed pair objects (`WeighedEvidence`,
`QuotedEvidence`), and promotion folds the pairs into the mapping the domain object keeps. The
proposal accepts the pre-DEC-087 mapping form on input so committed recordings stay loadable;
the exported schema — what the prompt teaches and the wire grammar compiles — is the pair list
only.

Why:

- The provider's strict structured-output grammar rewrites an open mapping into an object that
  accepts only `{}`. DEC-083 met this on an optional field and dropped the arm; the live
  ForgeFlow capture (#324) met it on a *required* one: `evidence_strengths` demanded one entry
  per cited reference while the compiled grammar forbade any entry at all, so the evidence
  validation agent burned five attempts on a structurally impossible instruction. Offline
  nothing noticed, because the deterministic model never serializes a schema for the wire.
- The pair list is also the better teaching shape: each entry names its `evidence_id` and its
  `strength` as declared fields the grammar enforces, instead of a key convention prose has to
  explain.

Tradeoffs:

- Proposal and domain shapes diverge again where they used to coincide, in the same direction
  and for the same reason as DEC-083; both modules say so.
- The legacy-form acceptance is one more input path. It is a loader's tolerance, not a schema
  the model is offered, and it retires whenever the recordings are next recaptured.

## DEC-101: Report section 7 carries the threats the approved findings rest on; duplicate questions collapse at render

Date: 2026-08-14

Status: Accepted

(Originally misfiled under a duplicate DEC-083 heading on 2026-08-14; renumbered 2026-08-17,
#502. The number changed; the decision did not.)

Decision:

**Section 7 of the report renders the threats referenced by the approved findings.** The
previous filter — `Threat.status is APPROVED` — was never satisfiable: threats have no approval
verb anywhere in the pipeline, so the section was structurally empty in every report ever
rendered, and the live capture's fifteen threats were invisible in the deliverable. The set a
reviewer transitively validated by approving the findings is the defensible set to print; a
zero-finding assessment renders the section's authored empty wording, which is the honest shape
for it. DEC-035's section table and ownership are unchanged — this decides the filter's
semantics, which DEC-035 never specified.

**Byte-identical open questions collapse onto one line at render, never at creation.** Two
mappings contradicted on the same requirement each produce "Which statement is authoritative
for req-X?", and section 11 rendered both verbatim. The collapse happens in the deterministic
renderer — the duplicate's identifier rides its survivor's line as "*(also asked as qst-NNN)*"
— because the objects must survive as allocated: the recorded report-generation response
enumerates the run's question identifiers, and dropping a duplicate at creation renumbers the
rest and invalidates the recording's own later call. That failure was observed, not
hypothesized: the first implementation deduped at consolidation and the flagship replay
exhausted its recorded responses retrying a report whose prose cited questions that no longer
existed.

**The consolidation question template interpolates missing-evidence entries as clauses.**
Agents write entries as sentences — leading capital, trailing period — and the template
produced "Can you confirm The webhook validation mechanism.?" in a section the reviewer reads
line by line. The entry is stripped of its trailing period and its leading capital lowered
unless the first word is an acronym.

Why:

**The report is the deliverable, and two of its sections argued against the product.** An
always-empty threats section reads as "the analysis produced no threats" when the run produced
fifteen; duplicated and malformed questions read as generator sloppiness in the section a
reviewer reads most closely. Both defects were visible in the flagship report the demonstration
opens.

**Creation-time deduplication was rejected by the recording itself.** A recorded run is a
historical artifact: later responses reference earlier allocations. Any change that renumbers
identifiers mid-run breaks every recording that spans the change, which is a compatibility rule
worth stating once and remembering — derived-output changes are re-pin cycles; allocation
changes are re-capture events.

Alternatives Considered:

- A threat approval verb or checkpoint subject (a third human surface nobody asked for)
- Rendering all validated threats regardless of findings (prints fifteen threats of which
  eleven produced no approved conclusion, burying the four that did)
- Deduplicating questions at consolidation (breaks recorded replays; observed)
- Leaving both sections as they were and narrating the emptiness

Tradeoffs:

- Section 7 now under-represents the analysis breadth: threats that produced only gaps or
  questions are absent. The section's lead-in names the rule so absence reads as scope, not
  omission.
- The render-time collapse leaves duplicate Question rows in the store; the count metrics see
  them. That is honest — the model did ask twice — and the DEC-081 history will show the
  duplicate rate fall when a future capture dedupes at the source.

## DEC-088: The CLI has four exit codes, and a stated refusal is code 3 rather than code 1

Date: 2026-08-14

Status: Accepted

Decision:

**The command line uses four exit codes, and "refused" is not "crashed".** `0` is success; `1` is
an error the operator can fix, named in one line; `2` is argparse rejecting the arguments (the
standard-library convention); and `3` is a stated refusal that is an answer rather than a fault —
a context that is not approvable, an approval blocked by an open question, evidence or a report
that no longer verifies, a `reset` dry run. Before this the CLI returned `1` for both a genuine
error and every one of those refusals, so a script could not tell the two apart without parsing
the prose the code was supposed to make unnecessary.

Two supporting changes land with it. `--max-cost` and `--max-model-calls` are parsed by argparse
converters that reject a non-number and a negative as exit `2`, rather than an inline `Decimal(...)`
whose `decimal.InvalidOperation` (an `ArithmeticError`, not a `ValueError`) escaped as a traceback.
And a `pydantic.ValidationError` from the pipeline is re-raised with its traceback instead of being
rendered as a one-line error: DEC-006 says a domain object never fails validation, so one that does
is a bug, not operator input — even though `ValidationError` is a `ValueError`, which the CLI still
catches for the domain's own operator-facing value errors (a malformed identifier through
`parse_id`, an out-of-range rubric score).

Why:

- DEC-032 makes the command line the interface a reviewer and an evaluation script both use, and the
  module's own docstring already promised "exit codes are answers ... a script can act on without
  parsing prose." A single non-zero code broke that promise for exactly the case it named: a refused
  approval and a crashed run were the same signal.
- The `--max-cost` traceback and the swallowed `ValidationError` were the same bug in two
  directions: a value the taxonomy did not classify surfacing raw, and a value the taxonomy
  over-classified being hidden. Both are the error contract failing to say what actually happened.

Alternatives Considered:

- Leaving one non-zero code and documenting that callers parse stderr (the thing the exit-code
  contract exists to avoid).
- Removing bare `ValueError` from the caught set entirely (rejected: the domain raises it on an
  operator-supplied identifier, so removal would traceback a mistyped `asm-001`; the narrower
  re-raise of `ValidationError` fixes the actual bug without that cost).

Tradeoffs:

- Code `3` is a new value a caller may not expect; a script that treated "non-zero" as failure now
  sees a refusal as failure, which is the old behaviour, so nothing regresses, but a script that
  wants to act on a refusal must learn the code. The `--help` epilog and the module docstring both
  state the table.
- The CLI still catches bare `ValueError` for the domain's and services' operator-facing value
  errors; a `CommandInputError` subclass names the CLI's own input errors, but the tuple is not
  yet free of the broad class. Narrowing it further is a domain change (typing `parse_id`'s error)
  left for when that surface is next touched.

## DEC-089: The object store carries an insert-order column, and a per-assessment purge is the way to shrink it

Date: 2026-08-14

Status: Accepted

Decision:

**`objects` gains a `seq` column: a monotonic insert order, assigned once and never moved by a
later replacement.** `oldest first` orders by it. Sorting on the `id` text was wrong the moment a
counter crossed 999: DEC-018 widens the identifier (`evd-1000`) rather than wrapping, and `evd-1000`
sorts lexically before `evd-999`, so a moderate corpus came back reordered — and because DEC-018
assigns identifiers in iteration order on a rerun, the reorder silently changed which identifier
attached to which object. The driver's per-object loop sort (`_sorted_by_id`) is keyed on the
identifier's *number* for the same reason. The column is a table-layout change, so `SCHEMA_VERSION`
moves to 2 and a v1 database is refused rather than migrated (DEC-020); the data root is gitignored
and regenerable.

**`trace assessment purge <id>` deletes one assessment entirely — its rows, its identifier counters,
and its directory.** Nothing else shrank the store: every run appends execution records, evaluation
results, prompt snapshots, and a failed-attempt file per retry, and an archived assessment kept them
all; the only remediation was `trace reset`, which removes the whole data root. Purge removes exactly
one assessment, which the store's scoping (`WHERE assessment_id = ?`) makes safe. It is destructive,
so it follows `reset`'s shape: a dry run without `--force` previews and refuses (exit 3, DEC-088).
Rows go first in one transaction, then the directory, so a crash between the two leaves an empty
assessment a re-run of purge finishes rather than rows pointing at deleted files. A retention cap
keeps only the most recent failed-attempt artifacts per assessment.

**The store grows an id-only read path.** `ids()` returns identifiers over the `id` column without
parsing or validating a payload, and `iterate()` yields validated objects one at a time; the many
call sites that need only "which ids exist" (the driver hands the evidence identifiers to an agent
six times a run and never the evidence text) use `ids()`. `EvidenceIndex` memoizes the source
documents and files it reads within one operation, so verifying K references into one document reads
that file once, not K times.

Why:

- The lexical-ordering hazard was documented in a test that then did nothing about it
  (`test_identifiers.py`), and evidence references are one per addressable segment, so a benchmark
  corpus crosses 999 routinely. An ordering that silently reshuffles a rerun is the exact failure
  the deterministic replay depends on not happening.
- A store that only ever grows, with `reset` as the sole eraser, makes a single throwaway run cost
  the whole data root to clean up. A scoped purge is the unit that matches how the data is scoped.

Alternatives Considered:

- Ordering by SQLite's implicit `rowid` (rejected: `rowid` is not stable across `VACUUM`, and an
  explicit column states the intent the ordering depends on).
- A `delete` that removes arbitrary objects (rejected: the domain owns referential integrity, so a
  partial delete could dangle references; purge removes a whole assessment, which cannot).

Tradeoffs:

- The `SCHEMA_VERSION` bump refuses every existing v1 database rather than migrating it. That is
  DEC-020's standing trade, and the data root is regenerable, but a developer with a local store
  from before this change re-runs `trace reset` once.
- `ids()`/`list_where()` only reach the columns DEC-020 lifts out of the payload (`status`); a query
  on any other field still lists and filters in Python, because DEC-020 keeps the payload unqueried.

## DEC-090: v0.1 is clone-only; the unused LangSmith dependency and the implicit store identities go

Date: 2026-08-14

Status: Accepted

Decision:

**v0.1 runs from a source checkout, not an installed wheel.** The prompts, the requirements
catalog, the report template, and the benchmark scenarios are version-controlled files in the
repository, read through `PROJECT_ROOT`-relative paths; they are not package data in the wheel.
`config.IS_SOURCE_CHECKOUT` detects the difference (a `pyproject.toml` beside `PROJECT_ROOT`), and a
command that would read those assets from outside a checkout stops with a clear
`SourceCheckoutRequiredError` rather than a dangling `FileNotFoundError` deep in a render or a
catalog load. `trace` and `trace --help` still work from an install, so the console script is honest
about what an install can do. Making the package installable -- moving the assets under
`src/trace_ai/` and reading them through `importlib.resources` -- is a later decision; this one makes
the current stance explicit instead of a metadata claim the code contradicts.

**The `langsmith` runtime dependency and its four settings are removed.** It was declared in
`pyproject.toml` and imported nowhere, shipping dead weight to every install, and the `langsmith_*`
settings it fed were read only by the banner. `openai_api_key` stays: it ships no dependency and the
seam is provider-agnostic by design (DEC-014), so a second adapter would read it. A package-layout
test now asserts every declared runtime dependency is imported somewhere in `src/`, so a
re-added-and-unwired dependency fails there rather than shipping.

**Two store identities that were implicit are now explicit.** The stored `object_type` was
`type(obj).__name__`, so renaming a domain class silently made every existing row unreadable; it is
now `DomainModel.stored_type`, a class attribute defaulting to the class name that a rename overrides
in one line. The row key for the one id-less object (`SystemContext`) was duck-typed ("no `id`? key
by `(assessment_id, version)`"), so any new id-less object would silently collide with it; it is now
`DomainModel.row_key()`, which `SystemContext` overrides and the base raises for -- a new id-less
object is a loud decision, not a collision. And `store_metadata` records `trace_version` at creation,
so a `CorruptRecordError` names the build that wrote the row, which keeps DEC-020's refuse-don't-
migrate stance while making the refusal actionable.

Why:

- The packaging metadata claimed installability (`[project.scripts]`, a distribution name) while
  `pip install trace && trace run` would fail on the first asset read, and nothing in CI caught it
  because `uv sync` is editable with the repo present. An MVP that DEC-004 scopes to a local
  single-user run does not need distribution; it needs its packaging to stop lying.
- Each store identity that lived only as `__name__` or a duck-typed branch was a rename or a new
  object away from silent data loss -- the one place the otherwise-explicit persistence layer
  guessed.

Alternatives Considered:

- Making the wheel self-contained now (rejected for v0.1: moving the requirements catalog and its
  content hash, the prompt tree, and the templates under the package, and rewriting every reader to
  `importlib.resources`, is a real migration for a distribution nobody is consuming yet).
- Keeping `langsmith` for a future tracing integration (rejected: an unwired dependency is dead
  weight now, and wiring tracing is its own decision when it happens).

Tradeoffs:

- A `SourceCheckoutRequiredError` from a wheel is less convenient than a working install, but it is
  honest, and the guard is one check past the banner rather than scattered through the readers.
- `stored_type` as a class attribute set in `__init_subclass__` is a small piece of metaclass-time
  machinery on `DomainModel`; it earns its place by turning a rename from silent data loss into a
  one-line override, and a conformance test pins that every object's `stored_type` is its name.

## DEC-091: Live capture is a command, generalized over the registry; decisions are authored per capture

Date: 2026-08-17

Status: Accepted

Decision:

**`trace capture <scenario> <stage>` replaces `scripts/capture_forgeflow.py`.** The capture logic
moves to `services/evaluation/capture.py`, parameterized by a registry `Scenario`
(`benchmarks/scenarios.yaml`, DEC-027): any registered scenario can be captured, not one hardcoded
demo. The three-stage shape is kept deliberately — `extract` to checkpoint 1, `reason` to
checkpoint 2, `report` to completion — because the pauses are where a person authors checkpoint
decisions, and the stages mirror `scripts/replay_forgeflow.py` call for call so a promoted capture
replays without the replayer changing.

**Checkpoint decisions are authored per capture, in the staging directory, from the files each
stage exports.** A scenario's committed `recorded/decisions-*.yaml` were authored against the run
that produced the committed recording; a fresh live run allocates identifiers against its own
objects (DEC-018), so applying a previous capture's decisions blind would decide objects nobody
reviewed — a clean approval record over an unreviewed run, which is the DEC-005 failure with extra
steps. The committed files remain the replay's input and a starting point for authoring, never a
live run's input. Answering a checkpoint from an authored decision file is not an ablation and
needs no switch (DEC-012); what this entry adds is only that the file must have been authored
against the run it decides.

**Everything the script guarded stays guarded.** Staging beside the scenario (`<scenario>/capture/`)
rather than in `recorded/`, so a partial capture cannot half-replace a committed recording;
promotion is a deliberate copy after the replay round-trip is verified. Each stage refuses to run
twice — the refusal is exit code 3, an answer rather than a fault (DEC-088) — and `--from-recorded`
resumes an interrupted capture by replaying the staged prefix before going live. The fake provider
is refused at stage entry, before any side effect: a capture of the deterministic substitute would
record what replay already has. The capture's data root is its own (`data/capture-<slug>`), apart
from the operator's assessments.

Why:

- The hardcoded script is why the eleven-scenario live sweep never ran and why the #331/#332
  comparison protocols have plumbing and no recorded execution. Every measurement item queued
  behind a live run was queued behind one scenario's script.
- The capture writes real usage into the recorded-response envelope (#461), and a command that any
  scenario can run is the only practical way those envelopes ever hold real values.

Alternatives Considered:

- Keeping the script and adding a `--scenario` flag (rejected: `--help` is a promise the command
  surface makes, and a live-spending tool hidden in `scripts/` is exactly the kind of capability
  the CLI exists to state; the script also duplicated service calls the module now owns once).
- Applying committed `recorded/decisions-*.yaml` to a fresh live run when present (rejected: the
  identifiers may not correspond, and a decision applied to an object its author never saw is an
  unreviewed approval with a reviewer's name on it).
- A single `trace capture <scenario>` that runs all three stages in one invocation (rejected: the
  stages pause where a person must author decisions; a one-shot command would either skip the
  authoring or invent it).

Tradeoffs:

- A test-only `data_root` parameter and an injectable `live` model widen the stage signatures, but
  they are what let the full three-stage round trip run offline in the default suite, asserting the
  committed ForgeFlow report hash byte for byte — the promotion criterion, tested without spend.
- The fake-provider refusal means `trace capture` cannot rehearse its own mechanics offline; the
  unit tests carry that instead, which keeps a meaningless zero-usage "capture" from ever landing
  in a staging directory.

Amendment (2026-08-17, #534): **`trace capture <scenario> <stage> --rehearse` runs the stage
offline, and nothing it stages can be promoted.** The tradeoff above bit harder than expected:
the entire keyed track queues behind `trace capture`, and the first run of the three-stage flow
for a new scenario happened with live spend. A rehearsal runs the same stage functions against
the deterministic substitute serving `--response` recordings, staging into its own
`capture-rehearsal/` directory beside the real one, with a `REHEARSAL` marker file for the
operator. The refusal this entry traded on is kept, structurally: every envelope a rehearsal
stages carries a `rehearsal` key, and `load_recorded_responses` — the reader behind the replay,
the harness, and any promoted recording — refuses such an envelope everywhere except inside the
rehearsal's own resume. A zero-usage artifact still cannot land where a recording is expected;
what changed is that the mechanics-validation pass no longer costs a dollar. Baseline stages are
excluded: one call has no mechanics to rehearse.

Date: 2026-08-17

Status: Accepted

Decision:

**The quoted per-assessment cost is the measured one.** DEC-014's open question asked what an
assessment actually costs and flagged its own answer — `scripts/estimate_cost.py`'s $2.25 to
$5.97 — as unmeasured, to be re-run against real `ExecutionRecord` data once the pipeline ran.
The pipeline has run: the DEC-077 stability protocol's five completed `claude-opus-5` runs of
`unsigned-webhooks` (`docs/eval/live-stability.json`) put a run at **$6.92 ± $3.28** and
**~41 ± 15 minutes**, with a mean of 15.4 model calls. The measured mean sits above the
estimate's ceiling. The conclusion the estimate was built to check survives: the cost does not
change the model tier, and effort-driven thinking depth remains the dominant term. Documents
that quoted the estimate as the cost of an assessment now quote the measurement; the estimate
script stays, docstring-marked as superseded for the per-assessment figure, because its
per-component model is still the only a-priori shape for scenarios never run live. The sweep
figure is restated from measurement: twelve scenarios at the measured mean is roughly $83, wide
variance stated rather than rounded away.

**`trace ledger` prints an assessment's recorded spend** — one line per model-assisted node per
workflow run: calls, the DEC-067 token spans kept disjoint (uncached input, cache reads, cache
writes, output), local duration, and estimated cost, with a per-run total. It reads what the
execution records already carry and computes nothing new. **Absent prints as a dash, never
zero:** an offline replay of a recording that captured no usage measured nothing, and a zero
would be a claim. A node line whose records partially reported sums what was reported.

**Usage plumbing is complete; values arrive only from live captures.** The #461 envelope carries
usage; `trace capture` (DEC-091) writes real usage at capture time; `DeterministicModel` replays
it; the ledger and the scorecard surface it. The 158 recordings migrated without usage stay
absent — backfilling them is a keyed re-capture per scenario, not an edit, and until one runs the
dashes are the honest answer.

Why:

- The project's stated identity is honesty about what is measured, and its flagship cost number
  was an estimate the one existing measurement contradicts. Quoting $2.25–$5.97 beside a committed
  $6.92 ± $3.28 measurement is the documentation-and-reality divergence the stop conditions name.
- Spend was visible only as two print lines inside `assessment status` and a run summary; a
  reviewer asking "which node spent it" had no answer short of querying SQLite by hand.

Alternatives Considered:

- Re-running the character-ratio estimate with tuned constants until it matched the measurement
  (rejected: a tuned estimate that agrees with one measurement is a curve fit wearing the
  measurement's authority; the measurement itself is the answer).
- Backfilling approximate usage into the 158 recordings from token-ratio math (rejected: it would
  turn every dash into a fabricated measurement and poison the offline ledger's honesty).
- A `--json` flag on `trace ledger` now (deferred to the CLI-wide JSON output contract, #486,
  so the ledger does not invent a one-off serialization the contract then has to unify).

Tradeoffs:

- One scenario measured five times is a thin base for a headline figure, and the entry says so:
  the figure is quoted with its variance and its n, and the eleven-scenario sweep (#484) is the
  named next step, not an implied one.
- Keeping the superseded estimate script means two cost numbers exist in the repository; the
  docstring states which one is quotable and why the other survives.

## DEC-093: Stability-protocol object decisions replay by content fingerprint

Date: 2026-08-17

Status: Accepted

Decision:

**A live run's context-object decisions replay from the recorded review file by content
fingerprint.** The DEC-077 stability protocol approved every context object under the default
policy and counted every one as defaulted — the harness disclosed as much
(`defaulted_decisions: 182` on the committed live measurement), and a sweep run against that
leniency would measure the harness, not the pipeline. Now a live object whose fingerprint
uniquely matches an object the recorded reviewer decided replays that disposition under the
protocol's reviewer identity, and only a genuinely novel or ambiguous object falls to the
default approval and counts. The defaulted count keeps its meaning as the disclosure — it now
measures extraction novelty rather than the protocol's own substitution.

**Fingerprints follow the DEC-056 matcher's conventions and are computed in `matching.py`,**
the one implementation the metrics and the diff already share: components, actors, assets, and
trust boundaries on normalized name; data flows on normalized (source, destination) component
names; claims on (subject name or the literal `system`, normalized predicate). Values and
descriptions are never compared — the fingerprint says "the same object", never "the same
wording".

**The recorded side's fingerprints come from the recorded extraction proposal.** The review
file's entries carry allocated identifiers; DEC-018 allocates at insert and insert follows
proposal order, so a section's entries sorted by identifier correspond to the proposal list
positionally, and no allocation is re-run. Three refusals keep the replay conservative, and
each falls to the counted default rather than to a guess: a section whose entry count disagrees
with its proposal list is skipped whole; a fingerprint occurring more than once on either side
is dropped as ambiguous; an object whose references cannot be resolved fingerprints as nothing.
Only `approve` and `reject` dispositions replay — an edit is authored content, not transferable
to an object its author never saw.

Why:

- The eleven-scenario live sweep (#484) is the largest unconverted claim in the project, and
  running it before this change would have measured the default policy's leniency. The
  committed live measurement's 182 defaulted decisions were the harness saying so.
- The conservative failure mode matters more than match rate: a decision applied to an object
  its reviewer never saw is DEC-091's unreviewed-approval failure inside the measurement
  itself.

Alternatives Considered:

- Matching on the DEC-019 content hash of the whole object (rejected: any wording difference —
  the exact thing a live re-run varies — breaks the match, so it degenerates to the default
  policy with extra machinery).
- Reconstructing recorded identifiers by re-running conversion and allocation against a scratch
  store (rejected: heavier, and it re-derives exactly the positional fact DEC-018 already
  guarantees).
- Replaying recorded edits onto matched objects (rejected: an edit constructs new content for a
  specific object; transplanting it onto a merely-similar one fabricates a review).

Tradeoffs:

- Positional correspondence leans on DEC-018's allocation order; a future change to insert
  order would silently unmatch everything. The count-mismatch skip bounds the damage to "more
  defaulted decisions, visibly counted" — the failure is loud in the summary, never wrong in
  the decisions.
- The committed `live-stability.json` predates this change; its 182 defaulted decisions are the
  old protocol's number and are not re-stated. The next live measurement re-derives it under
  the new matching, which is the honest comparison.

## DEC-094: One overlay-resolution path, and a template hash beside the composed one

Date: 2026-08-17

Status: Accepted

Decision:

**`build_model` is the one place a DEC-069 overlay resolves.** Two resolution paths existed and
neither was exercised: the factory built one adapter per overlaid agent
(`OverlayRoutingModel`, routing each call by its response schema), and the driver independently
handed every node `profile.for_agent(name)` — the same fact resolved a second time, free to
drift from the first. The factory path survives because it is the only one that can change the
model on the wire: the model identity lives in the adapter, and a single `StructuredModel`
object is load-bearing for replays (a per-agent model set would break recorded-response
ordering). The driver now passes the base profile to every node. Two consequences are accepted
and stated: budget *projection* prices at the base profile's rates while the resolved adapter
prices the recorded usage; and `AgentOverlay.settings` is removed — it could only take effect
through the driver path, and an overlay now names a model and its rates, nothing else.
Generation settings stay the base profile's, with creativity always the agent's own DEC-085
intent applied by the node from the AGENTS table.

**`PromptDefinition` carries a `template_hash` beside `content_hash`.** The DEC-019 hash is
computed over the composed, *substituted* text — the request, source corpus included — so it
identifies one composition and cannot answer "which template produced this": the same template
over two corpora hashes differently. The new `template_hash` covers the pre-substitution
composition — shared blocks merged, markers unfilled — so every composition of a prompt version
shares it across assessments, and a shared-block edit still moves it in every prompt that
includes the block, which is DEC-019's stated purpose. Both hashes persist in the
`traces/prompts/` snapshot and `resolve_definition` accepts either (or the reference).
`data-model.md` section 29 and the `hashing.py` input table carry the field.

Why:

- WS11's theme: facts written in two places with nothing asserting they agree drift silently.
  An overlay resolving in the driver and the factory was that shape, waiting for the first
  shipped overlay to expose whichever copy had rotted.
- The #331 prompt-version comparison needs to attribute results to prompt versions honestly,
  and the substituted hash cannot do that across scenarios — every corpus moves it.

Alternatives Considered:

- Keeping the driver path and deleting the factory's routing (rejected: `GenerationSettings` is
  deliberately model-free and the adapter's profile names the model, so the driver path cannot
  change what model answers; keeping only it would make overlays decorative).
- Redefining `content_hash` to the pre-substitution composition instead of adding a second hash
  (rejected: the append-only snapshot history — one definition per distinct substituted
  composition — is a pinned, deliberate property, and retiring the substituted hash would erase
  the record of what was actually sent).

Tradeoffs:

- Base-rate budget projection under-guards slightly when an overlay names a pricier model and
  over-guards when it names a cheaper one; projection is a pre-call ceiling check, the recorded
  cost is the adapter's, and the asymmetry is stated here rather than hidden in a resolution
  path nobody exercises.
- Snapshot files still accumulate per distinct substituted composition; `template_hash` makes
  the template identity queryable across them, which was the actual gap. Collapsing the
  snapshot granularity is a separate decision if the accumulation ever costs anything.

## DEC-095: A second provider adapter proves the seam, on its own SDK and its own terms

Date: 2026-08-17

Status: Accepted

Decision:

**`infrastructure/model/openai_adapter.py` is the second `StructuredModel` implementation.**
DEC-014 called the seam populated but not proven agnostic, and the interview package named a
second provider adapter first among what production would need. The adapter holds the same
three obligations as the Anthropic one, asserted by the same conformance suite
(`test_adapter_conformance.py`, now parametrized over both providers): exactly one attempt,
never raises — every provider condition returns a `ModelFailure` with usage — and `raw_output`
survives a schema failure while `error_message` stays free of model text.

**Provider-specific decisions, stated:**

- **Creativity maps to `reasoning_effort`** (`LOW → medium`, `MODERATE → high`), the same
  deliberation reading as the Anthropic mapping, recorded on every result's metadata.
- **Structured output is requested non-strict and validated by the adapter.** OpenAI's strict
  mode requires every schema key required and rewrites optionals as explicit nulls — a shape
  the proposals' defaulted fields would fail to validate. The schema goes as a non-strict
  `json_schema` response format; a provider that rejects the format falls back to
  `json_object`, recorded as `schema_grammar: "unsupported_omitted"` — the Anthropic grammar
  fallback's shape, for the same reason: validation is the application's either way.
- **Usage is made disjoint before pricing.** The provider's `prompt_tokens` includes the cached
  span, so the adapter subtracts `cached_tokens` to keep DEC-067's input spans disjoint;
  caching is automatic on this provider, `cache_prefix` is accepted and unused, and there is no
  cache-write premium, so `cache_creation_tokens` is always zero.
- **The boundary rule generalized rather than opened:** each adapter may import exactly its own
  SDK, and `test_model_boundary.py` asserts it per adapter over the whole tree.

**Two profiles ship with the adapter.** `openai-experimental` (`gpt-5.1`, hand-maintained rates
like every entry in the table) is the second provider's bundle; `economy-mapping` is the first
shipped profile carrying a DEC-069 overlay — the mapping agent, the call-heavy node, on
`claude-sonnet-5` under a `claude-opus-5` base — so the DEC-094 resolution path is exercised by
configuration that exists, and the #332 model comparison has named bundles to compare.

**What this does not claim:** no live OpenAI pipeline run has been measured. The integration
round trip (`tests/integration/test_openai_adapter.py`, opt-in, key-gated) is the adapter's
only live evidence until a `trace capture` or comparison run produces more, and every document
that states the seam is proven says exactly this much.

Why:

- An unproven claimed property is the kind of debt this project's identity rejects, and the
  configuration half-promised the proof: `openai_api_key` sat in `Settings` and `.env.example`
  while `build_model` refused the provider.
- #332's model comparison is only interesting across providers, and the comparison needs the
  adapter before the capture.

Alternatives Considered:

- The Responses API instead of Chat Completions (deferred: both exist in the installed SDK;
  Chat Completions has the simpler response shape for the seam's needs and the stable
  `response_format`/`reasoning_effort` surface. Moving is an adapter-internal change the seam
  never sees).
- Strict structured output with an SDK-transformed schema (rejected: the transformation
  rewrites optionals into explicit nulls the proposals' validators refuse; adherence help is
  not worth a schema the application's own models cannot round-trip).
- A mixed-provider overlay (rejected for now: an overlay carries a model and rates, not a
  provider, and `build_model` builds one provider's adapters per profile. A provider field on
  the overlay is a real extension left until a measurement wants it).

Tradeoffs:

- Two SDKs to keep current instead of one, and a second hand-maintained rate row that can go
  stale independently.
- The non-strict schema trades some adherence for validity: the provider may deviate where a
  strict grammar would not, and the adapter's own validation plus the orchestrator's retry
  budget are the recovery, exactly as on the Anthropic path after its grammar fallback.

## DEC-096: Read commands speak JSON, and the missing read commands exist

Date: 2026-08-17

Status: Accepted

Decision:

**Every read command takes `--json` and prints one JSON object.** The envelope is three things:
a `kind` naming what the object is, `data_model_version` naming the schema generation that
shaped it (DEC-020's version, so a consumer can refuse a payload it does not understand the way
the store refuses a row), and the payload. The command surface was thirteen groups of
human-formatted `print` with no machine-readable output anywhere — Trace composed with nothing,
and its own evaluation tooling lived CI-side because the CLI offered scripts no purchase.

**The JSON view carries the same information as the human view — no more.** This is the
contract's load-bearing clause. The CLI's standing rule is that source-derived text is printed
only where it was asked for and no command prints an absolute path; a `--json` flag that dumped
whole domain objects would have repealed both silently, putting quoted document content and
storage detail on screen as a side effect of scripting. So `evidence list --json` carries
locations and identifiers and `evidence show --json` carries the quotation, exactly as their
human views do; `findings show --json` carries evidence identifiers where the human view prints
labelled excerpts, and the quotations stay reachable through `evidence show`. Exit codes are
unchanged by the flag: `context show --json` still answers exit 3 while the context cannot be
approved (DEC-088), with `can_approve` in the payload saying so.

**Three read commands that should have existed do:** `trace threats` and `trace questions` list
first-class domain objects that were visible only through the HTML view or the rendered report;
`trace catalog show` and `trace catalog validate` reach the requirements catalog through the one
loader that may read it (DEC-010), making the loader's refusals — a moved hash, a manifest
mismatch — a command a person can run rather than a CI-only fact. `CatalogError` joins the
CLI's expected errors: exit 1 with the loader's reason, never a traceback.

**The relationship to exports (DEC-072) is division, not overlap.** `--json` is the CLI's own
view of its own answers, versioned by `data_model_version` and shaped per command; an export
(TM-BOM, SARIF) is an interchange document in someone else's schema for someone else's tooling.
Neither substitutes for the other, and the JSON contract deliberately does not promise
interchange stability beyond the data-model version it stamps.

Why:

- DEC-032 makes the command line the interface; an interface nothing can compose with is one
  only a person can use, and the assessment diffing candidate (future-features 4.1) wants
  stable serialized output on both sides before it can exist.
- Threats and questions are authoritative domain objects a reviewer reasons about; reaching
  them required rendering a report or starting a web server, which is the wrong shape for both.

Alternatives Considered:

- Dumping domain objects whole via `model_dump` everywhere (rejected: repeals the
  source-content and path rules silently; the per-command payload is more code and the only
  honest shape).
- A `--format json|yaml|table` axis (rejected: one machine shape is a contract, three are a
  maintenance surface; YAML adds nothing `jq` needs).
- Schema-versioning the envelope independently of the data model (rejected for now: the
  payloads are projections of DEC-020-versioned objects, and a second version number with no
  independent motion would be ceremony).

Tradeoffs:

- Per-command payload construction can drift from the human view it mirrors; the contract tests
  pin the envelope, the refusal exit code, and the no-quotation rule, which are the clauses
  that matter.
- `report show` keeps its Markdown body and `verify` its exit-code answer, without `--json` —
  the report is the deliverable itself and the manifest already exists for scripts; extending
  the flag to them is a later, smaller decision if a consumer appears.

Amendment (2026-08-17, #505): **`trace evaluate` and `assessment candidates` take `--json`.**
The evaluate omission was this entry's unexplained gap — the one command that emits metrics had
no machine shape. The envelope carries one `runs` list: per run, the identifiers, statuses,
metrics as a mapping, the DEC-075 adversarial block where the feed holds one, the repo-relative
feed path, and the offline replay pin's verdict. Exit codes are unchanged by the flag, including
the drift answer.

Amendment (2026-08-17, #523): **`report show` and `verify` take `--json`.** The consumer this
entry's tradeoff waited for appeared: the release-record machinery (#524) reads `verify --json`
as its integrity gate. `report show --json` carries the report body — or, with `--manifest`,
the parsed manifest — exactly as the human view prints it; `verify --json` carries the walk's
counts and every drifted item by identifier and hash, never content. Exit codes are unchanged
by the flag: drift is still exit 3 (DEC-088).

## DEC-097: Assessment diffing compares approved models by content fingerprint, conservatively

Date: 2026-08-17

Status: Accepted

Decision:

**`trace diff <before> <after>` compares two assessments' approved models** (future-features
4.1, promoted). Each side is read through its own scoped handle — two scoped reads, never a
cross-assessment query, so the store's scoping rule stands. Both sides must hold an approved
context, the refusal every export makes (DEC-072): a diff over candidates would report changes
no reviewer saw.

**Identity across assessments is the content fingerprint, and the matching is conservative.**
Identifiers are allocated per assessment (DEC-018), so the same component in two assessments
carries different identifiers; pairing reuses the conventions the evaluation matcher already
owns rather than inventing a second identity: DEC-093's fingerprints for context objects (names;
(source, destination) for flows; (subject, predicate) for claims), the persisted DEC-066 content
fingerprint for findings, normalized text for open questions. A fingerprint occurring more than
once on either side is ambiguous, and its objects report as added and removed rather than
paired — the diff must never guess, because a guessed pairing reports an edit nobody made.

**Threats and documentation gaps are not paired in v1.** A threat's identity is model-authored
wording plus its ground, both expected to vary across runs; they compare by ground (normalized
affected component and asset names) as counts with added/removed lists, stated as such, and
their "changed" list is empty by construction. Pairing them semantically is DEC-043's deferred
territory and waits for the same evidence.

**Changed means the content fields moved.** Matched objects compare on their model dump minus
the volatile fields — identifiers, timestamps, provenance, `status`, cross-references carrying
per-assessment identifiers — and the diff names the fields that differ. The command exits 0
whether or not differences exist: the diff is a report, not a gate, and a gating flag is a
later decision if a consumer wants one.

Why:

- future-features 4.1 called this one of the strongest extensions because it builds directly on
  the structured data model, and the promotion criteria were all met: a re-run assessment
  previously produced a wholly new report with no relation to the last, and the reviewer's
  actual question — what changed, what needs re-review — had no answer short of reading both.
- The matching conventions already existed (DEC-056, DEC-066, DEC-093); the diff consumes them
  rather than minting a competing identity, so the evaluation matcher and the diff cannot
  disagree about what "the same object" means.

Alternatives Considered:

- Pairing renamed objects by field similarity (rejected: a similarity threshold is a guess with
  a number on it, and the conservative failure mode — removed plus added — is both honest and
  actionable).
- Diffing all objects rather than approved models (rejected: candidates are proposals nobody
  reviewed, and DEC-072 already establishes that serialized comparisons speak for approved
  state).
- A separate persisted diff artifact (rejected: the diff is derived, regenerable from the two
  stores by one command, and DEC-073's rule for derived artifacts applies — no place in
  history).

Tradeoffs:

- Rename detection is deliberately absent: a renamed component reports as removed and added.
  The reviewer holding both reports can pair them by eye; the tool refusing to guess is the
  point.
- The volatile-field list is a judgment call pinned by tests; a new domain field that should
  count as content lands in the comparison automatically, while a new identifier-shaped field
  must follow the `_id`/`_ids`/`_at`/`_by` suffix conventions to be excluded — which the domain
  models already follow.

## DEC-098: The AI system threat-modeling pack grows catalog 0.2, and a scenario pins its catalog

Date: 2026-08-17

Status: Accepted

Decision:

**Catalog 0.2 (draft) gains the retrieval-augmentation and model-generated-code categories**
(future-features 8.1, promoted in part). Five requirements: the retrieval corpus's write path
is governed (req-RAG-001), retrieval is filtered by the requester's authorization
(req-RAG-002), the index follows its sources' lifecycle (req-RAG-003), model-generated code
executes in stated isolation (req-CODEGEN-001), and generated changes pass the same gates as
human changes (req-CODEGEN-002). Every statement is in the documentation register so silence
resolves to `unverified` (DEC-009), each carries `common_false_positives` naming what not to
conclude where AI-system documentation is habitually silent, and the wording is original with
sources cited by identifier (the catalog's own licensing rule). 0.2 is a draft under DEC-057,
so the growth is an edit and a re-freeze, not a new version; the fate map is untouched because
additions carry no prior fate.

**A scenario names the catalog version its assessments pin.** The registry entry gains an
optional `catalog_version` (absent means the loader's current version, exactly as before);
the harness and `trace capture` pass it through `AssessmentService.create`, which now accepts
the pin `new_assessment` always supported, and `trace assessment create --catalog-version`
exposes the same for an operator. This is DEC-010's pinning rule reaching the one caller that
could not state a version: without it, a scenario written against a draft catalog would be
assessed against whatever `current_version()` says, and the truth set and the run would
silently disagree about which requirements exist.

**The rag-support-bot scenario makes the pack measurable.** A RAG support assistant documented
well in most respects, with one affirmatively documented weakness and one genuine silence: one
expected finding (req-RAG-002 — the shared index selecting by relevance alone is a documented
absence of an entitlement filter, not silence), one expected gap with its paired question
(req-RAG-003 — deletion propagation unstated either way), and two expected rejections
(req-AI-001, req-RAG-001 — documented handling a naive pass reports over anyway). The authored
baselines commit exactly those failures, and the structured baseline's over-claim on
req-RAG-003 is kept deliberately: structure alone does not stop silence being read as absence,
which is the ablation narrative's point carried into the comparison. The scenario replays
offline with a full truth set like the other twelve, and pins catalog 0.2 through the registry.

Why:

- The catalog was the acknowledged weak substrate, and 8.1 is the growth direction the demo
  and the talk are already about; a pack without a scenario would be asserted value, and the
  promotion criteria require measured value.
- DEC-024 sends the whole catalog on every mapping call, and its partitioning cost question
  (2x or 5x?) is open; growing the catalog raises it, and DEC-092's measured token data is
  what will answer it. The growth deliberately does not populate `applicable_technologies` or
  add a pre-filter — that stays DEC-024's own decision, taken on cost evidence.

Alternatives Considered:

- A new catalog version 0.3 for the pack (rejected: 0.2 is a draft, mutable by DEC-057's own
  rule, and a third version before the second releases would multiply manifests without
  protecting anything the freeze guard does not already protect).
- Scoping the scenario's truth set to catalog 0.1 so no pinning plumbing was needed (rejected:
  0.1 has no retrieval requirements, so the pack's value would be unmeasurable — the exact
  failure the promotion criteria exist to prevent).
- Growing further in one change — fine-tuning pipelines, provider-integration depth (deferred:
  each wants its own scenario to be measurable, and the WIP limit says one primary problem).

Tradeoffs:

- A 37-requirement catalog raises every mapping call's input size under DEC-024; the cost
  question is now live and named rather than latent.
- The structured baseline losing its clean no-spurious record is a deliberate narrative trade:
  the honest comparison beats the tidy sentence, and the failure it now shows is the one the
  architecture exists to prevent.

## DEC-099: A catalog version releases when the first recorded scenario pins it; release is not the default

Date: 2026-08-17

Status: Accepted

Decision:

**The release condition DEC-057 left open is stated: a catalog version releases when the first
committed recorded scenario pins it.** DEC-057 defined the mechanics — a draft is freely
editable in place; a released version is immutable at PR time under
`scripts/check_catalog_freeze.py`; the registry carries lifecycle — and named 0.1's trigger (the
recorded ForgeFlow fixture) without naming 0.2's. The general rule behind that trigger is now
explicit: the moment a committed recording depends on a version's content, that content is
load-bearing for a replay, and content a replay depends on must freeze. `rag-support-bot`
(DEC-098) pinned 0.2, so the condition fired; `requirements/versions.yaml` records
0.2 as active, released 2026-08-17, and the freeze guard covers `requirements/0.2/` from this
change forward.

**Release does not move the default.** The root manifest (`catalog.yaml`) still names 0.1, so an
assessment that pins nothing is still assessed against 0.1. The two knobs are deliberately
separate: releasing freezes content a replay depends on; switching the default changes what every
new unpinned assessment maps against — and, because a mapping call carries the whole catalog
(DEC-024), it would also change the input surface of every default-profile run and interact with
the open partitioning cost question. Switching the default to 0.2 is its own later decision,
taken when the cost question has its measurement.

**Every registered version's citations are checked.** `scripts/asvs_resolver.py` resolved only
`current_version()`, which left 0.2's fourteen new requirements' ASVS citations unverified —
a citation in a released version is exactly as load-bearing as one in the default. The resolver
now iterates the governance registry's versions; all citations across 0.1 and 0.2 resolve.

**The evaluation stamps are version-honest.** `build_comparison.py` and `build_ablation.py`
stamped the whole corpus with one `current_version()` — structurally incapable of being true
over a mixed corpus, and false since DEC-098 ("catalog 0.1" over a corpus with a 0.2 scenario).
`catalog_version_summary()` in the evaluation registry counts what the scenarios actually
assess against ("0.1 (12), 0.2 (1)"), and the committed evaluation documents are regenerated
under it.

Why:

- An indefinitely editable version that a committed replay depends on is the drift DEC-057's
  freeze exists to prevent, one directory over from where the guard was looking.
- The stamp falsity was the stop condition — documentation and implementation describing
  different systems — in the project's own measurement artifacts, which is the worst place for it.

Alternatives Considered:

- Releasing on a calendar or review cadence (rejected: DEC-057's whole design keys immutability
  to what replays depend on, and a cadence would freeze content nothing depends on or leave
  depended-on content mutable between reviews).
- Moving the default to 0.2 in the same change (rejected: it changes every unpinned run's
  mapping input surface and the recorded ForgeFlow replay's environment while the DEC-024 cost
  question is unmeasured; releasing and defaulting are different risks and get different
  decisions).

Tradeoffs:

- Two active versions with 0.1 as default reads oddly until the default switches; the registry
  comment says why, and the alternative — a mutable version under committed replays — is worse.
- Growing the catalog further now means 0.3: the pack's remaining half (fine-tuning and
  training-data supply chains, DEC-098's deferral) pays the minor-version cost when it lands,
  which is exactly the cost DEC-057 designed it to pay.

## DEC-100: Baseline recordings are captured, not only authored

Date: 2026-08-17

Status: Accepted

Decision:

**`trace capture <scenario> baseline-generic|baseline-structured` captures a DEC-074 baseline
recording from one live call.** DEC-091 promoted pipeline capture to a command and left the
baselines out; the five scenarios carrying `recorded/baselines/` got them by hand, and #484's
"live baselines" clause was hard-blocked on there being no capture path at all. The stage is one
call and one file — `capture/baselines/baseline-<name>.json`, the bare `BaselineFindings` shape
the replay already reads (the baseline path predates the #461 envelope and keeps its shape) —
staged beside the pipeline stages with the same promote-by-copy rule.

**A captured baseline is scored immediately.** The stage runs through `run_baseline`, so the
same call that records also scores against the truth set and writes a feed; the operator sees
matched/missed/spurious before deciding to promote. A recording nobody judged would be a
recording nobody can trust, and the baseline exists to be compared.

**The same guards as the pipeline stages, plus one honest asymmetry.** An existing staged file
refuses the re-spend (exit 3, DEC-088); the fake provider is refused before the call; a
schema-invalid response records nothing — the schema failure is the scored result, in the feed,
because DEC-074 counts schema validity as a baseline metric rather than a retryable fault.
Baseline capture opens no store and needs no data root: the DEC-074 baseline is deliberately
storeless, and the capture inherits that.

Why:

- The keyed gate (#484, #331, #332) includes live baselines, and every other capture need had a
  command; this was the last hand-authoring step between a provider key and the gate clearing.

Alternatives Considered:

- Wrapping the baseline call in the #461 envelope with usage (rejected for now: the replay path
  reads the bare shape, and reshaping the five committed recordings plus the reader to gain
  usage on a single-call artifact is a separate, smaller decision — the pipeline ledger is
  where spend accounting lives).
- A separate `trace baseline capture` command (rejected: capture is one surface with stages,
  and a second top-level command would restate the same guards and the same staging rule).

Tradeoffs:

- The stage list on `trace capture` now mixes pipeline stages with baseline stages; the help
  text says which is which, and the alternative was a second command surface.
- Replay-through-fake when a test supplies a response leans on `build_model`'s rule that queued
  responses feed only the deterministic substitute; that rule is load-bearing here and is
  already pinned by the factory's own tests.

## DEC-102: Severity concordance is measured against the truth set's guidance, without a second reviewer

Date: 2026-08-17

Status: Accepted

Decision:

**A `severity_concordance` benchmark metric answers DEC-030's open question.** DEC-030 assigned
severity to the reviewer at checkpoint 2 and recorded, as a standing gap, that "nothing now
measures severity at all" — and asked specifically for a metric that does not require a second
reviewer. The data to answer it was already committed: every scenario's
`expected-findings.yaml` carries `severity_guidance` per finding, and every replayed run carries
the reviewer's assigned severity. For each matched finding whose expectation carries scalar
guidance, the metric compares the two: the value is the exact-agreement rate, and the notes
carry the within-one-level rate beside it. It is a benchmark metric
(`EvaluatorType.BENCHMARK`), computed by `metrics.py` and surfaced in the scorecard's
reserved-metrics table.

**It measures agreement, not correctness.** Severity is a risk judgment in business context
(DEC-030), and the guidance is one author's judgment, not ground truth — the metric's method and
notes say so. What it detects is drift between the reviewer playing the checkpoint and the
authored guidance, which is exactly the signal DEC-030 wanted: whether the blank-field
checkpoint produces severities anyone can predict. A scenario whose matched findings carry no
scalar guidance (ForgeFlow's `medium-or-high`, or a live run matching none of its truth)
measures nothing here and reports `None` — absence of guidance is not a spurious zero.

**A consolidated finding is held to the strictest guidance it stands for.** When one finding
matches several expectations, under-rating the worst weakness it represents is the error that
matters, so the toughest guidance among its matches is the bar. `unassigned` never appears —
the approval gate refuses it (DEC-030).

Why:

- DEC-030 named the metric it wanted and the constraint (no second reviewer); the guidance
  field existed for exactly this and had no consumer. Leaving a decided-open question
  answerable-with-committed-data unanswered is the kind of gap the roadmap's stop conditions name.
- It is the honest input future-features 7.7 (automatic severity calculation) would need before
  it could leave Research: 7.7 stays out (DEC-030 excluded a severity agent, and "new agents
  without measured benefit" is a stop condition), and this metric is the evidence that would one
  day argue for or against it.

Alternatives Considered:

- A severity agent proposing the value (rejected: DEC-030 excluded it, and this delivers the
  measurable half without one).
- Scoring only exact agreement (rejected as the sole signal: a one-level miss and a three-level
  miss are different failures, so the within-one-level rate rides in the notes).
- Requiring a second annotator for a true concordance (rejected: DEC-004 is single-user, and
  DEC-030 asked precisely for a metric that does not need one; agreement-with-guidance is what
  a single reviewer can be measured against).

Tradeoffs:

- Guidance is one author's judgment, so a low score can mean the reviewer erred or the guidance
  did; the metric flags divergence for a human to read, and does not adjudicate it. The method
  string says "agreement, not correctness" so no reader mistakes it for the latter.
- Scenarios with non-scalar guidance contribute nothing, so the metric's sample is smaller than
  the finding count; the sample size rides on every result, and the reserved-metrics column
  reads `—` where a scenario measures nothing.

## DEC-103: The assessment comparison report is the diff's narrative layer, an output artifact

Date: 2026-08-17

Status: Accepted

Decision:

**`trace diff --report` renders the structural diff as a Markdown comparison report** (promotes
future-features 13.3). DEC-097 shipped `trace diff` with one consumer, the CLI, and structural
output — families, fingerprints, changed field names. 13.3 is the layer a reviewer actually
reads: what changed between two approved models, ordered so the things that change a conclusion
come first — findings, then open questions and gaps, then threats, then context. It carries no
prose beyond the diff and draws no conclusion the diff did not; every line is derived from the
two approved models.

**It is an output artifact, not a report.** DEC-035's sixteen-section contract and
`templates/report-v1.md` are untouched; the comparison is Markdown written to the *later*
assessment's `outputs/`, content-addressed like the exports — it is that assessment's account of
what changed since the earlier one. Deterministic: the same diff renders byte-identically, so
re-running writes a new artifact beside the old rather than overwriting, and two comparisons of
the same pair agree.

Why:

- The diff had exactly one consumer and its structural shape is not what a reviewer reads; the
  narrative layer is the reviewer-decision value the roadmap's second question asks for, and it
  is measurable with what exists (the diff plus the corpus), which is why 13.3 promoted where
  the other 13.x ideas did not.
- Writing it to the later assessment's outputs, content-addressed, reuses the export family's
  rule rather than inventing a second artifact discipline.

Alternatives Considered:

- A new report *format* rather than an output artifact (rejected: DEC-035 makes the report
  Markdown-only with one owner per section, and a comparison is not the assessment's report — it
  is a derived artifact about two assessments, exactly the export family's shape).
- Writing to the earlier assessment, or a shared location (rejected: the comparison is the newer
  assessment's account of its own changes; the `AssessmentHandle` boundary keeps each
  assessment's artifacts its own, and the newer one is where a reviewer looks next).
- A gating exit code (rejected, as for the diff itself: the report is a report, not a gate;
  DEC-097 already settled that a gating flag is a later decision if a consumer wants one).

Tradeoffs:

- The report reads the diff, which does not detect renames (DEC-097): a renamed object narrates
  as removed-and-added. The narrative inherits that conservatism, which is the honest shape —
  the report does not claim a rename the diff refused to guess.
- Two comparison artifacts accumulate if a pair is compared before and after an edit; content-
  addressing keeps them distinct and append-only, the export family's accepted cost.

## DEC-104: The documentation site is a rendered view of committed sources, published from main

Date: 2026-08-17

Status: Accepted

Decision:

**`docs/` publishes as a static site — MkDocs Material, built by CI, deployed to GitHub Pages
from `main` through the Pages artifact flow.** The Markdown sources stay where they are and
remain authoritative: `mkdocs.yml` sits at the repository root with `docs_dir: docs`, so the
tree the conformance tests read by path is untouched, and nothing about the site changes what
any test or loader sees. A hand-authored `docs/index.md` is the site's landing page; the README
stays the repository's front page and is not copied in. The handful of links that escaped
`docs/` (into the README and `demo/forgeflow/`) became absolute repository URLs, which resolve
identically on GitHub and on the site. The build runs `mkdocs build --strict` on every pull
request that touches the sources, so a broken intra-site link fails CI; only a push to `main`
deploys. The rendered `site/` directory is gitignored and never committed.

This does not reopen DEC-076. The scorecard remains a committed artifact whose history is the
git history; the site copies `docs/eval/scorecard.html` verbatim rather than regenerating it at
deploy time. What DEC-076 rejected was leaving the scorecard *only* in a CI artifact with no
committed copy. The site's rendering is a different class of output: derived presentation of
committed Markdown, with no history of its own worth keeping — the same standing as the wheel
CI builds and discards.

Why:

- Stage 6's audience reads documentation as a navigable site with search, not as a file tree.
  The corpus is complete — guide, architecture, product, evaluation — and raw Markdown in a
  repository browser undersells it.
- Publishing from `main` keeps the site an account of released Trace. `develop` describes what
  the next release will do, and a site that tracks it would drift into the tense-discipline
  failure the working norms name: describing the pipeline as if the unreleased part exists.
- The artifact flow rather than a `gh-pages` branch: branch protection blocks CI pushes here by
  design (the scorecard and demo workflows already note this), and a rendered branch is a second
  copy of derived content in history.

Alternatives Considered:

- A GitHub wiki (rejected: a wiki is a separate repository outside pull requests, CI, and the
  conformance tests that hold `docs/` and the code in agreement; a doc edit would stop being
  reviewable and stop versioning with the code it describes).
- Committing the rendered site (rejected: DEC-076 committed the scorecard because its history is
  the record; a themed rendering of already-committed Markdown has no history of its own, and
  regenerated `site/` churn on every docs edit would bury real diffs).
- Publishing from `develop` (rejected: see Why; the integration branch is the wrong tense for a
  public account of the system).
- Restructuring `docs/` for the site — an `index.md`-per-directory layout or a `docs/src/` split
  (rejected: roughly twenty tests read these files by path, and the site is not worth a test
  migration; `docs_dir: docs` with an explicit nav gets the same structure for free).

Tradeoffs:

- The site lags `develop` by one release. Accepted: that is the point of publishing from `main`,
  and the sources on any branch remain readable in the repository.
- `mkdocs-material` joins the lockfile, and the existing CI jobs install it because they sync
  `--all-groups`. Accepted: pure-Python wheels, cached by the uv action; the docs workflow
  itself syncs `--only-group docs` and skips the project entirely.
- The scorecard page renders without the site's chrome, because it is copied verbatim as DEC-076
  requires. Accepted: it carries its own styling and always has.

## DEC-105: The catalog leads the mapping trusted region, and the seam carries a system-region cache hint

Date: 2026-08-17

Status: Accepted

Decision:

**The mapping trusted region opens with its stable span — the assessment header and the whole
requirements catalog — and everything the threat varies follows it.** The section order was
Assessment, Threat, Catalog, Controls, architecture, Evidence; it is now Assessment, Catalog,
Threat, Controls, architecture, Evidence. The reorder changes no content, only position, and the
composed prompt files are untouched — this is the runtime system region only.

**The seam gains `system_cache_prefix`, the same provider-neutral hint `cache_prefix` already
is, for the system region.** `MappingInput` carries the stable span as `trusted_cache_prefix`,
and the mapping node passes it through. The Anthropic adapter splits the system region at the
hint and marks the stable block ephemeral, with the same degradation rules as the user-message
split: no hint, or a hint that is not a prefix, sends the plain string. The OpenAI adapter
accepts and ignores it — that provider caches prefixes automatically and has no marker. Both
remain one contract under the adapter conformance suite.

Why:

- DEC-024 sends the full catalog on every mapping call and defends the cost by calling the
  catalog "a stable cacheable prefix on every mapping call" — but it was not one. The cache
  marker sat in the user message, after a system region that varies per threat, so across an
  assessment's ~15 mapping calls the catalog was re-sent uncached every time; only one threat's
  retries ever hit. DEC-098 grew the catalog to 37 requirements riding every call, making this
  the cheapest real cost lever available before the DEC-092-funded live sweep measures the
  pipeline again.
- The user-message marker stays: within one threat's retries the whole system region is
  identical, so the longer prefix still hits there, and the two markers compose.

Alternatives Considered:

- Moving the per-threat trusted content into the user message so the whole system region is
  stable (rejected: the trusted/untrusted boundary is decided surface — the system region is
  the application's voice and the user message carries the fenced source content; relocating
  approved objects across that line to serve a cache is the tail wagging the dog).
- Partitioning the catalog instead (deferred, unchanged: that is DEC-024's own open question,
  to be taken on cost evidence; this change extracts the available win without deciding it).

Tradeoffs:

- The seam's `generate` widens by one optional parameter across every implementation, including
  the test doubles. Accepted: the alternative was a mapping-only side channel past the seam,
  which DEC-014 exists to prevent.
- Marking the stable span costs the cache-write surcharge on the first mapping call of a run;
  every subsequent call reads it back. A run with one threat gains nothing and pays the
  surcharge once — the degenerate case, accepted.

## DEC-106: Data-model section 39's remaining questions are answered by practice or re-deferred with a trigger

Date: 2026-08-17

Status: Accepted

Decision:

Seven of section 39's questions were still open while the code had already chosen. Each is now
resolved by ratifying the practice, resolved by an existing decision the section never cited, or
re-deferred with the trigger named — the M12 pattern (#541). Per question:

- **Q1, claim shape:** both, with a division of labor. Typed objects carry the structured facts;
  `ContextClaim` keeps subject-predicate-value for the assertions about them, `value` as
  `JsonValue` domain-side and scalar-narrowed on the proposal side (DEC-083). The shipped
  pipeline uses exactly this split, and neither half substitutes for the other: typed models
  alone cannot carry an open assertion, and claims alone would untype the architecture.
- **Q5, machine-readable applicability:** re-deferred, trigger named. The DEC-024 partitioning
  measurement (#532) decides whether partitioning the catalog pays; machine-readable
  applicability is its representation question and waits on the same evidence.
- **Q8, merging multiple model outputs:** dissolved by the fixed pipeline (DEC-016). Every
  object has exactly one proposing call; a retry replaces the whole proposal (retry the attempt,
  never the conclusion); duplicates across calls belong to the deterministic consolidation rule
  and the reviewer. Model outputs are never merged with each other, and building a merge would
  invite the ambiguity the pipeline exists to prevent.
- **Q9, revision storage:** DEC-023 answered it — update in place under the same identifier,
  with `ReviewerDecision` history; `SystemContext`'s approved versions are the one revisioned
  lineage. No general revision store.
- **Q11, generation metadata:** `generated_by` and `created_at` on the object, and nothing
  more. The generation's conditions — model, profile, effort, retries, cost, raw failed output —
  are the `ExecutionRecord`'s and `traces/`, keyed by run. An object carrying its whole
  generation story would be a second execution ledger drifting from the first.
- **Q12, state contents:** DEC-016 answered it — identifiers and routing only, section 31's
  state-design rule.
- **Q16, rejected-object retention:** in place. Status `rejected`, `duplicate_of_id` where
  deduplication merged, decision history attached; DEC-040 keeps rejected objects out of
  approved baselines by revision membership, and the harness grades the negative set against
  `expected-rejections.yaml`. The only deletion is DEC-089's per-assessment purge.

Why:

- Pre-release, a shareable data-model document whose own open-questions section does not know
  what the code decided reads as a specification nobody reconciled. Ratifying practice on the
  record is cheap exactly because the code has already borne the decisions' weight; the
  expensive alternative — reopening each question as if undecided — would relitigate settled
  ground without new evidence.
- A re-deferral with a named trigger is an answer: Q5 now says *what evidence* reopens it,
  which is the difference between deferred and forgotten.

Alternatives Considered:

- One DEC per question (rejected: five of the seven are ratifications or citations with no new
  design content; seven entries would bury the two that carry any).
- Answering Q5 now by populating `applicable_technologies` (rejected: DEC-024 and DEC-098 both
  hold that the pre-filter decision is taken on cost evidence, and #532 is that evidence's
  issue).

Tradeoffs:

- Ratification risks blessing an accident as a decision. Mitigated by stating each answer's
  reason here rather than pointing at the code alone — if the reason stops holding, the entry
  is what a successor argues against.
