# Invoice Agent expected outputs

**Nothing in this directory is supplied to Trace during an assessment.** The material
Trace reads is `../input/`.

## Provenance

Derived from the annotated insecure invoice-agent sample in the
[GenAI Agent Security Initiative](https://github.com/GenAI-Security-Project/GenAI-Agent-Security-Initiative)
(`code_samples/agentic_top_ten/frameworks/pydantic/invoice_agent`). The sample names goal
manipulation and memory poisoning as the vulnerabilities it demonstrates; the remaining
expected threats derive from facts its code states plainly. The source repository carries
no asserted license, so everything in this scenario is written originally from those
facts and the source is cited by URL only — the same posture the severity rubric
references take with AIVSS.

This is the first agentic scenario: the subject under assessment is itself an LLM agent,
which is the ground the ASI Agentic Top 10 covers and ForgeFlow only touches.

## What is here

| File | Status |
| --- | --- |
| `evaluation-contract.yaml` | The grading policy. Declares no counts (DEC-028). |
| `expected-threats.yaml` | Authored — derived from the sample's described vulnerabilities. |

The remaining `expected-*.yaml` files from the DEC-027 derivation are not yet authored;
each will be added here as it lands.
