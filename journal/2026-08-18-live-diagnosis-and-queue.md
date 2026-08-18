# The live-failure diagnosis, and the queue worked in parallel

Two things happened this session: the flagship live failure finally got its diagnosis (#564,
DEC-116), and the fifteen-feature plan approved this morning became filed issues and then, for
seven of them, merged deliveries — most of them executed by parallel forked sessions in isolated
worktrees while the keyed confirmatory runs occupied the main tree.

## The plan became issues

The fifteen-feature plan was filed as eleven new issues (#564–#574) beside the four that already
existed (#484, #331, #332, #353), plus the docs-truth hygiene issue (#575, delivered immediately
as PR #576) and, later, the DEC-116 batching follow-up (#585). All were triaged through the
standard classifier; the twelve zero-open milestones were closed.

## The diagnosis (#564, DEC-116)

The recorded explanation for the flagship capture's 0-of-3 — "real weaknesses, wrong requirement
lens" — turned out to be wrong. The run produced mappings under all three expected requirements;
they died in an evidence-validation funnel: one call assessed 25 of 185 mappings, DEC-013
resolves an unassessed mapping to no output silently, and the assessed expected-requirement
mappings were downgraded to questions on contradictions the truth set resolves (and disagrees
with itself about — GW-13.2/13.3 expect questions where expected-findings expects findings; the
tension is recorded, not resolved). What changed: omission is now named (`unassessed_subject_ids`
on the validation outcome, node metadata, and the `evidence_assessment_coverage` metric in every
feed), and the wrong explanation is corrected at its sources. What deliberately did not: no
blocking coverage check (replay compatibility), no prompt edit (capacity, not instruction), no
truth-set edit. The behavioural fix — batching per subject group, DEC-024's shape — is #585.

Two runs confirmed the stability half: zero failures (the mechanical section-14 slip stayed
fixed), FND-UW-01 unanimous at two of two, coverage 1.0 in both runs — consistent with the
funnel being a scale behaviour — and DEC-093's replay live for the first time (33 defaulted
decisions per run against the old protocol's ~36; the count now measures novelty). $9.29 ± $0.01
and ~54 minutes per run. The committed n=5 record stands; the confirmation is committed beside
it.

Found along the way: the #534 merge had replaced the `## DEC-092` heading with the DEC-091
amendment paragraph, leaving the entry's body headingless inside DEC-091 through two merges
while the corpus cited it. The heading is restored and the decision-log guard now asserts the
numbering runs contiguously. Also: the provider's grammar-too-large rejection (a designed,
zero-cost degradation) logs as a bare httpx 400 per call and reads like a failure storm on a
live run; the adapter now says what happened at INFO.

## The queue, in parallel forks

Deliveries merged today by forked sessions in isolated worktrees, each with a centrally
pre-assigned DEC number (the collision-avoidance lesson applied in advance): #567 reviewer-time
instrument (DEC-117, PR #578), #571 stale-evidence flags (DEC-118, PR #577), #565's enablement —
the annotation protocol, adjudication rule DEC-119, and a real bug in the agreement instrument's
question-field reading (PR #579; the issue stays open for the human pass), #573 TM-BOM
round-trip accepted as the parser family's fifth member (DEC-120, PR #580), #572 clickable
lineage to the source span (PR #581, no DEC needed), #569 HCL via a deterministic subset scanner
rather than a parser dependency (DEC-121, PR #582), and #568 the fifteenth scenario —
nightly-reconciler, where asserted organizational controls suppress the two false positives a
generic review raises (DEC-122, PR #584, org-controls catalog 0.2).

The mechanics held with friction: the forks' background CI polls died repeatedly, so the
coordinating session finished two merges by hand; develop moved five times during the window and
every later branch paid a conflict round on the two append-only files. The decision log's
append-collision resolution — extract each side's entry whole, splice in numeric order, never
let a heading vanish — worked three times and is now the contiguity guard's job to keep honest.

## Open next

The keyed track in the standing order: the eleven-scenario live sweep with live baselines
(#484) — now fifteen scenarios and worth re-scoping the name — then the comparison recordings
(#331 waits on #585's version pair; #332's OpenAI leg waits on a second provider key). The demo
video (#353) is the last Stage 6 asset. #566 stays gated on the sweep's duplicate-miss rate.
#565 waits for a second human. The `test_evaluate_cleans_up_its_temporary_work_root` flake
(globs the shared system temp; collides with concurrent live runs) is a hygiene candidate, as is
the oidc-portal truth set's stale `catalog_version: "0.1"` pin.
