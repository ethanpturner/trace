"""The lineage walk: for any finding, the ordered chain of objects that produced it.

`data-model.md` section 32 requires a finding to be traceable through source document, evidence
reference, context claim, threat, requirement and control mapping, evidence assessment, critique,
and finding. This module is the query surface for that chain — what the checkpoint 2 review
package and the "why was this generated" view later consume. It is a walk over identifiers the
objects already carry, not a stored structure: DEC-006 makes the objects authoritative, so a
second persisted lineage would be a second copy that could disagree.

**A link that does not resolve raises.** Section 32 says every significant conclusion should have
understandable lineage, and a finding citing a threat nobody can produce is a finding whose
history cannot be read. `conversion_chain` (DEC-051) takes the same position for the same reason.
Not every finding uses every object — a chain with no evidence assessment and no critique is
ordinary — but a *named* reference that resolves to nothing is a defect, not a sparse chain.

**The chain must reach evidence.** A finding's `evidence_ids` is non-empty by schema, so a walk
that resolves is guaranteed at least one `EvidenceReference` — which is DEC-009's requirement
seen from the lineage side: no finding exists whose history bottoms out in silence.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from trace_ai.domain.evidence_assessment import SubjectType

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from trace_ai.domain.context_claim import ContextClaim
    from trace_ai.domain.control_mapping import ControlMapping
    from trace_ai.domain.critique import Critique
    from trace_ai.domain.evidence import EvidenceReference
    from trace_ai.domain.evidence_assessment import EvidenceAssessment
    from trace_ai.domain.finding import Finding
    from trace_ai.domain.source_document import SourceDocument
    from trace_ai.domain.threat import Threat

__all__ = ["FindingLineage", "LineageError", "finding_lineage"]


class LineageError(ValueError):
    """A finding names an object the assessment cannot produce. Its history cannot be read."""


@dataclass(frozen=True, slots=True)
class FindingLineage:
    """Section 32's chain for one finding, resolved and in the document's order.

    Fields are ordered source-first, the way section 32 draws the chain. Empty tuples are
    ordinary for `context_claims`, `evidence_assessments`, and `critiques` — not every finding
    uses every object — and never possible for `evidence_references`, whose non-emptiness the
    schema guarantees upstream.
    """

    finding_id: str
    source_documents: tuple[SourceDocument, ...]
    evidence_references: tuple[EvidenceReference, ...]
    context_claims: tuple[ContextClaim, ...]
    threats: tuple[Threat, ...]
    control_mappings: tuple[ControlMapping, ...]
    evidence_assessments: tuple[EvidenceAssessment, ...]
    critiques: tuple[Critique, ...]


def _resolve[ModelT](
    wanted: Iterable[str], available: Sequence[ModelT], *, kind: str, finding_id: str
) -> tuple[ModelT, ...]:
    """The named objects in first-reference order, or the missing identifier by name."""
    by_id = {str(getattr(obj, "id", "")): obj for obj in available}
    resolved: list[ModelT] = []
    seen: set[str] = set()
    for object_id in wanted:
        if object_id in seen:
            continue
        seen.add(object_id)
        found = by_id.get(object_id)
        if found is None:
            raise LineageError(
                f"{finding_id} traces to {kind} {object_id!r}, which is not among the objects "
                f"supplied. A finding whose chain has a missing link is a finding whose history "
                f"cannot be read (data-model.md section 32)."
            )
        resolved.append(found)
    return tuple(resolved)


def finding_lineage(
    finding: Finding,
    *,
    threats: Sequence[Threat],
    control_mappings: Sequence[ControlMapping],
    evidence_assessments: Sequence[EvidenceAssessment] = (),
    critiques: Sequence[Critique] = (),
    context_claims: Sequence[ContextClaim] = (),
    evidence_references: Sequence[EvidenceReference] = (),
    source_documents: Sequence[SourceDocument] = (),
) -> FindingLineage:
    """Walk section 32's chain backward from a finding and return it forward.

    Everything the finding names directly is required to resolve: its threats, its mappings, its
    evidence. From there the walk widens through what those objects name — a threat's assumption
    claims, a mapping's evidence, an assessment over a mapping — and everything *they* name must
    resolve too. Critiques are gathered rather than named: a critique points at its subject, so
    the finding's critiques are the ones whose subject is the finding, one of its threats or
    mappings, or an assessment over one of its mappings.
    """
    resolved_threats = _resolve(finding.threat_ids, threats, kind="threat", finding_id=finding.id)
    resolved_mappings = _resolve(
        finding.control_mapping_ids,
        control_mappings,
        kind="control mapping",
        finding_id=finding.id,
    )

    mapping_ids = {mapping.id for mapping in resolved_mappings}
    over_mappings = tuple(
        assessed
        for assessed in evidence_assessments
        if assessed.subject_type is SubjectType.CONTROL_MAPPING
        and assessed.subject_id in mapping_ids
    )

    assessment_ids = {assessed.id for assessed in over_mappings}
    subject_ids = {finding.id, *mapping_ids, *assessment_ids}
    subject_ids.update(threat.id for threat in resolved_threats)
    raised = tuple(critique for critique in critiques if critique.subject_id in subject_ids)

    claim_ids = [claim_id for threat in resolved_threats for claim_id in threat.assumption_ids]
    resolved_claims = _resolve(
        claim_ids, context_claims, kind="context claim", finding_id=finding.id
    )

    evidence_ids = [
        *finding.evidence_ids,
        *(eid for mapping in resolved_mappings for eid in mapping.evidence_ids),
        *(eid for threat in resolved_threats for eid in threat.evidence_ids),
        *(eid for assessed in over_mappings for eid in assessed.evidence_ids),
        *(eid for claim in resolved_claims for eid in claim.evidence_ids),
        *(eid for critique in raised for eid in critique.evidence_ids),
    ]
    resolved_evidence = _resolve(
        evidence_ids, evidence_references, kind="evidence reference", finding_id=finding.id
    )

    document_ids = [reference.source_document_id for reference in resolved_evidence]
    resolved_documents = _resolve(
        document_ids, source_documents, kind="source document", finding_id=finding.id
    )

    return FindingLineage(
        finding_id=finding.id,
        source_documents=resolved_documents,
        evidence_references=resolved_evidence,
        context_claims=resolved_claims,
        threats=resolved_threats,
        control_mappings=resolved_mappings,
        evidence_assessments=over_mappings,
        critiques=raised,
    )
