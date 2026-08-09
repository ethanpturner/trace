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

dec- Reviewer decision

run- Workflow run

exe- Execution record

eval- Evaluation result

UUIDs may be used internally, with readable prefixes added for debugging and demonstration.

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

A numeric confidence score may also be stored, but it should not create false precision.

Suggested interpretation:

| Level | Meaning |
|---|---|
| Low | Significant uncertainty or weak evidence |
| Medium | Plausible and partially supported |
| High | Strongly supported by evidence or user confirmation |

## 4.3 EvidenceStrength

Describes how strongly an evidence reference supports a claim.

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

## 4.5 Severity

Initial severity classification.

Possible values:

informational

low

medium

high

critical

unassigned

The MVP should avoid implementing an overly complex severity algorithm before the core workflow is validated.

## 4.6 ReviewDisposition

Possible reviewer actions.

approve

reject

edit

defer

request_more_analysis

convert_to_question

convert_to_documentation_gap

## 4.7 ValidationStatus

Used for claims, controls, and findings.

supported

partially_supported

unsupported

contradicted

requires_confirmation

not_evaluated

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

maximum_model_calls: 25

maximum_cost: 5.00

maximum_retries_per_node: 2

retain_debug_artifacts: true

enable_external_tracing: false

evidence_threshold: direct-or-confirmed

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
| content_hash | string | Yes | Hash of original content |
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
| content_hash | string | Yes | Evidence content hash |
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
| context_claim_ids | list[string] | Yes | Context claims |
| component_ids | list[string] | Yes | Components |
| asset_ids | list[string] | Yes | Assets |
| data_flow_ids | list[string] | Yes | Data flows |
| trust_boundary_ids | list[string] | Yes | Trust boundaries |
| approved_at | datetime | No | Context-approval timestamp |
| approved_by | string | No | Reviewer identifier |
| version | integer | Yes | Context revision number |

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
| confidence_score | decimal | No | Optional score from 0 to 1 |
| evidence_ids | list[string] | No | Supporting evidence |
| source_origin | SourceOrigin | Yes | Claim origin |
| generated_by | string | No | Workflow node or reviewer |
| reviewer_notes | string | No | Reviewer explanation |
| created_at | datetime | Yes | Creation timestamp |
| updated_at | datetime | Yes | Last update |
| supersedes_id | string | No | Prior claim replaced by this claim |

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

subject_id: cmp-identity

predicate: authentication_provider

value: enterprise_oidc

status: documented

confidence: high

evidence_ids:

- evd-014

source_origin: uploaded_document

generated_by: context-extraction-v1

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
| data_classifications | list[string] | No | Data processed or stored |
| authentication_mechanisms | list[string] | No | Authentication methods |
| authorization_mechanisms | list[string] | No | Authorization methods |
| evidence_ids | list[string] | No | Supporting evidence |
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
| data_classification | string | No | Classification |
| owner | string | No | Business or technical owner |
| component_ids | list[string] | No | Components holding or processing asset |
| evidence_ids | list[string] | No | Supporting evidence |
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
| capabilities | list[string] | No | Relevant actions or privileges |
| authentication_method | string | No | Authentication method |
| evidence_ids | list[string] | No | Supporting evidence |

## Actor-type examples

end_user

developer

administrator

service_identity

third_party_service

external_attacker

malicious_insider

compromised_dependency

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

- cmp-webhook-receiver

- cmp-job-worker

affected_asset_ids:

- ast-analysis-capacity

- ast-repository-metadata

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
| inheritance_scope | string | No | Scope of inherited protection |
| limitations | list[string] | No | Known limitations |
| status | ObjectStatus | Yes | Lifecycle state |

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
and records the downgrade.

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
| validation_status | ValidationStatus | Yes | Result |
| rationale | string | Yes | Explanation |
| missing_evidence | list[string] | No | Evidence still needed |
| contradictions | list[string] | No | Contradictory evidence |
| confidence | ConfidenceLevel | Yes | Confidence |
| generated_by | string | Yes | Workflow node or reviewer |
| created_at | datetime | Yes | Creation timestamp |

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
| status | ObjectStatus | Yes | Candidate, approved, rejected |
| generated_by | string | Yes | Workflow node or reviewer |
| created_at | datetime | Yes | Creation timestamp |
| updated_at | datetime | Yes | Last modification |
| duplicate_of_id | string | No | Canonical finding if duplicate |
| reviewer_notes | string | No | Reviewer explanation |

## Minimum validation rules

A provisional finding should not be created unless it has:

- At least one related threat
- At least one affected asset or component
- At least one applicable requirement or stated security expectation
- A described security impact
- Evidence or an explicit low-confidence justification
- A validation status
- A confidence classification

An approved finding should generally require:

- Reviewer approval
- Supported or partially supported evidence
- A clear distinction from a documentation gap
- Actionable remediation or acceptance criteria

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

- cmp-webhook-receiver

affected_asset_ids:

- ast-analysis-capacity

- ast-repository-metadata

evidence_ids:

- evd-031

validation_status: requires_confirmation

severity: high

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
| blocking | boolean | Yes | Whether workflow should pause |
| response | string | No | User response |
| response_origin | SourceOrigin | No | Response source |
| answered_at | datetime | No | Response timestamp |
| status | string | Yes | Open, answered, dismissed |
| generated_by | string | Yes | Workflow node or reviewer |

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

## Important distinction

A documentation gap means:

Trace cannot determine whether a control exists or is effective.

A finding means:

Available evidence supports the conclusion that a meaningful security weakness exists.

# 24. Critique

## Purpose

Represents a structured challenge to a generated threat, mapping, or finding.

## Fields

| Field | Type | Required | Description |
|---|---|---|---|
| id | string | Yes | Stable critique identifier |
| assessment_id | string | Yes | Parent assessment |
| subject_type | string | Yes | Object being challenged |
| subject_id | string | Yes | Object identifier |
| critique_type | string | Yes | Unsupported, duplicate, severity, etc. |
| description | string | Yes | Criticism |
| rationale | string | Yes | Supporting explanation |
| evidence_ids | list[string] | No | Supporting evidence |
| recommended_action | string | Yes | Keep, revise, reject, merge, investigate |
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
| checkpoint_reference | string | No | Persistence reference |
| model_profile | string | Yes | Model configuration used |
| prompt_versions | map[string, string] | Yes | Prompt versions |
| total_model_calls | integer | Yes | Model-call count |
| total_input_tokens | integer | No | Input-token count |
| total_output_tokens | integer | No | Output-token count |
| estimated_cost | decimal | No | Estimated cost |
| error_summary | string | No | Final error if failed |

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
| input_tokens | integer | No | Model input tokens |
| output_tokens | integer | No | Model output tokens |
| estimated_cost | decimal | No | Estimated call cost |
| metadata | map[string, any] | No | Additional execution details |

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
| id | string | Yes | Prompt identifier |
| version | string | Yes | Prompt version |
| name | string | Yes | Prompt name |
| purpose | string | Yes | Intended task |
| file_path | string | Yes | Version-controlled prompt file |
| expected_input_schema | string | Yes | Input model name or schema |
| expected_output_schema | string | Yes | Output model name or schema |
| model_constraints | list[string] | No | Required model capabilities |
| status | string | Yes | Draft, active, retired |
| content_hash | string | Yes | Prompt content hash |

# 30. RequirementsCatalog

## Purpose

Represents a versioned collection of reusable requirements.

## Fields

| Field | Type | Required | Description |
|---|---|---|---|
| id | string | Yes | Catalog identifier |
| name | string | Yes | Catalog name |
| version | string | Yes | Catalog version |
| description | string | No | Catalog purpose |
| requirement_ids | list[string] | Yes | Included requirements |
| created_at | datetime | Yes | Creation timestamp |
| status | string | Yes | Draft, active, retired |
| content_hash | string | Yes | Catalog hash |

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

- cmp-web

- cmp-api

- cmp-database

asset_ids:

- ast-source-code

- ast-access-token

data_flow_ids:

- df-web-api

- df-api-database

trust_boundary_ids:

- tb-internet

- tb-third-party

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
4. Should actors be separate first-class objects in the MVP?
5. How should requirement applicability conditions be represented in machine-readable form? Catalog version 0.1 leaves them as free text deliberately, so the vocabulary can be observed before it is fixed.
6. How should inherited-control scope be modeled?
7. Should confidence scores be generated numerically or only categorically?
8. How should multiple model outputs proposing the same object be merged?
9. How should object revisions be stored?
10. Should reviewer edits create new object versions or update the current object with decision history?
11. How much model-generation metadata belongs on each object?
12. Should workflow state store objects directly or only identifiers?
13. Which objects belong in SQLite versus version-controlled YAML or JSON?
14. How should severity be calculated?
15. ~~What is the minimum evidence required to approve a finding?~~ Resolved by DEC-013.
16. How should rejected threats and findings be retained for evaluation?
17. How should data-model migrations be handled during early development?

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
7. Component
8. Asset
9. DataFlow
10. TrustBoundary
11. Threat
12. Requirement
13. Control
14. ControlMapping
15. Finding
16. Question
17. DocumentationGap
18. ReviewerDecision
19. WorkflowRun
20. ExecutionRecord

Add Critique, EvidenceAssessment, PromptDefinition, RequirementsCatalog, and EvaluationResult once the main workflow begins operating.

The data model should serve the workflow. The workflow should not become complicated merely to exercise every possible object.
