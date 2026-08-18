# Trace

Trace is a context-aware security architecture analysis system. It reads a system's design
documentation, builds an evidence-linked model of what that documentation establishes, and
assesses the system against a version-controlled requirements catalog. The pipeline is fixed:
fourteen phases, six model-assisted agents each backed by a deterministic validation node, and
two human approval checkpoints that are workflow-graph nodes rather than options. Agents
propose schema-validated objects; the application validates and persists them; a person
approves the context and every finding. The deliverable is a sixteen-section Markdown report
in which each conclusion traces back to the evidence that supports it — and where the evidence
does not support a conclusion, the report says so rather than guessing.

![The fixed fourteen-phase pipeline: model-assisted agents alternating with deterministic nodes, through two human checkpoints, to a rendered report](assets/architecture.svg)

This site is a rendered view of the repository's `docs/` tree at the `main` branch. The
Markdown sources in the [repository](https://github.com/ethanpturner/trace) are authoritative;
the [README](https://github.com/ethanpturner/trace/blob/main/README.md) there carries the full
project account, including the demo scenario and the current status.

## Using Trace

These describe the system as it runs today.

| Document | What it covers |
|---|---|
| [Getting Started](guide/getting-started.md) | Install, configure, and complete an offline assessment in one sitting |
| [Assessment Walkthrough](guide/assessment-walkthrough.md) | Running Trace on your own documents, both checkpoints included |
| [CLI Reference](guide/cli-reference.md) | Every command, its flags, and the exit-code contract |
| [Reading the Report](guide/reading-the-report.md) | The sixteen sections, the vocabularies, and the lineage walk |
| [Troubleshooting](guide/troubleshooting.md) | Symptoms, what each one means, and the fix |

## Design corpus

These documents describe the intended system, not the implemented one. All are marked
*Proposed*, version 0.1.

| Document | What it covers |
|---|---|
| [Vision](product/vision.md) | Problem, users, principles, what Trace is not |
| [Design Principles](product/design-principles.md) | The principles in full, with rationale |
| [Roadmap](product/roadmap.md) | Seven-stage sequencing and stop conditions |
| [Demo Script](product/demo-script.md) | The ten-beat offline walkthrough and its recovery plan |
| [Ablation Narrative](product/ablation-narrative.md) | What each removed component changes, measured, with the framework story |
| [Future Features](product/future-features.md) | Deferred ideas and what would promote them |
| [Project Scope](architecture/project-scope.md) | MVP boundaries, non-goals, constraints |
| [Current Architecture](architecture/current-architecture.md) | Pipeline, components, proposed technology |
| [Agent Design](architecture/agent-design.md) | The six agents, deterministic nodes, safety properties |
| [Data Model](architecture/data-model.md) | Domain objects and the lineage chain |
| [Evaluation Plan](architecture/evaluation-plan.md) | Benchmarks, baseline comparison, metrics |
| [Decision Log](architecture/decision-log.md) | The accepted and rejected decisions |
| [Threat Model](architecture/threat-model.md) | Trace's own security boundaries, and where each mitigation is enforced |
| [Adversarial Defence](architecture/adversarial-defence.md) | The structural defence against prompt injection, demonstrated |

## Evaluation

The evaluation harness replays recorded benchmark scenarios against authored truth sets. The
committed results render here:

- [Scorecard](eval/scorecard.html) — per-scenario metrics across conditions, regenerated
  offline from recorded runs and checked current by CI
- [Model comparison](eval/comparison.md) — the recorded conditions side by side
- [Ablation results](eval/ablation.md) — what removing each component changes

## Presentation

The [presentation materials](presentation/README.md) — the deck, its claim-by-claim
[traceability table](presentation/traceability.md), and the one-page
[handout](presentation/handout.md) — cite the repository rather than duplicating it.
