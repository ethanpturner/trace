# Drafting the initial requirements catalog

**2026-08-08** · Stage 1

Filled `requirements/`, which had existed as an empty, untracked directory since the original scaffold
— the one directory neither repository-layout table mentioned. Twenty-three requirements across eleven
category files, plus a manifest, a README, and a test that enforces the catalog's shape.

The catalog is a Stage 3 deliverable and the project is inside Stage 1. That inversion is deliberate:
`future-features.md` lists "Draft the initial requirements catalog" as priority four of seven, ahead of
context extraction. It adds no *product* code — `src/` is untouched, and the README's account of what
does not exist yet stands.

## Where requirements should come from

The question that took the longest was provenance, and the answer turned on a change to OWASP ASVS
that is recent enough to be easy to miss.

ASVS 4.0 had a chapter called "Architecture, Design and Threat Modeling", which is the obvious place to
look for architecture-level requirements. In ASVS 5.0 that chapter was **deleted**, not renamed. Parts
were dropped as out of scope, the rest redistributed into domain chapters, and every identifier
changed. Only eleven of 286 requirements survived unchanged. Any architecture mapping built on ASVS V1
— and there are many — is now pointing at nothing.

What replaced it is more useful than what was lost. Every domain chapter in 5.0 now opens with an
explicit `X.1 Documentation` section, roughly forty requirements phrased as expectations about what the
documentation states rather than what the running application does. That is a corpus assessable from
design documents by construction, which is exactly and unusually what this project consumes. It also
pairs: a chapter documents an expectation in `X.1` and implements it in a later section, which is the
same split as DocumentationGap versus Finding. ASVS 5.0 became the primary source on that basis, with
NIST SP 800-53 secondary for the ground ASVS puts out of scope — segmentation, availability, retention,
external system services — and the OWASP LLM list for the AI surface neither covers.

**Deciding what to exclude mattered more than deciding what to include.** Three sources are plausible
and wrong here:

- **CIS Benchmarks.** Every recommendation is an audit procedure against a live account. A document
  asserting that MFA is enabled on the root user is a claim, not evidence. Scoring it satisfied would
  manufacture assurance, which is a worse failure than the false positives this project is built to
  avoid — and it is out of scope anyway, since Trace reads documents rather than cloud configuration.
- **OWASP SAMM.** It measures organizational process maturity, not a system's design. Asking a maturity
  question of one system's documentation produces precisely the DEC-009 failure.
- **Procedural control families** — NIST `AC-2`, `RA-5`, `CM-3/6/8`, `SI-2/3/4`, the whole `IR` family,
  and CIS's inventory safeguards. A design document's silence on these is *normal*. Including them
  would have built DEC-009 violations into the catalog by construction rather than leaving them to
  agent judgment.

The general rule that fell out: a source is usable only if the absence of a control from a design
document is genuine evidence about the design. Where absence is merely normal, the source is measuring
something else.

## Two schema decisions

**`common_false_positives` is new** (DEC-011). DEC-009 says missing documentation is not proof of
absence, but nothing in the schema recorded *which* wrong conclusion a particular requirement invites.
That knowledge existed only as prose in the demo scenario's intentional non-findings, where the
application cannot reach it. The distinction against the existing field is the one worth stating
precisely: `non_applicable_conditions` says the requirement does not apply; `common_false_positives`
says what not to conclude when it *does* apply and the documentation is silent. Delegated
authentication is the worked example — the requirement applies, ForgeFlow satisfies it, and the wrong
conclusion is specifically "no password policy".

The obvious risk is that the field encodes a wrong belief as durably as a right one, and that
suppressing named false positives suppresses a genuine finding resembling one. The evaluation plan's
false-negative measurement is what should catch that, which is an argument for building the evaluation
harness before trusting the field much.

**`content_hash` is deliberately absent** from `catalog.yaml`, though section 30 lists it as required.
It is derived, there is no loader to compute or verify it, and a hand-maintained hash is stale after
the first edit. `RequirementsCatalog` is itself deferred in the data model's implementation priority,
so the field would have been a fiction maintained by hand for a consumer that does not exist. Recorded
as a known deviation rather than faked.

## What the demo scenario got right, and one thing it missed

The scenario already listed twenty requirement topics to cover, with the instruction to write them
separately rather than copy them. That instruction turns out to have a second justification nobody had
recorded: ASVS is CC BY-SA 4.0, so reproducing its wording would place the catalog under a share-alike
obligation. Citing identifiers while writing original statements avoids it entirely — and independently
satisfies the clean-room principle. Two unrelated reasons converging on the same practice.

The twenty topics contain no delegated-authentication requirement, which is a real gap: the evaluation
plan's Scenario 2 exists specifically to check that delegated authentication does not generate
password-policy findings, and there was nothing for it to exercise. Added `req-AUTH-001`. Added
`req-AUTH-002` for the same reason a step later — the scenario's intentional non-finding 14.3 expects
application-managed MFA to be actively mapped to the external provider, and without a requirement that
conclusion can only be reached by the subject never arising. `req-NET-001` was added last for the same
reason again, against non-finding 14.4. Twenty-three rather than twenty, and every addition came from
an evaluation fixture with nothing to exercise rather than from a sense that the catalog looked thin.

## Deliberately not decided

**No applicability vocabulary.** `applicable_conditions` stays free text. Data-model open question 5
asks how applicability should be represented in machine-readable form, and inventing an enum before the
mapping step exists would answer it by accident, on no evidence. Conditions are written in a consistent
style so a vocabulary can be *observed* later. Forty-five applicable and forty-four non-applicable
conditions are now written down, which is a better basis for that decision than the zero available
yesterday.

## Verification

Schema conformance, identifier prefixes, manifest agreement, and citation format are checked by
`tests/unit/test_requirements_catalog.py`, which runs under a bare `uv run pytest`. It started as a
throwaway script and became a test in the same session, on the grounds that hand-maintained data with
no consumer is precisely what drifts unnoticed — the catalog has no compiler and will have no reader
until the mapping step exists.

What the test deliberately does not do is check that a cited control identifier *exists*. The
frameworks are not vendored, so `SC-7` and `SC-70` are equally acceptable to it. Every identifier in
version 0.1 was verified by hand against the published catalogs; nothing preserves that guarantee for
the next edit, and pinning it would mean vendoring NIST and ASVS to test data that no code reads yet.

The substantive check is against the demo fixtures, and it is the reason to believe the catalog does
its job:

- All four testable intentional non-findings are suppressed by a field that names them, not by
  accident. Missing password policy, undescribed database encryption, absent application-managed MFA,
  and absent custom cryptography each map to a requirement that explicitly records them as wrong
  conclusions.
- All five genuine weaknesses remain reachable, each with at least one requirement that would apply.
  A catalog that suppressed these would have over-corrected, which is the failure mode on the other
  side of DEC-009.
- The webhook ambiguity resolves the right way: `req-WEBHOOK-001` records "documentation stating only
  that requests are validated, where the mechanism is unstated" as a false positive, so the fixture
  produces a question rather than a finding.

Non-finding 14.4, that Redis is not internet accessible, is now covered by `req-NET-001`, which was
the last gap on this list. It is the requirement whose `common_false_positives` field carries the most
weight: the fixture says only that Redis "is accessible only from approved application workloads",
which states the placement without naming the mechanism enforcing it. The intended treatment is a
question about network placement, not a finding of public exposure, and the field records exactly that
— absent placement detail is not evidence of exposure, and a managed component described only as
managed is not evidence either.

That requirement also exposed a limit of ASVS as a primary source. ASVS scopes itself to the
application rather than to where the application sits, so it has no boundary-protection requirement at
all; `13.1.1` covers documenting communication needs and nothing covers the placement itself. `SC-7`
carries that half alone. It is the clearest case so far of why the catalog needs a second source
rather than a single one, and it argues the NIST citations are load-bearing rather than decorative.

## Open

- **Severity distribution is unexamined**: nine high, thirteen medium, one low, assigned by judgment
  with no calibration. Data-model open question 14 covers this.
- **Nothing verifies that a cited control identifier exists.** The test checks citation *format*, not
  existence. Every identifier in 0.1 was checked by hand against the published catalogs, which is a
  guarantee about today rather than about the next edit.
- **`requirements.json` in the evaluation plan** still names a per-scenario artifact in a different
  format from the catalog. Left alone deliberately — it is a scenario subset, not the catalog — but
  the relationship between the two is undefined.
- The catalog has never been applied to anything. Every claim about its usefulness is a claim about
  fixtures, not about behavior, until the mapping step exists.
