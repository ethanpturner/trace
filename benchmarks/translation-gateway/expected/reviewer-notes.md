# Helpdesk Translate reviewer notes

Guidance for whoever plays the reviewer at the two checkpoints in a benchmark run.

## Checkpoint 1 — context

Approve the context as extracted. The three documented claims — full body sent, no
retention agreement, over-scoped token — are the scenario's load-bearing facts.

## Checkpoint 2 — findings

Two findings are expected: the missing provider agreement (severity guidance `high` — full
customer content is in scope) and the over-scoped token (`medium`). Reject any finding that
asserts what the provider does with the text; that is unknown, and REJ-TG-01 names it.
