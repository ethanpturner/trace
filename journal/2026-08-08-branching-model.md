# Adopting a branching model

**2026-08-08** · Stage 1

Introduced a `develop` integration branch so that `main` holds released history rather than being
the branch daily work lands on.

```
feature/*  --squash-->  develop  --merge commit-->  main
```

Four pull requests: two feature branches into `develop`, and two release pull requests from
`develop` into `main`. The second release was the useful one — it proved the model rather than
merely exercising it.

## What made this harder than expected

The branching model was decided in one sentence. Making the repository actually support it took
three corrections, each caused by a setting that had looked correct in isolation.

**A protection rule set earlier the same week blocked the model outright.** When `main` was first
protected, it was given `required_linear_history` and merge commits were disabled — reasonable in a
world where every change arrives as a squashed pull request onto a single branch. A `develop`
branch invalidates that reasoning: a release must be a merge commit, so the rule had to come off
and merge commits had to be re-enabled. Worth recording as a reversal rather than quietly
adjusting it. The original decision was not wrong for the topology it was made in; it was wrong for
the one adopted a day later, and there was no way to see that at the time.

**Squash and rebase are both actively harmful for a long-lived branch.** The tidy-looking options —
squash each release into a single commit, or rebase to preserve granularity while staying linear —
both leave `main` holding a commit that is not an ancestor of `develop`. The consequence is not
cosmetic: the *next* release pull request re-proposes every already-released commit and conflicts.
This is precisely why git-flow specifies a merge commit at release, a detail that reads as
convention until the failure mode is traced out.

**The settings then deadlocked each other.** After the first release, `develop` sat one commit
behind `main` — the merge commit, with identical trees. At that point `main` required branches to
be up to date, so the next release would demand `develop` contain it; bringing it across requires a
merge commit; and `develop` required linear history, which rejects one. The next release would have
been unmergeable with nothing on either settings page explaining why. Found by asking what the
following release would do, not by hitting it.

Both settings are now off, with the reasoning written into CLAUDE.md rather than left as folklore.
Requiring `develop` to be current with `main` is circular in this topology: `main` only ever
receives commits from `develop`, so the merge commits it accumulates carry no content `develop` is
missing.

## Decisions

- **`main` stays the GitHub default branch.** Deliberate, and it has a cost: a fresh clone lands on
  `main` and `gh pr create` defaults there, so a feature branch can start from the wrong place
  without anything objecting. CLAUDE.md calls out both. This is the one sharp edge in the setup.
- **Features squash into `develop`; releases merge into `main`.** The two are not interchangeable
  and the reason is written down.
- **`develop` is protected identically to `main`.** Its deletion block is load-bearing rather than
  symmetric — the repository auto-deletes head branches on merge, so a release pull request would
  otherwise delete `develop`.
- **`develop` keeps the up-to-date requirement** even though `main` does not. A feature should be
  current with `develop` before merging; that catches semantic conflicts CI cannot see.

## Verification

The second release is the evidence. It contained exactly one commit, with a merge base of
`73b9305` — the previous release's `develop` tip — so the already-released work from the first
release did not reappear. That is the property squashing would have destroyed, observed rather than
asserted.

One API note worth remembering: `DELETE /branches/{branch}/protection/required_linear_history` does
not exist. The call returns without error and changes nothing. Linear history is only settable
through a full `PUT` of the protection payload, so a read-back is the only way to know whether the
change took.

## Open

- **Hotfixes are undefined.** The model covers planned work. Nothing describes what happens when a
  fix must reach `main` without waiting for `develop`. `develop` was left able to accept a merge
  commit from `main` so the option stays available, but no convention exists yet.
- Everything from the previous entry stands: no threat model, `demo/forgeflow/expected/` empty, and
  Stage 1 unfinished — no domain models, no persistence, no real CLI.
