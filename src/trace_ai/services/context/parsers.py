"""The DEC-070 parser family's one seeding entry point (#504).

Each parser converts what one artifact kind declares; this module is where the family meets the
driver. One call seeds every registered machine-readable artifact — compose manifests, then OpenAPI
specifications, then Terraform declarations, then org-controls assertions (#528), matching DEC-070's order — and the idempotence marker is checked
once for the family: components carry no `generated_by`, so `source_origin ==
structured_input` says *some* parser already seeded, and a re-extraction run (DEC-038) reuses
what the first run produced instead of minting duplicates. Per-parser idempotence would need a
marker no object carries; family idempotence is what the marker can honestly say.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from trace_ai.domain.enums import SourceOrigin
from trace_ai.services.context.compose import looks_like_compose, seed_compose_context
from trace_ai.services.context.iac import looks_like_terraform, seed_terraform_context
from trace_ai.services.context.openapi import looks_like_openapi, seed_openapi_context
from trace_ai.services.context.org_controls import (
    looks_like_org_controls,
    seed_org_controls_context,
)

if TYPE_CHECKING:
    from trace_ai.domain.proposals.conversion import ConvertedContext
    from trace_ai.services.assessment import AssessmentHandle

__all__ = ["seed_structured_documents"]


def seed_structured_documents(handle: AssessmentHandle) -> ConvertedContext | None:
    """Seed every registered machine-readable artifact, once per assessment.

    Returns what was (or already had been) seeded, or `None` when nothing machine-readable is
    registered. Documents seed in identifier order within each parser, parsers in DEC-070's
    order, so the allocation is deterministic and two runs over the same sources agree.
    """
    from trace_ai.domain.component import Component
    from trace_ai.domain.context_claim import ContextClaim
    from trace_ai.domain.data_flow import DataFlow
    from trace_ai.domain.proposals.conversion import ConvertedContext
    from trace_ai.domain.source_document import SourceDocument

    already = [
        component
        for component in handle.objects.list(Component)
        if component.source_origin is SourceOrigin.STRUCTURED_INPUT
    ]
    if already:
        flows = [
            flow
            for flow in handle.objects.list(DataFlow)
            if flow.source_origin is SourceOrigin.STRUCTURED_INPUT
        ]
        claims = [
            claim
            for claim in handle.objects.list(ContextClaim)
            if claim.source_origin is SourceOrigin.STRUCTURED_INPUT
        ]
        return ConvertedContext(
            components=tuple(already), data_flows=tuple(flows), claims=tuple(claims)
        )

    documents = handle.objects.list(SourceDocument)
    seeded: list[ConvertedContext] = []
    for document in sorted((d for d in documents if looks_like_compose(d)), key=lambda d: d.id):
        seeded.append(seed_compose_context(handle, document))
    for document in sorted((d for d in documents if looks_like_openapi(d)), key=lambda d: d.id):
        seeded.append(seed_openapi_context(handle, document))
    for document in sorted((d for d in documents if looks_like_terraform(d)), key=lambda d: d.id):
        seeded.append(seed_terraform_context(handle, document))
    for document in sorted(
        (d for d in documents if looks_like_org_controls(d)), key=lambda d: d.id
    ):
        seeded.append(seed_org_controls_context(handle, document))
    if not seeded:
        return None

    def _merged(field: str) -> tuple[Any, ...]:
        return tuple(obj for part in seeded for obj in getattr(part, field))

    return ConvertedContext(
        components=_merged("components"),
        data_flows=_merged("data_flows"),
        claims=_merged("claims"),
    )
