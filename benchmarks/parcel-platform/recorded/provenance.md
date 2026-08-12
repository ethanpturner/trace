# Recorded run for the parcel-platform scenario

Authored offline against the `offline-fake` profile and the deterministic model, shaped
exactly as recordings are consumed (one JSON per model call, schema inferred structurally,
replayed in order). Reviewer decisions reach the workflow through the same writers an
interactive session uses (DEC-017); replay is not an ablation (DEC-012). A live capture
replaces these files file for file. Version pins: profile offline-fake, workflow 0.1, catalog
0.1, report template report-v1, generation timestamp 2026-08-11T12:00:00+00:00.

## Scope

This recording exercises the large-architecture input: nineteen components, five actors,
five assets, thirteen flows, and four boundaries extracted from one document, with the
context checkpoint answered over all of them. Two unmet mappings become the two expected
findings (req-ADMIN-001 on the admin console's customer sign-in path, req-LOG-001 on the
notification templates' body-level logging), and two unverified mappings become the gaps
(req-DATA-002 for the warehouse's admittedly unwritten retention, req-NET-001 for the data
zone's unstated enforcement). The size lives in the context, not the finding count.
