# The section that said none

`docs/eval/exchange.md` landed with a sentence nobody had noticed was load-bearing: both runs'
reports stated that the assessment recorded no documentation gaps, while their packages held
twelve and twenty-five. Filed as #687 and framed there as a design question rather than a bug,
which it turned out to be.

The mechanism was three facts lining up. `DocumentationGap` is created `candidate`. Checkpoint 2's
subjects were the provisional findings and nothing else, so no step anywhere set a gap's status.
Report section 9 filters on `approved`. The section was therefore structurally empty in every
report the project has ever rendered, and `templates/report-v1.md` supplies authored wording for
an empty section — "The assessment recorded no documentation gaps. Every requirement it applied
could be evaluated against the documentation provided." Two sentences, both false whenever a gap
existed, printed by a renderer doing exactly what it was told.

This is DEC-101 again. That decision found section 7 filtering on `Threat.status is APPROVED`, a
condition nothing in the pipeline could satisfy, and fixed it by deriving the threats transitively
from the approved findings. The recurrence is the interesting part: the same class of defect, in
the same document, found the same way — by reading a rendered report rather than a test. A filter
that names a status is a claim that something sets it, and nothing checks that claim.

For gaps there is no transitive set to derive. A gap is not referenced by an approved finding; the
two are alternatives under DEC-009. So the question was who decides a gap, and the answer that
survived was the obvious one: the reviewer, at the checkpoint that already exists. DEC-159 makes
the candidate gaps subjects of checkpoint 2 alongside the findings.

Three things were decided rather than assumed on the way.

**The vocabulary is narrower than a finding's.** Approve, reject, edit. `defer` and
`request_more_analysis` both say more analysis may settle this, and what settles a gap is more
documentation — `requested_evidence` already records what to go and find, and re-running analysis
against the same silent documents produces the same silence. The two conversions are DEC-051's
escape hatches out of a finding resting on silence; a gap is already on that side of the line.

**There is no severity gate, and the absence is the decision.** The obvious move was to mirror
DEC-030's rule that a finding cannot be approved while its severity is `unassigned`. But DEC-045
already refuses `unassigned` on a gap at construction, because the node that raises the gap is the
only step that ever rates it. The gate had already run, one layer down. Adding a second one would
have gated on a field nothing can change — the kind of symmetry that looks like rigour and is
actually noise. The one refusal kept is structural: a gap that is no longer a candidate has been
decided already, which mirrors `approve_finding`'s refusal of a merged duplicate.

**The migration says what it is.** Making gaps subjects turned 264 of them across fifteen recorded
scenarios into subjects at once. Authoring 264 individual judgments as part of the change that
created the need for them would have been inventing a review nobody performed, and it would have
been invisible afterwards — 264 plausible rationales in the corpus, indistinguishable from real
ones. Each scenario now carries a `documentation_gaps:` block with one `default:` and a rationale
that begins "DEC-159 migration, not a review". A re-capture authors per-gap entries under `gaps:`
instead, and the harness accepts either and refuses a file carrying neither.

The default is `approve`, and the reasoning matters more than the value. A candidate gap asserts
only that something could not be determined from the documents supplied, which is exactly what the
run established; approving it adds no claim the run did not make. A finding is the opposite —
approval asserts a weakness exists — which is why the two defaults could not be the same.

What it cost: fifteen `report-hash-offline.txt` pins, the ForgeFlow `report-hash.txt`, and the
committed demo report asset all moved, because section 9 now renders. DEC-101 already named this
distinction — derived-output changes are re-pin cycles, allocation changes are re-capture events —
and this is squarely the first. No recording changed and no identifier moved.

Two things surfaced that were not in the plan. The capture stage's zero-finding branch, added as a
DEC-091 amendment in #484, asserted that a run with no findings never pauses; that is now false for
any run with gaps, and `oidc-portal` (eleven gaps, zero findings) is the case that proves it. The
test written for that amendment now asserts the pause instead. And `findings-export.yaml` had to
grow the gaps, for the reason the export exists at all: an author cannot decide what the export
does not show.

Open, and recorded in the DEC: whether a reviewer should be able to dispose of a set of gaps in one
action — husky-ai produces sixty-two — and whether a gap whose evidence is entirely report-kind
under DEC-157 should be refused approval outright rather than merely flagged. The second is the
doctored exchange run's real lesson, and it is a different decision from this one.
