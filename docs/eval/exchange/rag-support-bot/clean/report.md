# Security Architecture Assessment: rag-support-bot + Mantis packet (clean)

Assessment asm-001 · generated 2026-09-11T14:52:59.079101+00:00 · template report-v1

<!-- owner: agent -->
<a id="s01-executive-summary"></a>
## 1. Executive summary

This assessment reviewed the Relay Answers support assistant and its associated retrieval, ingestion, and supporting services based on the supplied architecture, API, operations, and review documentation. The review produced one approved finding, rated high severity: cross-workspace ticket corruption in the shared retrieval index due to unscoped source identifiers, allowing one workspace’s support-ticket–derived embeddings to overwrite, delete, or be exposed to another workspace, with resulting loss of integrity and confidentiality for support-history context. The documentation also records several important controls: a governed ingestion pipeline as the only writer to the retrieval index, running on a scheduled basis from two named content sources; restriction of the managed vector database so it is reachable only from the answer service’s network segment; workspace-scoped bearer-token authentication on the Relay Answers API; masking and time-limited retention of resolved support tickets in the external support platform; TLS protection for traffic from the answer service to the external model provider; and provider terms that exclude training on submitted Relay Answers content. No documentation gaps were recorded, but multiple open questions remain about how workspace identity from the bearer token is enforced on retrieval index reads and writes, how the vector database enforces logical tenant separation, what additional redaction or classification is applied to ticket content before embedding, how the system is reached from outside, and who operates and configures it; these uncertainties limit how far this assessment can speak to end-to-end authorization, tenant isolation, and data-protection posture.

<!-- owner: rendered -->
<a id="s02-scope"></a>
## 2. Scope

- Assessment: asm-001 — rag-support-bot + Mantis packet (clean)
- Description: Phase 5-A exchange: scenario inputs plus the Mantis run-2 review packet as an untrusted uploaded document
- Model profile: openrouter-economy
- Threat methodology: stride-scenario-based
- Evidence threshold: direct-or-confirmed

| Document | Identifier | Ingestion status |
| --- | --- | --- |
| architecture-overview.md | src-001 | ingested |
| mantis-review-packet.md | src-002 | ingested |
| openapi.yaml | src-003 | ingested |
| operations-notes.md | src-004 | ingested |

<!-- owner: agent -->
<a id="s03-system-overview"></a>
## 3. System overview

The system under assessment is a retrieval-augmented support assistant that serves signed-in Relay workspace users through a Help panel. The Help panel relies on the Relay Answers API, which is protected by a workspace-scoped bearer token representing the caller’s workspace identity. Content for answers is drawn from two primary sources: help-center documentation and resolved support tickets. The Documentation team manages help-center documentation content in a help-center repository, and Support team reviewers work with support ticket content in an external support platform. On a scheduled basis, a governed ingestion pipeline runs as the only writer to the retrieval index. It reads from the published help-center repository and from a resolved-tickets export produced by the support platform, chunks and embeds that content, and writes the resulting vectors and associated metadata into a managed vector database that serves as the retrieval embeddings index. Each indexed item records its source and timestamp. The retrieval index resides within a dedicated vector database network segment and is documented as reachable only from the answer service’s network segment, limiting direct network access to the index. When answering user queries, the answer service communicates with an external model provider over TLS, sending help-center and support-ticket–derived content as part of retrieval-augmented prompts. The model provider’s terms for this traffic exclude training on submitted content, so these prompts are not used to train the provider’s models. Across the system, key assets include the help-center documentation corpus, support ticket content, the retrieval embeddings index derived from these sources, and the workspace bearer tokens that authenticate and scope access to the Relay Answers API. The primary trust boundary highlighted in the context is the vector database network segment containing the retrieval index, which separates the index from other parts of the environment and is intended to constrain how it can be reached.

<!-- owner: rendered -->
<a id="s04-architecture-summary"></a>
## 4. Architecture summary

| Component | Identifier | Type | Internet accessible |
| --- | --- | --- | --- |
| Relay Answers API | cmp-001 | api_service | None |
| Help panel | cmp-002 | web_client | None |
| Retrieval index | cmp-003 | vector_database | None |
| Ingestion pipeline | cmp-004 | batch_job | None |
| Model provider | cmp-005 | llm_api | True |
| Support platform | cmp-006 | support_platform | None |
| Help-center repository | cmp-007 | content_repository | None |

| Actor | Identifier | Type |
| --- | --- | --- |
| Relay signed-in workspace user | act-001 | end_user |
| Support team reviewers | act-002 | internal_staff |
| Documentation team | act-003 | internal_staff |

| Data flow | Identifier | From | To | Encryption in transit |
| --- | --- | --- | --- | --- |
| Help-center repository to ingestion pipeline | df-001 | cmp-007 | cmp-004 | unknown |
| Resolved-tickets export to ingestion pipeline | df-002 | cmp-006 | cmp-004 | unknown |
| Ingestion pipeline writes embeddings to retrieval index | df-003 | cmp-004 | cmp-003 | unknown |

<!-- owner: rendered -->
<a id="s05-assets-and-trust-boundaries"></a>
## 5. Assets and trust boundaries

| Asset | Identifier | Type |
| --- | --- | --- |
| Help-center documentation content | ast-001 | documentation |
| Support ticket content | ast-002 | customer_support_data |
| Retrieval embeddings index | ast-003 | derived_embeddings |
| Workspace bearer token | ast-004 | credential |

| Trust boundary | Identifier | Type |
| --- | --- | --- |
| Vector database network segment | tb-001 | network_segment |

<!-- owner: agent -->
<a id="s06-risk-summary"></a>
## 6. Risk summary

The approved risk picture is dominated by a single high-severity finding in the shared retrieval index. Because source identifiers in the index are not properly scoped by workspace, one workspace’s support-ticket–derived embeddings can overwrite or delete those of another, and ticket-derived content from one workspace can be exposed in answers to another. This compromises both integrity and confidentiality of the retrieval corpus across tenants: a workspace may lose or have its own support-history context corrupted, and may also see content derived from other workspaces’ tickets. The confirmed controls show that ingestion into the index is governed and centralized, network access to the vector database is constrained, the API is authenticated with workspace-scoped bearer tokens, support tickets are masked for email addresses and retained for a limited period, traffic to the model provider is encrypted, and submitted content is not used for model training. However, the high-severity issue indicates that authorization and tenant isolation at the retrieval-index layer are not adequately enforced for the scenarios covered by the assessment. The open questions cluster around the same themes: how workspace identity from the bearer token is enforced on index reads and writes, how logical tenant separation is implemented within the vector database, the extent of redaction and classification applied to ticket content before embedding, and the system’s exposure and operational model. Until these questions are resolved and any required design or control changes are verified, the system remains exposed to cross-workspace corruption and leakage risks in its retrieval corpus, and the overall authorization and data-protection posture cannot be fully characterized beyond the single confirmed high-severity weakness and the controls already documented.

<!-- owner: rendered -->
<a id="s07-significant-threats"></a>
## 7. Significant threats

<a id="thr-002"></a>
### thr-002: Cross-workspace ticket corruption via unscoped source identifiers in the retrieval index

Scenario where, if the retrieval index identifies ticket-derived chunks solely by a source_ref built from ticket_id as described in candidate record B.1, tickets from one workspace can overwrite or delete embeddings belonging to another workspace, leading to cross-tenant data corruption and potential leakage through the assistant.

Impact: Integrity of the retrieval index and support-ticket–derived knowledge is compromised across tenants: one workspace’s tickets can overwrite or delete another’s embeddings, which can both leak another workspace’s ticket content through answers and corrupt or erase a workspace’s own support-history context (evd-014, evd-015, evd-024).

<!-- owner: rendered -->
<a id="s08-approved-findings"></a>
## 8. Approved findings

<a id="fnd-002"></a>
### fnd-002: Cross-workspace ticket corruption via unscoped source identifiers in the retrieval index (req-AUTHZ-001)

req-AUTHZ-001 is partially_satisfied for thr-002.

Relay Answers serves more than one customer workspace through the in-product help panel (evd-001, evd-002, evd-017, evd-025), and support-ticket data for those workspaces is held together in a single shared retrieval index (evd-002, evd-023, ast-003), so data belonging to distinct organizations is stored in shared infrastructure. This matches req-AUTHZ-001's conditions for tenant-aware authorization in a multi-tenant system.

- Severity: high
- Confidence: medium
- Validation status: partially_supported
- Affected components: cmp-004, cmp-003, cmp-001, cmp-002, cmp-006
- Affected assets: ast-002, ast-003
- Impact: Integrity of the retrieval index and support-ticket–derived knowledge is compromised across tenants: one workspace’s tickets can overwrite or delete another’s embeddings, which can both leak another workspace’s ticket content through answers and corrupt or erase a workspace’s own support-history context (evd-014, evd-015, evd-024).
- Recommendation: Establish whether req-AUTHZ-001 is met for thr-002, and record the control that meets it.

Evidence:

[evd-017 — openapi.yaml, info, lines 2-7]

```
info:
  title: Relay Answers API
  version: "1.2"
  description: >
    The in-product surface the help panel calls. One operation asks a question;
    the workspace token identifies the caller's workspace.
```

[evd-019 — openapi.yaml, components, lines 22-27]

```
components:
  securitySchemes:
    workspaceToken:
      type: http
      scheme: bearer
      description: The signed-in user's workspace-scoped session token.
```

[evd-020 — openapi.yaml, security, lines 28-29]

```
security:
  - workspaceToken: []
```

[evd-025 — openapi.yaml, info, lines 2-7]

```
info:
  title: Relay Answers API
  version: "1.2"
  description: >
    The in-product surface the help panel calls. One operation asks a question;
    the workspace token identifies the caller's workspace.
```

[evd-027 — openapi.yaml, components, lines 22-27]

```
components:
  securitySchemes:
    workspaceToken:
      type: http
      scheme: bearer
      description: The signed-in user's workspace-scoped session token.
```

[evd-028 — openapi.yaml, security, lines 28-29]

```
security:
  - workspaceToken: []
```

[evd-002 — architecture-overview.md, Components, lines 7-25]

```
## Components

- **Help panel** — the in-product chat surface. Available to every signed-in user of any
  workspace on any plan.
- **Answer service** — receives the question, runs retrieval, assembles the prompt, calls the
  model provider, and returns the answer with its citations.
- **Retrieval index** — a managed vector database holding embeddings of the help-center
  articles and of resolved support tickets. All workspaces are served from one shared index;
  a query returns the top eight passages ranked by embedding similarity, and relevance alone
  selects the passages that reach the prompt.
- **Ingestion pipeline** — the only writer to the retrieval index. It runs nightly, reads two
  named sources — the published help-center repository and the support platform's resolved
  tickets export — chunks and embeds them, and records the source and timestamp on every
  indexed item. Help-center content is published through the documentation team's review
  process before the pipeline ever sees it.
- **Model provider** — a hosted large-language-model API. The answer service sends the user's
  question and the retrieved passages; workspace identifiers and user identifiers are stripped
  from the request first.

```

<!-- owner: rendered -->
<a id="s09-documentation-gaps"></a>
## 9. Documentation gaps

The assessment recorded no documentation gaps. Every requirement it applied could be evaluated
against the documentation provided. This is not a statement that the documentation is complete —
only that its silences did not block a conclusion the assessment tried to reach.

<!-- owner: rendered -->
<a id="s10-assumptions"></a>
## 10. Assumptions

| Claim | Status | Statement | Rationale |
| --- | --- | --- | --- |
| ctx-026 | inferred | cmp-003: source_identification | The Mantis packet's candidate record B.1 (status PROVISIONALLY_VALID, unreproduced) provides a detailed description of how retrieval-index methods derive and use source_ref; this is treated as a provisional account of implementation details rather than a confirmed property. |
| ctx-027 | inferred | cmp-003: search_scope | The description comes from Mantis candidate record B.2, which is marked PROVISIONALLY_VALID and unreproduced; it is included as a provisional characterization of how search is currently wired rather than a confirmed vulnerability. |
| ctx-028 | inferred | cmp-004: deletion_handling | This behavior is described in Mantis candidate record B.3 (status PROVISIONALLY_VALID, unreproduced) and is treated as provisional detail about how the ingestion pipeline handles deletions and partial exports. |
| ctx-029 | inferred | ast-004: default_configuration_risk | The behavior is described in Mantis candidate record B.4 (status PROVISIONALLY_VALID, unreproduced); it is captured as a provisional account of configuration defaults rather than a confirmed vulnerability. |

<!-- owner: rendered -->
<a id="s11-open-questions"></a>
## 11. Open questions

- qst-004 (medium): Beyond masking customer email addresses, are any additional redaction or classification controls applied to support ticket content before it is embedded and added to the retrieval index (for example for secrets, configuration snippets, or other sensitive data)?
- qst-005 (medium): No actor in the context is anonymous or external. If the system is reachable from outside, who reaches it? If it is not, what establishes that?
- qst-006 (medium): No actor in the context is administrative or privileged. Who operates and configures the system, and through what?
- qst-007 (medium): Can you confirm design or implementation documentation describing how retrieval requests are scoped or filtered by workspace when querying the shared index; any tests or formal verification artifacts demonstrating compliance with req-RAG-002?
- qst-008 (medium): Can you confirm documentation or code excerpts showing how workspace identity from the bearer token is enforced on reads and writes to the shared retrieval index; tests demonstrating that users from one workspace cannot retrieve or modify artifacts belonging to another workspace?
- qst-009 (medium): Can you confirm design or configuration documentation describing logical tenant separation or access-control mechanisms within the vector database; evidence (tests, audits, or configuration) that enforces req-DATA-003 for embeddings and associated metadata?
- qst-010 (medium): Can you confirm the full text of req-RAG-001, including its specific success criteria for governing writes to the retrieval corpus; design or implementation documentation showing how the ingestion pipeline meets each element of req-RAG-001 (e.g., validation steps, error handling, provenance tracking, and controls preventing unauthorized writers)?

<!-- owner: rendered -->
<a id="s12-existing-controls"></a>
## 12. Existing controls

<a id="ctl-001"></a>
### ctl-001: Governed ingestion pipeline writes the retrieval corpus

The ingestion pipeline is documented as the only writer to the retrieval index, running nightly to read two named sources (the published help-center repository and the support platform's resolved-tickets export), chunk and embed their content, and record the source and timestamp on each indexed item.

<a id="ctl-002"></a>
### ctl-002: Retrieval index reachable only from the answer service's network segment

The retrieval index is a managed vector-database offering whose standard-tier instance is documented as reachable only from the answer service's network segment, limiting direct network access to the index.

<a id="ctl-003"></a>
### ctl-003: Support platform ticket masking and two-year retention

The external support platform retains resolved support tickets for two years and then deletes them under a customer-agreed retention schedule, and applies email-address masking before tickets are exported for ingestion.

<a id="ctl-004"></a>
### ctl-004: Workspace-scoped bearer token authentication for the Answers API

The Relay Answers API is secured with an HTTP bearer token security scheme named workspaceToken, described as the signed-in user's workspace-scoped session token; the API description states that the workspace token identifies the caller's workspace, and this scheme is applied as the default security requirement for the answers endpoint.

<a id="ctl-005"></a>
### ctl-005: Model provider excludes assistant traffic from training

The architecture overview states that the model provider's terms for Relay Answers traffic exclude training on submitted content, so prompts containing help-center passages and support-ticket text are not used to train the provider's models.

<a id="ctl-006"></a>
### ctl-006: Requests to model provider use TLS

The architecture overview records that requests from the answer service to the external model provider are sent over TLS, encrypting help-center and support-ticket content in transit to the provider.

<!-- owner: rendered -->
<a id="s13-recommended-actions"></a>
## 13. Recommended actions

- [high] fnd-002: Establish whether req-AUTHZ-001 is met for thr-002, and record the control that meets it.

<!-- owner: rendered -->
<a id="s14-methodology"></a>
## 14. Methodology

This assessment was produced by Trace, a context-aware security architecture analysis pipeline: documents are ingested and indexed as evidence, an approved system context is extracted and reviewed at a human checkpoint, threats are analysed against it, requirements are mapped and their evidence validated, and findings are consolidated and approved at a second human checkpoint before this report is rendered. Model-assisted steps propose; deterministic validation and human review decide. Absence of documentation is never treated as proof of a vulnerability.

### Source coverage

Every supplied document appears in exactly one bucket (DEC-071); unexamined material is listed, never silent.

| Document | Identifier | Coverage | Why |
| --- | --- | --- | --- |
| architecture-overview.md | src-001 | reviewed | ingested; its evidence was available to every stage |
| mantis-review-packet.md | src-002 | reviewed | ingested; its evidence was available to every stage |
| openapi.yaml | src-003 | reviewed | ingested; its evidence was available to every stage |
| operations-notes.md | src-004 | reviewed | ingested; its evidence was available to every stage |

- Architecture version: 0.1
- Workflow version: 0.2
- Prompt versions: generate-report-sections generate-report-sections-v1
- Requirements catalog version: 0.2
- Model: openai/gpt-5.1
- Model configuration: openrouter-economy

<!-- owner: rendered -->
<a id="s15-evidence-appendix"></a>
## 15. Evidence appendix

<a id="evd-002"></a>
[evd-002 — architecture-overview.md, Components, lines 7-25]

```
## Components

- **Help panel** — the in-product chat surface. Available to every signed-in user of any
  workspace on any plan.
- **Answer service** — receives the question, runs retrieval, assembles the prompt, calls the
  model provider, and returns the answer with its citations.
- **Retrieval index** — a managed vector database holding embeddings of the help-center
  articles and of resolved support tickets. All workspaces are served from one shared index;
  a query returns the top eight passages ranked by embedding similarity, and relevance alone
  selects the passages that reach the prompt.
- **Ingestion pipeline** — the only writer to the retrieval index. It runs nightly, reads two
  named sources — the published help-center repository and the support platform's resolved
  tickets export — chunks and embeds them, and records the source and timestamp on every
  indexed item. Help-center content is published through the documentation team's review
  process before the pipeline ever sees it.
- **Model provider** — a hosted large-language-model API. The answer service sends the user's
  question and the retrieved passages; workspace identifiers and user identifiers are stripped
  from the request first.

```

<a id="evd-003"></a>
[evd-003 — architecture-overview.md, Prompt assembly, lines 26-32]

```
## Prompt assembly

The prompt places retrieved passages inside a delimited context block, and the system
instructions state that content inside the block is reference material, not instructions. The
answer is returned with the source reference of each cited passage. Answers are rendered in the
help panel as plain text; the panel does not execute or interpret model output.

```

<a id="evd-004"></a>
[evd-004 — architecture-overview.md, Data handling, lines 33-38]

```
## Data handling

Resolved support tickets are retained on the support platform for two years and then deleted
under the retention schedule agreed with customers. The help-center repository is public
documentation. The model provider's terms for the assistant's traffic exclude training on
submitted content, and requests are sent over TLS.
```

<a id="evd-014"></a>
[evd-014 — mantis-review-packet.md, Appendix: Low Priority Findings, lines 60-74]

```
## Appendix: Low Priority Findings

No LOW-priority candidate is listed as a reportable finding because none met the mandatory actionable-quality predicate. The evidence gap applies to these four canonical candidate issue classes:

1. Global vector search may disclose support tickets across workspaces.
2. Unscoped source identifiers may allow cross-workspace replacement and deletion.
3. Missing token configuration may activate public development credentials.
4. Partial exports may retain deleted or corrected ticket data indefinitely.

These remain **unverified candidates**, not confirmed vulnerabilities in this packet. Obtain and persist reproduction commands, output, artifact paths, and evidence snapshot IDs, then recalibrate.

---

`review_packet-latest.md` is the authoritative current campaign view. Per-pass packets remain historical references.

```

<a id="evd-015"></a>
[evd-015 — mantis-review-packet.md, Appendix B: Candidate records (exported from the campaign knowledge base), lines 75-106]

```
## Appendix B: Candidate records (exported from the campaign knowledge base)

The four canonical candidate records referenced above, as recorded by the researcher stage. Status on every record is `PROVISIONALLY_VALID`: the review and critic stages did not confirm them, and no reproduction was attempted.

### B.1 Unscoped source identifiers allow cross-workspace replacement and deletion

- Status: `PROVISIONALLY_VALID` · Severity (as emitted): MEDIUM · CWE: CWE-639 · Signature: `101b3cc3c3705eae`
- Attacker position: None · Privileges required: None

RetrievalIndex.replace_source and remove_source identify objects solely by source_ref, while ticket source_ref is derived only from ticket_id. Workspace ownership and source kind are not part of the key or removal predicate. Consequently, duplicate ticket IDs in different workspace export rows cause the later row to remove and replace the earlier tenant's chunks; a tombstone for either row removes every chunk with that shared reference. chunk_id is likewise derived from the unscoped source_ref and position, so direct dictionary assignment also collides. This violates tenant-owned object invariants even if retrieval is later scoped correctly.

### B.2 Global vector search discloses support tickets across workspaces

- Status: `PROVISIONALLY_VALID` · Severity (as emitted): HIGH · CWE: CWE-862 · Signature: `4d80ffbe5116c4d3`
- Attacker position: None · Privileges required: None

The answer endpoint authenticates the bearer token and obtains a workspace_id, but uses that identity only for quota charging. It calls RetrievalIndex.search without an authorization scope. search scores every chunk in the process-global index, including private ticket chunks belonging to other workspaces, and returns the global top-k. Those unauthorized chunks are placed into the provider prompt and their chunk_id/source_ref values are serialized as citations. The existing two-workspace regression test concretely demonstrates a Globex request retrieving Acme ticket tickets/t-100. Candidate filtering must occur inside the index before similarity scoring and top-k selection; post-filtering would still permit ranking, cardinality, and timing leakage and could return fewer authorized results.

### B.3 Partial exports retain deleted or corrected ticket data indefinitely

- Status: `PROVISIONALLY_VALID` · Severity (as emitted): MEDIUM · CWE: CWE-459 · Signature: `9c79e0bbd3a5fbb3`
- Attacker position: None · Privileges required: None

run_nightly updates only rows present in the current export and propagate_deletions removes content only for explicit tombstone rows included in that same export. There is no generation marker, complete-snapshot contract, high-water mark, reconciliation against the set of active source keys, or persistent deletion ledger. If an export is partial, interrupted, or omits deleted records, old chunks remain in the process-global index without an expiration path. Reused identifiers and ownership corrections are also applied only when a replacement row happens to arrive.

### B.4 Missing token configuration activates public development credentials

- Status: `PROVISIONALLY_VALID` · Severity (as emitted): HIGH · CWE: CWE-798 · Signature: `ab1592ba67fc7feb`
- Attacker position: None · Privileges required: None

load_settings substitutes a hard-coded mapping containing dev-token-acme and dev-token-globex whenever WORKSPACE_TOKENS is unset or an empty string. main.py calls load_settings at import with no explicit development-mode gate or production startup validation. The credentials are present in source and documentation/test usage, so an externally reachable deployment missing one environment variable silently grants predictable workspace identities instead of refusing startup.

```

<a id="evd-017"></a>
[evd-017 — openapi.yaml, info, lines 2-7]

```
info:
  title: Relay Answers API
  version: "1.2"
  description: >
    The in-product surface the help panel calls. One operation asks a question;
    the workspace token identifies the caller's workspace.
```

<a id="evd-019"></a>
[evd-019 — openapi.yaml, components, lines 22-27]

```
components:
  securitySchemes:
    workspaceToken:
      type: http
      scheme: bearer
      description: The signed-in user's workspace-scoped session token.
```

<a id="evd-020"></a>
[evd-020 — openapi.yaml, security, lines 28-29]

```
security:
  - workspaceToken: []
```

<a id="evd-023"></a>
[evd-023 — operations-notes.md, The index, lines 12-18]

```
## The index

The nightly ingestion run replaces changed chunks by source reference. Tickets arrive in the
resolved-tickets export with customer email addresses masked by the support platform before
export. The index is the only copy of the embeddings; the vector database is the managed
offering's standard tier, reachable only from the answer service's network segment.

```

<a id="evd-024"></a>
[evd-024 — operations-notes.md, Known items, lines 19-24]

```
## Known items

- Ticket text sometimes quotes configuration snippets customers pasted into support
  conversations. The masking step covers email addresses only.
- The help panel ships to every plan, including trials.
- Answer quality review is a weekly manual sample of twenty answers by the support team.
```

<a id="evd-025"></a>
[evd-025 — openapi.yaml, info, lines 2-7]

```
info:
  title: Relay Answers API
  version: "1.2"
  description: >
    The in-product surface the help panel calls. One operation asks a question;
    the workspace token identifies the caller's workspace.
```

<a id="evd-027"></a>
[evd-027 — openapi.yaml, components, lines 22-27]

```
components:
  securitySchemes:
    workspaceToken:
      type: http
      scheme: bearer
      description: The signed-in user's workspace-scoped session token.
```

<a id="evd-028"></a>
[evd-028 — openapi.yaml, security, lines 28-29]

```
security:
  - workspaceToken: []
```

<!-- owner: agent -->
<a id="s16-assessment-limitations"></a>
## 16. Assessment limitations

No limitations were required by the run's state.
