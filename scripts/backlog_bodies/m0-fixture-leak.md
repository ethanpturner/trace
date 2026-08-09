## Context

`demo/forgeflow/input/structured-system-input.yaml` is a document supplied to Trace as
material under review. It ends with an `evaluation:` block declaring the benchmark
contract:

```yaml
evaluation:
  expected_outputs:
    findings: 3
    questions: 5
    documentation_gaps: 3
    contradictions: 2
    prompt_injection_fixture: true
```

`demo/forgeflow/forgeflow-scenario.md` section 25 states that expected files "should not be
supplied to Trace during the assessment." This one is, and it is inside the input directory
that the document loader will read.

Three consequences:

1. **Every measurement taken against this scenario is contaminated.** The system under
   evaluation is given the answer key.
2. **The pipeline is handed a finding quota.** `docs/product/design-principles.md`
   section 9 and `docs/architecture/evaluation-plan.md` section 20 both reject optimizing
   for finding count, and `CLAUDE.md` lists it as a binding constraint. A model that reads
   `findings: 3` has been told how many to produce.
3. **`README.md` quotes the block approvingly**, so the contamination is documented as a
   feature.

This is a defect, not a design decision. The counts themselves are disputed and are settled
separately in DX-18; this issue moves the data out of the input regardless of what the
numbers turn out to be.

## Scope

- Remove the `evaluation:` block from
  `demo/forgeflow/input/structured-system-input.yaml`.
- Relocate its content to `demo/forgeflow/expected/`, where
  `forgeflow-scenario.md` section 25 says it belongs. The exact filename follows the layout
  fixed in DX-18; if DX-18 has not landed, park it as
  `demo/forgeflow/expected/evaluation-contract.yaml` and note that the name is provisional.
- Update `README.md` so it no longer quotes the block as part of the input fixture. State
  instead that the expected outputs are held outside the input directory and are not
  supplied to Trace during an assessment.
- Add a test asserting that **no file under `demo/forgeflow/input/` contains
  expected-output data**, so the leak cannot silently return. Check for the `evaluation:`
  key and for the count field names.
- Add a test asserting that no agent payload assembler or ingestion path reads from
  `demo/forgeflow/expected/`.

## Acceptance criteria

- [ ] `demo/forgeflow/input/structured-system-input.yaml` contains no expected-output or
      benchmark data, and no `evaluation:` key.
- [ ] The relocated content exists under `demo/forgeflow/expected/`.
- [ ] A test fails if any file under `demo/forgeflow/input/` reintroduces expected counts
      or truth data, and the test names this issue in its docstring so the reason survives.
- [ ] A test asserts nothing in the ingestion path reads from `demo/forgeflow/expected/`.
- [ ] `README.md` no longer presents the block as input-fixture content.
- [ ] The remaining seven input documents are unchanged, byte for byte. In particular the
      prompt-injection fixture in `sample-repository-notes.md` is preserved exactly; it is
      test data and removing or altering it would destroy the case it exists to prove.
- [ ] `uv run pytest` passes with no provider API key.

## Out of scope

- Resolving the disputed counts. `forgeflow-scenario.md` section 19 lists four findings
  against the fixture's three, and section 20 lists ten questions against five. That is
  DX-18.
- Authoring the full expected-output set, which is an M3 and M4 issue.
- Changing the ForgeFlow scenario's design.

## References

- `demo/forgeflow/input/structured-system-input.yaml`, the `evaluation:` block
- `demo/forgeflow/forgeflow-scenario.md` section 25 (Benchmark Truth Files), sections 19
  and 20
- `docs/architecture/evaluation-plan.md` sections 5, 10, 20
- `docs/product/design-principles.md` section 9
- `CLAUDE.md`, "Binding design constraints"
- `README.md`, "Adversarial by design"
