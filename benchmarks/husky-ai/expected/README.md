# Husky AI expected outputs

**Nothing in this directory is supplied to Trace during an assessment.** The material
Trace reads is `../input/`.

## Provenance

The scenario is derived from the peer-reviewed Husky AI threat model in the
[OWASP Threat Model Library](https://github.com/OWASP/www-project-threat-model-library)
(`threat-models/ai-ml-systems/husky-ai-threat-model.json`, MIT license). The split follows
issue #225: the source's system description — trust zones, components, data stores, data
flows, actors, and the controls it marks `active` — became the input documents, written as
documentation a team would supply. Its threat list became `expected-threats.yaml` and is
never shown to the system. Controls the source marks `suggested` are deliberately absent
from the input documents: they are the source reviewers' recommendations, not the deployed
system, and their absence is part of what an assessment should navigate without concluding
absence-as-vulnerability (DEC-009).

## What is here

| File | Status |
| --- | --- |
| `evaluation-contract.yaml` | The grading policy. Declares no counts (DEC-028). |
| `expected-threats.yaml` | Authored — derived from the source threat list. |

The remaining `expected-*.yaml` files from the DEC-027 derivation are not yet authored.
The layout allows a registered scenario whose `expected/` holds only its contract;
authoring the context, mapping, and finding truth sets is follow-on work and each file
will be added here as it lands.
