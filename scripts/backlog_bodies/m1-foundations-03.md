## Context

`docs/architecture/data-model.md` section 2.1 requires every important object to carry a
stable identifier and lists nineteen readable prefixes. Identifiers are what let Trace link
findings to threats, link claims to evidence, resume interrupted workflows, and compare
evaluation runs. Content hashes serve the parallel purpose for artifacts: section 35 states
that the database stores references and content hashes for filesystem artifacts, and section
7 and section 8 both make `content_hash` required. This issue implements both, against the
scheme DX-02 settles and the computation rule DX-20 settles.

**Blocked on DX-02** (identifier scheme) and **DX-20** (`content_hash` computation). Do not
begin implementation until both are recorded in `docs/architecture/decision-log.md`.

## Scope

- Add `src/trace_ai/domain/identifiers.py`:
  - a prefix registry containing exactly the nineteen prefixes in data-model.md section 2.1:
    `asm`, `src`, `evd`, `cmp`, `ast`, `df`, `tb`, `ctx`, `thr`, `req`, `ctl`, `map`, `fnd`,
    `qst`, `gap`, `dec`, `run`, `exe`, `eval`
  - `new_id(prefix)` producing an identifier in the form DX-02 decides
  - `parse_id(value)` and an annotated Pydantic type per prefix, so that `Assessment.id` and
    `SourceDocument.assessment_id` are typed rather than bare `str`
- Accommodate hand-authored `req-` identifiers. `requirements/0.1/*.yaml` already contains
  identifiers such as `req-WEBHOOK-001` that no generator produced, and DEC-010 makes them
  stable across catalog versions, so validation must accept them.
- Add `src/trace_ai/domain/hashing.py` implementing the `content_hash` computation DX-20
  decides, producing the `sha256:<hex>` form the section 8 example uses
  (`content_hash: sha256:example`).
- Hash bytes, not decoded text, so that a line-ending or encoding difference is visible rather
  than absorbed.
- Add `tests/unit/test_identifiers.py` and `tests/unit/test_hashing.py`.

## Acceptance criteria

- [ ] `new_id("asm")` produces an identifier that `parse_id` accepts and that carries the
      `asm` prefix.
- [ ] An identifier with a prefix outside the registry is rejected, with a message naming the
      registry.
- [ ] Every identifier in `requirements/catalog.yaml` validates. A test parametrized over the
      real catalog identifiers asserts this.
- [ ] Identifier generation does not depend on any mutable display name (section 2.1).
- [ ] Uniqueness is tested in the form DX-02 decides: a collision test over a large sample if
      the scheme is random, or a counter-behavior test including behavior on a fresh process
      if the scheme is sequential.
- [ ] The content hash of a fixed byte string equals `"sha256:" + hashlib.sha256(...).hexdigest()`,
      asserted against a literal expected value rather than against a re-computation.
- [ ] Hashing the same file twice produces the same value; changing one byte produces a
      different one.
- [ ] A hash string that is not `sha256:` followed by 64 lowercase hex characters is rejected
      by the validation helper.
- [ ] `uv run mypy` passes strict.

## Out of scope

- Deciding the identifier scheme or the hash computation. Those are DX-02 and DX-20.
- Persisting a counter, if DX-02 chooses a sequential scheme. This issue defines the interface
  and an in-memory implementation; the store-backed one belongs with the persistence layer.
- Hashing prompt files or the requirements catalog. DEC-010 deliberately omits `content_hash`
  on `RequirementsCatalog` until a loader exists to compute it, and that loader is not in this
  milestone.

## References

- `docs/architecture/data-model.md` sections 2.1 (Stable identifiers), 7 (`content_hash`),
  8 (`content_hash` format precedent), 30 (RequirementsCatalog), 35 (Data Persistence),
  39 question 9
- `docs/architecture/decision-log.md` DEC-010, and DX-02 and DX-20 once recorded
- `requirements/README.md`, "Layout"
