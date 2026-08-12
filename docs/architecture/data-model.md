# Trace — Data Model

**Project:** Trace

**Subtitle:** Context-Aware Security Architecture Analysis

**Data model version:** 0.1

**Status:** Proposed

**Last updated:** 2026-08-05

## 1. Purpose

This document defines the core domain objects used by the Trace MVP.

Trace should exchange and persist structured, schema-validated objects rather than relying on free-form model output as authoritative application state.

The data model is designed to support:

- Context-aware security analysis
- Evidence traceability
- Human review
- Workflow checkpointing
- Explainable findings
- Evaluation
- Versioned requirements and prompts
- Future API and interface development

The model is intentionally focused on the MVP. It should evolve based on implementation and evaluation results.

## 2. Modeling Principles

### 2.1 Stable identifiers

Every important object should have a stable identifier.

Identifiers allow Trace to:

- Link findings to threats
- Link claims to evidence
- Track revisions
- Record human decisions
- Merge duplicates
- Resume interrupted workflows
- Compare evaluation runs

Identifiers should not depend on mutable display names.

Example identifier prefixes:

asm- Assessment

src- Source document

evd- Evidence reference

cmp- Component

ast- Asset

df- Data flow

tb- Trust boundary

ctx- Context claim

thr- Threat

req- Requirement

ctl- Control

map- Control mapping

fnd- Finding

qst- Question

gap- Documentation gap

obs- Source observation

act- Actor

eas- Evidence assessment

crq- Critique

dec- Reviewer decision

run- Workflow run

exe- Execution record

eval- Evaluation result

mrg- Finding merge record

cgc- Catalog gap candidate

## What the scheme governs

The scheme governs **objects an assessment produces**. An object is inside it when all three hold:
it is scoped to one assessment, it is persisted by the assessment store, and something else refers
to it by identifier. Those objects carry an `id` in one of the two forms below, using a prefix from
the list above.

`Requirement` is the one authored exception, and it is inside the scheme: assessment objects
reference it by identifier — a `ControlMapping` names `req-AUTH-001` — so it keeps its prefix.

**Authored configuration is outside the scheme.** `RequirementsCatalog` (section 30) and
`PromptDefinition` (section 29) are not scoped to an assessment, are not minted by the persistence
layer, and are referenced by *version* rather than by identifier. Their `id` is a **name**: a
lowercase slug, stable across versions, carrying no prefix and no number, with identity given by
`(id, version)` — `core` at version `0.1`, `extract-context` at version `v1`. A prefixed value there
would claim membership in a registry that does not contain it (DEC-034).

`SystemContext` (section 9) has no `id` at all. It is keyed by `(assessment_id, version)`.

## Two classes of identifier

**Authored identifiers** are written by hand and carry meaning. `req-` is the only authored prefix
currently in use, in the requirements catalog's `req-AUTH-001`. They are globally unique, stable
across catalog versions, and are the only identifiers a benchmark expected-output file may
reference.

**Generated identifiers** are minted during an assessment, in the form `<prefix>-<NNN>` using the
prefixes above. They are unique **within their assessment**, not globally — `thr-007` in two
assessments is two different objects, and an identifier is fully qualified only by
`(assessment_id, id)`.

A generated identifier is assigned by the persistence layer at insert, from a monotonic counter per
`(assessment_id, prefix)`. It is not assigned at construction: agents return proposal objects that
structurally cannot carry an identifier, so the application assigns one when it takes ownership
(DEC-018).

No generated identifier appears in a benchmark expected-output file. Expected outputs reference
authored catalog identifiers and match on content — the requirement, the affected components — not
on generated identity.

### 2.2 Evidence must be addressable

Important conclusions should link to specific source locations.

A source document alone is not sufficiently precise.

Evidence should identify:

- Source document
- Section or chunk
- Relevant text
- Location information
- Content hash
- Extraction method

### 2.3 Facts, assumptions, and interpretations are different objects

Trace should not treat every extracted statement as a confirmed fact.

Context claims should explicitly identify their status.

Possible statuses include:

- Documented
- Inferred
- User confirmed
- Assumed
- Contradicted
- Unknown
- Rejected

### 2.4 Findings are downstream objects

A finding should not be generated directly from a checklist item.

A valid finding should generally connect:

1. System context
2. A plausible threat scenario
3. A relevant requirement or security expectation
4. Available control information
5. Supporting evidence
6. Security impact
7. Reviewer judgment

### 2.5 Human actions must be preserved

Reviewer edits, approvals, and rejections are valuable data.

They support:

- Auditability
- Evaluation
- Model improvement
- Demo explainability
- Future workflow tuning

Reviewer actions should be recorded rather than silently overwriting generated content.

### 2.6 Current state and history are separate

Objects may change during analysis.

Trace should preserve:

- Current authoritative state
- Prior generated state
- Reviewer modifications
- Workflow execution history

The MVP does not need full event sourcing, but significant changes should remain traceable.

Three mechanisms, for three distinct causes (DEC-023):

| Cause | Mechanism |
|---|---|
| A reviewer edits an object | Mutate in place; write a `ReviewerDecision` carrying the changed fields before and after |
| A workflow node regenerates an object | The new object carries `supersedes_id` |
| The approved context baseline advances | `SystemContext.version` increments on approval |

`SystemContext` is the only versioned object, because it is the only one whose whole state is
approved as a unit and the only one later stages reason from as a baseline. A per-object version
number elsewhere would count edits rather than mark anything.

## 3. Core Entity Relationships

erDiagram

ASSESSMENT ||--o{ SOURCE_DOCUMENT : contains

SOURCE_DOCUMENT ||--o{ EVIDENCE_REFERENCE : provides

ASSESSMENT ||--|| SYSTEM_CONTEXT : develops

SYSTEM_CONTEXT ||--o{ CONTEXT_CLAIM : contains

SYSTEM_CONTEXT ||--o{ COMPONENT : contains

SYSTEM_CONTEXT ||--o{ ASSET : contains

SYSTEM_CONTEXT ||--o{ DATA_FLOW : contains

SYSTEM_CONTEXT ||--o{ TRUST_BOUNDARY : contains

THREAT }o--o{ COMPONENT : affects

THREAT }o--o{ ASSET : threatens

THREAT }o--o{ EVIDENCE_REFERENCE : supported_by

REQUIREMENT ||--o{ CONTROL_MAPPING : referenced_by

CONTROL ||--o{ CONTROL_MAPPING : referenced_by

THREAT ||--o{ CONTROL_MAPPING : evaluated_by

THREAT ||--o{ FINDING : contributes_to

CONTROL_MAPPING ||--o{ FINDING : contributes_to

FINDING }o--o{ EVIDENCE_REFERENCE : supported_by

ASSESSMENT ||--o{ QUESTION : raises

ASSESSMENT ||--o{ DOCUMENTATION_GAP : identifies

ASSESSMENT ||--o{ REVIEWER_DECISION : records

ASSESSMENT ||--o{ WORKFLOW_RUN : executes

WORKFLOW_RUN ||--o{ EXECUTION_RECORD : contains

ASSESSMENT ||--o{ EVALUATION_RESULT : measures

# 4. Shared Types

## 4.1 ObjectStatus

Represents an object’s lifecycle state.

Possible values:

draft

candidate

pending_review

approved

rejected

superseded

archived

Not every object needs every status.

## 4.2 ConfidenceLevel

Human-readable confidence classification.

Possible values:

low

medium

high

Confidence is **categorical only**. No numeric score is stored (DEC-022): a decimal alongside a
three-value enum invites reading confidence as probability, which design principle 15 warns
against, and conflates model confidence with evidence strength, which the same principle requires
be kept separate.

Model confidence lives here. Evidence strength lives on `EvidenceAssessment.evidence_strengths`.

Suggested interpretation:

| Level | Meaning |
|---|---|
| Low | Significant uncertainty or weak evidence |
| Medium | Plausible and partially supported |
| High | Strongly supported by evidence or user confirmation |

## 4.3 EvidenceStrength

Describes how strongly an evidence reference supports a claim.

Carried by `EvidenceAssessment.evidence_strengths`, a map from evidence identifier to strength
(DEC-022). It sits on the assessment rather than on the `EvidenceReference` because **strength is
relational, not intrinsic**: the same passage can be direct evidence for one claim and merely
contextual for another.

Possible values:

direct

indirect

contextual

contradictory

## 4.4 SourceOrigin

Identifies where information originated.

Possible values:

uploaded_document

structured_input

user_response

requirements_catalog

system_generated

reviewer_edit

external_tool

`structured_input` covers authored structured architecture input and, per DEC-070, anything
parsed deterministically from a machine-readable source; `generated_by` names the parser.

## 4.5 Severity

Initial severity classification.

Possible values:

informational

low

medium

high

critical

unassigned

**`unassigned` is the value a finding is created with.** No pipeline node assigns severity:
the reviewer assigns it at the finding checkpoint (DEC-030), because severity depends on
business context the source documents do not carry. It is the one required `Finding` field
that cannot be answered from the material under review.

**`unassigned` may not survive approval.** See the approval rules in section 21.

The MVP should avoid implementing an overly complex severity algorithm before the core workflow is validated. DEC-030 declined a deterministic heuristic on those grounds and on data: the fields a rule would use — `internet_exposed`, `business_criticality`, the impact fields, `data_classification` — are all optional and mostly free text with no controlled vocabulary.

## 4.6 ReviewDisposition

Possible reviewer actions.

approve

reject

edit

defer

request_more_analysis

convert_to_question

convert_to_documentation_gap

There is deliberately no `change_severity` value. A severity change is an `edit`, carrying
`prior_value` and `updated_value` on `ReviewerDecision` per DEC-023. `current-architecture.md`
section 5.12 lists changing severity among the reviewer's actions; that list names actions a
reviewer takes and this one names dispositions the system records, and the two do not
correspond one to one (DEC-030). A risk-treatment assignment is likewise an `edit`, not a new
disposition (DEC-060).

## 4.7 ValidationStatus

Used for claims, controls, and findings.

supported

partially_supported

unsupported

contradicted

requires_confirmation

not_evaluated

## 4.8 RiskTreatment

The reviewer's chosen response to a finding's risk, assigned at checkpoint 2 (DEC-060). A closed
vocabulary: the values are named, not illustrated, like `DataFlow.direction`. Findings are created
`undecided`, and unlike severity `undecided` may survive approval; the only gate is that `accept`
without a `treatment_rationale` is refused.

undecided

mitigate

accept

transfer

avoid

# 5. Assessment

## Purpose

Represents one complete security architecture analysis.

## Fields

| Field | Type | Required | Description |
|---|---|---|---|
| id | string | Yes | Stable assessment identifier |
| name | string | Yes | Human-readable assessment name |
| description | string | No | Brief description of the system under review |
| status | ObjectStatus | Yes | Current assessment state |
| created_at | datetime | Yes | Creation timestamp |
| updated_at | datetime | Yes | Last modification timestamp |
| created_by | string | No | Reviewer or local user identifier |
| architecture_version | string | Yes | Architecture version used |
| data_model_version | string | Yes | Data-model version used |
| workflow_version | string | Yes | Workflow definition version |
| requirements_catalog_version | string | No | Requirements catalog version |
| configuration | AssessmentConfiguration | Yes | Runtime configuration |
| active_workflow_run_id | string | No | Current workflow run |
| final_report_path | string | No | Generated report location |
| tags | list[string] | No | User-defined labels |

## Note on `status`

`status` describes the assessment **as a deliverable** — whether its conclusions may be used and
whether work may continue — and never where the pipeline has reached. Workflow progress lives on
`WorkflowRun.status` (section 26), and an assessment may have several runs, so it cannot mirror one.

Four `ObjectStatus` members are used (DEC-031):

| Status | Meaning |
|---|---|
| `draft` | Work in progress. The conclusions are not authoritative. |
| `pending_review` | Blocked on a human. No automated progress is possible. |
| `approved` | The pipeline completed and the reviewer approved the findings at checkpoint 2. |
| `archived` | Retired. Read-only, and terminal. |

`pending_review` says that a human is required, never which checkpoint; `WorkflowRun.current_node`
says which. It is set in the same transaction that sets `WorkflowRun.status` to `paused` and
cleared in the one that resumes, so the two cannot disagree.

`candidate`, `rejected`, and `superseded` are not used. An assessment is never proposed by an agent;
an assessment whose findings were all rejected is a completed assessment with zero findings, which
is a success rather than a rejection; and supersession belongs to re-generated objects, which
DEC-023 limits to the two carrying `supersedes_id`.

**A person may only archive.** Every other transition is written by a workflow node, and an
assessment completed by a non-authoritative run — one that applied an ablation, per DEC-012 — may
not reach `approved`.

## Example

id: asm-001

name: ForgeFlow Security Review

description: Review of a fictional GitHub-integrated developer platform

status: pending_review

created_at: 2026-08-05T14:00:00-06:00

updated_at: 2026-08-05T14:45:00-06:00

architecture_version: "0.1"

data_model_version: "0.1"

workflow_version: "0.1"

requirements_catalog_version: "0.1"

active_workflow_run_id: run-001

tags:

- demo

- isc2

- developer-platform

# 6. AssessmentConfiguration

## Purpose

Stores settings that affect an assessment run.

## Fields

| Field | Type | Required | Description |
|---|---|---|---|
| model_profile | string | Yes | Named model configuration |
| threat_methodology | string | Yes | Initial threat-analysis methodology |
| maximum_model_calls | integer | No | Execution safety limit |
| maximum_cost | decimal | No | Optional cost limit |
| maximum_retries_per_node | integer | Yes | Retry limit |
| retain_debug_artifacts | boolean | Yes | Preserve debugging output |
| enable_external_tracing | boolean | Yes | Allow configured external tracing |
| evidence_threshold | string | Yes | Minimum evidence policy for findings. `direct-or-confirmed` or `permissive` (DEC-013) |

## Example

model_profile: primary-development

threat_methodology: stride-scenario-based

maximum_model_calls: 40

maximum_cost: 8.00

maximum_retries_per_node: 2

retain_debug_artifacts: true

enable_external_tracing: false

evidence_threshold: direct-or-confirmed

## Note on the example limits

`maximum_model_calls` and `maximum_cost` above were originally 25 and 5.00. `scripts/estimate_cost.py`
models the pipeline against the ForgeFlow corpus and predicts **28 model calls**, which the original
limit would have halted, and **$2.25 to $5.97** per assessment on `claude-opus-5` depending on how
much adaptive thinking the effort level produces — so the original cost limit held at low effort and
was exceeded at high effort.

The values are raised to leave headroom rather than to describe a target. They remain examples; a
real assessment sets its own.

The estimate's dominant finding is that **thinking tokens, billed as output, are roughly 85% of the
cost**. Effort level is therefore the cost lever, ahead of model tier and well ahead of prompt
caching, which saves about 12%.

## Note on the human checkpoints

This object carries no setting that governs the two human checkpoints. Earlier versions
declared `require_context_review` and `require_finding_review` here; DEC-012 removed them.

The checkpoints are nodes in the workflow graph rather than runtime conditionals, so there
is no configuration value that advances the pipeline past an unapproved one. A field here
would be the switch that defeats DEC-005, whatever value it defaulted to.

Running a checkpoint without a human present is not a configuration concern. A checkpoint
answered from a recorded decision file is still a checkpoint: the node executes, the gate
holds, and a ReviewerDecision is written. That is the mode repeatable evaluation uses.

Removing a checkpoint altogether is an experiment on the architecture, described in the
evaluation plan's section 14. It belongs to the evaluation harness, and a run that applies
it is recorded as non-authoritative.

# 7. SourceDocument

## Purpose

Represents an original source supplied to the assessment.

## Fields

| Field | Type | Required | Description |
|---|---|---|---|
| id | string | Yes | Stable source identifier |
| assessment_id | string | Yes | Parent assessment |
| filename | string | Yes | Original filename |
| media_type | string | Yes | MIME or logical file type |
| origin | SourceOrigin | Yes | Source origin |
| original_path | string | No | Local artifact location |
| normalized_path | string | No | Normalized content location |
| content_hash | string | Yes | `sha256:<hex>` over the original file's raw bytes (DEC-019) |
| title | string | No | Document title |
| created_at | datetime | Yes | Registration timestamp |
| ingested_at | datetime | No | Successful ingestion timestamp |
| ingestion_status | string | Yes | Current ingestion state |
| trust_level | string | Yes | How the source should be treated |
| metadata | map[string, any] | No | Format-specific metadata |

## Trust-level values

untrusted

reviewer_supplied

system_fixture

trusted_catalog

Even reviewer-supplied documents should generally be treated as data rather than workflow instructions.

# 8. EvidenceReference

## Purpose

Represents an addressable piece of evidence from a source.

## Fields

| Field | Type | Required | Description |
|---|---|---|---|
| id | string | Yes | Stable evidence identifier |
| source_document_id | string | Yes | Parent source |
| assessment_id | string | Yes | Parent assessment |
| section_title | string | No | Source section |
| chunk_index | integer | No | Normalized chunk position |
| start_line | integer | No | Starting line |
| end_line | integer | No | Ending line |
| page_number | integer | No | Page number when applicable |
| quoted_text | string | Yes | Relevant source excerpt |
| normalized_text | string | No | Cleaned text |
| content_hash | string | Yes | `sha256:<hex>` over the UTF-8 bytes of `quoted_text` (DEC-019) |
| source_origin | SourceOrigin | Yes | Evidence origin |
| created_at | datetime | Yes | Creation timestamp |
| metadata | map[string, any] | No | Additional location details |

## Validation rules

- quoted_text must not be empty.
- At least one usable source-location field should be present when available.
- Evidence references must point to a valid source document.
- Evidence text should not be modified after creation; corrections create a new evidence reference.

## Note on locations

Every location field addresses the **original** document, never the normalized artifact
(DEC-015). `start_line`, `end_line`, and `quoted_text` are all taken from the file as supplied.
Normalization is line-count preserving, so the two addressings cannot diverge.

`quoted_text` is verbatim from the original and is what a reviewer sees and what the report
quotes. `normalized_text` is the derived form and exists for machine comparison. `content_hash`
covers `quoted_text`.

For Markdown and plain text, `chunk_index` counts sections segmented at the shallowest heading
level present in that document, and `section_title` is the chunk's own heading, flattened rather
than nested.

For JSON and YAML the address is a JSON Pointer carried in `metadata` under the reserved key
`json_pointer`, with `section_title` holding the readable dotted-path equivalent. Line numbers are
still populated so a reviewer can find the passage, but a line range is not an address in a
structured document — two sequence elements can be textually identical.

`page_number` is unpopulated until PDF ingestion arrives.

## Example

id: evd-014

assessment_id: asm-001

source_document_id: src-002

section_title: Authentication

start_line: 41

end_line: 46

quoted_text: >

Users authenticate through the corporate OIDC provider.

The application does not store local user passwords.

content_hash: sha256:example

source_origin: uploaded_document

created_at: 2026-08-05T14:10:00-06:00

# 9. SystemContext

## Purpose

Represents the structured architecture baseline used for downstream analysis.

## Fields

| Field | Type | Required | Description |
|---|---|---|---|
| assessment_id | string | Yes | Parent assessment |
| system_name | string | Yes | Reviewed system name |
| system_purpose | string | No | Business and technical purpose |
| business_criticality | string | No | Criticality classification |
| environment | list[string] | No | Development, test, production, etc. |
| deployment_model | string | No | Cloud, local, hybrid, managed |
| data_classifications | list[string] | No | Relevant data classifications |
| access_model | string | No | Deny by default, allow by default, mixed, unknown (DEC-068) |
| context_claim_ids | list[string] | Yes | Context claims |
| component_ids | list[string] | Yes | Components |
| asset_ids | list[string] | Yes | Assets |
| actor_ids | list[string] | Yes | Actors (DEC-037) |
| data_flow_ids | list[string] | Yes | Data flows |
| trust_boundary_ids | list[string] | Yes | Trust boundaries |
| approved_at | datetime | No | Context-approval timestamp |
| approved_by | string | No | Reviewer identifier |
| version | integer | Yes | Context revision number |

`access_model` (DEC-068) is a **closed** enum — `deny_by_default`, `allow_by_default`, `mixed`,
`unknown` — always present, defaulting to `unknown` exactly as section 14's transport fields do,
because an authorization posture nobody stated must never read as an answer. Closed because the
values are named rather than illustrated, like `DataFlow.direction`.

# 10. ContextClaim

## Purpose

Represents one architectural or business assertion about the reviewed system.

Examples:

- Authentication is delegated to an enterprise identity provider.
- The API is internet accessible.
- Repository data is stored in object storage.
- Database encryption is assumed but not documented.

## Fields

| Field | Type | Required | Description |
|---|---|---|---|
| id | string | Yes | Stable context-claim identifier |
| assessment_id | string | Yes | Parent assessment |
| subject_type | string | Yes | Type of object described |
| subject_id | string | No | Referenced object |
| predicate | string | Yes | Nature of the assertion |
| value | any | Yes | Asserted value |
| status | string | Yes | Documented, inferred, confirmed, etc. |
| confidence | ConfidenceLevel | Yes | Confidence classification |
| rationale | string | No | Why the claim holds. **Required when `status` is `inferred` or `assumed`** (DEC-022) |
| evidence_ids | list[string] | No | Supporting evidence |
| source_origin | SourceOrigin | Yes | Claim origin |
| generated_by | string | No | Workflow node or reviewer |
| reviewer_notes | string | No | Reviewer explanation |
| created_at | datetime | Yes | Creation timestamp |
| updated_at | datetime | Yes | Last update |
| supersedes_id | string | No | Prior claim this one replaces, on **re-extraction**. Not used for reviewer edits (DEC-023) |

## Status values

documented

inferred

user_confirmed

assumed

unknown

contradicted

rejected

## Example

id: ctx-021

assessment_id: asm-001

subject_type: component

subject_id: cmp-003

predicate: authentication_provider

value: enterprise_oidc

status: documented

confidence: high

evidence_ids:

- evd-014

source_origin: uploaded_document

generated_by: context-extraction-v1

# 10a. SourceObservation

## Purpose

Records something observed **about the source material**, as distinct from an assertion about the
reviewed system (DEC-021).

A `ContextClaim` asserts that authentication is delegated or that the API is internet-accessible. A
`SourceObservation` asserts that two documents disagree, or that a passage attempts to instruct its
reader. The distinction is categorical: one describes the system, the other describes the documents.

## Fields

| Field | Type | Required | Description |
|---|---|---|---|
| id | string | Yes | Stable observation identifier |
| assessment_id | string | Yes | Parent assessment |
| kind | string | Yes | `contradiction` or `injection_attempt` |
| summary | string | Yes | What was observed |
| evidence_ids | list[string] | Yes | Passages the observation rests on |
| subject_claim_ids | list[string] | No | Context claims the observation bears on |
| status | ObjectStatus | Yes | Lifecycle state |
| generated_by | string | No | Workflow node or reviewer |
| reviewer_notes | string | No | Reviewer explanation |
| created_at | datetime | Yes | Creation timestamp |

## Kind values

contradiction

injection_attempt

## Validation rules

- `contradiction` requires at least two evidence references.
- `injection_attempt` requires at least one.
- A SourceObservation carries no severity and never becomes a Finding. A Finding asserts a weakness
  in the reviewed system; an observation asserts something about a document.
- A contradiction does not resolve itself. Where the answer would materially change the assessment,
  a `Question` is raised alongside it. Trace must not silently choose the safer statement.

## Note on `ContextClaim.contradicted`

`ContextClaim`'s `contradicted` status means a SourceObservation of kind `contradiction` references
that claim in `subject_claim_ids`. The reference is one-directional, so a claim does not carry a
field naming what contradicts it and the two cannot disagree about whether they disagree.

# 11. Component

## Purpose

Represents a technical or logical part of the reviewed system.

Examples:

- Web frontend
- API gateway
- Repository service
- Background worker
- PostgreSQL database
- GitHub
- Identity provider

## Fields

| Field | Type | Required | Description |
|---|---|---|---|
| id | string | Yes | Stable component identifier |
| assessment_id | string | Yes | Parent assessment |
| name | string | Yes | Human-readable name |
| component_type | string | Yes | Service, datastore, external system, etc. |
| description | string | No | Purpose and behavior |
| technology | list[string] | No | Known technologies |
| ownership | string | No | Owning team or external party |
| deployment_zone | string | No | Runtime environment or network zone |
| internet_accessible | boolean | No | Exposure indicator |
| externally_managed | boolean | No | Whether another party manages it |
| entry_point_types | list[string] | No | How the component can be entered (DEC-068) |
| data_classifications | list[string] | No | Data processed or stored |
| authentication_mechanisms | list[string] | No | Authentication methods |
| authorization_mechanisms | list[string] | No | Authorization methods |
| evidence_ids | list[string] | No | Supporting evidence |
| source_origin | SourceOrigin | Yes | Where the object originated (section 4.4) |
| status | ObjectStatus | Yes | Lifecycle state |

## Component-type examples

user_interface

service

api_gateway

background_worker

data_store

message_queue

identity_provider

external_service

repository_provider

ci_cd_system

secrets_manager

object_storage

administrative_interface

`entry_point_types` (DEC-068) is an open-vocabulary list (`login`, `admin_interface`,
`file_upload`, `webhook`, `api`, `inter_system_interface`, and peers), normalized through
`domain/vocabulary.py`. Empty means the documentation names no entry points, not that the
component has none.

# 12. Asset

## Purpose

Represents something requiring protection.

Assets may be technical, informational, or operational.

## Fields

| Field | Type | Required | Description |
|---|---|---|---|
| id | string | Yes | Stable asset identifier |
| assessment_id | string | Yes | Parent assessment |
| name | string | Yes | Asset name |
| asset_type | string | Yes | Data, credential, service, reputation, etc. |
| description | string | No | Asset description |
| confidentiality_impact | string | No | Potential confidentiality impact |
| integrity_impact | string | No | Potential integrity impact |
| availability_impact | string | No | Potential availability impact |
| data_classification | string | No | Sensitivity classification, open vocabulary (DEC-068) |
| owner | string | No | Business or technical owner |
| component_ids | list[string] | No | Components holding or processing asset |
| stored_in_component_ids | list[string] | No | Subset of component_ids storing the asset at rest (DEC-068) |
| evidence_ids | list[string] | No | Supporting evidence |
| source_origin | SourceOrigin | Yes | Where the object originated (section 4.4) |
| status | ObjectStatus | Yes | Lifecycle state |

## Asset-type examples

customer_data

source_code

repository_metadata

access_token

api_key

user_identity

audit_log

model_output

service_availability

business_process

organizational_reputation

DEC-068 adds two things on the usual terms: `data_classification` normalizes against
`KNOWN_DATA_CLASSIFICATIONS` (`pii`, `phi`, `financial`, `credentials`,
`intellectual_property`, `telemetry`, `public`, and peers — open, per DEC-036, against TM-BOM's
closed enum), and `stored_in_component_ids` names the subset of `component_ids` that holds the
asset at rest — where encryption-at-rest and retention requirements attach. `component_ids`
keeps meaning "holds or processes."

# 13. Actor

## Purpose

Represents a legitimate user, system identity, administrator, threat actor, or external party.

## Fields

| Field | Type | Required | Description |
|---|---|---|---|
| id | string | Yes | Stable actor identifier |
| assessment_id | string | Yes | Parent assessment |
| name | string | Yes | Actor name |
| actor_type | string | Yes | Human, service, attacker, third party |
| trust_level | string | No | Trust classification |
| skill_level | string | No | Persona: presumed capability, open vocabulary (DEC-068) |
| access_level | string | No | Persona: starting access, open vocabulary (DEC-068) |
| capabilities | list[string] | No | Relevant actions or privileges |
| authentication_method | string | No | Authentication method |
| evidence_ids | list[string] | No | Supporting evidence |
| source_origin | SourceOrigin | Yes | Where the object originated (section 4.4) |

## Actor-type examples

end_user

developer

administrator

service_identity

third_party_service

external_attacker

malicious_insider

compromised_dependency

The persona fields (DEC-068) — `skill_level` and `access_level` — are open vocabularies
normalized through `domain/vocabulary.py` (starting sets: `opportunist`, `skilled`,
`organized_group`; `anonymous`, `authenticated`, `privileged`, `physical`). They exist so a
threat's preliminary likelihood is auditable against who it presumes; no formula computes with
them.

# 14. DataFlow

## Purpose

Represents movement of data or commands between components.

## Fields

| Field | Type | Required | Description |
|---|---|---|---|
| id | string | Yes | Stable data-flow identifier |
| assessment_id | string | Yes | Parent assessment |
| name | string | Yes | Human-readable flow name |
| source_component_id | string | Yes | Flow origin |
| destination_component_id | string | Yes | Flow destination |
| direction | string | Yes | One-way or bidirectional |
| protocol | string | No | HTTPS, webhook, queue, database protocol |
| data_types | list[string] | No | Data transferred |
| authentication | string | No | Authentication mechanism |
| encryption_in_transit | string | No | Documented encryption |
| crosses_trust_boundary_ids | list[string] | No | Boundaries crossed |
| internet_exposed | boolean | No | Internet exposure |
| evidence_ids | list[string] | No | Supporting evidence |
| source_origin | SourceOrigin | Yes | Where the object originated (section 4.4) |
| status | ObjectStatus | Yes | Lifecycle state |

## Validation rules

- Source and destination must be different valid components.
- Referenced trust boundaries must exist.
- Unknown encryption or authentication should be represented as unknown, not false.

# 15. TrustBoundary

## Purpose

Represents a change in trust, ownership, privilege, or security control.

## Fields

| Field | Type | Required | Description |
|---|---|---|---|
| id | string | Yes | Stable boundary identifier |
| assessment_id | string | Yes | Parent assessment |
| name | string | Yes | Boundary name |
| boundary_type | string | Yes | Network, identity, ownership, privilege, etc. |
| description | string | No | Boundary explanation |
| inside_component_ids | list[string] | No | Components inside boundary |
| outside_component_ids | list[string] | No | Relevant outside components |
| controls | list[string] | No | Known controls at boundary |
| evidence_ids | list[string] | No | Supporting evidence |
| source_origin | SourceOrigin | Yes | Where the object originated (section 4.4) |
| status | ObjectStatus | Yes | Lifecycle state |

## Boundary-type examples

internet_to_application

user_to_administration

application_to_data_store

organization_to_third_party

human_to_service_identity

low_privilege_to_high_privilege

tenant_boundary

assessment_data_boundary

# 16. Threat

## Purpose

Represents a plausible adverse security scenario.

A threat is not automatically a finding.

## Fields

| Field | Type | Required | Description |
|---|---|---|---|
| id | string | Yes | Stable threat identifier |
| assessment_id | string | Yes | Parent assessment |
| title | string | Yes | Concise scenario title |
| description | string | Yes | Full threat scenario |
| methodology | string | Yes | STRIDE or other method |
| category | list[string] | No | Threat categories |
| threat_actor_ids | list[string] | No | Relevant actors |
| affected_component_ids | list[string] | Yes | Affected components |
| affected_asset_ids | list[string] | Yes | Threatened assets |
| related_data_flow_ids | list[string] | No | Relevant data flows |
| preconditions | list[string] | No | Required conditions |
| attack_path | list[string] | No | Scenario progression |
| impact | string | Yes | Security consequence |
| likelihood | string | No | Preliminary likelihood |
| confidence | ConfidenceLevel | Yes | Scenario confidence |
| evidence_ids | list[string] | No | Supporting context |
| assumption_ids | list[string] | No | Assumptions used |
| open_question_ids | list[string] | No | Required clarification |
| status | ObjectStatus | Yes | Candidate, approved, rejected |
| generated_by | string | Yes | Workflow node or reviewer |
| created_at | datetime | Yes | Creation timestamp |

## Example

id: thr-007

assessment_id: asm-001

title: Forged repository webhooks trigger unauthorized analysis jobs

description: >

An attacker who can submit unsigned or incorrectly validated webhook

requests may trigger analysis jobs for repositories they do not control.

methodology: stride-scenario-based

category:

- spoofing

- elevation_of_privilege

affected_component_ids:

- cmp-004

- cmp-007

affected_asset_ids:

- ast-002

- ast-005

preconditions:

- webhook endpoint is reachable

- signature validation is absent or bypassable

impact: Unauthorized jobs, data exposure, and denial of service

confidence: medium

status: candidate

generated_by: threat-analysis-v1

# 17. Requirement

## Purpose

Represents a version-controlled security expectation in the requirements catalog.

Requirements should be reusable across assessments.

## Fields

| Field | Type | Required | Description |
|---|---|---|---|
| id | string | Yes | Stable requirement identifier |
| catalog_version | string | Yes | Catalog version |
| title | string | Yes | Requirement title |
| statement | string | Yes | Normative security expectation |
| rationale | string | Yes | Reason for requirement |
| category | list[string] | Yes | Security categories |
| applicable_technologies | list[string] | No | Relevant technology types |
| applicable_conditions | list[string] | No | Conditions that affect applicability |
| non_applicable_conditions | list[string] | No | Conditions that exclude applicability |
| acceptable_implementations | list[string] | No | Example ways to satisfy requirement |
| evidence_expectations | list[string] | No | Expected evidence |
| common_false_positives | list[string] | No | Conclusions wrongly drawn when this requirement is not evidenced |
| default_severity | Severity | No | Default severity if unmet |
| source_frameworks | list[string] | No | Related standards or frameworks |
| status | string | Yes | Draft, active, retired |
| supersedes_id | string | No | Prior requirement |

## Example

id: req-WEBHOOK-001

catalog_version: "0.1"

title: Validate webhook authenticity

statement: >

Systems receiving security-relevant webhook events must verify the

authenticity and integrity of each request before processing it.

rationale: >

Unverified webhook requests may allow attackers to spoof trusted events.

category:

- authentication

- integrity

applicable_technologies:

- webhook_receiver

acceptable_implementations:

- HMAC signature validation

- asymmetric signature validation

- mutually authenticated transport with sender authorization

evidence_expectations:

- implementation documentation

- configuration evidence

- source-code reference

common_false_positives:

- documentation stating only that requests are validated, where the mechanism is unstated

- absent description of secret storage where verification itself is documented

default_severity: high

status: active

## Note on common_false_positives

This field records the conclusions that are wrongly drawn when a requirement is not evidenced.

It is distinct from non_applicable_conditions.

non_applicable_conditions states when the requirement does not apply at all.

common_false_positives states what should not be concluded when the requirement does apply but the documentation is silent.

The field exists to carry accumulated knowledge of which absences are normal, in support of DEC-009.

# 18. Control

## Purpose

Represents an implemented, inherited, claimed, or proposed security safeguard.

## Fields

| Field | Type | Required | Description |
|---|---|---|---|
| id | string | Yes | Stable control identifier |
| assessment_id | string | Yes | Parent assessment |
| name | string | Yes | Control name |
| description | string | Yes | Control behavior |
| control_type | string | Yes | Implemented, inherited, compensating, proposed |
| provider_component_id | string | No | Component providing control |
| protected_component_ids | list[string] | No | Components protected |
| protected_asset_ids | list[string] | No | Assets protected |
| implementation_status | string | Yes | Implemented, claimed, unknown, absent |
| validation_status | ValidationStatus | Yes | Evidence result |
| evidence_ids | list[string] | No | Supporting evidence |
| owner | string | No | Control owner |
| limitations | list[string] | No | Known limitations |
| generated_by | string | Yes | Workflow node or reviewer (DEC-044) |
| created_at | datetime | Yes | Creation timestamp (DEC-044) |
| status | ObjectStatus | Yes | Lifecycle state |

## Note on inherited-control scope

Scope is expressed by the fields above, not by a free-text field (DEC-026): `provider_component_id`
says who provides the control, `protected_component_ids` and `protected_asset_ids` say what it
covers, and `limitations` says where the coverage stops.

An earlier `inheritance_scope` string described the same thing in prose, which meant it could
disagree with the structured fields with nothing to say which was right. It also could not be
compared against the architecture, and inherited-control recognition is a named evaluation metric.

Two states are distinguished by field combination, and the distinction is what the ForgeFlow
intentional non-findings turn on:

| Situation | `control_type` | `implementation_status` | Evidence | Outcome |
|---|---|---|---|---|
| Platform provides it, documentation says so | `inherited` | `implemented` | present | Requirement satisfied |
| Platform probably provides it, nothing says so | `inherited` | `claimed` | absent | A `Question` requesting confirmation |

The second never resolves to `absent`, and by DEC-013 never to `unmet`.

## Note on provenance

`generated_by` and `created_at` were added by DEC-044. A `Control` has three possible origins —
the Context Extraction step finds one described, the Mapping step proposes one, or a reviewer adds
one at a checkpoint — and section 18 as first written carried no field recording which. Every other
object produced by the pipeline carries provenance, and a control without it is the one object
whose origin cannot be recovered from the record.

## Note on evidence

An `implementation_status` of `implemented`, `partially_implemented`, or `absent` asserts something
about the system, so it cites at least one `EvidenceReference` (DEC-044). `claimed` and `unknown`
are exempt, and the exemption is DEC-009: they are what an unevidenced control is called, and
requiring evidence of them would leave an undocumented control nowhere to be recorded except as
absent. A `planned` or `recommended` control is exempt whatever its status, because it is the
assessment's own proposal and no source passage describes something nobody has built.

## Control-type values

implemented

inherited

compensating

planned

recommended

## Implementation-status values

implemented

partially_implemented

claimed

unknown

absent

not_applicable

# 19. ControlMapping

## Purpose

Represents the relationship among a threat, requirement, and control.

This is one of the most important objects in Trace because it prevents the application from jumping directly from a requirement to a finding.

## Fields

| Field | Type | Required | Description |
|---|---|---|---|
| id | string | Yes | Stable mapping identifier |
| assessment_id | string | Yes | Parent assessment |
| threat_id | string | Yes | Related threat |
| requirement_id | string | Yes | Applicable requirement |
| control_ids | list[string] | No | Relevant controls |
| applicability_status | string | Yes | Applicable, conditional, not applicable |
| applicability_reason | string | Yes | Explanation |
| suppressed_conclusion | string | No | A conclusion not drawn because a `common_false_positives` entry applies (DEC-025) |
| suppressed_by | string | No | The `common_false_positives` entry that applies (DEC-025) |
| downgraded_from | string | No | The satisfaction status validation lowered, if it did (DEC-046) |
| downgrade_reason | string | No | Why the downgrade happened (DEC-046) |
| satisfaction_status | string | Yes | Satisfied, partial, unverified, unmet |
| evidence_ids | list[string] | No | Mapping evidence |
| assumptions | list[string] | No | Assumptions affecting mapping |
| confidence | ConfidenceLevel | Yes | Mapping confidence |
| generated_by | string | Yes | Workflow node or reviewer |
| reviewer_status | ObjectStatus | Yes | Review state |

## Applicability-status values

applicable

conditionally_applicable

not_applicable

unknown

## Satisfaction-status values

satisfied

partially_satisfied

unverified

unmet

not_applicable

## Important rule

An unverified requirement does not automatically create a finding.

It may instead produce:

- A clarifying question
- A documentation gap
- A request for evidence
- A low-confidence candidate finding

DEC-013 defines when each satisfaction status may be used and narrows this list at the
default evidence threshold. Under `direct-or-confirmed`, an unverified requirement produces
a clarifying question or a documentation gap and never a finding; the low-confidence
candidate finding is reachable only under the evaluation-only `permissive` threshold.

`unmet` requires evidence that describes the absence or inadequacy of the control, or that
contradicts a claim that it exists. Because an EvidenceReference must quote real source
text, silence cannot be cited, so this rule is enforced by the schema rather than by
instruction. The Mapping Validation node downgrades an unsupported `unmet` to `unverified`
and records the downgrade on `downgraded_from` and `downgrade_reason` (DEC-046).

Two of DEC-013's four conditions for `unmet` cannot be checked at this node, because they read
`EvidenceAssessment`, which the Evidence Validation phase produces afterwards. DEC-046 records
which half is enforced where: Mapping Validation applies the conditions that read only the
mapping, the catalog, and the source observations; Finding Consolidation applies the outcome
table, by which point the evidence assessments exist.

A high proportion of `unverified` mappings is the expected result of assessing ordinary
architecture documentation. It is not a defect and must not be treated as one in evaluation.

# 20. EvidenceAssessment

## Purpose

Represents an explicit evaluation of whether evidence supports a claim, control, mapping, threat, or finding.

## Fields

| Field | Type | Required | Description |
|---|---|---|---|
| id | string | Yes | Stable evidence-assessment identifier |
| assessment_id | string | Yes | Parent assessment |
| subject_type | string | Yes | Object type being evaluated |
| subject_id | string | Yes | Object being evaluated |
| evidence_ids | list[string] | Yes | Evidence evaluated |
| evidence_strengths | map[string, EvidenceStrength] | Yes | Per-evidence strength, keyed by identifier in `evidence_ids` (DEC-022) |
| validation_status | ValidationStatus | Yes | Result |
| rationale | string | Yes | Explanation |
| missing_evidence | list[string] | No | Evidence still needed |
| contradictions | list[string] | No | Contradictory evidence |
| confidence | ConfidenceLevel | Yes | Confidence |
| recommendation | Recommendation | Yes | Continue, revise, stop, downgrade to a question, or documentation-gap treatment (DEC-047) |
| generated_by | string | Yes | Workflow node or reviewer |
| created_at | datetime | Yes | Creation timestamp |

## Subject-type values

context_claim

control

control_mapping

threat

finding

## Recommendation values

continue

revise

stop

downgrade_to_question

documentation_gap

# 21. Finding

## Purpose

Represents a potentially actionable security weakness supported by analysis.

A finding is provisional until approved by a reviewer.

## Fields

| Field | Type | Required | Description |
|---|---|---|---|
| id | string | Yes | Stable finding identifier |
| assessment_id | string | Yes | Parent assessment |
| title | string | Yes | Concise finding title |
| summary | string | Yes | Short description |
| description | string | Yes | Detailed explanation |
| threat_ids | list[string] | Yes | Supporting threats |
| requirement_ids | list[string] | Yes | Relevant requirements |
| control_mapping_ids | list[string] | Yes | Related mappings |
| affected_component_ids | list[string] | Yes | Affected components |
| affected_asset_ids | list[string] | Yes | Affected assets |
| evidence_ids | list[string] | Yes | Supporting evidence |
| validation_status | ValidationStatus | Yes | Evidence state |
| severity | Severity | Yes | Current severity |
| likelihood | string | No | Likelihood rationale |
| impact | string | Yes | Security and business impact |
| recommendation | string | Yes | Recommended action |
| acceptance_criteria | list[string] | No | Conditions for closure |
| assumptions | list[string] | No | Assumptions used |
| limitations | list[string] | No | Analysis limitations |
| confidence | ConfidenceLevel | Yes | Finding confidence |
| low_confidence_justification | string | No | Required when `confidence` is `low` (DEC-050) |
| status | ObjectStatus | Yes | Candidate, approved, rejected |
| generated_by | string | Yes | Workflow node or reviewer |
| created_at | datetime | Yes | Creation timestamp |
| updated_at | datetime | Yes | Last modification |
| duplicate_of_id | string | No | Canonical finding if duplicate |
| converted_from_id | string | No | The object this was converted from (DEC-051) |
| reviewer_notes | string | No | Reviewer explanation |
| risk_treatment | RiskTreatment | No | Reviewer-assigned response; `undecided` at creation (DEC-060) |
| treatment_rationale | string | No | Residual-risk statement; required to approve `accept` (DEC-060) |
| treatment_review_by | date | No | Optional date to revisit an accepted risk (DEC-060) |
| content_fingerprint | string | No | Derived cross-run identity; set at persist, recomputed on identity-field change (DEC-066) |

## Minimum validation rules

A provisional finding should not be created unless it has:

- At least one related threat
- At least one affected asset or component
- At least one applicable requirement or stated security expectation
- A described security impact
- Evidence, and an explicit low-confidence justification where confidence is `low`
- A validation status
- A confidence classification

An approved finding should generally require:

- Reviewer approval
- Supported or partially supported evidence
- A clear distinction from a documentation gap
- Actionable remediation or acceptance criteria

An approved finding **must** have:

- A severity other than `unassigned` (DEC-030)

This one is a hard rule rather than a general expectation. Severity is assigned only by the
reviewer, so without it the field would stay `unassigned` on every finding and the report
would have no ordering. It is what makes reviewer-assigned severity work instead of
degrading into nobody assigning severity.

DEC-060 adds a second, softer reviewer judgment: `risk_treatment` (closed vocabulary
`undecided`, `mitigate`, `accept`, `transfer`, `avoid`), `treatment_rationale`, and
`treatment_review_by`. Unlike severity, `undecided` may survive approval; the only gate is that
`accept` without a `treatment_rationale` is refused. The table rows above carry these fields and
the closed vocabulary is section 4.8, added alongside the model per the conformance test's
both-directions rule.

DEC-066 adds `content_fingerprint` on the same terms: a derived SHA-256 over the sorted
`requirement_ids` and the sorted, normalized affected-component names — structural fields only,
no prose — for cross-run identity alongside the allocated identifier, never instead of it.
`DocumentationGap` gets the same treatment through the requirement its mapping reaches.

## Example

id: fnd-003

assessment_id: asm-001

title: Webhook requests may be processed without verified authenticity

summary: >

The webhook receiver may accept repository events without validating

that they originated from the configured repository provider.

description: >

The architecture documents describe an internet-accessible webhook

endpoint but do not identify a request-signature validation control.

If authenticity validation is absent, an attacker could submit forged

events and trigger unauthorized analysis jobs.

threat_ids:

- thr-007

requirement_ids:

- req-WEBHOOK-001

control_mapping_ids:

- map-011

affected_component_ids:

- cmp-004

affected_asset_ids:

- ast-002

- ast-005

evidence_ids:

- evd-031

validation_status: partially_supported

severity: unassigned

impact: >

Unauthorized job execution, resource exhaustion, and potential exposure

of repository-related data.

recommendation: >

Validate each webhook request using the repository provider's supported

signature mechanism before accepting or queuing the event.

assumptions:

- No undocumented signature validation exists.

confidence: medium

status: candidate

generated_by: finding-consolidation-v1

This example remains a candidate because the absence of documented signature validation is not proof that validation is absent.

Two of its values were corrected by DEC-050, which records why. It carried `severity: high` on a
candidate, and DEC-030 has findings created `unassigned` because the reviewer assigns severity at
checkpoint 2. It carried `validation_status: requires_confirmation`, which is a status DEC-013's
outcome table produces no finding from — a finding is reachable only from `supported` or
`partially_supported`. An example is read as a template, so one carrying values the schema refuses
is a specification of an object nobody can build.

# 21a. FindingMergeRecord

## Purpose

Records one finding merge: which finding survived, which findings were merged into it, which
structural features matched, and whether the decision was structural or model-assisted.

Added by DEC-052, after the rest of these sections were numbered. `agent-design.md` section 11
requires the merge decision to stay explicit and traceable, and a decision recorded only in a
node's return value stops being traceable when the process exits. Every merge writes one record.

The identifier fields are finding identifiers by type, which is half of the DEC-009 enforcement: a
record naming a `DocumentationGap` does not validate, so a merge across the finding/gap boundary
is unrepresentable rather than merely forbidden.

## Fields

| Field | Type | Required | Description |
|---|---|---|---|
| id | string | Yes | Stable merge-record identifier |
| assessment_id | string | Yes | Parent assessment |
| surviving_finding_id | string | Yes | The canonical finding the merge kept |
| merged_finding_ids | list[string] | Yes | Findings merged into the survivor; each carries `duplicate_of_id` |
| matched_features | list[string] | No | Structural features that matched; empty only on a reviewer merge (DEC-052, DEC-054) |
| decision | MergeDecision | Yes | Structural or model-assisted (DEC-052) |
| detail | string | Yes | Human-readable account of the match |
| generated_by | string | Yes | Workflow node or reviewer |
| created_at | datetime | Yes | Merge timestamp |

`MergeDecision` has three values (DEC-052, amended by DEC-054): `structural`, a merge the
deterministic identifier rule decided; `model_assisted`, a merge a reviewer decided from a
model-proposed candidate pair; and `reviewer`, a merge the checkpoint 2 reviewer decided
unprompted. The node only ever writes `structural`; a model-assisted comparison proposes pairs
and merges nothing.

`matched_features` values name what overlapped: `threats`, `requirements`, `control_mappings`,
`components`, `assets`. The first two decide a structural merge; the rest corroborate. The list
may be empty only when `decision` is `reviewer` — the rule's reason is its features, while a
reviewer's reason lives on the `ReviewerDecision` rationale (DEC-054).

# 22. Question

## Purpose

Represents missing information that could materially affect the assessment.

## Fields

| Field | Type | Required | Description |
|---|---|---|---|
| id | string | Yes | Stable question identifier |
| assessment_id | string | Yes | Parent assessment |
| question | string | Yes | Reviewer-facing question |
| rationale | string | Yes | Why the answer matters |
| related_object_type | string | No | Threat, component, mapping, etc. |
| related_object_id | string | No | Referenced object |
| priority | string | Yes | Low, medium, high |
| blocking | boolean | Yes | Surfaced first at the next checkpoint; pauses nothing (DEC-054) |
| response | string | No | User response |
| response_origin | SourceOrigin | No | Response source |
| answered_at | datetime | No | Response timestamp |
| status | string | Yes | Open, answered, dismissed |
| generated_by | string | Yes | Workflow node or reviewer |
| converted_from_id | string | No | The object this was converted from (DEC-051) |

## Example

id: qst-006

assessment_id: asm-001

question: >

Does the webhook receiver validate the provider signature before

creating an analysis job?

rationale: >

The answer determines whether forged webhook events are a supported

security finding or only an unverified control.

related_object_type: threat

related_object_id: thr-007

priority: high

blocking: true

status: open

generated_by: evidence-validation-v1

# 23. DocumentationGap

## Purpose

Represents missing or inadequate documentation without asserting that the implementation itself is vulnerable.

## Fields

| Field | Type | Required | Description |
|---|---|---|---|
| id | string | Yes | Stable gap identifier |
| assessment_id | string | Yes | Parent assessment |
| title | string | Yes | Gap title |
| description | string | Yes | Missing documentation |
| importance | string | Yes | Why the gap matters |
| related_object_ids | list[string] | No | Related components, threats, or controls |
| requested_evidence | list[string] | No | Documentation needed |
| severity | Severity | Yes | Importance of documentation gap |
| status | ObjectStatus | Yes | Candidate, approved, resolved |
| generated_by | string | Yes | Workflow node or reviewer |
| evidence_ids | list[string] | No | Evidence showing ambiguity or contradiction |
| converted_from_id | string | No | The object this was converted from (DEC-051) |
| content_fingerprint | string | No | Derived cross-run identity, resolved through the related mapping (DEC-066) |

## Important distinction

A documentation gap means:

Trace cannot determine whether a control exists or is effective.

A finding means:

Available evidence supports the conclusion that a meaningful security weakness exists.

# 23a. CatalogGapCandidate

## Purpose

Represents a credible security concern that no requirement in the active catalog covers, flagged
as catalog-maintenance input and routed to the catalog owner (DEC-065). Added by DEC-065 after
the surrounding sections were numbered, the same way sections 10a and 21a were.

A candidate is about the catalog's coverage, not the system's controls. It is not an assessment
conclusion: no report section renders it, finding consolidation never reads it, and it is not a
checkpoint subject. It feeds the next catalog version through a human authoring decision
(DEC-057) and carries no authority of its own.

The schema deliberately carries no severity, no validation status, and no recommendation. A
shape that could be read as a finding would let the DEC-009 collapse happen through a side door,
so that shape is unrepresentable.

## Fields

| Field | Type | Required | Description |
|---|---|---|---|
| id | string | Yes | Stable candidate identifier |
| assessment_id | string | Yes | Parent assessment |
| concern | string | Yes | The uncovered security concern, in prose |
| suggested_category | string | Yes | Suggested primary category, open vocabulary (DEC-036) |
| nearest_requirements | list[object] | Yes | Requirements considered and why each does not fit; non-empty (DEC-065) |
| evidence_ids | list[string] | Yes | Evidence grounding the concern; non-empty |
| generated_by | string | Yes | The agent that raised it |
| created_at | datetime | Yes | Creation timestamp |

Each `nearest_requirements` entry carries `requirement_id` and `why_not`, both required. The
list is the quality gate: DEC-024's whole-catalog posture is what makes "no requirement covers
this" a claim an agent can actually make, and the named near-misses are what make it falsifiable.

# 24. Critique

## Purpose

Represents a structured challenge to a generated threat, mapping, or finding.

## Fields

| Field | Type | Required | Description |
|---|---|---|---|
| id | string | Yes | Stable critique identifier |
| assessment_id | string | Yes | Parent assessment |
| subject_type | CritiqueSubjectType | Yes | Object being challenged; closed by DEC-049 |
| subject_id | string | Yes | Object identifier |
| critique_type | CritiqueType | Yes | Closed by DEC-049 over the examples below, less `missing_high_impact_threat` |
| description | string | Yes | Criticism |
| rationale | string | Yes | Supporting explanation |
| evidence_ids | list[string] | No | Supporting evidence |
| recommended_action | RecommendedAction | Yes | Keep, revise, reject, merge, investigate (DEC-049) |
| confidence | ConfidenceLevel | Yes | Critique confidence |
| status | ObjectStatus | Yes | Review state |
| generated_by | string | Yes | Critic node or reviewer |

## Critique-type examples

unsupported_claim

missing_evidence

ignored_inherited_control

duplicate

severity_overstated

severity_understated

missing_precondition

weak_attack_path

generic_recommendation

documentation_gap_only

contradictory_analysis

missing_high_impact_threat

`missing_high_impact_threat` is **not** a `CritiqueType` value. A missing threat has no target
object, which `agent-design.md` section 15 makes invalid output, and proposing one is the
threat-generation loop section 27's worked example forbids. DEC-049 records the exclusion and
what it costs.

# 25. ReviewerDecision

## Purpose

Records a human decision affecting an assessment object.

## Fields

| Field | Type | Required | Description |
|---|---|---|---|
| id | string | Yes | Stable decision identifier |
| assessment_id | string | Yes | Parent assessment |
| subject_type | string | Yes | Object type reviewed |
| subject_id | string | Yes | Object reviewed |
| disposition | ReviewDisposition | Yes | Reviewer action |
| prior_value | map[string, any] | No | Relevant prior state |
| updated_value | map[string, any] | No | Updated state |
| rationale | string | No | Reviewer explanation |
| reviewer_id | string | No | Reviewer identifier |
| created_at | datetime | Yes | Decision timestamp |
| workflow_run_id | string | No | Related workflow run |

## Note on prior_value and updated_value

These hold **only the fields that changed**, before and after — not a whole-object snapshot
(DEC-023). Reviewer edit rate is a primary evaluation metric, and "the reviewer changed the
severity and left everything else" is more useful than "the reviewer changed this finding."

A reviewer edit **mutates the object in place** and writes one of these records. Section 2.5 forbids
overwriting generated content *silently*; recording the delta is what makes the overwrite
non-silent. History is reconstructed by replaying decisions in order against the object's generated
state, which satisfies section 2.6 without the event sourcing it declines.

`reviewer_id` is a configured local string defaulting to the operating-system username. It exists so
evaluation can attribute decisions when more than one person reviews the same benchmark. It is not
authentication and must not be treated as such — DEC-004 has none to draw from.

## Example

id: dec-019

assessment_id: asm-001

subject_type: finding

subject_id: fnd-003

disposition: convert_to_question

rationale: >

The documentation does not establish whether signature validation is

absent. Confirm implementation before treating this as a finding.

created_at: 2026-08-05T15:30:00-06:00

workflow_run_id: run-001

# 26. WorkflowRun

## Purpose

Represents one execution of the assessment workflow.

An assessment may have multiple workflow runs due to retries, revisions, or evaluations.

## Fields

| Field | Type | Required | Description |
|---|---|---|---|
| id | string | Yes | Stable run identifier |
| assessment_id | string | Yes | Parent assessment |
| workflow_version | string | Yes | Workflow version |
| status | string | Yes | Pending, running, paused, completed, failed |
| started_at | datetime | No | Start time |
| completed_at | datetime | No | Completion time |
| current_node | string | No | Current workflow node |
| model_profile | string | Yes | Model configuration used |
| prompt_versions | map[string, string] | Yes | Prompt versions |
| total_model_calls | integer | Yes | Model-call count |
| total_input_tokens | integer | No | Uncached input-token count |
| total_output_tokens | integer | No | Output-token count |
| total_cache_read_tokens | integer | No | Sum of the records' cache reads (DEC-067) |
| total_cache_creation_tokens | integer | No | Sum of the records' cache writes (DEC-067) |
| estimated_cost | decimal | No | Estimated cost, cache-weighted (DEC-067) |
| error_summary | string | No | Final error if failed |
| ablations | list[string] | No | Ablations the evaluation harness applied; empty for an ordinary run |

## Note on ablation marking

An ablated run names its ablations here, and a run with a non-empty list is non-authoritative
(DEC-012, DEC-031, DEC-073). The field is written at run creation by the evaluation harness —
the only caller that constructs an ablated run — and never by assessment configuration, which
carries no ablation switch. Replaying recorded reviewer decisions is not an ablation and leaves
the list empty.

## Note on failure

A failed run does not fail its assessment. `status` becomes `failed` and the assessment stays
`draft`, because an assessment with a failed run is one somebody may run again — this object
already permits several runs per assessment. There is deliberately no failed-shaped
`Assessment.status` (DEC-031).

## Note on pausing

A run pauses by persisting itself and letting the process exit (DEC-017). `status` becomes
`paused`, `current_node` names the checkpoint, and the assessment state's `pending_human_review`
block names the objects awaiting a decision. Nothing is held in memory across a human review, and
a paused run waits indefinitely — there is no review timeout.

Resuming is a separate invocation that loads the run and verifies that every object named in
`pending_human_review` has a `ReviewerDecision`.

Earlier versions carried a `checkpoint_reference` field holding a persistence reference to a
framework checkpoint. DEC-016 removed the framework and DEC-017 removed the field: `current_node`
says where the run stopped and `pending_human_review` says what it is waiting for.

# 27. ExecutionRecord

## Purpose

Represents one workflow node execution or deterministic processing step.

## Fields

| Field | Type | Required | Description |
|---|---|---|---|
| id | string | Yes | Stable execution identifier |
| workflow_run_id | string | Yes | Parent workflow run |
| assessment_id | string | Yes | Parent assessment |
| node_name | string | Yes | Workflow node |
| node_version | string | Yes | Node implementation version |
| execution_type | string | Yes | Model, deterministic, human checkpoint |
| prompt_version | string | No | Prompt used |
| model_name | string | No | Model used |
| input_object_ids | list[string] | No | Referenced inputs |
| output_object_ids | list[string] | No | Created or modified outputs |
| started_at | datetime | Yes | Start time |
| completed_at | datetime | No | Completion time |
| status | string | Yes | Running, completed, failed, retried |
| retry_number | integer | Yes | Retry count |
| error_type | string | No | Error classification |
| error_message | string | No | Safe error message |
| duration_ms | integer | No | Execution duration |
| input_tokens | integer | No | Uncached model input tokens at the full rate |
| output_tokens | integer | No | Model output tokens |
| cache_read_tokens | integer | No | Input served from the provider's cache (DEC-067) |
| cache_creation_tokens | integer | No | Input written into the provider's cache (DEC-067) |
| estimated_cost | decimal | No | Estimated call cost, cache-weighted (DEC-067) |
| metadata | map[string, any] | No | Additional execution details |

## Note on cache accounting

DEC-067's fields, with rollups `total_cache_read_tokens` and `total_cache_creation_tokens` on
`WorkflowRun`. The three input spans are disjoint — `input_tokens` means uncached input at the
full rate — and `estimated_cost` is the weighted sum at the model profile's rates: cache reads
at the provider's discount, cache creation at its premium, uncached input and output at list.
Absent cache fields mean "not reported," readable against the capability record DEC-014 keeps
on this object.

# 28. EvaluationResult

## Purpose

Represents a measured quality or performance result.

## Fields

| Field | Type | Required | Description |
|---|---|---|---|
| id | string | Yes | Stable evaluation identifier |
| assessment_id | string | Yes | Parent assessment |
| workflow_run_id | string | Yes | Evaluated workflow run |
| metric_name | string | Yes | Metric identifier |
| metric_value | number | Yes | Metric value |
| unit | string | No | Percentage, count, seconds, dollars |
| evaluator_type | string | Yes | Automated, reviewer, benchmark |
| evaluation_method | string | Yes | How result was measured |
| sample_size | integer | No | Number of evaluated objects |
| notes | string | No | Limitations or interpretation |
| created_at | datetime | Yes | Evaluation timestamp |

## Initial metric names

finding_evidence_coverage

unsupported_claim_count

reviewer_acceptance_rate

reviewer_rejection_rate

reviewer_edit_rate

duplicate_finding_rate

clarifying_question_usefulness

threat_coverage

requirement_mapping_accuracy

execution_duration

model_call_count

estimated_cost

node_failure_rate

# 29. PromptDefinition

## Purpose

Represents a versioned prompt used by a model-assisted workflow node.

The prompt body may remain stored in a file, while metadata is available to the application.

## Fields

| Field | Type | Required | Description |
|---|---|---|---|
| id | string | Yes | Prompt name: a lowercase slug, outside the identifier scheme (DEC-034) |
| version | string | Yes | Prompt version |
| name | string | Yes | Prompt name |
| purpose | string | Yes | Intended task |
| file_path | string | Yes | Version-controlled prompt file |
| expected_input_schema | string | Yes | Input model name or schema |
| expected_output_schema | string | Yes | Output model name or schema |
| model_constraints | list[string] | No | Required model capabilities |
| status | string | Yes | Draft, active, retired |
| content_hash | string | Yes | `sha256:<hex>` over the **composed** prompt text (DEC-019) |

# 30. RequirementsCatalog

## Purpose

Represents a versioned collection of reusable requirements.

## Fields

| Field | Type | Required | Description |
|---|---|---|---|
| id | string | Yes | Catalog name: a lowercase slug, outside the identifier scheme (DEC-034) |
| name | string | Yes | Catalog name |
| version | string | Yes | Catalog version |
| description | string | No | Catalog purpose |
| requirement_ids | list[string] | Yes | Included requirements |
| created_at | datetime | Yes | Creation timestamp |
| status | string | Yes | Draft, active, retired |
| content_hash | string | Yes | `sha256:<hex>` over a canonical re-serialization (DEC-019) |

## Note on identity

A catalog is identified by `(id, version)`, not by `id` alone: the slug names the family and the
version names the edition, and DEC-010 gives each version its own directory. Everything that refers
to a catalog refers to the version — `Assessment.requirements_catalog_version`, each requirement's
own `catalog_version`, and the `catalog_version` a benchmark scenario pins under DEC-027. Nothing
joins on `id`.

# 31. Assessment State

## Purpose

Represents the workflow-facing state used by the orchestrator.

The workflow state should primarily contain identifiers and concise routing information. Large objects should be stored in the persistence layer and retrieved when needed.

## Proposed Structure

assessment_id: asm-001

workflow_run_id: run-001

status: running

current_phase: evidence_validation

next_action: execute_node

source_document_ids:

- src-001

- src-002

system_context_version: 2

context_claim_ids:

- ctx-001

- ctx-002

component_ids:

- cmp-001

- cmp-002

- cmp-003

asset_ids:

- ast-001

- ast-002

data_flow_ids:

- df-001

- df-002

trust_boundary_ids:

- tb-001

- tb-002

candidate_threat_ids:

- thr-001

- thr-002

control_mapping_ids:

- map-001

candidate_finding_ids:

- fnd-001

open_question_ids:

- qst-001

documentation_gap_ids: []

pending_human_review:

checkpoint_type: context_review

object_ids:

- ctx-001

- ctx-002

execution_limits:

model_calls_remaining: 12

cost_remaining: 3.40

errors: []

## State-design rule

Do not place full source documents, full prompt transcripts, or every generated object into one continuously growing workflow-state payload.

## Note on `pending_human_review`

This block is what makes a paused run self-describing (DEC-017). `checkpoint_type` names which of
the two checkpoints the run stopped at, and `object_ids` names every object awaiting a reviewer
decision.

The checkpoint's completion condition is that every identifier in `object_ids` has a
`ReviewerDecision`. Partial progress is allowed and persisted; a run with some objects decided
stays paused.

The review package shown to the reviewer is **derived** from the run rather than stored in it, so
the pause mechanism does not presuppose an interface.

# 32. Object Lineage

Trace should preserve relationships showing how a conclusion was produced.

A finding should be traceable through this chain:

Source Document

↓

Evidence Reference

↓

Context Claim

↓

Threat

↓

Requirement and Control Mapping

↓

Evidence Assessment

↓

Critique

↓

Finding

↓

Reviewer Decision

↓

Final Report

Not every finding will use every object, but every significant conclusion should have understandable lineage.

# 33. Schema Validation

The implementation should use Pydantic models for domain validation.

Validation should occur:

- When input enters the application
- After model-generated structured output
- Before objects are persisted
- Before workflow transitions
- Before report generation

Validation errors should not be silently discarded.

The workflow should:

1. Preserve the invalid output for debugging.
2. Return validation feedback to the generating node when appropriate.
3. Retry within configured limits.
4. Stop or request human review if valid output cannot be produced.

# 34. Model-Generated Output

Model-generated objects should include generation metadata.

At minimum:

generated_by: context-extraction-v1

workflow_run_id: run-001

execution_record_id: exe-013

model_name: configured-model

prompt_version: extract-context-v1

generated_at: 2026-08-05T14:20:00-06:00

This metadata may be stored directly on the object or through a linked execution record.

The MVP should prefer linked execution records to avoid duplicating large amounts of metadata.

# 35. Data Persistence

The proposed MVP persistence model is:

### SQLite

Store:

- Assessments
- Context objects
- Components
- Assets
- Data flows
- Trust boundaries
- Threats
- Requirements metadata
- Controls
- Mappings
- Findings
- Questions
- Documentation gaps
- Reviewer decisions
- Workflow runs
- Execution records
- Evaluation results

### Local filesystem

Store:

- Original documents
- Normalized documents
- Prompt files
- Requirements catalog files
- Generated reports
- Debug artifacts
- Exported traces
- Evaluation fixtures

The database should store references and content hashes for filesystem artifacts.

## The split is by authorship, not size

Three stores, divided by whether a person wrote the artifact or a run produced it (DEC-020):

- **Version-controlled files** — the requirements catalog, prompt files, and benchmark expected
  outputs. Inputs to an assessment, edited in pull requests, reviewed in diffs.
- **SQLite** — everything an assessment generates.
- **`data/`, not version-controlled** — generated files too large or too binary for a row, in the
  per-assessment layout of `current-architecture.md` section 5.16.

A requirement is a file because a person wrote it; a threat is a row because a run produced it.

## How objects are stored

Generated objects are stored as **JSON payloads with identity and routing lifted into columns**:
one table keyed by `(assessment_id, id)`, with `object_type`, `status`, and `created_at` as columns
and the validated object serialized into a payload column.

Pydantic is the only schema. SQLite stores no field definitions, so adding, removing, or retyping a
field is a Pydantic change rather than a database migration — which matters while section 39's open
questions are still producing schema changes.

Referential integrity lives in application code, where the validation nodes already perform it. A
foreign key would express only half of each check: a mapping must reference a threat *in the same
assessment*, and a documented claim must carry evidence.

Identifier counters have their own table keyed by `(assessment_id, prefix)`, incremented in the
same transaction as the insert that consumes the number (DEC-018).

A repository is scoped to one assessment, so the assessment-data boundary is structural rather than
a rule each query must remember.

## Schema versioning

Every assessment records `data_model_version`. Loading one written by an incompatible version fails
with a message naming both versions; there is no migration machinery during early development
(DEC-020).

Re-running is cheaper than migrating and measurably so — `scripts/estimate_cost.py` puts an
assessment at $2.25 to $5.97. The trigger to add migrations is an assessment becoming expensive or
irreplaceable.

# 36. Data Retention

The MVP uses fictional or public demo data, but retention should still be explicit.

Trace should support deleting an assessment and its associated:

- Database objects
- Source documents
- Generated reports
- Debug artifacts
- Traces
- Cached model responses

External model providers or tracing services may retain data independently. Their retention behavior must be evaluated before real or sensitive data is used.

# 37. Data Export

The MVP should eventually support exporting an assessment as a portable package.

Possible structure:

assessment-export/

manifest.json

assessment.json

context.json

threats.json

controls.json

findings.json

decisions.json

evaluation.json

report.md

evidence/

sources/

This is not required for the first implementation milestone, but the data model should not prevent it.

# 38. Deferred Objects

The following objects are intentionally deferred unless implementation demonstrates a clear need:

- User
- Organization
- Team
- Tenant
- Policy exception
- Risk acceptance
- Remediation ticket
- Pull request
- Source-code finding
- Vulnerability scan result
- Cloud asset
- Deployment
- Repository
- Compliance framework
- Attack graph
- Exploit
- Remediation workflow
- Notification
- Fine-grained access-control object

These can be added later without expanding the initial MVP unnecessarily.

# 39. Open Data-Model Questions

1. Should context claims use a flexible subject-predicate-value structure or more specific typed models?
2. ~~Should evidence excerpts be duplicated in the database or loaded from normalized source files?~~ Resolved by DEC-015: `quoted_text` is stored verbatim from the original and is immutable, with `content_hash` covering it. Where the row is stored is a persistence question (DEC-012's successor), not a location one.
3. ~~How should evidence locations be represented consistently across Markdown, text, JSON, YAML, and future PDF inputs?~~ Resolved by DEC-015.
4. ~~Should actors be separate first-class objects in the MVP?~~ Resolved by DEC-037: yes. `SystemContext` gains `actor_ids`, and section 40's list gains `Actor`. An extracted actor that the approved baseline does not reference would be approved by nobody and reachable by nothing.
5. How should requirement applicability conditions be represented in machine-readable form? Catalog version 0.1 leaves them as free text deliberately, so the vocabulary can be observed before it is fixed. DEC-024 confirms they stay free text for now: with `applicable_technologies` populated on zero requirements there is nothing to filter on deterministically, so the whole catalog is passed and applicability is the agent's judgment.
6. ~~How should inherited-control scope be modeled?~~ Resolved by DEC-026: with the fields `Control` already has. `inheritance_scope` is removed.
7. ~~Should confidence scores be generated numerically or only categorically?~~ Resolved by DEC-022: categorically only. `confidence_score` is removed, and `EvidenceStrength` moves onto `EvidenceAssessment` so model confidence and evidence strength stay separate, as design principle 15 requires.
8. How should multiple model outputs proposing the same object be merged?
9. How should object revisions be stored?
10. ~~Should reviewer edits create new object versions or update the current object with decision history?~~ Resolved by DEC-023: update in place with decision history. Section 2.6 already declined full event sourcing, and `ReviewerDecision`'s `prior_value` and `updated_value` exist for exactly this.
11. How much model-generation metadata belongs on each object?
12. Should workflow state store objects directly or only identifiers?
13. ~~Which objects belong in SQLite versus version-controlled YAML or JSON?~~ Resolved by DEC-020: the split is by authorship. Authored artifacts are version-controlled files; generated objects are rows; generated files live under `data/`.
14. ~~How should severity be calculated?~~ Resolved by DEC-030: it is not calculated. The reviewer assigns it at the finding checkpoint, findings are created `unassigned`, and an approval carrying `unassigned` is rejected. No agent and no deterministic node proposes a value.
15. ~~What is the minimum evidence required to approve a finding?~~ Resolved by DEC-013.
16. How should rejected threats and findings be retained for evaluation?
17. ~~How should data-model migrations be handled during early development?~~ Resolved by DEC-020: they are not. An incompatible `data_model_version` refuses to load, and the assessment is re-run — which the cost estimate makes cheaper than writing a migration against a schema still under decision.

Consequential answers should be recorded in decision log.md.

# 40. Initial Implementation Priority

The first implementation should not build every object in this document.

Implement these first:

1. Assessment
2. AssessmentConfiguration
3. SourceDocument
4. EvidenceReference
5. SystemContext
6. ContextClaim
7. SourceObservation
8. Component
9. Asset
10. Actor
11. DataFlow
12. TrustBoundary
13. Threat
14. Requirement
15. Control
16. ControlMapping
17. Finding
18. Question
19. DocumentationGap
20. ReviewerDecision
21. WorkflowRun
22. ExecutionRecord
23. RequirementsCatalog
24. EvidenceAssessment
25. Critique
26. FindingMergeRecord
27. EvaluationResult
28. CatalogGapCandidate

`SourceObservation` (section 10a) was added by DEC-021 after this list was written, and the list
was not updated with it. It is not optional: DEC-021 makes contradictions and detected
prompt-injection attempts one object of this type, the context extraction step produces them, and
DEC-027 gives every benchmark scenario an `expected-observations.yaml` to grade them against. It
sits after `ContextClaim` because `subject_claim_ids` references claims.

`Actor` (section 13) was on neither list, and open question 4 asked whether actors are first-class
objects at all. DEC-037 answers it: they are, `SystemContext.actor_ids` references them, and the
entry above places `Actor` after `Asset` and before `DataFlow`.

`CatalogGapCandidate` (section 23a) was added by DEC-065 after this list was written. It sits
last: the Threat Analysis and Mapping agents raise it as an optional output, nothing downstream
consumes it, and the M12 decision-debt milestone is where it was built.

`RequirementsCatalog` (section 30) was on the deferred list, on the grounds that it should arrive
once the workflow operates. It arrives earlier than that, and not by preference: DEC-019 makes its
`content_hash` a value computed and verified at catalog load, DEC-024 puts the whole catalog into
every mapping call, and the requirement-matcher step needs a loader before either. A catalog read
without a manifest object is a catalog with no integrity marker and no single place that says what
version was used, so it sits last on this list rather than on the next one.

Add PromptDefinition once the main workflow begins operating.

`EvaluationResult` (section 28) was on that deferred list and is promoted by DEC-056: the M4
finding-quality metrics persist their results as rows, because `evaluation-plan.md` section 3
requires evaluations to be comparable across versions and comparability is a property of stored
rows rather than console output. It sits last on the list above because it references the
`WorkflowRun` it evaluates and nothing references it.

`Critique` (section 24) was on that deferred list too, and arrives for the same reason stated
differently: the critic is the fifth of section 36's six agents and roadmap Stage 4 sets a
decision gate on whether it improves results at all. The gate cannot be reached without the
object, and DEC-049 fixes the vocabularies section 24 left as prose examples.

`FindingMergeRecord` (section 21a) was added by DEC-052 after this list was written, the same way
`SourceObservation` was. It sits last because it references `Finding` and nothing references it:
a merge record that outran the object it records would be a record of nothing.

`EvidenceAssessment` (section 20) was on that deferred list and arrives with the mapping step
instead, which is the condition the list states. Two reasons make it earlier rather than
optional: DEC-022 gave it `evidence_strengths` as the only home for `EvidenceStrength`, and
DEC-013's `unmet` rule reads its `validation_status`, so the object is a dependency of a rule
the mapping slice already applies. DEC-046 records that the half of that rule which reads this
object waits for Finding Consolidation, which is only coherent if the object exists.

The data model should serve the workflow. The workflow should not become complicated merely to exercise every possible object.
