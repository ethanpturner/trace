# Release record

The longitudinal record evaluation-plan section 17 specifies: every release records its
version, date, major changes, evaluation summary, known regressions, and outstanding issues.
Sections are authored, newest first. The evaluation-summary block inside each section is
generated from the committed artifacts by `scripts/build_release_record.py` and rewritten in
place between its markers — the numbers a release claims are the numbers the artifacts hold,
and `--check` fails on drift. `tests/unit/test_release_record.py` holds every section to the
section-17 shape and every git tag to a section.

## v0.1 — 2026-08-18

### Major changes

The first release: the complete MVP pipeline. All six model-assisted agents behind
deterministic validation nodes, fourteen orchestrated phases, both structural human
checkpoints, and the rendered sixteen-section report with a derived HTML view (DEC-108). The
evaluation harness replays fourteen registered scenarios offline — thirteen authored
recordings beside the live-captured ForgeFlow flagship — with baselines, ablations, the
adversarial condition, and a CI-checked scorecard carrying cross-version trends. Two provider
adapters sit behind the model seam under one conformance contract, the OpenAI adapter on the
Responses API. The DEC-070 parser family is complete (compose, OpenAPI, Terraform JSON, and
the org-controls assertion), the requirements catalog stands at 0.3 with the OAuth/OIDC and
fine-tuning packs, and the mapping catalog rides a cached prefix with the partitioning
alternative measured and closed (DEC-105, DEC-107). The three delivery waves that assembled
this surface are recorded in the journal and the decision log (through DEC-115).

### Evaluation summary

<!-- evaluation-summary -->
- Retained snapshot 2026-08-18 (git `cfedb65`, catalog 0.1), the latest in `docs/eval/history.jsonl`.
- Pooled over 16 authoritative rows across 14 scenarios: precision 80%, recall 84%, F1 82%.
- Live stability (DEC-077): 5 runs of `unsigned-webhooks` on `primary-development`, 3 failed, mean cost $6.92 per completed run. Everything else replays offline; a dash on the scorecard is unmeasured, never zero.
<!-- /evaluation-summary -->

### Known regressions

None recorded — this is the first entry, so there is no prior release to regress from. The
live-capture caveat carries forward rather than regressing: the flagship live run's approved
findings matched none of the truth set's three expected findings. Diagnosed after this release
(#564, DEC-116): the expected requirement lenses were produced as mappings and lost in the
evidence-validation funnel — see `docs/eval/live-diagnosis.md`; the release-time reading
("wrong requirement lens", `demo/forgeflow/recorded/provenance.md`) understated the mechanism.

### Outstanding issues

- The keyed live-measurement track: the eleven-scenario live sweep with live baselines (#484),
  the prompt-version comparison recording (#331), and the model comparison recording (#332) —
  now cheaper to attempt, with capture rehearsal (DEC-091 amendment) costing nothing first.
- The narrated demo video (#353).
- A genuinely second annotation pass for the agreement instrument (DEC-112), and real
  organizational facts for the org-controls catalog (DEC-115).
