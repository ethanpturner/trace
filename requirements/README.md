# Requirements catalog

Version-controlled security expectations that the Requirement and Control Mapping step is designed to
apply against an approved system context. This directory holds data.
`src/trace_ai/services/requirements/loader.py` reads it, validates it, and computes its
`content_hash`; `tests/unit/test_requirements_catalog.py` tests the loader and holds the authoring
conventions the loader does not.

The catalog exists so that requirement applicability can be *decided* rather than assumed. Its purpose
is as much to establish when a requirement does not apply as when it does — see
[DEC-009](../docs/architecture/decision-log.md).

## Layout

```
catalog.yaml         version 0.1's manifest (the root manifest; current_version() reads it)
catalog-0.2.yaml     version 0.2's manifest -- each later version gets its own (DEC-057)
versions.yaml        the governance registry: lifecycle status, maintainer, dates (DEC-057)
mappings/            cross-version fate maps, one per version pair
0.1/                 requirements for catalog version 0.1, one file per primary category
0.2/                 requirements for catalog version 0.2
```

Each file under `0.1/` holds a single `requirements:` list. Requirement objects follow
[`docs/architecture/data-model.md`](../docs/architecture/data-model.md) section 17, which is
authoritative for field names and types.

`category` is a list, so a requirement may carry several categories. **File placement is by primary
category only** — `req-WEBHOOK-001` lives in `webhook-validation.yaml` while also carrying
`authentication` and `integrity`.

A new catalog version gets a new directory. Requirement identifiers are stable across versions; a
requirement that is replaced rather than edited records the identifier it replaces in `supersedes_id`.

## Lifecycle

DEC-057 governs how versions change. The short form:

- **Versions are `<major>.<minor>`, and there is no patch level.** A minor version may add,
  revise, and retire requirements but never renumbers or reuses an identifier; a major version may
  renumber and then ships a fate map. The patch class is empty by construction: the content hash
  covers the parsed catalog, so any change a parser can see breaks verification against recorded
  runs. A fix, however small, is a new minor version.
- **A version is editable while `draft` and immutable once released.** Version 0.1 released when
  the recorded ForgeFlow fixture (#263) landed and is recorded `active` in `versions.yaml`; its
  directory is frozen. CI fails any pull request touching a file under a released directory
  (`scripts/check_catalog_freeze.py`); the loader's hash check remains the read-time backstop.
- **Governance metadata lives outside the frozen content**, in the top-level `versions.yaml`
  (lifecycle status, maintainer, release date, last-reviewed date), so retiring a version does not
  move a hash a recorded assessment verifies. The loader sources lifecycle status from the
  registry where an entry exists; each frozen manifest keeps the status it carried when it froze.
- **A requirement retires by `status: retired`, never by deletion, within a major lineage.** The
  entry stays in its category file so old references resolve. Removal happens only at a major
  version, recorded as a fate.
- **Cross-version fate maps are authored data**: `mappings/0.1-to-0.2.yaml` records one fate per
  old identifier (`unchanged`, `revised`, `retired`; at a major boundary also `moved_to`,
  `merged_to`, `split_to`, `deleted` with a reason). Tests hold them referentially complete in
  both directions. The loader never reads them.

## How to read a requirement

Four fields carry most of the meaning, and three of them exist to prevent a requirement from being
applied where it does not belong.

- **`statement`** is the expectation. It is written so that *absence of evidence* resolves to
  `unverified`, never to `unmet`. Nothing in this catalog is phrased so that silence in a document
  proves a control is missing.
- **`applicable_conditions`** and **`non_applicable_conditions`** are the conditions under which the
  requirement does and does not apply to a given component. A mapping must carry a rationale referring
  to these, not merely a verdict.
- **`acceptable_implementations`** is **non-exhaustive by construction**. It lists example mechanisms
  that satisfy the requirement; it is not a list of approved products, and an implementation absent
  from the list is not thereby wrong. Treating one example as the only valid control is an explicit
  failure condition for the mapping step
  ([`agent-design.md`](../docs/architecture/agent-design.md), sections 12 and 13). Entries are
  therefore written as mechanism classes rather than brand names.
- **`common_false_positives`** records the conclusions that are wrongly drawn when this requirement is
  not evidenced. It is the field that carries the project's accumulated knowledge of which absences are
  normal. `non_applicable_conditions` says when the requirement does not apply; `common_false_positives`
  says what not to conclude when it does apply but the documentation is silent.

## Applicability vocabulary

`applicable_conditions` and `non_applicable_conditions` are free-text lists, as section 17 defines
them. **No controlled vocabulary has been introduced, deliberately.** Data-model open question 5 — how
requirement applicability conditions should be represented in machine-readable form — is still open,
and inventing an enum before the mapping step exists would answer it by accident.

Conditions are written in a consistent style so that a vocabulary can be observed later rather than
imposed now: a condition is a statement about the system, in the present indicative, that a reviewer
can answer from the approved context. The recurring subjects across version 0.1 are exposure, tenancy,
delegation, data sensitivity, retention, external processing, automation of publication, and whether a
privileged interface exists.

## Citing external frameworks

`source_frameworks` is **provenance, not compliance mapping**. Broad compliance-framework mapping is
explicitly deferred in [`current-architecture.md`](../docs/architecture/current-architecture.md). A
citation records that a requirement is grounded in public work; it is not a claim of coverage of the
cited framework, and no framework in this catalog is covered completely.

Citations use one string per reference:

```
"<framework>: <version-qualified reference>"
```

The version belongs inside the string because section 17 types this field as a list of strings, and
because control identifiers are not stable across releases — NIST renders the same control as
`AC-2(1)`, `AC-02(01)`, or `ac-2.1` depending on the source. Recording the version makes a stale
citation visible rather than silent.

**Where a framework prescribes a reference format, the reference segment uses it.** ASVS's README
prescribes `v5.0.0-2.1.1` for citing a requirement in an external document, precisely because
identifiers are not stable across versions, so an ASVS citation here is `"OWASP ASVS:
v5.0.0-2.1.1"` and the framework segment carries no version of its own (AISVS prescribes the same
shape, `v1.0-C9.4.3`, should the catalog ever adopt it). NIST SP 800-53 and the LLM Top 10
prescribe no reference format, so their citations keep the version in the framework segment:
`"NIST SP 800-53 5.2.0: SI-10"`, `"OWASP Top 10 for LLM Applications 2025: LLM01"`.

Sources used in version 0.1:

| Framework | Role |
|---|---|
| OWASP ASVS 5.0.0 | Primary. Version 5.0 gives 11 of its 17 chapters an explicit `X.1 Documentation` section, so those requirements are assessable from design documentation rather than from a running application. The other six — V1, V4, V9, V10, V12, V17 — open with sections that are not documentation requirements; anyone extending this catalog into their territory does not get a documentation anchor for free. Every chapter version 0.1 cites is among the eleven. |
| NIST SP 800-53 Release 5.2.0 | Secondary. Covers ground ASVS leaves out of scope: segmentation, availability, retention, external system services. Public domain. |
| OWASP Top 10 for LLM Applications 2025 | The AI-provider surface, which neither of the above addresses. **An archived release**: the 2026 list was published 2026-08-04 under the [GenAI Security Project organisation](https://github.com/GenAI-Security-Project/GenAI-LLM-Top10), and the original OWASP repository is now a legacy archive. The 2026 release renumbers two of the categories this catalog cites — Improper Output Handling moves LLM05:2025 to LLM10:2026, Unbounded Consumption moves LLM10:2025 to LLM06:2026 — so the version-pinned 2025 citations below remain correct provenance, and a bare `LLMxx` with no year is ambiguous. DEC-058 decides it: catalog 0.2 cites `LLMxx:2026`; 0.1's 2025-pinned strings stand as archived provenance. |

Sources adopted for version 0.2 (DEC-058, DEC-059) and cited by it:

| Framework | Role and posture |
|---|---|
| OWASP AISVS 1.0 | Agentic and MCP ground (chapters C9 and C10) for 0.2's AI categories. Cited as `"OWASP AISVS: v1.0-C9.4.3"` — AISVS prescribes the reference form, so the framework segment carries no version. **The register caveat is binding**: AISVS phrases for runtime verification, so a requirement grounded in it adopts the substance rewritten into the documentation register — silence resolves to `unverified`, never `unmet`. CC BY-SA 4.0: cited by identifier, wording never reproduced. |
| OWASP AI Exchange | A living document with no versioned releases; permalink plus accessed date is the only stable handle, and the date is mandatory: `"OWASP AI Exchange: /go/<anchor>/, accessed YYYY-MM-DD"` — `/go/` is the site's canonical permalink prefix. May stand as a sole citation. |
| OWASP Cumulus | Ground for the 0.2 cloud-operations category (DEC-059). Prescribes no reference format, so the version stays in the framework segment: `"OWASP Cumulus v1.2.0: <suit> <rank>"` — cards are identified suit-and-rank (`Recovery K`, `Monitoring 7`), and v1.2.0 (2025-10-27) is the release the 0.2 citations were verified against. **CC BY 4.0, not share-alike** (the GitHub license API misreports it as null because of the REUSE layout): wording may be adapted with attribution, unlike the ASVS and AISVS posture. Do not apply either source's posture to the other. |

OpenCRE identifiers were considered as renumbering-proof anchors and rejected (DEC-058): their
public ASVS mapping still resolves to v4.0.3, and an anchor whose own mappings lag reintroduces
the crosswalk problem it claims to solve. `source_frameworks` also stays `list[string]` for 0.2 —
the structured-object alternative waits for a machine consumer (DEC-058).

Requirement text in this catalog is **written originally**. ASVS 5.0 is licensed CC BY-SA 4.0 —
the version matters, since ASVS 4.x shipped under CC BY-SA 3.0, and the vendored export's
`LICENSE.txt` in [`_external/asvs/`](_external/asvs/) carries the 4.0 text — so
reproducing its wording would place this catalog under a share-alike obligation; citing identifiers
while writing an original `statement` does not. This also satisfies the clean-room expectation in
[`design-principles.md`](../docs/product/design-principles.md) that the project use public standards
and original requirements.

Three limits worth stating rather than hiding:

- **`req-WEBHOOK-002` carries no ASVS citation.** ASVS 5.0 addresses replay only for authentication
  tokens and has no general inbound-event replay requirement. The requirement is original and cites
  NIST by analogy.
- **`req-NET-001` cites ASVS only for the documentation half.** ASVS scopes itself to the application
  rather than to its network placement, so it carries no boundary-protection requirement. `13.1.1`
  covers documenting communication needs; the placement expectation itself cites `SC-7`.
- **ASVS 5.0.0 removed its CWE mappings**, and its published NIST mapping still targets SP 800-63-3
  though Revision 4 is final. Citations here are made directly and are not chained through it.
- **Never source ASVS crosswalks through OpenCRE.** As of 2026-08-10 its public ASVS mapping still
  resolves to v4.0.3 blob URLs, one major version behind what this catalog cites. Trace cites
  5.0.0 directly, ahead of the mapping ecosystem; a crosswalk pulled through OpenCRE would silently
  reintroduce 4.x identifiers, which do not survive the 5.0 renumbering.

## Validation

Most of this happens at load, for every caller, in
[`loader.py`](../src/trace_ai/services/requirements/loader.py). It refuses to return a catalog that
is not well-formed rather than returning a partial one:

- **Schema conformance** against data-model.md section 17 — required fields present, no unknown
  fields, `status` and `default_severity` drawn from the vocabularies in section 4.5. Enforced by
  the `Requirement` model itself, which inherits `extra="forbid"`.
- **Identifier form** — every requirement identifier is *authored* in the DEC-018 sense:
  `req-AUTH-001`, prefix and category and number. `req-001` is a valid generated identifier and is
  refused here, because a catalog entry numbered by a counter is one no person assigned.
- **Manifest agreement** — `catalog.yaml` and the category files list the same identifiers, in both
  directions, with no duplicates, all declaring the same `catalog_version`.
- **Version pinning** — a caller names the version it wants. Nothing globs the version directories
  and takes the last one, so adding `0.2/` cannot change what an in-flight assessment is assessed
  against.
- **`content_hash`** — recomputed and compared on every load. See below.

Two things stay in `tests/unit/test_requirements_catalog.py`, because they are authoring
conventions rather than schema:

- **Citation format** — every `source_frameworks` entry parses as `<framework>:
  <version-qualified reference>` and names a framework the catalog has already adopted, and an
  ASVS reference uses the `v5.0.0-2.1.1` form ASVS prescribes. The adopted list lives in the test:
  adopting a framework is a provenance decision recorded in this file, not a code change.
- **`applicable_technologies` is populated on nothing.** Asserted, because it is the fact DEC-024
  turns on — it is the only structured filter field section 17 offers, it carries no data, and that
  is why there is no deterministic requirement pre-filter.

None of it checks judgment. That a requirement is well-formed says nothing about whether it is
right, whether its citation is apt, or whether it belongs in the catalog at all; those stay review
questions. **ASVS citations are resolved against a cached v5.0.0 export** by
`scripts/asvs_resolver.py` and tested in `tests/unit/test_requirements_catalog.py` (issue #221,
survey item A1); NIST SP 800-53 and OWASP Top 10 for LLM Applications are not vendored, so a
plausible but wrong identifier for either of those still passes.

Adding a field to a requirement fails validation by design. The Requirement object is
defined in the data model, so extending it is a design change and belongs in the decision log
(DEC-011 is the worked example) rather than in a YAML file.

## The catalog's name

`catalog.yaml` calls itself `core`, and that is a **name rather than an identifier**. DEC-034 puts
authored configuration outside the identifier scheme in
[`data-model.md`](../docs/architecture/data-model.md) section 2.1: a catalog is not scoped to an
assessment, is not minted by the persistence layer, and is referenced by version rather than by
identifier. Its identity is `(id, version)` — the slug names the family, the version names the
edition, and everything that refers to a catalog refers to the version.

The value was `cat-core` until DEC-034. `cat` is not a prefix in section 2.1 and never was, so the
value read as an identifier from a registry that does not contain it. **Do not give a catalog name a
prefix.** Requirement identifiers inside the catalog are a different thing entirely: `req-AUTH-001`
is authored, globally unique, and inside the scheme, because assessment objects cite it.

## `content_hash`

Section 30 requires `content_hash` on `RequirementsCatalog`, and `catalog.yaml` carries one.
DEC-010 omitted it while no loader existed to compute it; DEC-019 states what the loader computes
and the loader now does.

It is `sha256:` followed by 64 lowercase hexadecimal characters, over a **canonical
re-serialization** of the parsed catalog with keys sorted and formatting discarded — not over the
file bytes. Reformatting, reordering keys, reordering `requirement_ids`, and editing comments
therefore do not change the hash. `loader.py`'s module docstring states the exact input, because a
hash over an unstated input is not verifiable.

**Do not edit the value by hand.** Editing a requirement moves it, and the loader then refuses to
read the catalog until it is regenerated:

```bash
uv run python scripts/catalog_hash.py            # print declared and computed
uv run python scripts/catalog_hash.py --write    # rewrite the line
```

That has a consequence worth knowing when editing this catalog: the hash covers what the parser
sees. Prose carried in a YAML comment is invisible to it, even where that prose is doing real work
— including the comment above `content_hash` itself.

## Version 0.1

Twenty-three requirements across eleven category files, scoped to the ForgeFlow demo scenario so that
every requirement has documentation to be exercised against.

| Category file | Requirements |
|---|---|
| `administrative-access.yaml` | `req-ADMIN-001` |
| `ai-input-handling.yaml` | `req-AI-001` … `req-AI-004` |
| `authentication.yaml` | `req-AUTH-001`, `req-AUTH-002` |
| `authorization.yaml` | `req-AUTHZ-001`, `req-AUTHZ-002` |
| `cicd-trust.yaml` | `req-CICD-001` |
| `data-protection.yaml` | `req-DATA-001` … `req-DATA-004` |
| `logging.yaml` | `req-LOG-001`, `req-LOG-002` |
| `network-segmentation.yaml` | `req-NET-001` |
| `secrets-management.yaml` | `req-SECRET-001`, `req-SECRET-002` |
| `third-party-integration.yaml` | `req-TPI-001`, `req-TPI-002` |
| `webhook-validation.yaml` | `req-WEBHOOK-001`, `req-WEBHOOK-002` |

The catalog is small on purpose. A successful assessment may apply very few of these requirements, and
none of them is intended to be applied to every component.

## Version 0.2

Thirty-two requirements: everything in 0.1 carried under its identifier (three entries `revised`
for the LLM Top 10's 2026 renumbering — see `mappings/0.1-to-0.2.yaml` for every fate), plus two
new categories:

| Category file | Requirements | Ground |
|---|---|---|
| `agentic-orchestration.yaml` | `req-AGENT-001` … `req-AGENT-004` | AISVS C9/C10 and the AI Exchange (DEC-058), substance rewritten into the documentation register |
| `cloud-operations.yaml` | `req-OPS-001` … `req-OPS-005` | Cumulus v1.2.0 (DEC-059), adapted with attribution under CC BY 4.0 |

Version 0.2 also moves the LLM Top 10 citations to the 2026 identifiers under the GenAI Security
Project publisher (`"GenAI Security Project LLM Top 10: LLM01:2026"`), per DEC-058. It is `draft`
in `versions.yaml` and editable in place until released.
