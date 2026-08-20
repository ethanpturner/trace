# The sweep unparked: two pilots, a model verdict, and the first gateway capture promoted

The day the #484 sweep stopped being budget-parked and started being measured. Three PRs merged
ahead of this one — OpenRouter behind the OpenAI adapter (DEC-135, #618), scorecard model
attribution (DEC-136, #619), and the profile re-pointed to `openai/gpt-5.1` after the
flash-tier model failed in practice (#620) — and then the pilots ran, and one of thirteen
sweep scenarios is captured, promoted, and committed.

## The model was chosen three times, each time by a harder test

The trivial copy-task probe picked `google/gemini-3.7-flash`; the first real capture stage
exposed it — a schema-valid, completely empty extraction, twice, the second time burning 50k
reasoning tokens to produce nothing. The rebuilt probe ran the actual extract stage on two
scenarios across six candidates and picked `openai/gpt-5.1` (the only zero-retry candidate).
The pilots then priced the finalists: gpt-5.1 completed crypto-wallet end to end at $5.23;
`kimi-k2.6`, four times cheaper by rate, spent two hours failing to get through one evidence
batch across two attempts — one wedge, one timeout-into-retries — and was stopped. The lesson
worth keeping: **probe capture models with the pipeline's own stages, never a toy task, and
price reliability in wall clock, not only in dollars.** Each verdict is an amendment on
DEC-135 with the tables recorded.

## The crypto-wallet capture

The third live-captured scenario, the first through the gateway, and the first live run of the
DEC-134 batched evidence shape — six batches, every subject named, none silently omitted,
which is what #585/#588 built. The capture survived an external kill that orphaned its run
(the #613 shape, with new forensics filed on the issue: SQLite journal recovery can rewind the
run row to the checkpoint-1 pause while committed object rows survive — two inconsistent
states, not one) and recovered at zero re-spend through the DEC-091 rebuild: discard the data
root, replay the staged prefix, spend only on unanswered calls. Round trip verified
byte-for-byte after one self-inflicted lesson (the round-trip scenario must carry the registry
name — the assessment name is in the report bytes). Reviewer decisions: all 52 context objects
approved with two `internet_exposed` corrections and both blocking questions answered as
undetermined; one of three finding candidates approved (medium), two rejected on DEC-009
grounds. Against the scenario's deliberately authored zero-finding truth set the approval
scores spurious — lens divergence on exactly the hedged statement the scenario was built
around, recorded in provenance as the measurement it is, reconciliation being #589's.

## Instruments that worked on their first real use

DEC-136's attribution column rendered `openai/gpt-5.1` on the promoted rows and dashes on
every authored row (including forgeflow, whose pre-usage-format capture honestly attributes to
nothing — the usage backfill remains). The registry's DEC-134 pin took its first non-default
value. The capture budget, the staged-envelope recovery, and the refusal-on-rerun all behaved
under real interruptions.

## Open next

Twelve scenarios remain at a measured ~$5.25 each (~$70–80 with baselines and the DEC-077
stability protocol) — a tenth of the rate that parked the sweep, four times the flash-tier
projection that bought nothing. The operational playbook (detached stages, envelope-count
progress, wedge signatures, rebuild-from-staging, the promotion checklist) is written and
proven; the remaining captures are parallelizable in waves of three or four, with
checkpoint-decision authoring between stages as the human-scale step. Day's total spend
including every probe and both pilots: roughly $12.
