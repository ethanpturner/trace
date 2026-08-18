# 2026-08-14 — WS9: CI cost and blind spots (#450)

The ninth robustness workstream. The scorecard job was replaying the recorded pipeline roughly six
times per pull request, and CI had a handful of gaps a change could slip through. This closes the
cost and the gaps together.

## What changed

**Sweep once, render twice.** The scorecard and the comparison table read the same feeds, so the
sweep no longer runs once for each. `collect_feeds` moved out of `scripts/build_scorecard.py` into
a new `src/trace_ai/services/evaluation/sweep.py`, alongside `dump_feeds`/`load_feeds`. Both build
scripts now import it from the package rather than through the sibling import
`from build_scorecard import collect_feeds`, which only resolved when run from the `scripts/`
directory. `build_scorecard.py` gained `--sweep-to PATH` (sweep once, write the feeds, exit) and
both scripts gained `--from-feeds PATH` (render from that file). The scorecard workflow now sweeps
once into `$RUNNER_TEMP/feeds.json` and renders both `--check` steps from it.

**Dropped the re-render.** The workflow's "Render fresh copies for review" step re-ran all three
sweeps purely to produce upload artifacts — half the job's cost for no new information. When the
checks pass, the committed pages *are* the current pages by definition, so the upload now takes the
committed files and runs only on success. On a stale page the check is already red with the
regeneration command, and there is nothing worth uploading.

Net: the scorecard job goes from ~6 sweeps per PR (scorecard + comparison + ablation, each swept
for `--check` and again for the re-render) to 2 (one shared scorecard+comparison sweep + the
ablation's own, which drops nodes and cannot share the clean feeds).

**CI blind spots.**
- Wheel-smoke: `uv build && uv run --isolated --with dist/*.whl trace --help`, proving the
  clone-only distribution (DEC-090) still exposes its console entry point from a built wheel.
- `scripts/catalog_hash.py --check` wired into `ci.yml` — a fast, named signal for catalog-hash
  drift instead of an opaque loader refusal buried in a test failure.
- Coverage `fail_under = 80` in `pyproject.toml`, with `scripts` added to the coverage source.
  Real coverage is 85%, so the floor has headroom; it is a floor, not a target.
- A `macos-latest` job running the test suite. macOS is the dev platform and has a
  case-insensitive filesystem the artifact store's untrusted-filename handling never otherwise
  meets in CI. Only pytest is platform-sensitive, so lint/typecheck/secret/catalog guards stay on
  the single Linux job rather than duplicating the Linux-only gitleaks download on macOS.
- `persist-credentials: false` on every checkout (ci, scorecard, demo) — no step pushes, so the
  stored token is dead weight a compromised step could otherwise use to write to the repo.

**Tests.** `test_catalog_freeze.py` pins that the real `versions.yaml` declares a frozen version
(so the guard actually guards something) and that a blanked or draft-only registry freezes nothing.
`test_sweep.py` pins the `dump_feeds`/`load_feeds` round-trip and the non-list rejection.

## Decisions and deliberate omissions

- **No `paths-ignore` added.** The issue suggested a narrow docs-only filter, but `scorecard.yml`'s
  header comment already argues against path filters (#405): the harness replays the full pipeline,
  so a change to `workflow/`, `domain/`, or any service can move a feed, and a filter let those
  changes drift the committed pages silently. A journal/README-only exclusion would be safe, but
  reversing a documented decision to shave a now-cheap job is not worth it. Reducing the sweep cost
  addresses the root concern directly; the filter is a follow-up with a decision-log entry if ever
  wanted.
- **Action tags not SHA-pinned.** The corpus pins to fictional-future versions
  (`actions/checkout@v7`, `upload-artifact@v7`, `setup-uv@v9.0.0`, `vhs-action@v2`) that do not
  resolve on real GitHub — `gh api` 404s each, including the one CI already runs against. Pinning
  to a commit SHA requires resolving each action to a real commit; doing it blind would pin to a
  nonexistent ref and break CI. Left for a pass in an environment with authenticated access to the
  real action repositories. `persist-credentials: false` is the resolution-free half of the
  hardening and is applied now.
- No decision-log entry: nothing here changes a decided surface. The wheel-smoke relies on DEC-090
  (clone-only), already recorded; the coverage floor is a working norm; the sweep extraction is an
  internal refactor.

## Verification

`ruff check`, `ruff format --check`, `mypy` (strict, 295 files), and `pre-commit run --all-files`
all clean. Full suite 3737 passed, coverage 85.09% over the new 80 floor. The ForgeFlow replay
canary reproduces byte-for-byte (`sha256:63b3a83a…`). The shared-feed path renders both committed
pages identically to the sweeping path (`--sweep-to` then `--check --from-feeds` for both, and the
plain `--check` for all three, all report "current").

## Open next

WS10 (#451, prompt caching and unified budgets) and WS11 (#452, one agent table / one attempt loop
/ proven seam) remain, plus follow-ups #455 and #461. The action SHA-pinning above is the one loose
end from this workstream.
