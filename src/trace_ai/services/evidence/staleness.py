"""Stale-evidence detection: which of a finding's citations have aged past the threshold (#571).

The age anchor is the citation's best real timestamp, measured against a caller-supplied
`as_of`, never a wall clock read here. When a reference carries `observed_at` — a date its
ingestion path truly recorded, such as the last commit touching a repository file (DEC-140) —
that is the anchor, because it is closer to when the cited fact was last true. Otherwise the
anchor stays `EvidenceReference.created_at`, the capture time, which DEC-118 records as the
only timestamp the system holds for a supplied document. **Every flag names which basis it
used**: a flag that silently switched meaning between "observed N days ago" and "captured N
days ago" would be worse than the capture-age proxy it replaces.

The report passes its own `generated_at` stamp, so two renders of identical approved state at
the same stamp stay identical; the read-only view passes the request's time, because a view is
a point-in-time look and says so.

A flag is all this module produces. Nothing here suppresses, expires, or downgrades anything:
severity stays the reviewer's (DEC-030), and a finding with stale citations is a finding whose
evidence a reader should re-verify, not a lesser finding. No configured threshold means no
flags — absence of a policy is not a policy (DEC-036's discipline). Future-features 6.6's
expiration-policy machinery stays Research.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Literal, NamedTuple

if TYPE_CHECKING:
    from collections.abc import Mapping

    from trace_ai.domain.evidence import EvidenceReference
    from trace_ai.domain.finding import Finding

__all__ = ["AgeBasis", "StaleCitation", "stale_citations"]

AgeBasis = Literal["observed", "captured"]
"""Which timestamp anchored the age: the source's own observation date, or capture time."""


class StaleCitation(NamedTuple):
    """One citation past the threshold, with the basis its age was measured on."""

    evidence_id: str
    basis: AgeBasis


def stale_citations(
    finding: Finding,
    references: Mapping[str, EvidenceReference],
    *,
    threshold_days: int,
    as_of: datetime,
) -> tuple[StaleCitation, ...]:
    """The finding's cited references older than `threshold_days` at `as_of`, with their basis.

    Results are in the finding's own citation order. A citation that does not resolve is not
    returned: the report already renders an unresolvable citation as its own, louder problem,
    and calling it stale would dress a missing passage as an old one.
    """
    cutoff = as_of - timedelta(days=threshold_days)
    stale: list[StaleCitation] = []
    for evidence_id in finding.evidence_ids:
        reference = references.get(evidence_id)
        if reference is None:
            continue
        observed = reference.observed_at
        basis: AgeBasis = "observed" if observed is not None else "captured"
        anchor = observed if observed is not None else reference.created_at
        if anchor < cutoff:
            stale.append(StaleCitation(evidence_id, basis))
    return tuple(stale)
