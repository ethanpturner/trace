"""Stale-evidence detection: which of a finding's citations have aged past the threshold (#571).

The age anchor is `EvidenceReference.created_at` — the moment the passage was captured from the
source document — measured against a caller-supplied `as_of`, never a wall clock read here. The
report passes its own `generated_at` stamp, so two renders of identical approved state at the
same stamp stay identical; the read-only view passes the request's time, because a view is a
point-in-time look and says so. DEC-118 records why capture time is the anchor: it is the only
timestamp the system actually holds. An observed-at field nobody supplies would be a fabricated
measurement, and future-features 6.6's expiration-policy machinery stays Research.

A flag is all this module produces. Nothing here suppresses, expires, or downgrades anything:
severity stays the reviewer's (DEC-030), and a finding with stale citations is a finding whose
evidence a reader should re-verify, not a lesser finding. No configured threshold means no
flags — absence of a policy is not a policy (DEC-036's discipline).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping

    from trace_ai.domain.evidence import EvidenceReference
    from trace_ai.domain.finding import Finding

__all__ = ["stale_evidence_ids"]


def stale_evidence_ids(
    finding: Finding,
    references: Mapping[str, EvidenceReference],
    *,
    threshold_days: int,
    as_of: datetime,
) -> tuple[str, ...]:
    """The finding's cited reference ids captured more than `threshold_days` before `as_of`.

    Ids are returned in the finding's own citation order. A citation that does not resolve is
    not returned: the report already renders an unresolvable citation as its own, louder
    problem, and calling it stale would dress a missing passage as an old one.
    """
    cutoff = as_of - timedelta(days=threshold_days)
    return tuple(
        evidence_id
        for evidence_id in finding.evidence_ids
        if (reference := references.get(evidence_id)) is not None and reference.created_at < cutoff
    )
