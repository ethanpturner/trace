# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Trace is a context-aware security architecture analysis system. **The pipeline is built and runs
end to end, the demonstration surface exists, and the debt milestones are closed; what remains
open is the Stage 6 portfolio material.** All six
model-assisted agents exist, each with a deterministic validation node behind it; both human
checkpoints are workflow-graph nodes; `trace run` and `trace resume` drive all fourteen phases
from the command line through both checkpoints to a rendered report; and the evaluation harness
(`trace evaluate`) replays registered benchmark scenarios against authored truth sets, with
baselines, ablations, the adversarial condition, and a CI-checked scorecard.

Every model call in `src/` goes through the seam, and no default test makes one: everything runs
against `DeterministicModel`, and `--model-profile offline-fake --response recorded.json` is a
supported way to run the pipeline without a provider. Live measurement exists but is thin: the
flagship ForgeFlow recording is a live capture, and the DEC-077 stability protocol has run once —
five completed `claude-opus-5` runs of one scenario at $6.92 ± $3.28 each (DEC-092). Everything
else replays offline, and the eleven other benchmark recordings are authored, not captured.

Read `README.md` for the full picture. The authoritative design lives in `docs/architecture/` and
`docs/product/` — all plain Markdown, all marked *Proposed, version 0.1*.

## Commands

```bash
uv sync                          # install runtime + dev dependencies from uv.lock
uv run trace                     # no arguments: env, log level, configured credentials
uv run trace assessment create --name X          # the command surface; --help lists it
uv run trace run asm-001 --model-profile offline-fake --response recorded.json
uv run trace context show asm-001 --evidence     # the review package, excerpts labelled
uv run trace context approve asm-001             # non-zero while something blocking is open
uv run trace evaluate --all                      # replay every recorded benchmark scenario
uv run trace capture unsigned-webhooks extract   # stage a live recording; spends provider calls
uv run python scripts/replay_forgeflow.py        # the whole pipeline, hash-checked, no key

uv run pytest                    # unit tests; integration and evaluation are deselected
uv run pytest tests/unit/test_config.py::test_settings_are_frozen   # one test by node id
uv run pytest -k blank_key       # one test by keyword
uv run pytest -m integration     # opt into a deselected marker
uv run pytest -m evaluation      # the benchmark suite: ForgeFlow regressions, and one live file
uv run pytest --cov=trace_ai.config          # coverage for one module

uv run ruff check .              # lint
uv run ruff format .             # format
uv run mypy                      # strict; covers src, tests, and scripts
uv run pre-commit run --all-files            # everything the hooks check
uv run pre-commit run gitleaks --all-files   # a single hook
```

`uv sync --locked` is what CI runs; it fails if `uv.lock` is stale relative to `pyproject.toml`.

## Repository layout

```
src/trace_ai/        configuration, process bootstrap, and cli.py -- the command surface
src/trace_ai/domain/           domain objects, identifiers, hashing, and proposals/
src/trace_ai/domain/proposals/ what an agent returns: local keys, nothing authoritative
src/trace_ai/services/         ingestion/, evidence/, context/, threats/, requirements/,
                     prompts/, the execution ledger, and driver.py -- the composition
                     point that runs all fourteen phases through the orchestrator
src/trace_ai/services/context/ input_package.py, pipeline.py, review_file.py
src/trace_ai/services/threats/ input_package.py -- what the threat agent sees
src/trace_ai/services/requirements/ loader.py -- the only reader of requirements/
src/trace_ai/infrastructure/   filesystem/, database/, and model/ -- stores and the model seam
src/trace_ai/workflow/         phases, transitions, limits, the node protocol, and the nodes
                     Dependencies point inward. domain/ imports neither of the other two and
                     no provider SDK; tests/unit/test_package_layout.py asserts both.
tests/unit/          the tests that run by default
tests/integration/   one live adapter call; marked `integration`, deselected
tests/evaluation/    the live context fixtures; marked `evaluation`, deselected
docs/product/        vision, design principles, roadmap, future features
docs/architecture/   scope, current architecture, agent design, data model,
                     evaluation plan, decision log
demo/forgeflow/      the ForgeFlow scenario: the demo and benchmark scenario one
demo/forgeflow/input/      material supplied to Trace
demo/forgeflow/expected/   the truth set; never supplied to Trace. Fully authored;
                           see its README for the file list
requirements/        the requirements catalog; see Requirements catalog below
journal/             dated session entries; see Journal below
benchmarks/          scenarios two onward, same input/ + expected/ + recorded/ layout;
                     all twelve registered scenarios are fully authored and replay offline
benchmarks/scenarios.yaml  the scenario registry -- the authoritative list
prompts/             prompt files; shared/ holds the blocks composed into agent prompts
templates/           report-v1.md, the report template; see Report shape below
scripts/             repository utilities
```

The import package is `trace_ai`, not `trace` — `trace` shadows a stdlib module, and importing it
silently resolves to the standard library. The distribution and CLI are still named `trace`.

**The same rule applies to modules inside the package.** Structured logging lives in
`observability.py` because `logging.py` broke on the first import, and the reasoning that a
namespaced module cannot shadow anything is exactly backwards: importing a submodule binds it as
an attribute of its package, so `from trace_ai.logging import install` in `__init__.py` would set
`trace_ai.logging` to that module and shadow the same file's `import logging`. Do not name a
module after a standard-library one it or its package imports.

## Architecture in brief

Trace is designed as a **fixed pipeline, not a free-form agent conversation**. Model-assisted steps
alternate with deterministic nodes, and two human approval checkpoints are structural rather than
configurable. Agents propose schema-validated objects; the application validates them and owns all
authoritative state.

Before changing anything about the pipeline, the agents, or the domain objects, read
`docs/architecture/current-architecture.md`, `docs/architecture/agent-design.md`, and
`docs/architecture/data-model.md`.

## Binding design constraints

These are decided. Violating one is a design change requiring an entry in
`docs/architecture/decision-log.md`, not an implementation detail.

- **Six model-assisted agents, capped.** Context Extraction, Threat Analysis, Requirement and
  Control Mapping, Evidence Validation, Critical Review, Report Generation. A seventh requires
  evidence that it improves results. Report *rendering* uses no model. The corpus specified a
  seventh — Severity Support — and DEC-030 excluded it rather than deferring it: four of its six
  outputs already existed as `Finding` fields. **Severity is assigned by the reviewer at
  checkpoint 2**, no node proposes one, and a finding may not be approved while its severity is
  `unassigned`. `tests/unit/test_agent_cap.py` pins the inventory.
- **Agents never write authoritative state.** They return proposed objects; the application
  validates and persists. Agents also get no internet, shell, filesystem, database writes, or cloud
  credentials.
- **Source documents are untrusted data.** Nothing inside a document under review may redefine an
  agent's role, schema, or instructions. `demo/forgeflow/input/sample-repository-notes.md` contains
  a deliberate prompt-injection fixture; it is test data, not a live payload.
- **Missing documentation is never proof of a vulnerability** (DEC-009). It becomes a Question,
  an assumption, a DocumentationGap, or a low-confidence finding. A **Finding** means evidence
  supports a weakness; a **DocumentationGap** means it cannot be determined whether a control
  exists. Collapsing the two is the exact failure this project exists to avoid.
- **Two human checkpoints are structural** (DEC-005): context approval, then finding approval.
  They are workflow-graph nodes, not runtime conditionals, and `AssessmentConfiguration`
  carries no setting that governs them (DEC-012). Removing a checkpoint is an evaluation
  ablation that marks the run non-authoritative; answering one from a recorded decision file
  is not an ablation and needs no switch.
- **State is structured and schema-validated**, not a conversational transcript (DEC-006).
- **Local, single-user MVP** (DEC-004). No cloud deployment, multi-tenancy, or RBAC.
- **The report has sixteen sections and each has exactly one owner** (DEC-035). Four are prose from
  the Report Generation agent — `executive_summary`, `system_overview`, `risk_summary`,
  `limitations` — and twelve are rendered deterministically from approved objects. A section is
  never both, and the agent never rewrites an approved object's text: a `Finding.description` is
  what the reviewer approved at checkpoint 2. `templates/report-v1.md` fixes the sections, their
  numbering, their anchors, and the authored wording for every section that can be empty;
  `tests/unit/test_report_template.py` holds it, the decision table, and section 5.13 in agreement.
  Markdown is the only MVP output format.
- **Quality over finding volume.** A successful assessment may produce no findings. Never optimize
  for finding count.

Two things are commonly assumed and are **not** decided:

- **There is no orchestration framework** (DEC-016). LangGraph was proposed in DEC-007 and
  rejected: the pipeline is fourteen ordered phases with two pause points and no analytical
  branching, and a framework checkpointer would be a second authoritative store alongside the
  domain objects DEC-006 makes authoritative. Orchestration is a node protocol, an explicit
  transition table, and a persisted `WorkflowRun` row. Every entry in the decision log is now
  Accepted or Rejected; none is Proposed.
- **The model interface is provider-agnostic; Anthropic is the default** (DEC-014). The
  application talks to a seam and provider code lives in an adapter behind it. `claude-opus-5` is
  the primary model, and `model_profile` names a provider-model-settings bundle rather than a bare
  model identifier. Behind the seam today: the Anthropic adapter, the deterministic substitute,
  the recorded-response loader, the caching wrapper, and the profile registry — one provider, so
  the seam is populated but not proven agnostic. `anthropic` is the only provider SDK declared;
  DEC-016 removed the orchestration and model-framework dependencies.
- **`agent-design.md` section 29's creativity column is provider-neutral intent, not a sampling
  parameter.** Each adapter maps it to its own controls; the Anthropic adapter maps it to effort
  and adaptive thinking, because `temperature`, `top_p`, and `top_k` are rejected on the current
  Anthropic models. Do not read the column as naming a knob. DEC-085 resolved the table's two
  "low to moderate" rows: critical review runs at moderate, report generation at low.

## Requirements catalog

`requirements/` holds version-controlled YAML requirements, one file per primary category under a
directory named for the catalog version (DEC-010). `services/requirements/loader.py` reads it and is
the only thing that does; it validates every requirement, checks the manifest and the files against
each other in both directions, and recomputes `content_hash` on every load.
`requirements/README.md` is the full guide — read it before editing the catalog.

**Editing a requirement moves the content hash, and the loader then refuses to read the catalog.**
Run `uv run python scripts/catalog_hash.py --write`. The hash covers the *parsed* catalog (DEC-019),
so comments, indentation, and key order do not move it, and a comment doing real work is invisible
to it.

Five things are easy to get wrong:

- **`docs/architecture/data-model.md` section 17 is authoritative** for field names and types. The
  catalog conforms to it; it does not define its own shape.
- **`acceptable_implementations` is non-exhaustive by construction.** It lists mechanism classes, not
  approved products. Treating an example as the only valid control is an explicit failure condition
  for the mapping step (`agent-design.md`, sections 12 and 13).
- **`common_false_positives` is not `non_applicable_conditions`** (DEC-011). The latter says the
  requirement does not apply; the former says what not to conclude when it *does* apply and the
  documentation is silent.
- **`source_frameworks` is provenance, not compliance mapping.** Broad compliance-framework mapping is
  deferred. Requirement text is written originally — ASVS 5.0 is CC BY-SA 4.0, so its wording is cited by
  identifier and never reproduced.
- **A requirement identifier is authored, and a caller names the catalog version it wants.**
  `req-AUTH-001`, not `req-001`: a counter-numbered identifier is one no person assigned, and the
  loader refuses it. `load_catalog(version)` takes the version rather than globbing the directories,
  so a `0.2/` added mid-assessment cannot change what an in-flight run is assessed against.

Requirements are phrased so that absence of evidence resolves to `unverified`, never `unmet`. A
requirement written so that silence proves absence is a DEC-009 violation regardless of how it is
worded elsewhere.

## Branching

```
feature/*   individual work
   |  squash-merge PR
   v
develop     integration branch                    hotfix/*  cut from main
   |  release PR, merge commit                       |  merge commit
   v                                                 v
main        stable / released history  <-------------+
                                                     |
                        back-merge PR, merge commit  |
                        develop <--------------------+
```

**Branch from `develop`.** The single exception is a hotfix, which is cut from `main` — see below.
`main` is the default branch on GitHub, so a fresh clone lands there; check out `develop` first.

```bash
git checkout develop && git pull
git checkout -b feature/<short-slug>
# ... work, commit ...
gh pr create --base develop          # --base is required; it would otherwise default to main
```

Both branches are protected: a pull request and a green CI run are required, direct pushes are
rejected including for admins, and neither can be force-pushed or deleted. `develop`'s deletion
block is load-bearing — the repository auto-deletes head branches on merge, so a release PR would
otherwise delete it.

Two protection settings are deliberately off, and turning either on deadlocks the next release:

- **`main` does not require branches to be up to date.** After a release, `main` holds a merge
  commit that `develop` lacks. Requiring `develop` to be current would demand a back-merge before
  every release, which is circular here: `main` only ever receives commits from `develop`, so those
  merge commits carry no content `develop` is missing.
- **`develop` does not require linear history.** It has to accept the merge commit that carries a
  hotfix back from `main`.

Merge types are not interchangeable. **Only `feature/*` into `develop` is squashed**; everything
else is a merge commit:

- **`feature/*` into `develop` — squash.** One commit per feature keeps `develop` readable.
- **`develop` into `main` — merge commit.** This is why merge commits are enabled and why `main`
  does not require linear history. Squashing or rebasing a release would leave `main` with a commit
  that is not an ancestor of `develop`, and every later release PR would re-show already-released
  work and conflict. A long-lived branch has to be merged, not replayed.
- **Anything into `main`, and any back-merge into `develop` — merge commit,** for the same reason.

### Hotfixes

For a fix that must reach `main` without waiting for everything queued on `develop`. Everything
else, including work that merely feels urgent, goes through `develop`.

A hotfix is two pull requests. The second is not optional: without it the fix exists only on `main`
and the next release, which merges `develop` into `main`, will not carry it forward.

```bash
# 1. cut from main -- the one time you do not branch from develop
git checkout main && git pull
git checkout -b hotfix/<short-slug>
# ... fix, commit ...
gh pr create --base main            # merge commit

# 2. after it merges, back-merge main into develop
git checkout develop && git pull
git checkout -b chore/backmerge-<short-slug>
git merge origin/main
gh pr create --base develop         # merge commit
```

**The back-merge needs its own branch; a `main` into `develop` pull request will not work.**
`develop` requires branches to be up to date, which means the head must already contain `develop`'s
tip. Once `develop` has moved on, `main` does not, so the pull request is blocked with no useful
explanation. A branch cut from `develop` and merged with `main` contains both sides and satisfies
the rule.

Squashing either pull request breaks the chain: the hotfix commit stops being an ancestor of
`develop`, and the next back-merge re-proposes it.

## Working norms

- **mypy is strict and covers `scripts/` too.** New utilities are type-checked like product code.
- **`data-model.md` is authoritative, and `tests/unit/test_data_model_conformance.py` enforces
  it.** It parses the field tables and the section 4 enums and compares them to the code, in both
  directions — a rename in the document alone fails, and so does a field the document never
  sanctioned. **When you implement a domain object, flip its registry entry in that file to
  `IMPLEMENTED` and name the model in the same change**, or the object ships unguarded. Every
  section from 5 to 31 is classified there; a new one fails until it is added.
- **Every domain object subclasses `DomainModel`** (`src/trace_ai/domain/base.py`) and inherits
  `extra="forbid"`. Do not relax it on a subclass: it is the mechanism by which an agent-proposed
  object carrying an invented field fails validation instead of passing downstream stripped of
  the field and looking valid. Timestamps come from `domain.base.now()`, never `datetime.now()`.
- **Identifier allocation belongs to the store, not to a caller.** DEC-018 assigns a generated
  identifier at insert from a monotonic per-`(assessment_id, prefix)` counter. `InMemoryAllocator`
  in `domain/identifiers.py` is for tests: a fresh instance restarts at `001`, so two of them
  collide and a resumed run would re-mint identifiers that already exist. Depend on the
  `IdentifierAllocator` protocol and let the persistence layer supply the implementation.
  **The scheme governs objects an assessment produces** (DEC-034). Authored configuration —
  `RequirementsCatalog`, `PromptDefinition` — is outside it and carries a *name*: a lowercase slug
  with no prefix, identified by `(id, version)`. Do not give one a prefix; `cat-core` was that
  mistake.
- **A type field the document illustrates is an open vocabulary** (DEC-036). `component_type`,
  `asset_type`, `actor_type`, and `boundary_type` accept any term and normalize it to one spelling
  through `domain/vocabulary.py`; the `KNOWN_*` constants are documentation and validate nothing. A
  closed enum would reject `demo/forgeflow/input/structured-system-input.yaml`, which uses six
  component types `data-model.md` never lists. `DataFlow.direction` is the counter-example: section
  14 names the values rather than illustrating them, so it is a closed enum. Where absence would
  read as a negative answer, say `unknown` explicitly — never `False`, never `None`.
- **Go through `AssessmentService` for anything assessment-shaped**, and hold the
  `AssessmentHandle` it returns rather than an identifier: it carries the scoped repository
  and the scoped artifact store together, so one assessment's code cannot reach another's.
- **`Assessment.status` is the deliverable's lifecycle, never the pipeline's position** (DEC-031).
  Workflow progress is `WorkflowRun.status`; an assessment may have several runs. Four values only
  — `draft`, `pending_review`, `approved`, `archived` — reached through named verbs
  (`begin_review`, `resume_from_review`, `approve`, `begin_revision`, `archive`) rather than a
  status setter, because a setter is what let the pre-DEC-031 version mean "at a checkpoint"
  without anyone deciding it should. A person may only `archive`. A failed run leaves its
  assessment in `draft`.
- **Reach persisted objects through a scoped `AssessmentRepository`.** `AssessmentStore.repository(
  assessment_id)` is the only way in; there is no cross-assessment read but `assessment_ids()`,
  which returns identifiers and no content. Identifiers come from `repository.allocate(prefix)`,
  never from a caller, and a counter increment commits with the insert that consumes it — wrap
  both in `repository.transaction()`. Bumping `SCHEMA_VERSION` is for table-layout changes only; a
  domain-object change is invisible to SQLite by design.
- **Reach the filesystem through `ArtifactStore`, never through a path you built.** It is bound to
  one assessment, creates `sources/`, `normalized/`, `outputs/`, `traces/`, and `evaluation/` on
  demand, and treats `SourceDocument.filename` as untrusted — a caller-supplied name reaching a
  path expression. It also refuses to overwrite a stored file with different content, because
  every `EvidenceReference` into the original would keep a hash that no longer verifies.
- **Never quote source-document content into a log record.** Source documents are untrusted input
  and may carry anything. Reference them by `SourceDocument.id` or `EvidenceReference.id`; the
  redaction filter in `trace_ai.observability` replaces a field whose name marks it as
  source-derived with a length and that identifier. Pass values as structured context
  (`extra={...}` or `bind(...)`), never pre-formatted into the message — a secret interpolated
  into the message string before `logging` sees it is indistinguishable from prose, and the filter
  says so rather than pretending otherwise.
- **Build an edited object with `model_validate`, never `model_copy`.** Domain objects are frozen,
  so a DEC-023 reviewer edit constructs a new instance and persists it under the same identifier.
  `model_copy(update=...)` looks like the API for that and validates nothing: an invalid enum
  value survives and serializes into the DEC-020 JSON payload, and `extra="forbid"` is bypassed.
  Use `type(obj).model_validate({**obj.model_dump(), **changes})`. This is the only path on which
  a human-supplied value enters a domain object, so it is the one that least tolerates skipping
  the schema. Pinned by `tests/unit/test_domain_base.py`.
- **The Context Validation node reports and routes; it never corrects** (`agent-design.md` section
  8). It does not merge duplicates, fill in fields, or re-label a `documented` claim with no
  evidence as `assumed` to make it pass — that last one would turn a claim the agent asserted into
  one nobody asserted, with a clean validation record. Errors are returned with an `ErrorClass` so
  the extraction node routes on a class rather than a message.
- **The fence is the security boundary, and a document that can close it escapes it.**
  `services/context/input_package.py` wraps every excerpt in a marker carrying its evidence
  identifier and neutralises any delimiter found *inside* an excerpt. The ForgeFlow injection
  fixture is the live test: the block is **present** — it is evidence — and appears only inside the
  fence. The package carries no path, credential, environment value, or configuration object, and
  a budget overrun **names** the excluded evidence rather than truncating.
- **A proposal carries local keys and nothing the application owns** (`agent-design.md` section
  22, DEC-006). `domain/proposals/` has no `id`, no `status`, no approval field, and no severity;
  `extra="forbid"` makes an invented one a validation failure. A key shaped like an identifier is
  refused too, because DEC-018 allocates at insert and an agent-chosen number could collide.
  `convert_proposal` resolves keys to allocated identifiers, sets everything `candidate`, and
  refuses before allocating anything if a key is unresolved.
- **Routing is the orchestrator's; ceilings are the orchestrator's** (DEC-016, `agent-design.md`
  section 27). A node declares a phase, takes a `NodeContext`, and returns a `NodeResult`; it is
  given no registry, no orchestrator, and no peer, because a node that could reach one could build
  the loop section 27 prevents. The fourteen phases are `current-architecture.md` section 5.3's and
  transitions are declared data — anything the table does not name is refused. Exceeding a ceiling
  **stops** the run with a classified error; it never skips a node or shrinks a request.
  `AssessmentState` holds identifiers and routing only (`data-model.md` section 31's state-design
  rule), because a state carrying content is a second copy of the authoritative data.
- **A checkpoint cannot be skipped, and the mechanism is that skipping is unrepresentable**
  (DEC-005, DEC-012). `CheckpointNode` takes no flag, consults no configuration, and advances only
  when every subject has a `ReviewerDecision`; `AssessmentConfiguration` carries no field that
  governs one. Pausing is stopping (DEC-017): the state is written to `traces/`, the process exits,
  and resuming is a read in a new process. The review package is **derived** from the run, never
  stored in it.
- **Retry the attempt, never the conclusion** (`agent-design.md` section 26). `workflow/errors.py`
  holds a closed taxonomy: schema failures, provider failures, and missing relationships are
  retryable; insufficient evidence, an unresolved contradiction, and required reviewer input are
  not, whatever the retry budget says. Retrying an analysis condition invites an agent to fabricate
  an answer on the third attempt, because producing one is the only way to stop being retried. A
  retry carries **validation feedback** forward or it is a repetition, and a failed attempt's raw
  output goes to `traces/` — never into `error_message`, which section 27 requires to be safe.
- **A prompt is a file, and shared blocks are composed rather than copied.** `agent-design.md`
  section 34 is authoritative for the tree; `current-architecture.md` section 10 was corrected to
  match it. `services/prompts/` reads the tree, joins each declared `shared/` block in order, and
  hashes the **composed** text (DEC-019) — so an edit to a shared block changes the hash of every
  prompt including it. A missing declared block raises: a prompt that composes short still runs and
  still answers, having lost the untrusted-source boundary.
- **Reach a model through `StructuredModel`, never through a provider SDK** (DEC-014).
  `infrastructure/model/anthropic_adapter.py` is the only module that may import `anthropic`, and
  `tests/unit/test_model_boundary.py` fails if another one does. An adapter makes **exactly one
  attempt** and returns a `ModelFailure` rather than raising — the retry budget is the
  orchestrator's, and a hidden loop would break the `ExecutionRecord` retry count and the cost
  ceiling. A schema failure keeps the raw output (`data-model.md` section 33). `model_profile`
  resolves through `infrastructure/model/profiles.py`; `Creativity` is provider-neutral intent and
  names no knob.
- **CI must never need a provider API key.** The `integration` and `evaluation` markers are
  deselected by default in `addopts` precisely so a bare `pytest` cannot spend money.
- **Secrets go through `trace_ai.config.Settings`** as `SecretStr`. `.env` is gitignored;
  `.env.example` is committed with blank values, and a test fails if the two drift apart or if a
  key-shaped entry in the example is non-empty.
- **The design docs are hand-edited Markdown now.** The `.docx` originals and the spent
  `scripts/docx_to_md.py` migration tool are both deleted; their history is in git. Do not treat the
  Markdown as generated output.
- **Match the corpus's prose register** in docs, README, and PR descriptions: flat declarative,
  no marketing language, no emoji. Keep tense discipline — present indicative only for what runs
  today, "is designed to" for everything specified but unbuilt. It is easy to accidentally describe
  the pipeline as if it exists.

## Journal

`journal/` is a dated record of how the project evolved: what changed, which decisions or
inflection points mattered, and why. It exists so the project's history can be read back as a
coherent story, and it feeds the portfolio narrative in roadmap Stage 6.

**Write an entry at the end of each working session**, as `journal/YYYY-MM-DD-short-slug.md`. One
file per session. Cover what changed, decisions made and the reasoning behind them, anything
discovered that altered the plan, and what is open next. Record the reasoning, not just the diff —
the commit log already has the diff.
