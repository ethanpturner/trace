# The live run that did not finish, and the four defects it paid for

## What happened

The #324 capture — the ForgeFlow recording from a live `claude-opus-5` run — ran four times and
finished zero. It stopped for good when the API account's credit balance ran out, roughly $11 in.
That is above the issue's $2.25–$5.97 estimate and bought no recording; what it bought instead is
four live-run defects the offline suite structurally could not see, each now fixed and pinned by
offline tests:

1. **The provider refuses the extraction schema's grammar.** "The compiled grammar is too large"
   — a 400 that precedes the model, bills nothing, and fails identically under `messages.parse`,
   so a large schema had no path to a live call at all. The adapter now resends without the
   server-side format when that specific rejection arrives; the client-side validation it has
   performed since #413 is the enforcement that matters, and the degradation is recorded on the
   outcome's metadata. A fence-stripping unwrap covers the model packaging JSON in Markdown.

2. **Adaptive thinking spends from the output budget.** All three attempts of run two truncated
   at the 16,000-token ceiling — the thinking and the 100KB proposal share `max_tokens`. The
   default is now 64,000 with an 1,800-second deadline, both documented as measured rather than
   guessed. A ceiling is not a purchase; only produced tokens are billed.

3. **The retry feedback said "invalid" and nothing else.** Since #413 the adapter's schema-failure
   message was deliberately generic (section 27), so `run_with_retries` carried feedback with no
   actionable content — run three burned three attempts on four misfilled fields the model was
   never told about. The message now carries field locations and pydantic error types, which are
   schema-shaped and safe; the one exception, `extra_forbidden`'s invented key, is masked unless
   it is identifier-shaped, so a document cannot smuggle prose into `error_message` through a
   field name.

4. **The prompt never stated the vocabulary-term rule.** With locations in the feedback, run four
   converged to two errors and regressed to eight — the model kept writing sentence-long values
   with commas and semicolons into `authentication`, `encryption_in_transit`, and `access_level`,
   because nothing told it those fields are labels. The extract prompt now states the rule and
   where the sentence belongs instead: a claim, a description, or a rationale.

Alongside the fixes: `scripts/capture_forgeflow.py`, a three-stage capture that mirrors the
replayer exactly (staging directory, refuse-to-respend guards, recording wrapper, exported review
files between stages), and the replayer's file list is now derived from the directory so a
capture with a different threat count replaces the recording without code edits.

## The lesson worth the money

Every one of these is the README's "no live provider run has been measured" made concrete. The
offline discipline — deterministic model, recorded responses, byte-identical replays — is what
made the pipeline's logic trustworthy, and it is also exactly why none of these four could have
been found without spending: the deterministic model never serializes a schema, never thinks,
never retries against real variance, and never misfills a field. The capture is not just a demo
asset; it is the only test of this seam that exists.

## Open

#324 stays open, blocked on account credits. When they exist, the capture is three commands and
two authored decision files from done — the machinery is committed and the known failure modes
are spent.
