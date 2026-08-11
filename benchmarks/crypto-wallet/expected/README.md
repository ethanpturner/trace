# Wallet and Exchange expected outputs

**Nothing in this directory is supplied to Trace during an assessment.** The material
Trace reads is `../input/`.

## Provenance

Derived from the cryptocurrency-wallet threat model in the
[OWASP Threat Model Library](https://github.com/OWASP/www-project-threat-model-library)
(`threat-models/web/cryptocurrency-wallet-threat-model.json`, MIT license), itself ported
from the Threat Modeling Cookbook. The source's system description became the input
document; its three-threat list became `expected-threats.yaml` and is never shown to the
system. The source's two unconfirmed assumptions — TLS termination at the load balancer,
and wallet-file encryption being enabled — are carried into the input document as hedged
statements, because surfacing them as questions or assumptions rather than treating them
as facts is part of what the scenario measures (DEC-009).

## What is here

| File | Status |
| --- | --- |
| `evaluation-contract.yaml` | The grading policy. Declares no counts (DEC-028). |
| `expected-threats.yaml` | Authored — derived from the source threat list. |

The remaining `expected-*.yaml` files from the DEC-027 derivation are not yet authored;
each will be added here as it lands.
