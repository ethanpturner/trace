# 2026-08-12 — M12 Decision Debt: the remaining eleven

Closed milestone M12. The eleven issues left after the first-four session each shipped as its own
squash-merged PR to `develop` (#374–#384), CI green throughout, the recorded ForgeFlow replay
byte-identical at every merge except the two that changed the report on purpose.

## What changed

- **#341 — content fingerprints (DEC-066).** `Finding` and `DocumentationGap` gain
  `content_fingerprint`, computed at persist from the evaluation matcher's one implementation so
  scoring and longitudinal identity cannot drift. The gap resolution the DEC deferred is fixed:
  related mapping → `requirement_id`, plus the mapping's threat's component names. Recomputed on
  identity-field edits (observable in the captured delta), both merge paths, and the DEC-051
  conversion.
- **#339 — critic precedent (DEC-064), and DEC-080.** Rationale-bearing dismissals render as a
  marked block in the critique package, matched deterministically; precedent identifiers stay out
  of `referenceable_ids`, so context-not-subject is enforced by reference validation. DEC-064's
  open question — cap and ordering — needed closing to build the block, so **DEC-080** records
  it: ten entries, match tightness before recency, exclusions named.
- **#340 — catalog-gap candidates (DEC-065).** `CatalogGapCandidate` (section 23a, prefix `cgc`)
  with the falsifiability gate (nearest requirements considered, why each does not fit — empty is
  a schema failure). Structurally excluded from conclusions: no report section, no consolidation
  path, a source-scan test. Listing surfaces: the checkpoint 2 informational block and
  `trace assessment candidates`. Prompt guidance landed on the mapping agent only — the threat
  agent keeps the schema capability but is not invited to name requirements it is never shown.
- **#342 — cache-token accounting (DEC-067).** Disjoint input spans through the seam, the ledger,
  and the `WorkflowRun` rollups; `estimated_cost` is the profile-weighted sum, with
  `cache_creation_cost_per_million` joining the renamed `cache_read_cost_per_million`.
- **#343 — context-model extensions (DEC-068).** Sensitivity vocabulary and at-rest split on
  `Asset`, personas on `Actor`, `entry_point_types` on `Component`, the closed `access_model` on
  `SystemContext`, and the two adopted checks: warn-only zone mismatches, and privilege-extremes
  Questions raised idempotently by the driver. Both questions fire on the ForgeFlow recording —
  its context represents neither extreme — so the pinned report hash moved.
- **#344 — profile overlays (DEC-069).** Per-agent model-and-rates overlays validated at load
  against the cap's six agent names. Routing reuses the proposal schemas' mutual exclusivity
  (what `recorded.py` already relies on) so the seam gains no parameter; attribution rides
  `ExecutionRecord.model_name` unchanged.
- **#346 — coverage ledger (DEC-071).** Every source document in exactly one bucket, rendered in
  section 14; the renderer refuses a ledger that does not account for every document. The
  carriers the DEC left open: the agent nodes now persist excluded-evidence *names* on execution
  metadata, not counts. Second intentional hash move.
- **#345 — compose parser (DEC-070).** Deterministic proposals from compose manifests, evidence
  quoting the artifact's own lines, `structured_input` provenance, same conversion and
  checkpoint 1 as agent output. The baseline unions seeded objects explicitly rather than
  sweeping the repository, so a re-extraction run cannot adopt a rejected revision's objects.
- **#349 — prompt definitions.** Section 29 implemented — the last deferred registry entry, so
  section 40's deferred list is now empty. Compositions snapshot their `PromptDefinition` into
  `traces/prompts/` append-only via a registry subclass the driver binds; resolvable by reference
  or composed hash.
- **#347 — TM-BOM export (DEC-072).** `trace export tm-bom` against the vendored OWASP Threat
  Model Library schema (v1.0.2, MIT). Where the schema demands booleans Trace honestly lacks, the
  export writes the conservative value, names it in an `unconfirmed` assumption row, and carries
  the raw fields in the extensions block — DEC-009 under a strict schema. Findings ride
  extensions verbatim rather than TM-BOM risks, whose score arithmetic the reviewer never
  assigned.
- **#348 — catalog 0.2 (DEC-057/058/059).** Thirty-two requirements: 0.1 carried forward (three
  `revised` for the LLM 2026 renumbering), `req-AGENT-001..004` from AISVS C9/C10 rewritten into
  the documentation register, `req-OPS-001..005` from Cumulus v1.2.0 cards adapted under
  CC BY 4.0. The DEC-057 machinery landed with it: per-version manifests, the `versions.yaml`
  registry (0.1 recorded active without touching frozen content), the fate map held complete in
  both directions, and the CI freeze guard.

## Decisions and reasoning

- **Answer an open question with a DEC when it gates the build; fix a deferred resolution in the
  implementing change when the DEC says so.** DEC-064's cap/ordering became DEC-080 (the DEC-079
  precedent); DEC-066's gap resolution and DEC-071's carriers were explicitly delegated to
  implementation and landed there, documented in code and docs.
- **Verify external identifiers before citing them.** A research pass against the AISVS 1.0
  chapter sources and the Cumulus deck source preceded 0.2's authoring: MCP is C10 (not C11),
  AISVS publishes no git tag (the locked `1.0/` folder is the citable identity), Cumulus cards
  are suit-and-rank, and the AI Exchange's canonical permalink prefix is `/go/`, not `/goto/`.
  Each of these would have shipped wrong from memory.
- **Two intentional pinned-hash moves, both regenerated end to end** (report-hash, demo report,
  eval pages — pages regenerated byte-identical both times). Everything else held the replay
  byte-for-byte, which caught real ordering mistakes twice (seeding before evidence listing;
  persist-then-list in the extraction baseline).
- **One process slip, recovered**: #339's commit initially landed on local `develop` before
  branching; the branch carried it and local `develop` was reset to origin. Protected-branch
  rules would have caught it, but the reset kept the local tree honest.

## Open next

- M12 is closed. Remaining milestones: M11 Evaluation Completion (9 issues), M13 Surface
  Completion (3), M9/M10 leftovers (5).
- Catalog 0.2 is `draft` and editable in place; DEC-059's open question stands — no seeded
  benchmark exercises the cloud-operations category yet.
- DEC-072's open question (TM-BOM round-trip as structured input) and the SARIF/Mermaid entries
  remain unscheduled by design.
- PR #281 (roadmap M6–M9) from an earlier session is still open on `feature/roadmap-m6-m9`, and
  `stash@{0}` ("parallel-session-uncommitted-M9-work") is still unrestored on `develop`.
