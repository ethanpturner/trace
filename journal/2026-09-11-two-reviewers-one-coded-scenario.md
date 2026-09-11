# 2026-09-11 — Two code reviewers on the first coded scenario

The coded scenarios (DEC-156) and the external-arm scorer (DEC-155) landed yesterday so that this
could happen: a code reviewer and the documentation pipeline measured on the same system. Today
Google's Mantis and OpenAI's Codex Security reviewed `unsigned-webhooks/code/` at `c5b0590`, both on
`gpt-5.6-sol` through OpenAI's API so that the model is not a variable, and their findings were
hand-mapped and scored. The page is `docs/eval/reviewer-arms.md`; the two rows are on the
comparison.

## What changed

- `results/mantis/unsigned-webhooks-run-{1..5}.yaml` and `results/codex-security/unsigned-webhooks-run-4.yaml`:
  the hand-mapped feeds. Every row carries a requirement, a component, a `path:line` locator, and the
  mapper's reasoning; no tool prose.
- The sweep now scores an external feed's locators against the scenario's committed `code/` when it
  exists, so the comparison's evidence cell for an external arm is measured rather than "not
  measured". Before this the sweep passed no worktree and the page could not show what the CLI
  already computed.
- `scripts/score_code_layer.py`: the RealVuln-style scorer over `code-ground-truth.yaml`, with a
  function-span switch for the two `main.py` entries that share CWE-306. Tested against the real
  truth file.
- `docs/eval/reviewer-arms.md`, in the site nav.

## What was found

Both reviewers found the documented weakness in every completed run: Mantis 5 of 5, Codex Security
1 of 1, against Trace's live 2 of 5 on this scenario. That is the negative read the plan wrote down
for recall, and it stands.

Two things cut the other way. Mantis asserted in three of five runs that the delivery ledger is
inadequate replay protection, the exact claim `REJ-UW-01` records a correct assessment does not make,
because the documentation is silent on replay and the truth records a gap. That is 3 of 10 rejections
breached on the documentation-gap mechanism; neither tool touched the false-positive-class
rejection. And Mantis's own review and critic stages confirmed none of its findings: every row in
every run stayed `PROVISIONALLY_VALID`. Scored by the tool's own vocabulary it claimed nothing, so
the recall it earns here is recall it did not stand behind. The page reports both views and says
which is which.

Precision was low in the as-emitted view: 5 matched of 19 distinct Mantis claims, 1 of 3 for Codex
Security. The spurious claims are mostly one shape, unbounded work reachable from the public
endpoint, mapped to `req-TPI-002`; no run flagged any of the four scoring traps.

## Two things about the instruments

Mantis's `signature` is a digest of its own title, so five runs that agree on every finding at the
requirement level agree on nothing at the signature level: Jaccard 0.00, nineteen signatures each
seen once. The identity key measures wording. And in one run Mantis cited the target root and no
file for every finding, so the locator metric fell to 0 of 2 for that run; the other four resolved
every locator.

Codex Security's `--max-cost 3` stopped three attempts inside three minutes with nothing written,
because its bundled price table is stricter than OpenAI's list price. The completed run under a $10
limit cost $4.81 at list price and $6.76 by the tool's own count.

## Open

`rag-support-bot`'s runs are in progress and will get the same treatment. The Mantis `--sync`
snapshot mode does not exist in the ADK harness, so the reviewed SHA is pinned by the run script and
the attestation rather than by the tool; the skills-mode harness would pin it itself.
