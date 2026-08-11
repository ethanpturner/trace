"""Typed routing reasons on checkpoint subjects (DEC-062), derived, never stored.

A reason code triages a reviewer's attention: it says *why* a subject is worth a closer look,
computed as a deterministic function of persisted state at package-build time. Nothing on the
run, the validation output, or the subject records a code — the package is a view over stored
facts (DEC-005, DEC-017), and a code is re-derivable from those facts at any time, which is the
audit.

Two guards are part of DEC-062, not decoration. A reason never filters: every subject still
requires a `ReviewerDecision`, and a subject with no codes is routine rather than exempt. And a
reason is not a verdict: it grants no node authority and the validation node's report-and-route
remit is unchanged.

The vocabulary is closed. This module derives `injection_flag` (issue #274); the other codes'
derivations land with the features that produce their inputs — `revisit_due` with DEC-061,
`contradicted` and `no_evidence` as their handling is built. An absent code never reads as a
clean bill.
"""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

from trace_ai.domain.evidence import EvidenceReference
from trace_ai.domain.source_observation import ObservationKind, SourceObservation

if TYPE_CHECKING:
    from trace_ai.services.assessment import AssessmentHandle

__all__ = ["ReasonCode", "injection_flagged_subjects"]


class ReasonCode(StrEnum):
    """The closed routing-reason vocabulary (DEC-062). Extending it is a design change."""

    LOW_CONFIDENCE = "low_confidence"
    CONTRADICTED = "contradicted"
    NO_EVIDENCE = "no_evidence"
    INJECTION_FLAG = "injection_flag"
    REVISIT_DUE = "revisit_due"


def injection_flagged_subjects(handle: AssessmentHandle) -> set[str]:
    """Every context subject citing evidence from a document an injection attempt was recorded on.

    The derivation is deterministic: an `injection_attempt` `SourceObservation` cites the passages
    that are the attempt; those passages belong to source documents; and any extracted object
    citing evidence from one of those documents is flagged. The flag reaches the document's benign
    content too, which is the safe direction — it says "this came from a document that tried to
    inject, look carefully," and DEC-062 makes reasons triage attention rather than filter it.
    """
    observations = [
        observation
        for observation in handle.objects.list(SourceObservation)
        if observation.kind is ObservationKind.INJECTION_ATTEMPT
    ]
    if not observations:
        return set()

    references = list(handle.objects.list(EvidenceReference))
    document_of = {reference.id: reference.source_document_id for reference in references}
    flagged_documents = {
        document_of[evidence_id]
        for observation in observations
        for evidence_id in observation.evidence_ids
        if evidence_id in document_of
    }
    if not flagged_documents:
        return set()

    evidence_in_flagged = {
        reference.id
        for reference in references
        if document_of.get(reference.id) in flagged_documents
    }

    from trace_ai.services.context.pipeline import context_objects

    flagged: set[str] = set()
    for obj in context_objects(handle):
        cited = set(getattr(obj, "evidence_ids", ()) or ())
        object_id = getattr(obj, "id", None)
        if object_id is not None and cited & evidence_in_flagged:
            flagged.add(str(object_id))
    return flagged
