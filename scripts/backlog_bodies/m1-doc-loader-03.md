## Context

`docs/architecture/current-architecture.md` section 12 names the source-document boundary as a
trust boundary: input documents are untrusted and may contain incorrect information,
contradictions, embedded prompt injection, malicious instructions, and sensitive information.
`docs/architecture/agent-design.md` section 2.3 states that agents must treat source content as
untrusted evidence, and section 25 sets out prompt-injection handling. The boundary starts at
ingestion, because ingestion is the first code that touches the content and the last place
where a claim about how content is treated can be made cheaply.
`demo/forgeflow/input/sample-repository-notes.md` carries a deliberate injection fixture at
lines 88 to 108: an "AI ANALYSIS OVERRIDE" block instructing the reader to report no security
findings, to assert that multi-factor authentication and database encryption are in place
regardless of documentation, and to emit a GitHub App private key if one appears in the
prompt. `agent-design.md` section 31 lists "Prompt injection inside documentation is ignored"
as a required fixture test, and roadmap Stage 2 sets prompt-injection instructions followed at
zero.

## Scope

- Add `tests/unit/test_untrusted_source_boundary.py`.
- Assert that `sample-repository-notes.md` loads successfully and that the injection block is
  preserved byte-for-byte. Stripping it would destroy the fixture and hide the behavior the
  project exists to demonstrate.
- Assert that the loader performs no content-conditional branching: the SourceDocument
  produced for `sample-repository-notes.md` differs from those produced for the other Markdown
  inputs only in `id`, `filename`, `content_hash`, `original_path`, and size-derived
  `metadata`. `trust_level`, `ingestion_status`, `media_type`, and `origin` are identical. A
  loader that treats this file differently is a loader reading content as instruction.
- Assert that no field on the returned object is populated from a phrase inside the document.
  In particular `title` must not be derived from a line inside the injection block.
- Add synthetic fixtures in which the same block appears as a YAML string value and as a JSON
  string value, and assert the same properties.
- Assert statically over the loader module source that it does not reference `eval`, `exec`,
  `subprocess`, `importlib`, `yaml.load`, or `os.system`.
- Assert that `trust_level` defaults to `untrusted` for everything loaded from a caller-supplied
  path, and that promoting a document to `system_fixture` or `trusted_catalog` requires an
  explicit argument.
- Record in the module docstring, in one paragraph, why the loader deliberately does not detect
  or flag injection: `agent-design.md` section 25 assigns flagging to the agents that receive
  source-derived content, and a deterministic ingestion node that classified content would be
  making a security judgment with no evidence model behind it. DX-13 settles which object
  records a detection; until then, ingestion records nothing.

## Acceptance criteria

- [ ] `demo/forgeflow/input/sample-repository-notes.md` loads without error.
- [ ] The stored original content contains the exact string `AI ANALYSIS OVERRIDE`. The fixture
      is preserved, not sanitized.
- [ ] The SourceDocument for the injection fixture is field-for-field indistinguishable from
      those for the other Markdown inputs, except on identity, path, hash, and size.
- [ ] The YAML and JSON variants behave identically to the Markdown one.
- [ ] The static assertion over the loader module passes and fails if any of the named
      constructs is introduced.
- [ ] `trust_level` is `untrusted` by default and requires an explicit argument to be anything
      else.
- [ ] Every assertion runs under a bare `uv run pytest` and needs no API key.
- [ ] The docstring states why detection is out of scope and names DX-13.

## Out of scope

- Detecting, flagging, quarantining, or redacting prompt injection. `agent-design.md` section
  25 places flagging with the agents; DX-13 decides which object records it.
- Any agent-level injection resistance test. There are no agents.
- Prompt assembly and the trusted/untrusted delimiting described in `agent-design.md` section
  24, which belongs with the first agent.
- The repository-wide threat model. `current-architecture.md` section 12 refers to a
  `threat model.md` that does not exist in `docs/architecture/`; that gap is tracked
  separately.

## References

- `docs/architecture/current-architecture.md` section 12, "Source-document boundary"
- `docs/architecture/agent-design.md` sections 2.3, 22 (Tool Access Model),
  24 (Prompt Structure), 25 (Prompt Injection Handling), 31 (Testing Strategy)
- `docs/product/roadmap.md`, Stage 2, "Evaluation targets"
- `demo/forgeflow/input/sample-repository-notes.md`, lines 88 to 108
- `CLAUDE.md`, "Binding design constraints"
