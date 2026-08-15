# WS12: packaging stance, dead config, and store-identity hardening

Twelfth and last workstream of the robustness program (#453), phase 5. Five loosely-related parts;
it carries a decision-log entry (DEC-090) for the packaging stance, and it unblocks WS9's
wheel-smoke step (done next).

## What changed

**v0.1 is declared clone-only (DEC-090).** The prompts, requirements catalog, report template, and
benchmark scenarios are version-controlled files read through `PROJECT_ROOT`-relative paths, not
package data in the wheel — so `pip install trace && trace run` would fail on the first asset read
while `[project.scripts]` claimed installability. `config.IS_SOURCE_CHECKOUT` detects the difference
(a `pyproject.toml` beside `PROJECT_ROOT`), and a command past the banner run outside a checkout
stops with a clear `SourceCheckoutRequiredError` rather than a dangling `FileNotFoundError`. `trace`
and `trace --help` still work from a wheel (verified: `uv build` + an isolated install runs
`trace --help`), which is what the WS9 smoke step checks. Making the wheel self-contained via
`importlib.resources` is a later decision; this makes the current stance honest.

**The unused `langsmith` dependency and its settings are removed.** It shipped in the wheel and was
imported nowhere; the four `langsmith_*` settings it fed were read only by the banner. A
package-layout test now asserts every declared runtime dependency is imported in `src/`.
`openai_api_key` stays — it ships no dependency and the seam is provider-agnostic by design.

**Two implicit store identities are now explicit.** `DomainModel.stored_type` (a class attribute
defaulting to the class name, set in `__init_subclass__`) replaces `type(obj).__name__` as the stored
`object_type`, so a class rename is a one-line override rather than silent unreadability of every
existing row. `DomainModel.row_key()` replaces the duck-typed SystemContext special case — the base
returns the identifier and raises for an id-less object, which `SystemContext` overrides, so a new
id-less object is a loud decision rather than a collision. `store_metadata` records `trace_version`
at creation, so a `CorruptRecordError` names the build that wrote the row.

**A stale ablation name now raises.** `_apply_ablations` counts substitutions per requested ablation
and refuses if any matched no node — a name that drifted out of step with its node used to run the
full pipeline while marking the run non-authoritative, a measurement that lies. The identifier
registry gained an agreement test: every prefix in `PREFIXES` has an exported `{ObjectType}Id` alias
and vice versa, and `PREFIXES` is now a `Final[Mapping]`.

**Dead surface removed:** `scripts/docx_to_md.py` (a spent migration tool, provenance in git) and the
CLAUDE.md line describing it.

## Deferred

The `.env` near-miss warning (warn on an env key resembling a known field) is the softest sub-item;
it needs its own mechanism (reading and Levenshtein-matching the `.env`) and is left out of this
already-broad change. `extra="ignore"` on `Settings` is unchanged.

## Tests

Clone-only guard refuses a real command and the banner still works; every declared dependency is
imported; a renamed class reads its rows via `stored_type`; a corrupt record names the writing build;
`row_key` defaults to the id and raises for id-less objects; a stale ablation name raises and every
known ablation substitutes a node; the identifier registry agrees. Full suite green (3729); ForgeFlow
replay byte-for-byte; `uv build` + isolated `trace --help` works.

## Open next

WS9 (#450, CI cost and blind spots) is the last remaining workstream. Its wheel-smoke step
(`uv build && uv run --isolated --with dist/*.whl trace --help`) is now backed by a wheel that works.
