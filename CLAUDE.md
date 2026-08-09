# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Trace is a context-aware security architecture analysis system. It is **in the design stage**: the
architecture, data model, agent design, and evaluation plan are written; the analysis pipeline is
not built. What exists today is configuration, process bootstrap, tooling, and a complete design
corpus. There are no agents and no model calls anywhere in `src/`.

Read `README.md` for the full picture. The authoritative design lives in `docs/architecture/` and
`docs/product/` — all plain Markdown, all marked *Proposed, version 0.1*.

## Commands

```bash
uv sync                          # install runtime + dev dependencies from uv.lock
uv run trace                     # run the CLI (prints env, log level, configured credentials)

uv run pytest                    # unit tests; integration and evaluation are deselected
uv run pytest tests/unit/test_config.py::test_settings_are_frozen   # one test by node id
uv run pytest -k blank_key       # one test by keyword
uv run pytest -m integration     # opt into a deselected marker
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
src/trace_ai/        configuration and process bootstrap -- the only product code that runs
src/trace_ai/domain/           enums.py and base.py; no concrete domain object yet
src/trace_ai/services/         ingestion/ and evidence/ -- empty
src/trace_ai/infrastructure/   filesystem/ and database/ -- empty
                     Dependencies point inward. domain/ imports neither of the other two and
                     no provider SDK; tests/unit/test_package_layout.py asserts both.
tests/unit/          the only tests that exist
tests/integration/   scaffolded, empty
tests/evaluation/    scaffolded, empty
docs/product/        vision, design principles, roadmap, future features
docs/architecture/   scope, current architecture, agent design, data model,
                     evaluation plan, decision log
demo/forgeflow/      the ForgeFlow scenario: the demo and benchmark scenario one
demo/forgeflow/input/      material supplied to Trace
demo/forgeflow/expected/   the truth set; never supplied to Trace. Only the contract is
                           written; the expected-*.yaml files are not yet authored
requirements/        the requirements catalog; see Requirements catalog below
journal/             dated session entries; see Journal below
benchmarks/          scenarios two onward, same input/ + expected/ layout
benchmarks/scenarios.yaml  the scenario registry -- the authoritative list
prompts/             scaffolded, empty -- versioned prompt definitions land here
scripts/             repository utilities
```

The import package is `trace_ai`, not `trace` — `trace` shadows a stdlib module, and importing it
silently resolves to the standard library. The distribution and CLI are still named `trace`.

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
  model identifier. Nothing behind the seam is built yet, and a seam with one implementation is not
  proven agnostic. `anthropic` is now the only provider SDK declared; DEC-016 removed the
  orchestration and model-framework dependencies.
- **`agent-design.md` section 29's creativity column is provider-neutral intent, not a sampling
  parameter.** Each adapter maps it to its own controls; the Anthropic adapter maps it to effort
  and adaptive thinking, because `temperature`, `top_p`, and `top_k` are rejected on the current
  Anthropic models. Do not read the column as naming a knob.

## Requirements catalog

`requirements/` holds version-controlled YAML requirements, one file per primary category under a
directory named for the catalog version (DEC-010). It is data; no product code reads it, and
`tests/unit/test_requirements_catalog.py` checks that it is well-formed. `requirements/README.md` is
the full guide — read it before editing the catalog.

Four things are easy to get wrong:

- **`docs/architecture/data-model.md` section 17 is authoritative** for field names and types. The
  catalog conforms to it; it does not define its own shape.
- **`acceptable_implementations` is non-exhaustive by construction.** It lists mechanism classes, not
  approved products. Treating an example as the only valid control is an explicit failure condition
  for the mapping step (`agent-design.md`, sections 12 and 13).
- **`common_false_positives` is not `non_applicable_conditions`** (DEC-011). The latter says the
  requirement does not apply; the former says what not to conclude when it *does* apply and the
  documentation is silent.
- **`source_frameworks` is provenance, not compliance mapping.** Broad compliance-framework mapping is
  deferred. Requirement text is written originally — ASVS is CC BY-SA, so its wording is cited by
  identifier and never reproduced.

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
- **`data-model.md` section 4 is authoritative for the shared enums**, and
  `tests/unit/test_domain_enums.py` parses it to prove it. Changing a member in the document
  without changing `src/trace_ai/domain/enums.py` fails the suite; so does the reverse. Edit both
  in one change.
- **Every domain object subclasses `DomainModel`** (`src/trace_ai/domain/base.py`) and inherits
  `extra="forbid"`. Do not relax it on a subclass: it is the mechanism by which an agent-proposed
  object carrying an invented field fails validation instead of passing downstream stripped of
  the field and looking valid. Timestamps come from `domain.base.now()`, never `datetime.now()`.
- **CI must never need a provider API key.** The `integration` and `evaluation` markers are
  deselected by default in `addopts` precisely so a bare `pytest` cannot spend money.
- **Secrets go through `trace_ai.config.Settings`** as `SecretStr`. `.env` is gitignored;
  `.env.example` is committed with blank values, and a test fails if the two drift apart or if a
  key-shaped entry in the example is non-empty.
- **The design docs are hand-edited Markdown now.** The `.docx` originals are deleted and
  `scripts/docx_to_md.py` is a spent migration tool retained for provenance — do not treat the
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
