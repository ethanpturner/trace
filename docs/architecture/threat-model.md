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
uses three values:

| Status | Meaning |
|---|---|
| **Enforced** | Code exists, runs today, and is named. |
| **Designed** | Specified in the corpus, not built. The issue that builds it is named. |
| **Open** | Depends on a decision that has not been made. The issue that decides it is named. |
| **Partial** | A control exists and does not cover every path. What it misses is stated. |

ForgeFlow's threat model is scenario data and lives in `demo/forgeflow/forgeflow-scenario.md`.
Nothing here describes it.

## 2. What Trace is, for the purposes of this document

DEC-004 makes the MVP a local, single-user application. There is no deployment, no multi-tenancy,
no authentication, and no network service. DEC-032 makes the interface a command line through M4,
so there is no browser and no listening port.

That shapes the whole analysis. The adversary is **not** a remote attacker; there is nothing
remote to attack. The adversary is **the content Trace is asked to read**, and the party at risk is
**the reviewer**, who may act on a conclusion Trace produced.

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
| Source content redefines an agent's role, schema, or tool grants | Every agent receiving source-derived content is instructed that source content is untrusted data, cannot modify its role, cannot redefine output schemas, and cannot authorize tools | `agent-design.md` section 25; the shared prompt block | **Designed** — #70 authors the block, #71 fences the content |
| An agent-proposed object carries an invented field that a consumer later trusts | `extra="forbid"` on every domain object: an unknown key fails validation rather than being dropped | `trace_ai.domain.base.DomainModel` | **Enforced** |
| A source filename escapes the assessment directory | Filenames are refused by shape (no separators, no `..`, not absolute) and again by resolution, so a clean name landing through a symlink is also refused | `ArtifactStore._safe_path` | **Enforced** |
| Injected content is silently followed rather than recorded | Detection produces a `SourceObservation` of kind `injection_attempt` (DEC-021), which carries no severity and never becomes a `Finding` | `data-model.md` section 10a | **Designed** — #140 builds the object, #74 tests the fixture |
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
| A credential is committed past the hooks | gitleaks scans staged content — but only locally. It is a pre-commit hook and **is not in the CI workflow**, so `--no-verify`, or a clone without `pre-commit install`, bypasses it entirely | `.pre-commit-config.yaml` | **Partial** — see section 8 |
| CI spends money or needs a key | The `integration` and `evaluation` markers are deselected in `addopts`, so a bare `pytest` cannot make a provider call | `pyproject.toml` | **Enforced** |
| Source content or prompts reach an external tracing provider | `enable_external_tracing` is off unless set, and section 5.17 requires a data-handling review before it is enabled | `AssessmentConfiguration`, default from `default_configuration()` | **Enforced** for the default; **Designed** for the tracing integration itself |
| A run costs more than intended | `maximum_model_calls` and `maximum_cost` are optional limits, carried as `Decimal` so a comparison at the limit is exact | `AssessmentConfiguration` | **Designed** — the fields exist; nothing enforces them until the orchestrator does |
| A secret is interpolated into a log message before `logging` sees it | Nothing can catch this. A pre-formatted string has no field name and no type, and the module documents the gap rather than implying coverage | `trace_ai.observability` module docstring, and a test that proves it leaks | **Known gap**, deliberately unmitigated |

**What leaves the machine is a design surface, not an accident.** Design principle 13 requires that
a user can understand which external services receive assessment information, and the honest answer
today is: the configured model provider, and an external tracing provider only if switched on.

## 5. Browser-to-application boundary

**This boundary does not exist in the MVP.** DEC-032 makes the command line the interface through
M4: there is no browser, no listening port, and no server process holding assessment data.

Section 12 lists it because earlier drafts preferred a local web application. The boundary was not
mitigated; it was removed, which is the cheaper outcome and worth stating as such rather than
quietly dropping the row.

It returns if a Stage 5 read-only view is built. That view is a rendering of persisted state and
not a way to drive the pipeline, so the surface would be narrow — but a local HTTP server on a
reviewer's machine is reachable by any page they have open, and request forgery against a
state-changing endpoint would be the first thing to analyse. **This document is revisited before
any such view ships**, per section 9.

Input validation, which section 12 attaches to this boundary, is not deferred with it. Every input
reaching workflow or storage is validated by the schema regardless of what supplied it — a command
line, a file, or a future view all construct the same objects through the same models.

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

Model-generated content is untrusted until validated and reviewed. This boundary is almost entirely
unbuilt, because nothing generates yet.

| Risk | Mitigation | Where | Status |
|---|---|---|---|
| An agent writes authoritative state directly | Agents return proposed objects; the application validates and persists. Agents get no database writes, no filesystem, no shell, no internet, and no credentials | `agent-design.md` section 22, design principle 13 | **Designed** — no agent exists, and no module reachable from one touches a store |
| Missing documentation is reported as a weakness | A `Finding` asserts a weakness; a `DocumentationGap` says it cannot be determined. `EvidenceReference` cannot express absence at all — `quoted_text` is required and non-empty, so there is no way to cite silence | `trace_ai.domain.evidence`, DEC-009 | **Enforced** for the evidence half; **Designed** for the finding half (#96) |
| Unapproved content reaches the report | The finding-approval checkpoint is a workflow node rather than a runtime conditional, and `AssessmentConfiguration` carries no setting that governs it | DEC-005, DEC-012, `AssessmentConfiguration` and its tests | **Enforced** for the absence of the switch; **Designed** for the gate (#102, #103) |
| An ablated run produces an approved assessment | An assessment completed by a non-authoritative run cannot reach `approved` | `AssessmentService.approve` | **Enforced** — the authority flag is supplied by the caller until `WorkflowRun` exists (#57) |
| A reviewer edit enters an object without validation | Edited objects are rebuilt through `model_validate`; `model_copy` validates nothing and is documented as the wrong API | `trace_ai.domain.base` docstring, `CLAUDE.md`, four pinning tests | **Enforced** by convention and tests, not by the type system |
| Report rendering introduces content no model or reviewer produced | Rendering is deterministic and uses no model | `current-architecture.md` section 5.13 | **Designed** (#106) |

## 8. Cross-cutting: what is not covered

Stated because a threat model that only lists what it handles is misleading.

- **No scheduled re-verification.** Content hashes are checked when something reads through the
  helper. Nothing detects that `data/` and the database have diverged — an artifact referenced by
  a row but missing from disk. DEC-020 records this as an open question.
- **A pre-formatted log message can leak anything.** See section 4.
- **`reviewer_id` is a configured local string** and is trivially forgeable. DEC-023 says plainly
  that it is not authentication, and nothing enforces that it is not read as such.
- **Secret scanning stops at the local machine.** gitleaks is a pre-commit hook and is not a CI
  step. `git commit --no-verify` skips it, and so does any clone where `pre-commit install` was
  never run. `CLAUDE.md` describes secret scanning as repository hygiene, which reads as stronger
  than "runs if the author opted in". This was found while writing this document; adding the hook
  to `.github/workflows/ci.yml` closes it and is a few lines.
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
- an interface is added that accepts input over a network, which under DEC-032 means before any
  Stage 5 view ships;
- a boundary's `Designed` or `Open` row becomes `Enforced`, so the status column stays true.

The first of those triggers arrives in M2, with the first outbound model call. This document was
written before it rather than after.

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
