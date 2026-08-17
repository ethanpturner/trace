"""Assessment diffing: what changed between two assessments of the same system (DEC-097).

Promoted from future-features 4.1. A re-run assessment previously produced a wholly new report
with no relation to the last one; this package answers the reviewer's actual question — what
changed, what needs re-review — by comparing two local assessments' approved models.

Identity across assessments is the hard problem: identifiers are allocated per assessment
(DEC-018), so the same component in two assessments carries different identifiers. Matching
reuses the conventions the evaluation matcher already owns (`matching.py`, DEC-056, DEC-093):
names for components, actors, assets, and boundaries; (source, destination) for flows;
(subject, predicate) for claims; the persisted DEC-066 content fingerprint for findings.
Anything ambiguous or unresolvable is reported as added or removed, never force-paired — a
diff that guessed a pairing would report a change nobody made.
"""

from trace_ai.services.diff.assessments import (
    AssessmentDiff,
    DiffEntry,
    FamilyDiff,
    diff_assessments,
)

__all__ = ["AssessmentDiff", "DiffEntry", "FamilyDiff", "diff_assessments"]
