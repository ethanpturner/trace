# M7 closes: the pipeline learns to measure itself, and the thesis becomes a number

Six issues (#266–#271), and the sentence `benchmarks/scenarios.yaml` carried since M2 — "Nothing
reads this file yet. The evaluation harness is not built." — is gone. The harness reads it, drives
the ordinary pipeline over recorded scenarios, and the project's central claim now renders as a
table anyone can regenerate from the repository.

## The harness is a caller, not a second pipeline

DEC-073's insistence carried the whole milestone: the harness drives `run_assessment` /
`resume_assessment`, the same nodes and stores an interactive assessment uses, answering both
checkpoints from recorded decisions through the same writers. The temptation to re-implement the
pipeline for speed is exactly what DEC-073 forbids, because a harness that bypassed a checkpoint or
kept private state would quietly change what every downstream measurement means. Two homes for
results — `EvaluationResult` rows authoritative with the assessment, a derived gitignored feed
under `benchmarks/results/` for the scorecard — resolved DEC-073's open question the way DEC-062
resolves its kind: the feed regenerates by one command, so it earns no place in history.

Ablations became a real schema change: `WorkflowRun.ablations`, marked from birth by `start_run`,
with the driver substituting named stand-ins so the table still sees every declared node. An
ablation is a *named removal on a marked run*, never a silent skip.

## #267 was already done, and saying so was the work

The ForgeFlow observations and reviewer notes #267 asked for had been authored during M5's
alignment pass. The honest move was to verify that against the layout tests and close the issue as
satisfied rather than re-author what existed — the decision-log discipline applied to an issue
whose body was a stale snapshot.

## Four scenarios, and the shape of a benchmark that runs

#268 authored four small architectures, each exercising one catalog mechanism: delegated auth
(the password-policy false positive), inherited encryption (the encryption false positive), a
documented-absent signature check (a finding), and contradictory retention docs (a finding plus an
observation). The two finding-bearing ones carry recordings and score their finding; the two
zero-finding ones carry their truth sets with recordings pending, and the harness names them
skipped. Authoring them surfaced two harness bugs — a recording's assessment id had to be rebound
to a shared-store run, and a bare `recorded/` directory was being run empty — both fixed where
they belong.

## The thesis, finally a number

#269 is the milestone's point. Two single-pass baselines through the same seam, same documents,
same matcher, scored honestly: on the zero-finding scenarios the generic baseline invents exactly
the false positives the catalog names — a local password policy where auth is delegated,
encryption where a managed platform provides it — and the structured baseline, given the
discipline in one prompt, produces none. The contrast is the project's whole argument, and now it
is `false_positive` counts a skeptic can re-derive.

#270 answered the other half — does each stage earn its place? Removing evidence validation raises
unsigned-webhooks' false-negative rate from 0 to 1: the finding is lost without it. Measuring that
required stopping before the report, because an ablation changes the finding set and the recorded
report sections were authored for the authoritative findings — so the orchestrator gained a clean
`stop_before` phase, useful beyond ablations. Stability was the honest refusal: DEC-077 says
recorded replay measures nothing, so `run_stability` refuses the offline profile rather than
present a deterministic zero as a result. The aggregation is a pure function, tested; the live
runs are a manual, priced measurement that gates nothing.

## #271: the boring, auditable page

The scorecard is deterministic HTML from the feeds — counts, rates, cost, no assessment content,
which is a security property because adversarial feeds summarize attack-payload runs. It is
committed and CI-checked from recorded runs, and it carries the thesis in its precision column.
DEC-076 called deterministic generation "auditably boring," which is the compliment.

## Open next

M7 is empty. M8 Adversarial opens with the poisoned-document corpus (#272) as scenario variants,
which the harness's condition axis already anticipates, and the two-axis attack metrics that the
scorecard reserved a column's worth of intent for. The zero-finding scenarios' pipeline recordings
and ForgeFlow's full-truth recording remain the honest debt this milestone names in three
provenance files.
