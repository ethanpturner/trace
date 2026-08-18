# Round three: twenty features planned, twenty delivered, and the first release cut

The session began as a planning exercise while round two was still merging: fan out over the
corpus, the decision log, and the issue tracker, and produce the next wave. It ended with all
twenty planned issues (#522–#541) delivered, three decision-log collisions survived, one
release cut, and the catalog two minor versions further on.

## What changed

The wave grouped into five threads, delivered in dependency order rather than issue order.

**Cost and measurement.** The mapping cache split (DEC-105) made DEC-024's "stable cacheable
prefix" sentence true — the catalog now leads the trusted region and the seam carries a
system-region cache hint. The offline partitioning measurement (#532) then closed DEC-024's
escalation path on evidence: fan-out multiplies cache-adjusted input roughly ninefold, because
everything that is not the catalog duplicates per partition (DEC-107). The scorecard grew an
F1-across-versions matrix (#535) and a duplicate-miss instrument (DEC-110) so DEC-043's
revisit trigger can actually fire; annotator agreement got its machinery (DEC-112) and — on
the record — no data, because a second annotation authored by the session that wrote the
instrument would be self-agreement wearing independence's clothes.

**Decided families, completed.** DEC-096 closed (`report show`/`verify --json`); DEC-070
closed twice over — the IaC parser (Terraform JSON, DEC-113) and the cross-claim consistency
observations (#526), which now have three parsers' worth of mechanical claims to check against
prose; DEC-097's diff residuals landed as declared-never-applied readings (rename candidates
and finding↔gap resolution shifts); DEC-095's Responses API deferral was discharged under the
conformance suite; DEC-091's capture rehearsal gap got `--rehearse`, with the zero-usage guard
kept structural (a rehearsal envelope is refused by every recording reader).

**The catalog.** Two packs in one still-draft version: OAuth/OIDC (DEC-111), measured against
oidc-portal with its recorded mapping re-authored to engage the new requirements, and
fine-tuning (DEC-114), measured by the new fourteenth scenario `reply-tuner` — one authored
recording exercising a documented-negative finding, a silence-shaped gap, and a suppressed
false positive at once. The org-controls catalog (DEC-115) arrived as the fourth parser:
hash-verified central facts entering only as documented claims, never as authority.

**Surfaces.** HTML report rendering as a derived view (DEC-108, escape-first, no second
renderer to disagree with the first); the lineage walk made navigable with per-hop anchors and
live re-verification at the evidence leaf (#533); the tracing emitter built to the section
5.17 review with a span that structurally cannot carry content (DEC-109).

**Docs made true and kept true.** Section 15 now records the real tree with a two-direction
conformance test (#540); data-model section 39's seven live questions were resolved or
re-deferred with named triggers (DEC-106); the release record exists with assembled-not-
authored numbers (#524); and the decision log gained a structure guard after a real failure —
a conflict-resolution script truncated DEC-113 to a bare heading and two merges passed before
anything noticed. The restored entry and the test landed together.

## What the session taught

Three sessions were writing the decision log concurrently, and the DEC numbers collided twice
(DEC-104 went to the documentation site mid-flight; DEC-113's body was lost to a truncating
conflict script). The lesson is recorded as machinery, not as a resolution to be more careful:
merge develop before numbering, and a structural test that a heading without a body fails.

The other lesson is about honest instruments. Three of this wave's features are measuring
devices delivered without the data they measure — duplicate misses, annotator agreement, the
capture rehearsal — and each states on the record why the data is deliberately absent. The
alternative in every case was a number that looked like evidence and was not.

## Open next

- The keyed track, unchanged and now better instrumented: the eleven-scenario live sweep
  (#484) will measure the cache split's real saving; capture rehearsals cost nothing first.
- The registry-only flip of catalog 0.3 to active rode the release prep; the org-controls
  catalog waits for an operator's real organizational facts.
- A genuinely second annotation pass, by a person, for the agreement instrument.
- The narrated demo video (#353) remains the one open Stage 6 item.
