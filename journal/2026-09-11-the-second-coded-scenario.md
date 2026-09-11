# 2026-09-11 — The second coded scenario, and the program's totals

`rag-support-bot`'s reviewer runs finished overnight and got the same treatment as
`unsigned-webhooks`: five Mantis runs attested and scored, Codex Security's one attempt scored as a
capped partial, feeds committed under `results/`, the page extended, the comparison regenerated.

## What was found

Mantis matched FND-RSB-01 in 5 of 5 runs and Codex Security's partial in 1 of 1, against Trace's live
3 of 5 on comparable findings. Mantis produced 17 spurious claims over 22 distinct findings and
breached one rejection in ten: run 1 asserted that ticket-borne prompt injection reaches answers
unmitigated, which the documents answer and `REJ-RSB-01` records. Its own gates confirmed nothing,
again.

Two claims recurred in every run and are worth recording. Every Mantis run and the Codex Security
partial say a repository-known development bearer credential is accepted when production token
configuration is absent. The code layer's truth does not list that fact. DEC-149 says a truth set is
edited on an argument from its inputs, not from a run, so the observation is on the page and the
truth is untouched; whoever next opens `code-ground-truth.yaml` for this scenario has the argument to
make. And every run says source identifiers are not qualified by workspace, so one tenant's ingestion
can replace another's chunks: a tenant-separation claim on the write path that the documentation
layer never had to decide.

## Two instrument notes

The RealVuln-style file rule and the requirement rule disagree on this scenario in both directions.
Mantis located the retrieval weakness at the answer endpoint in two runs, which the requirement
matcher credits and the file rule does not; in one run the file rule credited a `replace_source`
finding that shares file and CWE family with the vulnerable `search`. The page reports the rule's
answer and says where it bends.

Codex Security's `--max-cost 10` was enough for 9 files and not for 13. It stopped with a findings
file written, so the partial is scored and labelled; the three earlier $3 attempts wrote nothing.

## The program

Fifteen of twenty planned jobs ran: ten Mantis, five Codex Security attempts of which one completed.
$46.81 at list price against the $60 cap; 2 h 27 min of job time. Ten of ten Mantis runs and both
Codex Security partials are attested and verify offline.
