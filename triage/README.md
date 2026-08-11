# Issue triage: tiers, routing, and the outcomes ledger

Every open issue carries one `model:[0-3]-*` label saying how sophisticated a model an
unattended "proceed to issue #N" delivery needs. `scripts/triage.py` assigns it: a Haiku
call over the API proposes a tier, deterministic rules clamp it, and the result lands as
the label plus a `<!-- trace-triage -->` marker comment recording the rationale and a
hash of the issue body at classification time. `scripts/proceed.sh N` routes delivery to
the model the tier names via `scripts/tier-models.yaml`.

The design is recorded in `journal/2026-08-10-model-tier-triage.md`. The short form: the
classifier is treated the way Trace treats its own agents — the model proposes,
deterministic code owns the labels, and the guardrails are enforced in code, not prompts.

## Labels

| Label | Meaning |
|---|---|
| `model:0-mechanical` | Transcription-grade; the body states the edit and the checks. |
| `model:1-routine` | Localized and fully specified; every criterion mechanically checkable. |
| `model:2-standard` | Real implementation whose design is already done in the spec. |
| `model:3-judgment` | Decisions, composition work, authored security content, constraint-adjacent work. |
| `model:auto` | Machine-assigned and unconfirmed. Removing it, or hand-editing the tier, is confirmation; human tiers are never overwritten by the script. |
| `model:low-confidence` | The classifier hit a rubric edge; the tier is a floor and `proceed.sh` pauses. |
| `model:escalated` | A cheaper attempt failed and the tier was bumped. |
| `blocked` | Routes to no model until the named blocker closes. |

`type:decision` is tier 3 by hard rule, with no model call. `design-change`,
`needs-decision`, and a content deny-list (decision-log authoring, checkpoint mechanics,
the excerpt fence, log redaction, the model seam, identifier allocation, shared prompt
blocks, CI and branch mechanics) clamp to tier 3 in `triage.py` and are re-checked in
`proceed.sh`, so neither a bad classification nor a mislabel routes them cheap.

## The outcomes ledger

`outcomes.jsonl` in this directory is append-only, one line per delivered issue, written
by the delivering session as the final step before the PR merges (the instruction rides
in the launch prompt). Labels are operational; this file is analytical.

```json
{"issue": 261, "tier": 2, "model": "claude-sonnet-5", "classified_by": "claude-haiku-4-5",
 "outcome": "clean", "escalated_to": null, "date": "2026-08-10", "note": ""}
```

`outcome` is one of `clean` (merged as landed), `rework` (fix commits after review), or
`escalated` (re-run on a higher tier; `escalated_to` names it).

## Reading the ledger

Monthly, or every twenty issues:

```bash
jq -s 'group_by(.tier)[] | {tier: .[0].tier, n: length,
  escalation: (map(select(.outcome=="escalated"))|length)/length,
  clean: (map(select(.outcome=="clean"))|length)/length}' triage/outcomes.jsonl
```

Adjustment rules, in order:

- Escalation above 20% in any tier: the rubric is wrong there; move the borderline
  criterion up a tier in `scripts/triage.py`'s rubric.
- Escalation above 40% at the Sonnet tier: suspend down-tagging (point tier 2 at
  `claude-opus-5` in `tier-models.yaml`) until the rubric changes — beyond that rate the
  scheme costs more usage than it saves.
- Escalation under 5% with clean-merge above 90% for two consecutive readings: loosen
  one boundary downward to capture more savings.
- Fewer than ten issues in a tier: no adjustment; the sample is noise.
