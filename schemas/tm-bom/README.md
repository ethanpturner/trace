# TM-BOM schema (vendored)

`threat-model.schema.json` is the OWASP Threat Model Library schema, vendored so the DEC-072
TM-BOM export can be validated offline — CI must never need the network, and a serializer checked
against a schema fetched at test time would be checked against whatever the network said that day.

- Source: https://github.com/OWASP/www-project-threat-model-library
- Version: v1.0.2 (the schema's own `$id`)
- License: MIT (Threat Model Library Team)
- Retrieved: 2026-08-12

The schema is pre-1.0 as a project; DEC-072 records the tracking cost and names the `extensions`
block as the hedge — Trace-specific content rides there and survives schema drift. Update by
replacing the file wholesale and bumping this note; never hand-edit the schema.
