# The external arm: scoring a tool that cannot run through the seam

DEC-074 drew a line four weeks ago: a baseline runs through the seam, emits the schemas the agents
emit, and is scored by the same matcher, or it is not a baseline. STRIDE GPT stayed in the
portfolio write-up because a wrapper would measure the wrapper. That line held, and it left a
question open that this session closes: what does the harness do with a tool whose output is
worth scoring but which cannot be *run* here at all?

## What prompted it

Google open-sourced Mantis on 2 September: nineteen prompt files a coding agent follows to find,
reproduce, and patch vulnerabilities in source code. It publishes no precision figure, no
stability figure, and no replayable run. OpenAI's Codex Security CLI, released the same week, is a
program rather than a prompt suite, emits SARIF and a run manifest, and publishes a recall claim
measured on internal repositories nobody outside can re-run. Neither reads architecture
documentation. Both read code, and no Trace scenario contains any.

The plan that came out of the landscape survey is to write code for two scenarios from their truth
sets, run both reviewers on the same OpenRouter model five times each, and score what they produce
under the negative set. That plan needs one thing the harness did not have: a way to score findings
that arrive as a tool's JSON rather than as a seam call.

## The decision

DEC-155: an **external arm**. A person maps each of the tool's validated findings to a catalogue
requirement and a component name under the DEC-056 rule and records the mapping, with reasoning,
in a committed feed under `results/<arm>/<scenario>-run-<N>.yaml`. The harness scores the rows by
`score_produced` — the baseline scorer, now public — and nothing else, so matched, missed, divergent
(DEC-148), conditional-unreached (DEC-133), spurious, and the DEC-154 rejection breaches are
classified under exactly the rule every other arm is classified under, ties resolved in the external
tool's favour.

Three things the feed carries that a baseline feed does not, because the arm's honesty depends on
them. `models:` for DEC-136 attribution, since the model is not read from a recording envelope
here. `provenance:` as `captured` or `authored`, because DEC-152 applies to any zero this row might
show. And an `unverified:` list: findings the tool itself left unproven — `failed_to_reproduce`,
`not_attempted` — which enter no metric. Mantis's own README says a failed reproduction "does not
definitively mean it is a false positive." That is DEC-009 in Google's words, and the feed states it
back to the tool: unverified is unverified, never a miss and never a match.

Citation fidelity is ported to code. A baseline cites a passage and DEC-151 measures whether the
passage resolves; an external tool cites `path:line`, and given the worktree at the snapshot it
reviewed, each locator either resolves or does not. Without a worktree the metric is not emitted
(DEC-150). With one, the comparison cell shows counts and a rate only over five or more.

## What was refused

A Mantis skill emitting Trace-shaped proposals. It would be a seventh agent, and DEC-030 refused
one with far less at stake. A parser promoting another model's conclusions into `documented`
context claims. DEC-070's parsers quote what an artifact *states* — a port, a route; a reviewer's
finding is a model's *conclusion*, and promoting it is the fabrication DEC-118 and DEC-140 refused.
And a similarity threshold anywhere in the mapping: the mapping is a person's record, and the
reasoning stays in the feed file where a reader can dispute it, never on a rendered page.

## What it looks like

```
uv run trace evaluate --external results/mantis/ --worktree /tmp/uw-code
```

One block per run: matched keys, missed, divergent, spurious with the count that names no
requirement at all, unverified, rejection breaches per mechanism, locators resolved of total. Where
an arm has several runs on one scenario, the per-item agreement across them follows — the DEC-077
shape, read from derived feeds rather than driven live. The comparison table gains a row per arm,
labelled `external, non-authoritative`, attributed, with its provenance inline, and a footnote
naming the tool, its version or commit, and the snapshot. No feed committed means no row, no
footnote, and a page byte-identical to yesterday's.

## Open next

The `results/` directory is empty. The first feed needs the coded scenarios (the other fork's
work), a reviewer run, and an afternoon of mapping. The mapping protocol — who maps, whether a
second mapper checks, how a disputed row is recorded — is written into DEC-155's open questions
rather than decided here, because the first mapping will teach more about it than a paragraph
written before one exists.
