# 2026-09-10 — Two scenarios gain the system they describe, as code

The corpus had fifteen scenarios and no source code. Every reviewer the portfolio now wants to be
measured against reads code only, and no public corpus pairs code with design documentation and
an authored truth set. This session wrote the code for two scenarios and decided how it lives in
the corpus (DEC-156).

## What changed

`benchmarks/unsigned-webhooks/code/` is a FastAPI service that receives deployment events and
posts them to chat. Its receiver parses and dispatches any well-formed body. It ships a correct
HMAC helper with a constant-time compare and never calls it; the shared secret is accepted in
configuration. That is FND-UW-01 made literal, and the unused helper is the first trap: a reviewer
has to decide whether an unused correct control is a control.

`benchmarks/rag-support-bot/code/` is the Relay Answers service. Its retrieval call resolves the
caller's workspace from the bearer token, charges the quota, and then searches one shared index
with no workspace argument, although every chunk carries the workspace it came from. That is
FND-RSB-01 made literal. Its deletion-propagation job exists, which the documentation never says,
and keys on tombstones the export may or may not emit, which the documentation cannot say.

Each is a standalone project with its own lock, runs with one command, and has five tests that
prove it starts and misbehaves: a forged delivery is accepted and posted; one workspace's pasted
configuration reaches another workspace's citations.

## The decisions, and the one that changed mid-session

**Where the truth goes.** The plan said `code/ground-truth.yaml`. Writing the intent note first
made the problem visible: a code reviewer receives `code/` whole, and a note that says which
module realises which finding is the answer key. Both files moved under `expected/`, where the
one rule the corpus already enforces structurally — nothing under `expected/` reaches the system
under test — covers them without a new exclusion list. A test now fails if any file under `code/`
names a truth key, the truth file, or the note.

**Whose schema.** The code-level truth mirrors RealVuln's ground-truth fields exactly, because it
is the one public code corpus with false-positive traps and a run manifest, and thirty-three
scanners are scored against it. A score against these two scenarios should read beside that
leaderboard. The one divergence is `commit_sha: null`: the file lives inside the commit it would
name, so the pin is the manifest's `code` digest.

**What a gap is in code.** The documentation layer records replay handling and deletion
propagation as gaps because the inputs do not settle them. The code layer could have settled
them either way and would then have described a different system. Instead each is implemented in
a form whose adequacy depends on deployment facts the code does not decide, and recorded with
RealVuln's `scoring: non_scoring` and a stated reason. DEC-009, in a second layer.

**The manifest.** `code` is a sixth group, the package version is 1.1, and the manifest excludes
the scratch a local `uv sync` leaves behind, because a digest that moved on every test run would
answer no question.

## What the layout test now holds

A code layer is a sibling of `input/`, never inside it. Its truth and intent note exist under
`expected/` if and only if it exists. The truth's fields are RealVuln's and no others. Each
scenario authors at least one vulnerability and at least three traps. Every truth location names a
file that exists and a function defined in it. Nothing under `code/` carries an answer key. Each
code layer has a pyproject, a lock, and a README. The manifest digests the group.

## Open

Whether the code layer should reach `nightly-reconciler` and `oidc-portal`, where a code-only
reviewer would be expected to lose most. Whether a run against a coded scenario should record the
reviewer's snapshot identity in the metrics feed beside the manifest digest. The reviewer runs
themselves, which this session did not start: the develop SHA after this merge is the snapshot
both arms pin.
