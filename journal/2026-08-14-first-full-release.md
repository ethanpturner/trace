# The first full release since M4, and the freeze guard meets its first release PR

The session started with a small question — is the architecture diagram done? — and the answer
exposed that everything since release #285 was still sitting on `develop`: ninety-one commits
spanning the M5 through M12 sessions, the Stage 5 evaluation work, the live capture, the
demonstration surface, and the interview package. The diagram was in the README on `develop` and
invisible on `main`, which is what GitHub shows. So the session became the release.

## The release PR

PR #438, `develop` into `main`, merge commit per the branching rules. The body groups the
ninety-one commits by theme rather than listing them; the roadmap's Stage 6 deliverables list is
what the grouping answers to. Preflight was clean: green CI on `develop`'s tip, nothing open
against `develop` worth waiting for.

## The freeze guard re-litigates history, and the fix is a scope condition

The release PR failed CI, and the failure was worth understanding rather than overriding: the
DEC-057 catalog freeze guard flagged all nine `requirements/0.1/` files as touched. Every flagged
change came from #288 — the canonical-citation edit to `source_frameworks` — which merged on
2026-08-10, two days before `versions.yaml` recorded 0.1 as frozen. No commit in the release
touched the catalog after the freeze.

The guard diffs the pull request's whole span against its base. On a feature PR that span is the
proposed edit, which is exactly what DEC-057 wants checked. On a release PR the span is the entire
unreleased history, so the guard re-flags changes that were legitimate when they merged — any
catalog edit that predates its version's freeze will trip every release PR that carries it,
forever, because `main` never catches up except by the release the guard is blocking.

The fix is a condition, not a code change: the guard now skips when the head ref is `develop`.
DEC-057's own wording justifies it — the guard "fails any pull request that proposes an edit," and
a release PR proposes none; every commit riding it already passed the guard in its own PR into
`develop`. Hotfix PRs still run the guard against `main`, which is the correct base for a branch
cut from `main`. This is the guard's mechanism catching up with the decision's intent, not a new
decision, so it carries no DEC entry.

## Open next

- Merge #438 once the re-run is green; `main` then carries the diagram, the scorecard, and the
  interview package.
- `demo/forgeflow/speaker-notes.md` is untracked locally and rides nothing yet; it needs its own
  feature PR if it belongs in the repository.
- Stage 6 remains the open milestone: the portfolio narrative, screenshots or a recording, and
  the public-repository checklist from the roadmap's deliverables section.
