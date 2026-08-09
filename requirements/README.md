# Requirements catalog

Version-controlled security expectations that the Requirement and Control Mapping step is designed to
apply against an approved system context. This directory holds data. No product code reads it;
`tests/unit/test_requirements_catalog.py` checks that it is well-formed.

The catalog exists so that requirement applicability can be *decided* rather than assumed. Its purpose
is as much to establish when a requirement does not apply as when it does — see
[DEC-009](../docs/architecture/decision-log.md).

## Layout

```
catalog.yaml     the catalog manifest
0.1/             requirements for catalog version 0.1, one file per primary category
```

Each file under `0.1/` holds a single `requirements:` list. Requirement objects follow
[`docs/architecture/data-model.md`](../docs/architecture/data-model.md) section 17, which is
authoritative for field names and types.

`category` is a list, so a requirement may carry several categories. **File placement is by primary
category only** — `req-WEBHOOK-001` lives in `webhook-validation.yaml` while also carrying
`authentication` and `integrity`.

A new catalog version gets a new directory. Requirement identifiers are stable across versions; a
requirement that is replaced rather than edited records the identifier it replaces in `supersedes_id`.

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
"<framework> <version>: <control id>"
```

The version belongs inside the string because section 17 types this field as a list of strings, and
because control identifiers are not stable across releases — NIST renders the same control as
`AC-2(1)`, `AC-02(01)`, or `ac-2.1` depending on the source. Recording the version makes a stale
citation visible rather than silent.

Sources used in version 0.1:

| Framework | Role |
|---|---|
| OWASP ASVS 5.0.0 | Primary. Version 5.0 gives every domain chapter an explicit `X.1 Documentation` section, so those requirements are assessable from design documentation rather than from a running application. |
| NIST SP 800-53 Release 5.2.0 | Secondary. Covers ground ASVS leaves out of scope: segmentation, availability, retention, external system services. Public domain. |
| OWASP Top 10 for LLM Applications 2025 | The AI-provider surface, which neither of the above addresses. |

Requirement text in this catalog is **written originally**. ASVS is licensed CC BY-SA 4.0, so
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

## Validation

`tests/unit/test_requirements_catalog.py` runs under a bare `uv run pytest`. It enforces four things
and deliberately no more:

- **Schema conformance** against data-model.md section 17 — required fields present, no unknown
  fields, `status` and `default_severity` drawn from the vocabularies in section 4.5.
- **Identifier convention** — every requirement identifier starts with `req-`.
- **Manifest agreement** — `catalog.yaml` and the category files list the same identifiers, with no
  duplicates.
- **Citation format** — every `source_frameworks` entry parses as `<framework> <version>: <control
  id>` and names a framework the catalog has already adopted.

It checks form, not judgment. That a requirement is well-formed says nothing about whether it is
right, whether its citation is apt, or whether it belongs in the catalog at all; those stay review
questions. In particular **nothing verifies that a cited control identifier exists** in the framework
it names — the frameworks are not vendored, and a plausible but wrong identifier passes.

Adding a field to a requirement fails the unknown-field test by design. The Requirement object is
defined in the data model, so extending it is a design change and belongs in the decision log
(DEC-011 is the worked example) rather than in a YAML file.

## `content_hash`

Section 30 lists `content_hash` as required on `RequirementsCatalog`, and `catalog.yaml` does not carry
one. It is a derived value; there is no loader to compute or verify it, and a hand-maintained hash
would be stale after the first edit. `RequirementsCatalog` is itself deferred in the data model's
initial implementation priority. The hash is designed to be computed when a loader exists.

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
