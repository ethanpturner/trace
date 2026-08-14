# Husky AI reviewer notes

Guidance for whoever plays the reviewer at the two checkpoints in a benchmark run, so runs
stay comparable (DEC-023 attributes decisions; this file keeps them consistent).

## Checkpoint 1 — context

Approve the extracted context as long as documented claims cite the security notes or the
overview. The completeness statement in the security notes preamble ("records what is
implemented; does not list planned work") is load-bearing for FND-HA-01 — a context that
carries it as a documented claim is extracting well.

## Checkpoint 2 — findings

Two findings are expected (see `expected-findings.yaml`); severity guidance is `medium` for
both. Approve a finding only if its evidence is the documented mechanism — the password
authentication summary, the API-key storage placement — and reject any finding that rests on
silence: absent integrity validation, absent rate limiting, and absent storage encryption are
the gap, the gap, and the rejection this scenario grades.
