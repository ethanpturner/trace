# Foundation and documentation

**2026-08-06 to 2026-08-08** · Stage 1

First working sessions after the Stage 0 document set landed. The goal was the repository
foundation from roadmap Stage 1: dependencies, tooling, configuration, and a public front page.
No product code was written — deliberately, since Stage 1 exits on scaffolding rather than on any
model-assisted behaviour.

## What changed

Dependencies installed (LangGraph, LangChain and its Anthropic/OpenAI providers, Pydantic,
instructor, both provider SDKs, LangSmith). Build pipeline configured: Ruff, Pytest, mypy in strict
mode, and pre-commit hooks including gitleaks secret scanning, with the test run deferred to
pre-push so commits stay fast. CI runs the same four checks on every
pull request. `main` was put behind branch protection. Typed settings with `SecretStr` were added
and wired into the entry point. The design corpus and the ForgeFlow fixtures were converted out of
Word into Markdown and YAML. README, MIT licence, and this journal convention followed.

Six pull requests, all squash-merged.

## Inflection points

**The package name was broken from the first commit.** `src/trace/` shadowed Python's stdlib
`trace` module, so `import trace` silently resolved to the standard library and the project package
was unreachable. The console script pointed at stdlib `trace.main`, a CLI entry point — which is
why the first ever `pytest` run died with `SystemExit: 2` parsing its own argv. Renamed the import
package to `trace_ai` while keeping the distribution and command named `trace`. Worth noting that
the defect predated the pipeline by three commits and was invisible until something actually tried
to import the package; a repository can look healthy while being fundamentally unimportable.

**`cp .env.example .env` would have produced confusing auth failures.** Blank environment variables
parse as `SecretStr("")`, which is not `None`, so the `require()` accessor would have handed an
empty string to a provider SDK and the failure would have surfaced as a 401 from the API rather
than a message naming the missing key. That is the single most likely first-run path for anyone
cloning the repo. A `mode="before"` validator now maps blank to unset.

**There is no threat model.** `docs/architecture/Threat_Model.md.docx` was a byte-identical copy of
`Agent_Design.md.docx` — same MD5, and its own title line read *"Trace — Agent Design"*. A
copy-paste error. This matters beyond the file: the roadmap lists a threat model among Stage 0
deliverables, so **Stage 0 is not actually complete**. Nine documents were converted, not ten, and
the README states the gap rather than papering over it.

**The demo fixture referenced files that did not exist.** `structured_system_input.yaml` declares
its corpus as `product-overview.md`, `architecture-overview.md` and so on, while every `.docx` on
disk used underscores. Nothing matched. Converting to the hyphenated names the fixture itself
declares makes the scenario internally consistent for the first time — all seven declared documents
now resolve.

## Decisions

- **MIT licence.** There was no licence file at all; the repo was public but unlicensed.
- **Branch protection with zero required approvals.** Requiring reviews would lock a solo maintainer
  out of merging entirely, since GitHub does not permit self-approval. The check that has teeth is
  the required green CI run, enforced for admins.
- **Design docs converted rather than left as Word.** They are the strongest artifact this project
  has and were invisible on GitHub, where a `.docx` link downloads rather than renders.
- **Conversion written as a script, not done by hand.** `scripts/docx_to_md.py` makes the result
  reproducible and reviewable. It is a spent migration tool now, retained for provenance.
- **The README leads with a status callout.** The requested section order puts Status fourth, so a
  reader would meet a seventeen-node pipeline diagram before learning none of it is built. A header
  callout and a banner under Architecture carry the honest framing earlier, without reordering.

## Notes on method

Three of the mistakes made this week were caught only by checking rather than assuming, and all
three would have shipped silently:

- A single-file sample showed zero tables, so the first converter had no table support. The corpus
  actually has 47, 27 of them in the data model.
- Grepping for `<w:b/>` returned zero, suggesting no bold. Word writes `<w:b w:val="1"/>`; there
  were 1,877 bold runs.
- The lineage diagram was written as two source lines, but Mermaid's `LR` layout ignores line
  breaks and emitted one unreadably wide row. Only visible by rendering the diagram and looking at
  it.

Adding `scripts/` to the mypy file list immediately surfaced three type errors in code that had
been passing CI, because the directory had never been type-checked.

## Open

- No threat model exists; Stage 0 is incomplete until one is written.
- `demo/forgeflow/expected/` is empty. The scenario declares its contract — 3 findings, 5 questions,
  3 documentation gaps, 2 contradictions — but the artifacts to grade against are not authored.
- Stage 1 remains unfinished: no domain models, no persistence, and no CLI beyond a banner.
- Next is the Context Extraction vertical slice, now unblocked because the fixtures are finally
  machine-readable.
