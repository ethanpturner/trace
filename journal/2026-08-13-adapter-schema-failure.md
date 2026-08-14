# The audit, and the adapter owning its own validation

## What happened

A forensic documentation-versus-implementation audit ran over the whole repository: every README
claim, CLAUDE.md rule, decision-log entry, and threat-model row checked against the committed
source. Eighteen issues came out of it (#395 through #412), and the first was fixed in this
session's change.

The audit's shape was unexpected. The usual finding — features claimed, code missing — barely
appears. The pipeline's claims held: the transition table, both checkpoints, the DEC-013 outcome
table, the report path, the requirements loader, the stores, and the evaluation metrics all
verified against their documentation. The gaps ran the other way — the docs understate the code.
The M0-wave paragraph still calls sixteen built and tested decisions unbuilt (#410); the threat
model carries Designed rows whose enforcement has existed for milestones (#411). The genuine code
defects cluster at the edges nothing offline exercises: retry and ceiling accounting (#396, #397,
#398), unwired reviewer actions (#399), the dead sixth trigger (#400), evaluation rendering and
gating (#403, #404, #405), and the adapter (#395, #412).

## The fix: #395

`messages.parse` validates each text block client-side and raises `pydantic.ValidationError` when
the text does not fit the schema — the exact shape of a `max_tokens`-truncated response. The
adapter's `anthropic.*` exception ladder cannot catch it, so the one exception the adapter's
contract exists to prevent escaped on the very responses its failure branches were written for,
and took the raw output `data-model.md` section 33 requires preserved with it.

The fix moves the validation into the adapter. It sends the same wire request through
`messages.create` — the schema through the SDK's own public `transform_schema`, merged into
`output_config` exactly as `parse` merges it — then checks `stop_reason` first, so truncation
reports as truncation, and only then validates the text itself, returning a `ModelFailure` that
carries the raw output either way. The new offline test file drives the adapter through a stub
client with the responses a live provider would need to be coaxed into producing, and asserts the
request shape — the section 29 effort mapping had no offline test at all.

## What the fix uncovered

Reordering the call exposed a latent live-run blocker: `ContextExtractionProposal` cannot be
transformed for the structured-output format at all. `ContextClaimProposal.value` is
`pydantic.JsonValue`, whose schema contains the unconstrained `{}`, and `transform_schema`
refuses it — under `messages.parse` exactly as under this adapter. The first live agent call
would have failed before a request was sent. Nothing offline noticed because the deterministic
model never serializes a schema for the wire, and the opt-in integration test uses a toy schema.
Filed as #412; the adapter now returns the condition as a classified `INVALID_REQUEST` failure
rather than raising, which is the contract's job, and the schema change is #412's.

That discovery is the audit's thesis in miniature: the README's "no live provider run has been
measured" is not a formality. The measurement would have found this on call one.

## Open next

#412 is the natural next change — the proposal schema needs a `value` shape the provider accepts,
which is also the shape the prompt should be teaching. The retry-accounting pair (#397, #398)
touch the same node loop and should land together.
