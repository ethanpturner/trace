# 2026-08-09 — Storing objects while the schema is still moving

Closes #23 as DEC-020. The last M0 item gating M1 code, which means the foundations block is now
fully buildable.

## Most of it was already decided

`data-model.md` section 35 lists what goes in SQLite and what goes on the filesystem, and section
5.15 says the same thing again. What was actually open was the mapping between Pydantic objects and
rows, plus the two questions section 39 records: which objects belong in a database versus
version-controlled files, and how migrations work during early development.

## Question 13 had the wrong axis in my head

I had been reading "SQLite versus version-controlled YAML or JSON" as a question about size — big
things on disk, small things in rows. That is how section 35's own lists read, since they sort by
what is obviously large.

The axis that actually works is **authorship**. A requirement is a file because a person wrote it
and a reviewer reviews it in a diff. A threat is a row because a run produced it. That splits
cleanly into three: version-controlled files for the catalog, prompts, and benchmark expected
outputs; SQLite for everything an assessment generates; `data/` for generated files too large or
too binary for a row.

Size correlates with the answer but does not explain it, which is why the size reading kept
producing edge cases — a small generated object and a large authored file both sit on the wrong side
of it.

## The mapping question turns on one observation

**The schema is the least stable thing in the project right now.** DEC-012 removed two fields,
DEC-015 constrained three, DEC-017 removed one, DEC-018 rewrote the identifier scheme, DEC-019
redefined four field descriptions. Five schema-affecting decisions in two days, and section 39 still
has twelve open questions, several of which will change it further.

An ORM that mirrors the object model in table definitions turns each of those into a migration, and
a migration written against a model still under active decision is work that gets thrown away.

So: JSON payloads with identity and routing lifted into columns. Pydantic is the only schema;
SQLite stores no field definitions. Adding or removing a field is a Pydantic change.

The corpus had already declined the main argument against this. Referential integrity is checked by
the validation nodes in application code, deliberately, because the checks are semantic — a mapping
must reference a threat *in the same assessment*, a documented claim must carry evidence. A foreign
key expresses only the first half of each. Adding constraints would not replace those nodes, it
would duplicate part of them, and the two would disagree the first time a validation rule changed.

DEC-004 removes the other argument: a local single-user application whose process exits at every
checkpoint has no concurrency for a relational engine to arbitrate.

## The cost estimate paid off sooner than expected

Question 17 — migrations during early development — resolves to *there are none*. An incompatible
`data_model_version` refuses to load and the assessment is re-run.

Two days ago that would have been an assertion that regeneration is cheap. Now it is a number: an
assessment costs $2.25 to $5.97. Regenerating one costs a few dollars and no engineering time;
writing a migration against a schema still being decided costs hours and produces code that itself
needs maintaining.

I did not expect the cost estimate to be load-bearing for a persistence decision. It is the
difference between a preference and an argument.

## Where it strains

Refusing to load old assessments discards evaluation history at every schema change, and
`evaluation-plan.md` section 17 wants a longitudinal record across releases. Those pull against each
other directly.

The mitigation is to write evaluation summaries and the longitudinal record as version-controlled
artifacts, not only as rows — so the history stays readable even when the assessments behind it do
not load. That is a real mitigation and not a fix: the results survive, the ability to re-examine
them does not.

The other thing I am uneasy about is that a database with no column types and no constraints will
accept whatever the application writes. Pydantic validates on the way in, so the guarantee holds
exactly as long as nothing bypasses the repository — and "nothing bypasses the repository" is a
convention, not a mechanism.

## The decision has an expiry

This is shaped by the schema being unstable, and that is temporary. Once section 39's questions
close, the reasoning weakens: relational constraints get cheaper as the model stops moving, and the
tooling opacity of JSON payloads stops being worth paying for.

The entry says so and asks what the trigger is — a closed section 39, a shipped MVP, or the first
assessment worth keeping. I do not know which, and a decision that expires without a stated trigger
tends to just persist.

## Open next

M1 implementation is unblocked. The foundations block — package layout, shared types, identifiers
and hashing, artifact store, persistence, execution ledger — has every decision it needs.

Twelve M0 decisions remain, none of them gating M1. #19, the threat model, still needs writing and
needs no decision at all.
