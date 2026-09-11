# The seed did not survive the architect

Two of the plan's exchange steps ran today: Trace's approved outputs fed into Mantis, in the two
ways Mantis offers.

## What changed

- `results/mantis-seeded-kb/unsigned-webhooks-run-{1..5}.yaml`: five hand-mapped DEC-155 feeds from
  Mantis runs whose knowledge base was pre-seeded with Trace's approved system context. A third
  external row follows on the comparison and scorecard, keyed `external-mantis-seeded-kb`.
- `docs/eval/reviewer-arms.md`: a new section, "The exchange into Mantis", with the seeded-knowledge-
  base comparison against the five unseeded runs and the SAST-seed dispositions.

## How the seed got in

The ADK harness keeps Mantis's workspace in `knowledge.db`, keyed by a run identifier it mints with
`uuid4()` at pipeline start and reads back strictly. There is no flag to set it. A wrapper outside
the Mantis tree pins the harness module's `uuid` reference to a fixed value, writes six files under
that identifier with `record_artifact`, then calls the unchanged launcher. The seed was the approved
context as the recorded scenario renders it: components, actors, assets, flows, the one trust
boundary, the documented no-signature-check statement, and the approved documentation-gap wording for
replay. A grep for truth tokens ran over the seed before every launch.

## What happened

The architecture stage read all six seeded files in every run, and rebuilt all six from code in
every run. Its skill says to rebuild from scratch when no snapshot is pinned, and the harness has no
snapshot mode, so that was the only outcome available. The sentence that replay is undetermined did
not survive the rebuild in any run. What survived was structure: the two external platforms the seed
introduced as entities stayed as entities in all five rebuilt knowledge bases, and the threat models
say more about the outbound boundary.

The number the seed was meant to move did not move the way one might hope. Unseeded, Mantis asserted
the replay ledger as inadequate protection in 3 of 5 runs; seeded, in 5 of 5. The recall it does
not need help with stayed at 5 of 5. Spurious claims went from 14 to 16 over five runs, and the
signature concordance stayed at zero. Reading the transcripts, the reason is plain: the stages that
decide what to investigate never saw the seed, only the architect's rebuild of it. This is an
observation about one harness and five runs, and the page says so.

## The SAST seed

Mantis documents an intake for external findings, the SAST-seed JSONL, and the ADK harness does not
consume it. The two Trace candidates (the approved finding, and the approved gap as a LOW candidate
that says it is a gap) went into the finding store directly, and a review-only workflow ran twice.
Both times the reviewer routed `confirmed` and the critic `viable` on the authenticity finding, the
calibrator scored it 2.0 of 10 and LOW because no reproduction was attempted, and the replay
candidate was left LOW with a note that it must not be confirmed without evidence. Neither reached
`VALID`: the harness has no tool by which a reviewer writes a per-finding status, so the vocabulary
that would answer "did it survive the gates" is not reachable here. Two runs, $1.30.

## Cost and attestation

Seven runs, $14.72 at list price against a $22 cap. Every run is attested in the attestrun
manifests under the session's `exchange-b/manifests/`, all `verified`.

## Open

- A seed placed after the architecture stage, through a workflow that skips it, would test whether
  the threat-model stage honours a documentation gap it can actually read.
- Skills mode, where a human runs the architecture skill against an existing knowledge base, is the
  path Mantis's README describes for "internal documentation"; it was not exercised.
- The record-before-send reliability claim appeared in all ten Mantis runs on this scenario and names
  no requirement in catalog 0.1; whether the catalogue should carry a delivery-integrity requirement is
  a DEC-149 argument to make from the inputs, not from these runs.
