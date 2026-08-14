# Wallet and Exchange reviewer notes

Guidance for whoever plays the reviewer at the two checkpoints in a benchmark run, so runs
stay comparable.

## Checkpoint 1 — context

Approve the extracted context as long as the two hedged statements stay hedged: the
wallet-file encryption claim and the TLS termination claim should carry the document's own
qualification, not a resolved value in either direction.

## Checkpoint 2 — findings

No findings are expected. If a candidate finding asserts the wallet file is unencrypted or
that transit is unprotected, reject it — those are the rejections this scenario grades
(`expected-rejections.yaml`). The correct outputs are the wallet-encryption question and the
exchange-store gap.
