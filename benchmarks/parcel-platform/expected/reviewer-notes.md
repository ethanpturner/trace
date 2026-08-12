# Parcelworks reviewer notes

Guidance for whoever plays the reviewer at the two checkpoints in a benchmark run.

## Checkpoint 1 — context

The context is large — nineteen components across four zones — and the review is mostly
volume. Approve as extracted; the load-bearing claims are the admin sign-in path, the
notification logging, the warehouse copies with their unwritten retention, and the data
zone's stated reachability.

## Checkpoint 2 — findings

Two findings are expected: the admin access path (severity guidance `high` — the console
reaches every customer account) and the notification logging (`medium`). The warehouse
retention and the data-zone enforcement are gaps, not findings, however tempting the size
of the platform makes a longer list.
