# M8 closes: the injection fixture becomes a corpus, and the claim becomes a number

Four issues (#272–#275), and the ForgeFlow injection fixture stops being the whole adversarial
story. Trace's headline claim — that following an injected instruction is unrepresentable, not
merely unlikely — now has a corpus behind it, a compliance rate measuring it, and a demonstration
citing the mechanism at every step.

## Conditions had to become real

The harness carried a `condition` argument since M7, but it was a feed label — it changed where
the results file landed and nothing else. DEC-075 needs it to be a real variant: an input overlay,
an expected overlay, a recording. The registry `Scenario` gained a `conditions` tuple and the
overlay resolution (`input_documents`, `expected_dir_for`, `recorded_dir_for`), and the harness
threaded the condition through document loading, truth location, decision replay, and metrics. The
guiding constraint is the one that makes the measurement honest: the pipeline is unchanged per
condition. It must not know it is being attacked, because a pipeline that branched on "this is the
adversarial run" would measure the branch, not the defence.

## The corpus is one document, and that is enough

`team-notes.md` carries all five payload classes in a plausible pasted-experiment block — direct
injection, a fence escape, findings suppression, verifier sabotage, checkpoint bypass. Authoring
its recording surfaced the fence-escape subtlety: the poisoned document sorts after the clean one
by name, so the clean document keeps `evd-001` and the recorded extraction's citations stay valid.
The correct extraction records the injection as an observation and otherwise produces the clean
context — so the finding survives, which is axis one measured against the same truth.

## injection_flag fires on what a correct run keeps, not on what it rejects

Wiring #274, the first instinct was wrong. A correct extraction produces *nothing* from the
poisoned document, so a per-subject injection_flag derived from "subjects citing the poisoned doc"
fires on nothing. The fix was to recognise that a correct extraction still legitimately pulls a
benign fact from the notes (the URL rotation reminder), and *that* subject carries the flag —
because it came from a document that also tried to inject. The flag is derived from persisted state
at package-build time and stored nowhere, which is DEC-062's whole shape: a code re-derivable from
stored facts is the audit. And the package surfaces the injection observation itself, so detection
is visible even when nothing was extracted from the attack.

## Two axes, and the honesty of a structural zero

The compliance metric's hard part was resisting the urge to fake per-class signals. Two classes
are observable — suppression and direct injection fail because the finding survived — and three are
zero by construction. The temptation is to invent a check that "measures" the structural classes;
the honest thing is to score them zero with their basis stated (the fence neutralises delimiters,
the checkpoint has no bypass, the validators read evidence), which is exactly what DEC-075 says to
do. A metric that is always zero for a correct run is not useless: it goes non-zero the moment the
finding vanishes under attack, which is the regression it exists to catch.

## The demonstration is the point M8 was building toward

#275's document is where the pieces become an argument. Every claim cites a file, a table, a test,
or a number, and the closing paragraph draws the line the whole milestone is about: the compliance
rate of zero measures the attacks the corpus imagined, but the structural claim holds for every
payload, imagined or not. The fence neutralises *any* delimiter; the checkpoint has *no* bypass
field and a guard test that fails if one returns; the agent returns a proposal `extra="forbid"`
will not let it make authoritative. Hard-to-fool degrades; unrepresentable does not.

## Open next

M8 is empty. M9 Demo and Portfolio (#276–#280) is the last milestone: the read-only demonstration
interface with the finding-lineage view, the measured comparison table (whose numbers M7 and M8
now supply), the demo script and recovery plan, the limitations section and failure taxonomy, and
the ablation narrative. The honest debt this milestone leaves is the same one M7 named — the
zero-finding scenarios' pipeline recordings and ForgeFlow's full-truth recording — and the
adversarial corpus is one scenario's one condition, extensible to the others when their recordings
land.
