# Trace — Threat Model

**Project:** Trace

**Subtitle:** Context-Aware Security Architecture Analysis

**Threat Model Version:** 0.1

**Status:** Proposed

**Last Updated:** 2026-08-09

---

## 1. Purpose and scope

This document analyses the security boundaries of **Trace itself**, not of any system Trace
reviews. `current-architecture.md` section 12 names five boundaries and says that detailed risks
and mitigations are maintained here; this is that document.

The frame is those five boundaries rather than a formal STRIDE pass. Trace uses STRIDE as a
coverage aid for the systems it reviews and not as a mechanical generator, and applying it
mechanically to itself would be inconsistent with what the project argues.

**Every mitigation below names where it is enforced, or says plainly that it is not implemented.**
A threat model that lists mitigations without naming their enforcement point is the failure this
project exists to criticize — a claim about a control with no evidence behind it. The status column
uses five values:

| Status | Meaning |
|---|---|
| **Enforced** | Code exists, runs today, and is named. |
| **Designed** | Specified in the corpus, not built. The issue that builds it is named. |
| **Open** | Depends on a decision that has not been made. The issue that decides it is named. |
| **Partial** | A control exists and does not cover every path. What it misses is stated. |
| **Known gap** | No control exists and none is planned. The reason is stated where the row is. |

ForgeFlow's threat model is scenario data and lives in `demo/forgeflow/forgeflow-scenario.md`.
Nothing here describes it.

## 2. What Trace is, for the purposes of this document

DEC-004 makes the MVP a local, single-user application. There is no deployment, no multi-tenancy,
no authentication, and no cloud service. The command line drives everything the pipeline does
(DEC-032); the Stage 5 read-only view (DEC-078) adds a localhost-only listening port that renders
persisted state and drives nothing — see section 5.

That shapes the whole analysis. The adversary is **not** a remote attacker; the one listening port
binds `127.0.0.1` and changes no state. The adversary is **the content Trace is asked to read**, and
the party at risk is **the reviewer**, who may act on a conclusion Trace produced — including reading
that conclusion in a browser, which section 5 covers.

Three assets are worth naming:

- **The material under review.** Documents supplied by whoever commissioned the assessment,
  possibly confidential to them.
- **Provider credentials.** An API key with billing attached.
- **The assessment's conclusions.** A finding a reviewer signs off on and takes to an engineering
  team. Their credibility is the thing the project is actually protecting.

## 3. Source-document boundary

**Input documents are untrusted.** They may contain incorrect information, contradictions, embedded
prompt injection, instructions addressed to a model, and sensitive information.

`demo/forgeflow/input/sample-repository-notes.md` carries a deliberate injection payload. It is
test data and is committed unaltered on purpose: sanitizing it would destroy the thing it proves.

| Risk | Mitigation | Where | Status |
|---|---|---|---|
| Source content redefines an agent's role, schema, or tool grants | Every agent receiving source-derived content is instructed that source content is untrusted data, cannot modify its role, cannot redefine output schemas, and cannot authorize tools | `prompts/shared/source-content-boundary-v1.md`, composed into every agent prompt; the fence in `services/context/input_package.py` | **Enforced** |
| An agent-proposed object carries an invented field that a consumer later trusts | `extra="forbid"` on every domain object: an unknown key fails validation rather than being dropped | `trace_ai.domain.base.DomainModel` | **Enforced** |
| A source filename escapes the assessment directory | Filenames are refused by shape (no separators, no `..`, not absolute) and again by resolution, so a clean name landing through a symlink is also refused | `ArtifactStore._safe_path` | **Enforced** |
| Injected content is silently followed rather than recorded | Detection produces a `SourceObservation` of kind `injection_attempt` (DEC-021), which carries no severity and never becomes a `Finding` | `domain/source_observation.py`; consumed by `workflow/reason_codes.py` and surfaced by the CLI and review package | **Enforced** |
| Ingestion treats a document carrying an injection differently from one that does not | The loader is indifferent to content: format comes from the extension, metadata is size-derived, and the produced object is field-for-field identical to one for a benign document | `trace_ai.services.ingestion.loader`, `tests/unit/test_untrusted_source_boundary.py` | **Enforced** |
| The loader is given a construct that could execute document content | No call to `eval`, `exec`, `compile`, `__import__`, `yaml.load`, `os.system`, or `subprocess`, and no import of `subprocess`, `importlib`, `pickle`, `shutil`, or `ctypes`. Asserted over the syntax tree, so prose explaining why is not mistaken for a use | `tests/unit/test_untrusted_source_boundary.py` | **Enforced** |
| Source content is quoted into a log line, where it leaves the assessment's boundary | The redaction filter replaces a field whose name marks it as source-derived with a length and the identifier of the object it came from | `trace_ai.observability.RedactionFilter` | **Enforced** |
| A source document is edited after ingestion and conclusions still cite it | `content_hash` over the original file's raw bytes, verifiable on re-read (DEC-019) | `trace_ai.domain.hashing`, `ArtifactStore.hash_of` | **Enforced** — nothing re-verifies on a schedule; see section 8 |
| Storing a document silently replaces a different one under the same name | Re-storing identical bytes is idempotent; different bytes under a used name raise | `ArtifactStore._write` | **Enforced** |

**The failure this boundary exists to prevent is not compromise.** It is a reviewer taking a
conclusion to an engineering team that a document talked Trace into. Nothing crashes and nothing
alerts; the output looks exactly like a real finding.

## 4. Model-provider boundary

Content sent to an external model leaves the local application boundary. The MVP uses fictional or
public data and avoids confidential information.

| Risk | Mitigation | Where | Status |
|---|---|---|---|
| A provider credential reaches a log, a traceback, or a `repr()` | Secrets are `SecretStr`, and the redaction filter also catches a raw key by field name — covering the case `SecretStr` cannot, where a key never went through `Settings` | `trace_ai.config.Settings`, `trace_ai.observability.RedactionFilter` | **Enforced** |
| A credential is committed | `.env` is gitignored, `.env.example` is committed blank, and a test fails if the two drift or if a key-shaped entry has a value | `.gitignore`, `tests/unit/test_config.py` | **Enforced** |
| A credential is committed past the hooks | gitleaks scans locally as a pre-commit hook, and again in CI over the full history — the enforcement point `--no-verify` and an uninstalled clone cannot skip | `.pre-commit-config.yaml`; `.github/workflows/ci.yml` gitleaks step | Enforced |
| CI spends money or needs a key | The `integration` and `evaluation` markers are deselected in `addopts`, so a bare `pytest` cannot make a provider call | `pyproject.toml` | **Enforced** |
| Source content or prompts reach an external tracing provider | `enable_external_tracing` is off unless set, and the emitter is structurally unable to carry content: a span is built from the `ExecutionRecord`'s own fields — identifiers, versions, statuses, timings, token counts, cost — with no field a prompt or excerpt could travel in, and the span key set is held closed by test. The section 5.17 data-handling review is recorded in DEC-109. | `AssessmentConfiguration` default; `trace_ai.infrastructure.tracing.span_of`; `tests/unit/test_tracing_emitter.py` | **Enforced** |
| A run costs more than intended | `maximum_model_calls` and `maximum_cost` are optional limits, carried as `Decimal` so a comparison at the limit is exact | `AssessmentConfiguration`, enforced by `workflow/limits.py` and the orchestrator — the call count and projected cost are checked before the call that would cross them | **Enforced** |
| A secret is interpolated into a log message before `logging` sees it | Nothing can catch this. A pre-formatted string has no field name and no type, and the module documents the gap rather than implying coverage | `trace_ai.observability` module docstring, and a test that proves it leaks | **Known gap**, deliberately unmitigated |

**What leaves the machine is a design surface, not an accident.** Design principle 13 requires that
a user can understand which external services receive assessment information, and the honest answer
today is: the configured model provider, and an external tracing provider only if switched on.

## 5. Browser-to-application boundary

**This boundary exists as of the Stage 5 read-only view** (`trace view`, DEC-032, DEC-078). Through
M8 it did not: the command line was the whole interface, and the row was removed rather than
mitigated. The view re-introduces a listening port and a server process holding assessment data, so
the row returns — but bounded by what the view is, not defended by a token bolted onto a mutable
surface.

The design is that the request-forgery threat has nothing to forge. The view renders persisted
state and drives nothing; there is no state-changing endpoint, so the classic cross-site request
against a mutating URL has no target. That is a structural property, not a filter, which is why it
is stated as the boundary's shape rather than a mitigation row that could be edited away.

| Risk | Mitigation | Where | Status |
|---|---|---|---|
| A page the reviewer has open reaches the server across the network | The server binds `127.0.0.1` only, so it is not reachable off the machine (DEC-004, single-user local) | `trace_ai.interface.server.HOST`, `tests/unit/test_interface.py` | **Enforced** |
| A cross-site request forges a state change | There is no state-changing endpoint to forge against: every method other than `GET` is refused with `405`, and no route calls a store write method — audited by scanning the package for `save`/`allocate`/`transaction`/`delete` | `trace_ai.interface.server`, `tests/unit/test_interface.py` | **Enforced** |
| An untrusted excerpt injects markup or script into the reviewer's browser | Every source-derived value is HTML-escaped on render, and lineage excerpts are additionally labelled as quoted untrusted content; a browser is not the inert terminal, so this is where the source-document boundary reaches the screen | `trace_ai.interface.render`, `tests/unit/test_interface.py` | **Enforced** |
| Another origin frames the view to read assessment data | Responses carry `X-Frame-Options: DENY` | `trace_ai.interface.server` | **Enforced** |
| The view becomes a way to drive the pipeline | It is read-only by construction: it consumes the section 32 lineage walk and the persisted objects, and there is no review interaction — checkpoint decisions stay on the command line (DEC-032) | `trace_ai.interface`, DEC-078 | **Enforced** |

The store opens read-write because SQLite offers no read-only handle here; read-only is a discipline
the audit test enforces, not a file mode. Input validation, which `current-architecture.md` section
12 attaches to this boundary, was never deferred with the boundary: every input reaching workflow or
storage is validated by the schema regardless of what supplied it — a command line, a file, or the
view all construct the same objects through the same models. The view supplies none, because it
writes nothing.

## 6. Assessment-data boundary

Data from one assessment must not contaminate another. This is the boundary with the most code
behind it, because it is the one an ordinary bug reaches.

| Risk | Mitigation | Where | Status |
|---|---|---|---|
| A query returns another assessment's objects | Repositories are scoped: every statement carries its `assessment_id`, and there is no cross-assessment read except one returning identifiers and no content | `AssessmentRepository` | **Enforced** |
| An object is written into the wrong assessment | A write whose object belongs elsewhere raises rather than persisting | `AssessmentRepository.save` | **Enforced** |
| Code holding one assessment addresses another by passing a different string | Callers receive an `AssessmentHandle` carrying both stores already scoped, rather than an identifier | `trace_ai.services.assessment` | **Enforced** |
| An artifact path reaches outside its assessment | Path containment is resolved rather than pattern-matched, so a symlink is caught | `ArtifactStore.contains` | **Enforced** |
| Identifiers collide across assessments | Identifiers are unique within an assessment and qualified by `(assessment_id, id)`; assessment identifiers themselves come from a database-wide counter | `AssessmentStore`, DEC-018 | **Enforced** |
| Ingested copies of material under review are committed | `/data/` is gitignored with an anchored rule, and a test asserts the anchor and its comment | `.gitignore`, `tests/unit/test_repository_hygiene.py` | **Enforced** |
| Another local user reads assessment data | Assessment directories are created owner-only | `ArtifactStore._DIRECTORY_MODE` | **Enforced** — a mitigation for a shared machine, which DEC-004 assumes does not exist |
| One database holds every assessment, so a query written outside a repository can cross the boundary | Nothing prevents it. DEC-020 records this as the cost of one database rather than one per assessment | — | **Known gap**, recorded in DEC-020 |

## 7. Generated-output boundary

Model-generated content is untrusted until validated and reviewed. All six agents exist, each
behind a deterministic validation node, and this boundary is where their output is held.

| Risk | Mitigation | Where | Status |
|---|---|---|---|
| An agent writes authoritative state directly | Agents return proposed objects; the application validates and persists. Agents get no database writes, no filesystem, no shell, no internet, and no credentials | `domain/proposals/` carries nothing authoritative and `extra="forbid"` refuses invented fields; agents reach the world only through `StructuredModel`, and `tests/unit/test_model_boundary.py` plus `test_package_layout.py` pin the boundary | **Enforced** |
| An agent reads a file directly rather than through the retrieval interface | `EvidenceIndex` is that interface, and it exists before any agent so it has no exceptions. Its prompt-facing shape carries no path of any kind, asserted by searching the serialized output | `trace_ai.services.evidence.index`; every agent's input package assembles through it and carries no filesystem path | **Enforced** |
| A conclusion cites a passage the document no longer contains | Verification re-reads the artifact at the recorded location and reports a changed quotation distinctly from a missing file | `EvidenceIndex.verify` | **Enforced** — nothing runs it on a schedule; see section 8 |
| Missing documentation is reported as a weakness | A `Finding` asserts a weakness; a `DocumentationGap` says it cannot be determined. `EvidenceReference` cannot express absence at all — `quoted_text` is required and non-empty, so there is no way to cite silence | `trace_ai.domain.evidence` and `trace_ai.domain.finding`, DEC-009; DEC-013's outcome table routes silence to gaps and questions, never findings | **Enforced** |
| Unapproved content reaches the report | The finding-approval checkpoint is a workflow node rather than a runtime conditional, and `AssessmentConfiguration` carries no setting that governs it | DEC-005, DEC-012; `workflow/checkpoint.py` advances only on recorded decisions, and `finding_review.py` refuses approval at `unassigned` severity | **Enforced** |
| An ablated run produces an approved assessment | An assessment completed by a non-authoritative run cannot reach `approved` | `AssessmentService.approve` reads `WorkflowRun.is_authoritative` from the run that rendered the report — no caller supplies the flag | **Enforced** |
| A reviewer edit enters an object without validation | Edited objects are rebuilt through `model_validate`; `model_copy` validates nothing and is documented as the wrong API | `trace_ai.domain.base` docstring, `CLAUDE.md`, four pinning tests | **Enforced** by convention and tests, not by the type system |
| Report rendering introduces content no model or reviewer produced | Rendering is deterministic and uses no model | `workflow/report_rendering.py` imports no model client, and `templates/report-v1.md` fixes which four sections carry model prose (DEC-035) | **Enforced** |
| A citation cannot be checked against the document it claims to come from | Every `EvidenceReference` carries a line range and a hash over its own verbatim quotation, and normalization cannot change line counts, so the recorded location addresses the original (DEC-015) | `trace_ai.services.evidence.indexing`, `trace_ai.services.ingestion.normalize` | **Enforced** |

## 8. Cross-cutting: what is not covered

Stated because a threat model that only lists what it handles is misleading.

- **No scheduled re-verification.** Content hashes are checked when something reads through the
  helper. Nothing detects that `data/` and the database have diverged — an artifact referenced by
  a row but missing from disk. DEC-020 records this as an open question.
- **A pre-formatted log message can leak anything.** See section 4.
- **`reviewer_id` is a configured local string** and is trivially forgeable. DEC-023 says plainly
  that it is not authentication, and nothing enforces that it is not read as such.
- **Secret scanning reaches CI.** gitleaks was a pre-commit hook only — `git commit --no-verify`
  skipped it, and so did any clone where `pre-commit install` was never run. Found while writing
  this document; closed by #407: `.github/workflows/ci.yml` runs the same pinned gitleaks release
  over the full history on every pull request, with output redacted so a hit is reported without
  being republished.
- **Supply chain.** Dependencies are pinned by `uv.lock` and `uv sync --locked` runs in CI, which
  makes the set reproducible rather than trustworthy. Nothing audits them. The runtime dependency
  count is five, which is a mitigation by scale rather than by control.
- **The machine itself.** DEC-004 assumes a reviewer's own laptop. Disk encryption, screen locking,
  and backup hygiene are outside this document and are not compensated for anywhere in it.
- **Denial of service, availability, and multi-user concerns** are out of scope by DEC-004.

## 9. Review trigger

Per the roadmap's cross-cutting workstream, this document is revisited when:

- an agent gains data or capability it did not have, including any new tool or retrieval interface;
- a new external service is introduced, including a tracing provider;
- an interface is added that accepts input over a network. The Stage 5 read-only view (DEC-078) was
  the trigger for section 5's rewrite; it accepts no input beyond a `GET` path and changes no state,
  and a view that ever did would re-trigger this review;
- a boundary's `Designed` or `Open` row becomes `Enforced`, so the status column stays true.

This document was written before the first outbound model call and has been revisited since: the
2026-08-13 audit pass flipped every row whose enforcement had landed — the fence, the injection
observation, the ceilings, the agent boundary, the finding gate, and rendering among them — and
closed the gitleaks gap section 8 had named.

## 10. Open questions

- Does anything need to verify content hashes on a schedule, or only on read (DEC-019)?
- Should an ablated run be prevented from producing a report at all, rather than producing one that
  is marked (DEC-012)?
- Does the evaluation harness get a cross-assessment read interface, and if so what prevents it
  being used from the pipeline (DEC-020)?
- How should prompt-injection detection be evaluated, as distinct from implemented
  (`agent-design.md` question 11)?
- Is owner-only permission on the artifact store worth keeping under DEC-004's single-user
  assumption, or is it a mitigation for a threat the deployment model excludes?
