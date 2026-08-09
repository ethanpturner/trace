# 2026-08-09 — Three mapping decisions, one of which reversed my own recommendation

Closes #27, #29, and #33 as DEC-024, DEC-025, and DEC-026. All three govern the Requirement and
Control Mapping step, and they were taken together because deciding them apart would have risked
three answers that did not fit each other.

## I had recommended something the data contradicts

The #27 issue body — which I wrote — recommended "a deterministic requirement retrieval and
applicability pre-filter, with the Control mapper as the single model-assisted mapping agent." I
then told the M3 research team to assume it, and DEC-014's framing repeated it.

Checking the catalog before writing DEC-024 was the first time anyone verified the pre-filter had an
input. It does not.

`applicable_technologies` is **the only structured filter field in the section 17 schema, and it is
populated on zero of the twenty-three requirements.** The other candidates fail for their own
reasons: `applicable_conditions` and `non_applicable_conditions` are populated on all 23 but are
free text, deliberately, because `requirements/README.md` records that no vocabulary was fixed so one
could be observed first. Category has data — 17 distinct values — but filtering on it means deriving
a category from a threat, and that derivation is a judgment. Doing it with a hand-written table
reproduces the mechanical checklist behaviour the project exists to reject; doing it with a model
makes a seventh agent.

So the pre-filter is not merely unnecessary. It has nothing to filter on.

The whole catalog is passed instead — 23 requirements, roughly 12,600 tokens, and the single largest
stable cacheable prefix in the pipeline. There is one mapping agent, as `agent-design.md` section 12
always said.

What I want to record is not the correction but how ordinary the error was. The recommendation reads
plausibly. A deterministic pre-filter is the right instinct, `applicable_technologies` is exactly the
field it would use, and the field exists. Only its contents contradict the plan, and that is one
query away from anyone who thinks to run it. I did not, for three days, while writing the
recommendation into a backlog issue and two other decisions.

## The prohibition that invites the wrong reading

Section 12 prohibits "apply every catalog requirement to every component" and makes undiscriminated
applicability a failure condition. Read quickly, that sounds like an instruction to narrow the input.

It is not — it constrains what the agent *concludes*. Reading it the other way produces a system that
silently never considers most requirements, and the failure is invisible, because a requirement that
was never shown produces no mapping to inspect. That is a false-negative machine that looks clean.

So discrimination is enforced at the output: every mapping carries a reason, and a run where nothing
is marked not-applicable is flagged.

## Threat-gating, stated rather than assumed

`ControlMapping.threat_id` is required, so a requirement is only ever evaluated through a threat.
DEC-024 keeps that and states the consequence plainly: **a requirement that applies to the system but
that no threat reaches is never evaluated and appears nowhere.**

Coverage is therefore bounded by threat generation. I nearly made `threat_id` optional to close it,
and did not, because a system-level applicability pass is a different feature with its own agent
question. It is recorded as a gap with the false-negative rate as the only thing that would detect
it, which is weaker than I would like.

## Suppression had to become visible

DEC-011 added `common_false_positives`, and its own tradeoffs say "nothing yet enforces that the
field is consulted." It is populated on all 23 requirements with 51 entries and read by nothing.

The argument for recording suppressions is a measurement one. The catalog encodes fifty-one specific
wrong conclusions. If suppressing one leaves no trace, a catalog entry that is too aggressive
produces a false negative that no metric can attribute — the rate moves and nothing says why.

The part I am happiest with is the enforcement. Deciding whether a free-text entry *matches* a
proposed conclusion is a semantic judgment, and a validation node attempting it would be a model call
inside a deterministic node. So the check is structural: a mapping proposing `unmet` against a
requirement that has such entries must say why they do not apply. That is checkable without judgment,
and it converts "the agent never looked" into "the agent looked and said why."

## The third field removed for the same reason

`Control.inheritance_scope` was free text. `Control` already carries `provider_component_id`,
`protected_component_ids`, `protected_asset_ids`, and `limitations` — who provides it, what it
covers, where coverage stops. The scope string described the same thing in prose, could disagree with
the structured fields, and nothing said which was right.

That is the third field removed across recent decisions for the same shape of reason:
`checkpoint_reference` whose referent had gone, `confidence_score` that nothing consumed, and now
this. All three were plausible when written and became redundant as the things around them were
decided.

The removal is the small part. What matters is the two-state distinction — `inherited` plus
`implemented` with evidence versus `inherited` plus `claimed` without — because the ForgeFlow
intentional non-findings turn on it. The failure mode is not getting the scope wrong; it is
collapsing "undocumented" into "absent."

## Open next

Five M0 decisions remain: #35 (CLI versus web), #37 (severity), #38 (report template), #39
(benchmark layout), and #19 (the threat model, which needs no decision at all).

DEC-024 has the shortest expected life of anything decided so far. It works at 23 requirements and
will not at two hundred, and the trigger — a catalog whose token count stops being comfortably
cacheable — is stated but not measured.
