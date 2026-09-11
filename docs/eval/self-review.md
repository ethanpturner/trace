# Trace reviewed as a system: two code reviewers and Trace itself

**Captured 2026-09-11** against trace at `3e325f66d3f43e60e32b220cc5faa51c844bde11` (develop).
Nothing on this page replays in CI: the reviewer runs are live agent runs, and Trace's own run
spent live provider calls. What is committed is the classification, the feeds under
`results/*/self-review/` (which the sweep does not descend into, because there is no truth set),
the attestation manifest for the Mantis run in the session scratchpad, and the issues filed.

`benchmark-package.md` states the corpus's limitation: it is synthetic by construction. This
page is the one non-synthetic system Trace and the reviewers have been pointed at, and it is the
system whose threat model the reviewers were being compared against.

## What was reviewed

The code reviewers received an export of the packages that implement the three boundaries
`threat-model.md` treats as highest-risk, plus their direct imports: 24 Python files, 4,051
lines.

| Boundary (threat-model.md) | Packages exported |
|---|---|
| Source-document (§3) | `services/ingestion/` (loader, repository fetch, segmenter, PDF), `services/context/input_package.py` (the fence), `services/budget.py`, `infrastructure/filesystem/` (artifact store, atomic write, permissions) |
| Browser-to-application (§5) | `interface/` (server, render) |
| Dependencies | `observability.py`, `config.py`, `domain/{base,hashing,source_document,evidence,enums}.py` |

A README in the export stated the deployment model (local, single-user, no network exposure
beyond a read-only 127.0.0.1 view) so the reviewers had the same premise the threat model has.
No test, truth, or `expected/` material was present; the export was checked for truth tokens.

Trace received four of its own documents as uploaded sources: `current-architecture.md`,
`threat-model.md`, `agent-design.md`, `data-model.md` (218 KB, 132 evidence references), and ran
on `openrouter-economy` through both checkpoints. The reviewer at checkpoint 1 was the session
that ran it; decisions are recorded on the assessment with their reasoning.

## Counts

| Arm | Model | Outcome | Distinct findings | Cost (list price) | Wall |
|---|---|---|---|---|---|
| Mantis @ d13c93f, medium effort, no reproduce/chain/patch | gpt-5.6-sol via api.openai.com | exit 0, all stages | 7 (14 rows emitted, 7 byte-identical duplicates) | $4.93 | 1,048 s |
| Codex Security 0.1.26, `--max-cost 5`, high effort | gpt-5.6-sol via api.openai.com | capped at $5 after 255 s, no artefacts | 0 | $3.55 (tool's own estimate $5.11) | 255 s |
| Trace, `openrouter-economy` | openai/gpt-5.1 via OpenRouter | stopped at its $5 ceiling in evidence validation (13 calls; DEC-016 stop, not a crash) | 0 findings, 3 documentation gaps, 7 threats, 4 questions, 1 contradiction (through checkpoint 1; checkpoint 2 not reached) | $4.32 (ledger) | 3,865 s of model time |

Mantis's review and critic stages left every finding `PROVISIONALLY_VALID`, as in the twenty
scored runs on `reviewer-arms.md`. Its architecture stage did write a knowledge base this time
(six entity pages, seven inferred trust boundaries, a threat model with `Intent: PRODUCTION`
despite the README's stated deployment model), which the low-effort pilot had not.

## Classification of the reviewer findings

Each Mantis finding was read against the cited code and against `threat-model.md`. Codex
Security produced nothing to classify.

| # | Finding (Mantis title, as emitted) | Cited code | Class | Why |
|---|---|---|---|---|
| 1 | Document-controlled metadata is promoted into the trusted model region | `input_package.py:143-224` | **c** | Verified. Filenames, section titles, evidence locations, and `structured_input` are serialised into the trusted region; only excerpt bodies are fenced. §3 row 1 names the fence as Enforced and is silent about the manifest. [#675](https://github.com/ethanpturner/trace/issues/675) |
| 2 | Budget accounting omits separators between included evidence blocks | `budget.py:84-86,124-130` | **c** | Verified. Admitted blocks are charged without the two-newline separators they are joined with, so the emitted region can exceed the residual by 2·(N−1) characters. No row covers the accounting DEC-070 relies on. [#676](https://github.com/ethanpturner/trace/issues/676) |
| 3 | Frozen domain models expose mutable metadata that bypasses validation | `base.py:81`, `source_document.py:145`, `evidence.py:115` | **c** | Verified as a code fact: `frozen=True` with `dict[str, Any]` metadata fields. Reachable by application code only, so low; filed because the immutability claim in the docstring is broader than the type enforces. [#677](https://github.com/ethanpturner/trace/issues/677) |
| 4 | Repository access token is exposed in the git process command line | `repository.py:87-105` | **a** | §3 repository rows state the token "reaches only the subprocess clone URL"; that is this exposure, accepted as the design. The row does not name the process table and could. Another local process reading argv is outside DEC-004. |
| 5 | Predictable temporary files enable symlink-following overwrite and concurrent corruption | `atomic.py:27`, `artifact_store.py:151` | **b** | Another local process writing into the assessment directory is the shared-machine adversary §6 and §8 exclude under DEC-004. The same-process collision needs two concurrent writers to one path; the pipeline is sequential. `O_EXCL` hygiene is cheap and noted, not filed. |
| 6 | File validation and reading race permits unintended file disclosure and size-limit bypass | `loader.py:284-305` | **b** | A time-of-check race needs a local writer racing the reviewer's own process on the reviewer's own directory; excluded by DEC-004 (§2, §8). |
| 7 | Duplicate structured keys create ambiguous evidence addresses | `loader.py:380-382`, `segment.py:161-188` | **d** | Duplicate mapping keys do yield two segments with one JSON Pointer, but an `EvidenceReference` is verified by line range and quotation hash (DEC-015, §7), not by pointer. A robustness note, not a security gap. |

Totals: a 1, b 2, c 3, d 1, of 7. Three findings were filed as issues; none was a hallucination,
and every cited path and line resolved at the snapshot (the feed's `code_paths` field, by
contrast, carried only the target root, so locators were taken from the finding bodies).

## What the reviewers said about the threat model, and what Trace said

Mantis's inferred threat model draws seven boundaries where `threat-model.md` draws five. Two
of the seven are folded into other sections of the human-written document: "assessment names
to filesystem paths" (§6's path-containment row) and "parsed or edited data to evidence
claims" (§7's citation rows). It marked deployment intent as `PRODUCTION`, which is its
fail-closed default, against a README that stated the opposite; that is the behaviour the
Project 1 guide predicted for a code-only pipeline handed design intent as prose.

### Trace on its own documentation

Trace read four of its own documents and stopped where its ceiling told it to: `maximum_cost`
was set to $5 for this run, and the step that would have crossed it was the fourth
evidence-validation batch, at an estimated $5.14. Agent-design section 27 makes that a stop with
a classified error, not a skipped node, so checkpoint 2 was never reached and no finding was
proposed. What it recorded before stopping is still the assessment's state, and it is listed
here as what it is: a run that ended at its budget.

**Checkpoint 1.** Nineteen components, four actors, three assets, twenty-four data flows, five
trust boundaries (the five sections of `threat-model.md`, named as such), fifteen claims of which
fourteen `documented` and one `unknown` (`present_in_mvp`, left undecided). Context Validation
raised one contradiction and one consistency observation:

- **obs-001**, a contradiction between two of Trace's own documents: `current-architecture.md`
  says the browser-to-application boundary is absent because the interface is command-line only;
  `threat-model.md` section 5 describes the read-only view and reintroduces the boundary. The
  extractor also raised it as a blocking question (qst-001). Resolved at the checkpoint as
  *present*, with threat-model.md authoritative because its mitigations are enforced in code, and
  filed as [#678](https://github.com/ethanpturner/trace/issues/678). The threat model does not
  answer this; it is the document that is right, and the other one is stale.
- **zone_mismatch** (warn-only): a flow from a component in zone `reviewer_workstation` to one in
  `local_workstation` crosses no declared boundary. A vocabulary inconsistency between the two
  documents, noted on the same issue.

Three further questions were answered from the corpus at the checkpoint: confidential data is not
planned for the MVP (DEC-004, threat-model §4); the machine itself is out of scope (§8); the
reviewer is the only operator (DEC-032). The threat model answers all three.

**Threats.** Seven, every one of which maps onto a section of `threat-model.md`: prompt injection
through source documents (§3), misleading documentation driving a wrong baseline (§3's closing
paragraph), markup executing in the read-only view (§5), assessment content leaving to the
provider (§4), provider-key exposure (§4), cross-assessment contamination (§6), and the optional
tracing service receiving more than intended (§4, DEC-109). Nothing the threat agent proposed is
absent from the human-written document, and nothing in the document's five sections is absent
from the seven.

**Documentation gaps, not findings.** Requirement mapping proposed three gaps and no finding:
what the provider retains and under what terms is not documented (gap-001, gap-003), and the
credential's storage location and lifecycle are not documented (gap-002). Two of the three are
the same gap seen from two requirements. The threat model states the first as a design surface
(§4's closing paragraph: the provider and, if enabled, the tracer are what leaves the machine)
without recording any provider's terms; the second is answered in prose across `config.py`'s
docstring and CLAUDE.md rather than in the architecture documents. Both are gaps in the
documentation, which is what Trace said.

Set beside the code reviewers: Mantis found three real things in the code that the documents do
not describe; Trace found one real inconsistency between the documents and three things the
documents do not say. Neither found anything the other did, which is the docs-versus-code split
the Project 1 guide predicted, on the one system where nobody wrote the truth set.

## Provenance and limits

- Reviewer runs: `reviewers/scaled/runs/trace-self/{mantis,codex-security}/run-1/` in the
  session scratchpad; the Mantis run's attestrun/2 manifest verified over its recorded feed,
  target export, and transcript (`reviewers/scaled/manifests/trace-self-mantis-run-1.json`).
- Trace run: data root `self-review/data/` in the scratchpad, assessment `asm-001`; checkpoint-1
  decisions recorded as `dec-001` to `dec-076`; the journaled responses live in the run's
  traces.
- Costs are OpenAI list prices from the recorded token counts (Mantis) and the tool's own
  reporting (Codex Security); Trace's is the ledger's estimate.
- Nothing here is a truth set. The classification is one reader's, recorded with its reasons so
  it can be disagreed with row by row.
