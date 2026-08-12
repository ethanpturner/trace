# Model-tier triage for the issue backlog

The Claude usage limits started binding, and the response is process rather than
austerity: every issue now carries a `model:[0-3]-*` label saying how sophisticated a
model its unattended delivery needs, so cheap models take the mechanical work and
Opus-class capacity is reserved for judgment. The design came out of three parallel
design passes — one read the issue corpus and built the rubric, one designed the
pipeline mechanics against the repo's conventions, one verified pricing and how
subscription limits pool — and the synthesis landed as `scripts/triage.py`,
`scripts/proceed.sh`, `scripts/tier-models.yaml`, `.claude/commands/triage.md`, and
`triage/README.md`.

## What the design turns on

Two facts carried the decision. Subscription limits are a shared, model-weighted pool
with a separate Opus sub-limit, and the sub-limit is what runs out first: in this
backlog the cheap tiers are roughly a quarter of the tokens but well over half of the
issues, so routing them off Opus frees the capacity that actually binds. And difficulty
here is judgment density, not diff size — the issue bodies are specified well enough
that a long body is often the easy case, while the small-looking changes near the
binding constraints are where a cheap model does real damage. The rubric keys on
judgment signals and never on length.

The classifier is treated exactly the way Trace treats its own agents. A Haiku call
over the API proposes `{tier, confidence, rationale}`; deterministic code decides.
`type:decision` is tier 3 by hard rule with no model call. A deny-list — the labels
`design-change` and `needs-decision`, plus content triggers for decision-log authoring,
checkpoint mechanics, the excerpt fence, log redaction, the model seam, identifier
allocation, shared prompt blocks, and CI posture — clamps to tier 3 in `triage.py` and
is re-checked in `proceed.sh`, so neither a bad classification nor a hand-mislabel
routes that work cheap. Classification runs locally and pay-per-token, never through a
subscription session and never in CI, which stays keyless.

## Decisions made along the way

The synthesis had put the requirements catalog on the deny-list; implementation took it
back off. The rubric's worked examples show catalog edits with named rituals are
exactly the cheap-tier work, and the guarded failure there is loud — the loader and
hash tests convert a subtle mistake into a red CI run. The risk worth engineering
against is behavioral: a cheap model rerunning `catalog_hash.py --write` to silence a
loader failure it caused. That is now a standing instruction in the launch prompt
rather than a static clamp.

Trust is asymmetric by construction. A tier label with `model:auto` is a machine guess
and may be refreshed when the body hash moves; a tier label without it is a person's
word and the script never overwrites it. Escalation strips `model:auto` too — a
recorded failure outranks the classifier. In the expensive direction the tag is
enforced (deny-hits refuse to launch cheap); in the cheap direction it is advisory.

The machine has no API key in `.env`, which surfaced late. `--rules-only` was added so
the backfill could land value immediately: 33 of the 49 open issues are rule-decidable
— the decision-heavy tail of the backlog — and the 16 remaining for the classifier are
the catalog and docs issues the rubric expects to land in tiers 0–1.

## Open next

The Haiku-classified residue needs a key in `.env`, then
`uv run python scripts/triage.py --all-untriaged --apply`. The calibration loop starts
empty: `triage/outcomes.jsonl` accumulates one line per delivered issue via the launch
prompt's standing instruction, and the first honest reading of escalation and
clean-merge rates is twenty issues away. The tier-to-model mapping is data in
`scripts/tier-models.yaml`; retuning it is an edit, not a design change.
