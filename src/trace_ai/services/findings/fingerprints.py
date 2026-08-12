"""DEC-066 applied at the persistence boundary: the stored fingerprint is the matcher's.

`services/evaluation/matching.py` owns the computation — `finding_fingerprint` and
`gap_fingerprint` are DEC-056's benchmark matching rule promoted to an object property — and this
module is the only bridge from a repository to it. Everything here resolves identifiers to the
inputs those functions take (normalized component names, the requirement behind a mapping) and
rebuilds the object through the schema with the result. Computing the hash anywhere else is how
evaluation matching and longitudinal identity drift apart, which is the failure DEC-066 exists to
prevent.

The fingerprint is derived, so setting it is a rebuild, not an edit: `updated_at` does not move
and no `ReviewerDecision` is written here. The callers are the persist and edit paths — finding
consolidation, the checkpoint 2 edit and merge actions, and the DEC-051 conversion — each of
which recomputes exactly when DEC-066 says identity can change.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from trace_ai.domain.component import Component
from trace_ai.domain.control_mapping import ControlMapping
from trace_ai.domain.documentation_gap import DocumentationGap
from trace_ai.domain.finding import Finding
from trace_ai.domain.threat import Threat
from trace_ai.services.evaluation.matching import (
    finding_fingerprint,
    gap_fingerprint,
    normalized_name,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from trace_ai.services.assessment import AssessmentHandle

__all__ = [
    "component_name_index",
    "fingerprinted_finding",
    "fingerprinted_gap",
    "gap_identity_indexes",
]


def component_name_index(handle: AssessmentHandle) -> dict[str, str]:
    """Component identifier to normalized name — the index the evaluation matcher builds.

    Built the same way `services/evaluation/metrics.py` and the harness build theirs, so the
    persisted fingerprint and the matcher's computation read identical inputs.
    """
    return {
        component.id: normalized_name(component.name)
        for component in handle.objects.list(Component)
    }


def gap_identity_indexes(
    handle: AssessmentHandle,
) -> tuple[dict[str, str], dict[str, tuple[str, ...]]]:
    """The two resolutions `gap_fingerprint` takes, read from the assessment's objects.

    A mapping reaches its requirement directly; it reaches component names through the threat it
    evaluates, because a mapping carries no components of its own — the resolution DEC-066 left
    to the implementing change. A mapping whose threat is not persisted contributes its
    requirement and no names, which keeps the fingerprint total rather than raising over an
    object the gap merely refers to.
    """
    names = component_name_index(handle)
    threats = {threat.id: threat for threat in handle.objects.list(Threat)}

    requirement_by_mapping: dict[str, str] = {}
    component_names_by_mapping: dict[str, tuple[str, ...]] = {}
    for mapping in handle.objects.list(ControlMapping):
        requirement_by_mapping[mapping.id] = mapping.requirement_id
        threat = threats.get(mapping.threat_id)
        if threat is not None:
            component_names_by_mapping[mapping.id] = tuple(
                names.get(component_id, component_id)
                for component_id in threat.affected_component_ids
            )
    return requirement_by_mapping, component_names_by_mapping


def fingerprinted_finding(finding: Finding, component_names: Mapping[str, str]) -> Finding:
    """The finding carrying its current DEC-066 fingerprint, rebuilt only when it moved."""
    fingerprint = finding_fingerprint(finding, component_names)
    if finding.content_fingerprint == fingerprint:
        return finding
    return Finding.model_validate({**finding.model_dump(), "content_fingerprint": fingerprint})


def fingerprinted_gap(
    gap: DocumentationGap,
    *,
    requirement_by_mapping: Mapping[str, str],
    component_names_by_mapping: Mapping[str, Sequence[str]],
) -> DocumentationGap:
    """The gap carrying its current DEC-066 fingerprint, rebuilt only when it moved."""
    fingerprint = gap_fingerprint(
        gap,
        requirement_by_mapping=requirement_by_mapping,
        component_names_by_mapping=component_names_by_mapping,
    )
    if gap.content_fingerprint == fingerprint:
        return gap
    return DocumentationGap.model_validate({**gap.model_dump(), "content_fingerprint": fingerprint})
