# Interview package

Eight stories, each sourced from the decision log and the measured record. Every claim below
cites the decision entry or the number behind it; nothing is asserted that the repository does
not carry. Each story is sized to be told in one to two minutes and to survive the follow-up
question, which is the point of sourcing them.

## 1. Why Trace exists

Generic AI security review fails in a specific, repeatable way: given ordinary architecture
documentation, it converts silence into findings. A document that does not mention a password
policy becomes "no password policy"; an undescribed encryption setting becomes "data is
unencrypted." Trace is built around the opposite rule, and it is the project's oldest binding
constraint: **missing documentation is never proof of a vulnerability** (DEC-009). Silence
becomes a question or a documentation gap; a finding requires evidence that affirmatively
supports a weakness. The distinction is enforced structurally — DEC-013's outcome table has no
route from an unverified conclusion to a finding, and the `Finding` schema refuses validation
statuses the table produces no finding from — not by prompt phrasing.

The measured version: across thirteen benchmark scenarios, the generic single-prompt baseline
invents seven false positives over five scenarios; Trace's pipeline produces four candidate
rejections over thirteen, and every one of its eighteen approved findings links to hashed source
evidence where the baselines can cite nothing even in principle (`docs/eval/comparison.md`).

## 2. Why LangGraph was evaluated and rejected

DEC-007 (2026-08-05) proposed LangGraph as the workflow orchestrator, before the workflow's
shape was known — the pipeline needed structured state, pauses, checkpointing, retries, and
resumability, and LangGraph is built for stateful model workflows. DEC-016 (2026-08-09)
rejected it once the shape existed, and the reasoning is the story:

- **The pipeline is fixed and linear** — fourteen ordered phases, two pause points, no
  analytical branching. That is a transition table of about twenty lines; a graph framework
  earns its cost on graphs whose shape is unknown until runtime, and this graph is a list.
- **A framework checkpointer would be a second authoritative store.** DEC-006 makes
  schema-validated domain objects the authoritative state; a checkpointer persists its own
  serialized copy on its own schedule. Two stores of truth that can disagree is the exact
  condition DEC-006 exists to prevent.
- **The ceilings that matter are application-domain.** Model-call, cost, and duration limits
  live on `AssessmentConfiguration` and are enforced by the orchestrator; a framework cannot
  see what a call costs.

The decision removed `langgraph`, `langchain`, and `langchain-anthropic` from the
dependencies, leaving `anthropic` as the only provider SDK behind the DEC-014 seam at the
time (`openai` joined later as DEC-095's second adapter, each SDK importable only by its own
adapter). The
recorded tradeoff is honest: retries, limits, and resume are now owned code, and the trigger
to revisit is a workflow that stops being a list.

## 3. Why structured state matters

The workflow's state is not a conversation transcript (DEC-006). Agents return proposals —
local keys, no identifiers, no status, no severity, `extra="forbid"` — and the application
validates them, allocates identifiers at insert (DEC-018), and owns every authoritative
object. Three consequences carry the argument:

- **An invented field is a validation failure, not silent data.** A proposal carrying a field
  the schema does not name fails loudly instead of passing downstream stripped and
  plausible-looking.
- **Pausing is stopping** (DEC-017). A checkpoint writes state and exits the process; resuming
  is a read in a new process. There is no long-lived loop to keep alive, which is also what
  makes the recorded-replay evaluation harness possible — a file of decisions and a directory
  of responses reproduce a run byte-for-byte (`scripts/replay_forgeflow.py`, hash-pinned).
- **The report cannot drift from the analysis.** Twelve of sixteen report sections render
  deterministically from approved objects; the model writes four prose sections and may not
  restate an approved object's text (DEC-035). A finding's description is what the reviewer
  approved.

## 4. How prompt injection is handled

Structurally, then measured. Source documents are untrusted data: every excerpt reaches an
agent inside a fence carrying its evidence identifier, delimiters inside excerpts are
neutralized, and the demo corpus itself contains a deliberate injection payload
(`demo/forgeflow/input/sample-repository-notes.md` — instructions to report no findings,
fabricate MFA and encryption claims, and exfiltrate the signing key).

In the live `claude-opus-5` capture, the extraction produced an `injection_attempt`
observation naming the payload and the four claims it tried to poison, followed none of it,
and the reviewer meets the attempt framed as data at checkpoint 1 (`trace context show
--observations`). The measured half is DEC-075: the adversarial condition runs a poisoned
document through the ordinary pipeline and scores injected-instruction compliance per payload
class. The committed result is 0% compliance across all five classes — checkpoint bypass,
direct instruction injection, fence-delimiter escape, findings suppression, verifier sabotage
— with the target finding still produced (`docs/eval/scorecard.html`). The single-prompt
baselines have no defense to test, and the comparison table says so rather than scoring them.

## 5. How inherited controls reduce false positives

The requirements catalog is written so that absence of evidence resolves to `unverified`,
never `unmet`, and every requirement carries two structured escape routes (DEC-011):
`non_applicable_conditions` (the requirement does not apply here) and
`common_false_positives` (the wrong conclusion to draw when it does apply and documentation is
silent). Inherited platform controls are modeled explicitly (DEC-026), and DEC-025 adds a
structural check: an `unmet` conclusion on a requirement with named false positives must
address them or it is downgraded.

Two benchmark scenarios exist purely to test this. `oidc-portal` delegates authentication to
an enterprise IdP — the local-password-policy false-positive class — and the correct, measured
result is zero findings with the suppressed conclusions recorded on the mappings.
`managed-db-service` documents platform-default encryption — the encryption-detail class —
same shape. Both scenarios score 100% on the scorecard by *not* finding anything, which is the
product thesis as a regression test: a successful assessment may produce no findings.

## 6. How evaluation changed the architecture

The evaluation harness is not a report card bolted on; it repeatedly changed what was built.

- **The ablations reshaped confidence in the pipeline itself.** Removing evidence validation
  raises the false-negative rate from 0% to 100% on the two scenarios that carry a genuine
  finding — the component the credibility literature says to ablate is measurably
  load-bearing. Removing the critic and the context checkpoint moved no metric on that corpus,
  and the null result is published rather than hidden (`docs/product/ablation-narrative.md`,
  `docs/eval/ablation.md`).
- **Authoring recordings surfaced real defects.** The reserved-metrics work found that report
  metrics had no pipeline caller at all; recording authorship exposed a stale run-row counter
  (`model_call_count`, fixed in #424); demo preparation found report section 7 structurally
  empty because its filter was never satisfiable (DEC-101, renumbered from a duplicate DEC-083 heading).
- **The live capture measured the miss.** The flagship run matched none of the then-three authored
  expected findings and approved four defensible ones. The diagnosis (#564, DEC-116) is the
  better story: the run produced mappings under all three expected requirements, and they died
  in the evidence-validation funnel — one call assessed 25 of 185 mappings, and an unassessed
  mapping resolves to no output — so the number is on the public scorecard with its mechanism,
  not in a drawer. The diagnosis also exposed the truth set disagreeing with itself, and DEC-133
  decided it: two expectations were conditional on a contradiction resolution the run was never
  given, they now declare it, and a run that correctly asks instead of concluding is scored as
  asking, not as missing. The DEC-077 stability protocol (five live runs, ~$6.92 ±
  $3.28 each) showed the headline finding reproducing in only two of five runs; the flicker is
  reported and gates nothing.

## 7. What was removed because it added no value

- **The seventh agent.** The corpus specified a Severity Support Agent; DEC-030 excluded it
  outright after a field-by-field comparison showed four of its six outputs already existed as
  required `Finding` fields. Severity itself became the reviewer's act at checkpoint 2 — no
  node proposes one, and a finding cannot be approved with severity unassigned.
- **The orchestration and model frameworks** (DEC-016, story 2): three dependencies removed;
  the replacement is ~twenty lines of transition table plus a node protocol.
- **The web framework that was never added.** The Stage 5 read-only view is stdlib
  `http.server`, localhost-only, GET-only, read-only by an audited discipline (DEC-078) —
  answering "which web framework?" with *none*, consistently with the rest.
- **A generic status setter.** `Assessment.status` moves only through named verbs (DEC-031);
  the setter that let a status mean something nobody decided was removed with the lifecycle
  redesign.

The common thread: each removal is recorded with what would trigger revisiting it, which is
the difference between minimalism and under-building.

## 8. How the system would evolve for production

The MVP's constraints are decisions, not accidents, and each names its expansion path:

- **Local and single-user** (DEC-004) is the current trust model — no cloud, no RBAC, and the
  read-only browser boundary is bounded rather than defended (DEC-078). Production means
  re-opening that threat model deliberately: authentication, tenancy, and the storage
  boundary the assessment stores already enforce per-assessment.
- **The model seam is provider-agnostic with two adapters** (DEC-014, DEC-095) — the second
  adapter the earlier version of this list named as what production would need. Both are held
  to one contract by the conformance suite; no live OpenAI pipeline run has been measured yet.
  Cost and token accounting already flow through the seam; the live stability run populated
  them.
- **The evaluation machinery is the production readiness gate.** Scorecard history keyed by
  git ref, prompt digest, and catalog version (DEC-081) plus the prompt- and model-comparison
  protocols (`--label`/`--diff-against`) are how a prompt or model change would be admitted:
  measured against the register, diffed per item, retained.
- **The catalog versioning already supports growth**: assessments pin a catalog version, so
  a new catalog cannot change what an in-flight run is assessed against (DEC-010, DEC-034).
- What would need building, stated plainly: multi-user review attribution beyond DEC-023's
  local reviewer string, retention and deletion policies for assessment data, and the
  interactive lineage view future-features 13.1 sketches. The second provider adapter this
  list once named is built (DEC-095); what remains for it is a measured live run.

The closing line of the story is the project's own: the roadmap's exit criterion for the
public release is that it "does not imply production readiness it has not earned."
