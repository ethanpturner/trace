"""The read-only demonstration interface (DEC-032, issue #276).

A local, localhost-only rendering of a completed assessment's persisted objects — the seven Stage 5
views, including the finding-lineage walk no other tool can render because no other tool holds the
chain. It is a *view*, not a second way to drive the pipeline: no route mutates state, review stays
on the command line (DEC-032), and closing it loses nothing because everything it shows is derived
from the store.

The interface uses `http.server` from the standard library and no framework — the answer to
`current-architecture.md` section 19's open question is "none," consistent with DEC-016's rejection
of a framework and DEC-032's no-dependency rule. `render.py` turns persisted objects into HTML
strings and is pure and testable; `server.py` binds those strings to a localhost port. Source-
derived text is HTML-escaped and labelled untrusted, because a browser is not the inert terminal
the command line renders into.
"""
