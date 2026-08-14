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
| `expected-findings.yaml` | Authored (#327) — two findings resting on the documents' own affirmative statements. |
| `expected-documentation-gaps.yaml` | Authored (#327) — two gaps, each with a paired question. |
| `expected-questions.yaml` | Authored (#327). |
| `expected-rejections.yaml` | Authored (#327) — the claims the documented controls contradict. |
| `reviewer-notes.md` | The checkpoint guidance for whoever plays the reviewer. |

The scenario also carries a recording (`../recorded/`, #327), so `trace evaluate husky-ai`
replays it offline and scores it against these files. The findings rest on affirmative
statements — the password-only experimental boundary in a security-notes document that
states its own completeness, and API keys placed in a storage account — never on the
silences the threat-truth header lists, which resolve to the gaps.
