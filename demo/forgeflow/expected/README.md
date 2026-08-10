# ForgeFlow expected outputs

**Nothing in this directory is supplied to Trace during an assessment.** These files are the truth
set: what a correct assessment of the ForgeFlow scenario produces. The material Trace reads is
`../input/`, and the two directories are siblings so that withholding the truth set is a single
rule about a directory rather than a per-file judgement.

The rule is not a convention. `demo/forgeflow/input/structured-system-input.yaml` once ended with
an `evaluation:` block declaring expected finding, question, documentation-gap, and contradiction
counts, and that file *is* supplied to Trace. Every measurement taken against the scenario while it
was there was contaminated, and the pipeline was additionally handed a finding quota — which
`docs/product/design-principles.md` section 9 rejects outright. Issue #18 moved the block here;
DEC-028 then removed the counts entirely, because a declared count that can disagree with its own
enumeration is a second source of truth.

Three tests keep it that way, and they are the enforcement rather than this file:

- `tests/unit/test_forgeflow_fixture.py` asserts that no input document declares expected outputs,
  and that no module under `src/` references this directory.
- `tests/unit/test_benchmark_layout.py` asserts that `expected/` is a sibling of `input/` for every
  registered scenario, never a descendant.
- `tests/unit/test_context_fixtures.py` asserts that `expected-context.yaml` conforms to the M2
  domain models and that every passage it cites exists in the input documents.
- `tests/unit/test_benchmark_truth.py` holds the four M3 truth files to their shape, resolves
  every requirement identifier against catalog 0.1, asserts that no requirement text is restated,
  and asserts that every suppression names an entry the catalog actually has.

## What is here

| File | Status |
| --- | --- |
| `evaluation-contract.yaml` | The grading policy. Declares no counts (DEC-028). |
| `expected-context.yaml` | The context-extraction truth set. Authored. |
| `expected-questions.yaml` | Authored — M3. |
| `expected-observations.yaml` | Authored — M4. |
| `expected-threats.yaml` | Authored — M3. |
| `expected-control-mappings.yaml` | Authored — M3. |
| `expected-findings.yaml` | Authored — M4. |
| `expected-documentation-gaps.yaml` | Authored — M4. |
| `expected-rejections.yaml` | Authored — M3. |
| `reviewer-notes.md` | Authored — M4. |

The file list is derived from the object model rather than enumerated in prose (DEC-027): one
`expected-*.yaml` per domain object type the pipeline produces and the benchmark grades, plus the
negative set. `tests/unit/test_benchmark_layout.py` pins the derivation so that adding an object
type to `data-model.md` without adding a file is a failing test rather than a silent omission.

## Deriving an expected file

The scenario narrative, `../forgeflow-scenario.md`, contains more than the input documents do. Its
sections 5, 7, 8, 10, and 11 enumerate the actors, components, assets, data flows, and trust
boundaries as the scenario's author knows them; sections 13 to 22 state the intended findings,
non-findings, ambiguities, and contradictions. **The parts of it describing what the documents do
not say are hidden truth and must not reach an expected file for a step whose input is those
documents.** Grading an extraction against facts nobody supplied rewards invention, which is the
DEC-009 failure with its sign flipped.

Each `expected-context.yaml` entry therefore cites the input document and section it rests on, and
a test checks the citation resolves.
