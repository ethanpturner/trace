## Summary

<!-- What changed and why. One paragraph. Flat declarative, no marketing language, no emoji. -->

## Related issues

<!--
Note: closing keywords only fire on a merge into the default branch, which is `main`.
A feature pull request targets `develop`, so `Closes #N` links but does not close.
Close the issue explicitly at merge, or let the release pull request close it.
-->

Relates to #

## Definition of done

An unchecked box needs a sentence saying why.

### Code quality

- [ ] `uv run ruff check .` passes.
- [ ] `uv run ruff format .` leaves no changes.
- [ ] `uv run mypy` passes in strict mode. New utilities under `scripts/` are type-checked
      like product code.
- [ ] `uv run pytest` passes with no marker overrides.
- [ ] `uv run pre-commit run --all-files` passes, including gitleaks.
- [ ] `uv.lock` is regenerated if `pyproject.toml` changed. `uv sync --locked` succeeds,
      which is what CI runs.

### Tests

- [ ] Core behaviour is covered by unit tests that run under a bare `uv run pytest`.
- [ ] No test requires a provider API key. Live-provider tests carry the `integration`
      marker and evaluation-suite tests carry `evaluation`. Both stay deselected by default.
- [ ] Model-assisted behaviour is tested against recorded fixtures or a fake client, not a
      live call.
- [ ] Any bug this fixes has a regression test. Any false positive has a benchmark fixture.

### Secrets and safety

- [ ] Any new secret is a `SecretStr` field on `trace_ai.config.Settings`, added blank to
      `.env.example` in the same change, keeping the drift test green.
- [ ] No key material, source-document content, or quoted evidence appears in logs, error
      messages, committed fixtures, or test output.
- [ ] Source-derived text reaching a prompt goes through the untrusted-content wrapper and
      never occupies a system-instruction position.

### Binding design constraints

- [ ] No new model-assisted agent beyond the capped six. Report rendering uses no model.
- [ ] Agents propose objects; the application validates and persists. No agent code writes
      authoritative state, touches the filesystem, or holds credentials.
- [ ] Finding and DocumentationGap remain distinct. Missing documentation resolves to a
      question, assumption, gap, or unverified control, never to an asserted weakness
      (DEC-009).
- [ ] Neither human checkpoint can be skipped by configuration (DEC-005).
- [ ] Nothing assumes cloud deployment, multi-tenancy, or RBAC (DEC-004).
- [ ] Nothing optimizes for finding count.

### Documentation

- [ ] `docs/architecture/data-model.md` is updated if any field or type changed. It is
      authoritative.
- [ ] An entry is added to `docs/architecture/decision-log.md` for any design change,
      framework acceptance or rejection, schema change, threshold change, provider
      selection, security tradeoff, or scope-boundary change.
- [ ] `README.md` and `CLAUDE.md` are updated where they state what exists. Neither
      describes an unbuilt capability as running.
- [ ] Known limitations are documented rather than omitted.

### Register

- [ ] Flat declarative. No marketing language, no emoji.
- [ ] Present indicative only for what runs today. "Is designed to" for anything specified
      but unbuilt.

### Process

- [ ] Branched from `develop`, and this pull request targets `develop`
      (`gh pr create --base develop`). A hotfix is the sole exception and carries its own
      back-merge pull request.
- [ ] Merge type is correct: squash for `feature/*` into `develop`, merge commit for
      everything else.
- [ ] A journal entry exists for the session under `journal/YYYY-MM-DD-short-slug.md`,
      recording reasoning rather than the diff.
