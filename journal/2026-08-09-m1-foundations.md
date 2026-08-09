# 2026-08-09 — The first implementation session, and what writing code found in the corpus

Twelve pull requests. Ten M1 issues — #41 through #50 — plus two that add work to the backlog
rather than doing any. Tests went from 296 to 699.

This is the first session that produced product code. Everything before it was decisions, and the
change in activity turned out to matter more than the change in output: **writing the code found
four things in the corpus that reading it had not**, across two days of six independent research
passes and thirty decision-log entries.

## The pattern that emerged, without being planned

The first substantial thing I wrote was `test_package_layout.py`, and it set a shape that every
later file followed. Section 15 says the important property of the repository layout is that the
layers stay separated. That is a claim nothing enforces, so the test walks `domain/` with `ast` and
fails on any import of `services` or `infrastructure`.

Then the same question arrived again in `test_domain_enums.py`: `data-model.md` section 4 is
authoritative for seven vocabularies, and that is easy to state and hard to keep true, because the
document and the code are edited by different activities months apart. So the test parses section 4
and compares member for member.

By #45 it had generalized into `test_data_model_conformance.py`, which reads the field tables
directly. Three properties of that file are the whole idea:

- **The document leads.** A rename there fails the suite; so does a field the document never
  sanctioned.
- **The parser is guarded.** Every comparison is vacuously true if the parser stops matching, so a
  separate test asserts it found what it should have — a subsection count, a member total, a row
  count it cannot reach by accident.
- **The comparison is proven before it has anything to compare.** No object in sections 5 to 31
  existed when the guard was written. A conformance loop running zero times is the most dangerous
  kind of green, so the registry classifies all twenty-seven sections explicitly and five mutations
  of a throwaway model each fail.

The habit that came with it was verifying guards by breaking them. Every one of these PRs contains
a paragraph reporting which tests fail when the protection is removed, because I got tired of
writing tests whose passing meant nothing. Removing the artifact store's symlink resolution fails
two tests. Removing the store's scope predicate fails two more. Reintroducing a checkpoint setting
fails three.

## What the code found that the reading had not

**`requirements/catalog.yaml` calls itself `cat-core`.** `cat` is in no prefix list. The shape is
neither of DEC-018's two forms. And DEC-018 states that the catalog's `req-` identifiers are "the
only class currently in use", which was already untrue in the same directory when it was written.
Filed as #137, scoped wider than the one value: section 2.1 never says *which objects the scheme
governs*, and `RequirementsCatalog` is authored configuration rather than assessment data. That is
the question that decides the rest.

**`SourceObservation` was on neither of section 40's lists.** DEC-021 added the object the day
after the implementation priority was written, and nothing went back. Everything except the build
plan already treated it as real — `obs-` in section 2.1, a full field table at section 10a, its own
`expected-observations.yaml` in DEC-027. Fixed in #45's PR, then #140 filed because it also had no
work item anywhere in the backlog, which was seeded the day before DEC-021.

**The `asm` prefix cannot use DEC-018's counter.** Generated identifiers are unique within their
assessment, qualified by `(assessment_id, id)`. An assessment identifier has nothing above it to be
qualified by. The counter needs a scope that is not an assessment, and DEC-018 does not mention the
case. Implemented under a reserved scope; still unrecorded.

**"Required" needed a definition.** The conformance guard rejected my first `AssessmentConfiguration`
because I had given defaults to four fields section 6 marks `Required: Yes` — including the default
of 2 the issue explicitly asks for. That forced a reading, and it governs every object still to
come: *a field the document marks required carries no Pydantic default*, because "the constructor
must be given a value" is the only reading that is mechanically checkable. The defaults moved into
`default_configuration()`, where they are visible as choices rather than invisible in a signature.

None of the four is a large problem. What is notable is that they were all invisible to reading and
obvious to compiling. Three of them surfaced from a test comparing the document to the code, which
is exactly what those tests were written to do — I just did not expect them to find anything on the
first run.

## Two mistakes worth recording

**I named a module `logging.py`.** The issue asked for it, and I talked myself past the obvious
concern with an argument that sounded right: a namespaced module cannot shadow a standard-library
one, and indeed `trace_ai/logging.py` can import the stdlib `logging` from inside itself perfectly
well. The import broke on the first run. Importing a submodule binds it as an attribute of its
package, so `from trace_ai.logging import install` in `__init__.py` set `trace_ai.logging` to the
new module and shadowed that file's own `import logging`.

It is the mistake the package name records — `trace` shadowing the stdlib `trace` — displaced one
level down, into the exact spot where the reassuring argument runs backwards. It is now
`observability.py` and `CLAUDE.md` carries the rule next to the original one.

**I asserted `Decimal("5.10") != Decimal("5.1")`.** They compare equal. The test was trying to
demonstrate that the cost field does not route through `float` and was demonstrating nothing; the
real property is that `Decimal.from_float(0.1)` differs from `Decimal("0.1")`. A test that passes
for a reason you did not intend is worse than no test, and I nearly kept it because it was green.

## The `model_copy` hole

Asked to explain why `frozen=True` does not conflict with DEC-023's mutate-in-place, I went looking
and found something concrete. The two are compatible — DEC-023 is about the record and `frozen` is
about the Python instance — but the obvious way to build the edited object is
`model_copy(update=...)`, and it validates nothing. An invalid enum value survives and serializes
into the DEC-020 JSON payload with only a `UserWarning`.

The reviewer-edit path is the only path on which a human-supplied value enters a domain object,
which makes it the worst possible place to skip the schema. `validate_assignment` does not help
either, because `frozen` raises first. Pinned with four tests, the correct form
(`model_validate` over the merged dict) named in the class docstring and in `CLAUDE.md`, because
#63, #76, #100, and #102 all sit on that path and the wrong API is the discoverable one.

## Where the implementation departed from its issues

Six times, each recorded in the pull request that did it. The pattern is the same in every case: the
backlog was written before several decisions landed, so the issue text is occasionally behind the
decision log.

- No module-level `new_id()`. DEC-018 makes allocation a store operation, and a process-global
  counter would work in every test and collide with the store in the one place it matters.
- Twenty prefixes, not nineteen. DEC-021 added `obs` after the issue was written.
- `new_assessment` takes an identifier rather than minting one, for the same DEC-018 reason.
- No `Settings` field for the artifact root. `DATA_ROOT=` in `.env.example` would resolve an empty
  value to the working directory, which is a worse default than a fixed path.
- `trace.db` at the `data/` root rather than per-assessment. DEC-020 rejects one database per
  assessment; the issue predates it.
- Required fields carry no defaults, as above.

## Where it strains

`AssessmentService.create` writes to two stores with no transaction spanning them. It orders the
work and cleans up, and an injected-failure test proves the cleanup, but a process killed between
the directory and the row still leaves a directory. That is acceptable — an empty directory is
inert, a persisted assessment whose files are missing is not — and it is DEC-020's open question
about `data/` diverging from the database, still open.

The assessment status transitions are invented. Nothing in the corpus states an assessment
lifecycle, so `ASSESSMENT_TRANSITIONS` is the narrowest table that supports the workflow the rest of
it describes. #58 will expose those transitions to a user, which is the point at which a wrong guess
becomes expensive.

## Open next

Eight M1 issues remain: `EvidenceReference` and `SourceDocument`, the document loader, the
untrusted-source boundary test, normalization and evidence indexing, evidence retrieval, the
execution ledger, and the CLI. The CLI is the only one blocked, on #35, which asks whether the first
interface is a command line or a local web application.

Three M0 issues are open besides that: #19, the threat model, which needs writing and no decision;
#38, the report template; and #137 from this session.

Two things from this session are unrecorded decisions rather than open questions, and either could
reasonably become a decision-log entry: the global scope for the `asm` counter, and
required-means-no-default. The second is the one I would record, because it constrains twenty
objects that do not exist yet and is currently written down only in a class docstring.
