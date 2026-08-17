"""The Mermaid DFD export: the approved architecture as a diagram source (DEC-072, #503).

Third in the serializer family, with its constraints decided before it was built: rendered
deterministically from the approved `Component` and `DataFlow` objects — never model-drawn — a
standalone artifact in the assessment's `outputs/`, and not embedded in the MVP report (the
sixteen-section contract and `templates/report-v1.md` stay untouched). This also discharges
future-features 13.2: a visualization that reflects reviewer-approved state rather than raw
model output, because it is derived from nothing else.

**What the diagram shows is what the reviewer approved, and only that.** Components are nodes,
approved actors are external entities, approved data flows are edges labelled with their names,
and trust boundaries are subgraphs over their inside components. An object outside the approved
context leaves no trace, exactly as in TM-BOM and SARIF. Determinism is the family's rule made
visual: objects render in identifier order, so two exports of the same approved state are
byte-identical and the artifact is content-addressed like its siblings.

**Labels are escaped, not trusted.** A component name is reviewer-approved text, but Mermaid
assigns meaning to quotes and brackets; every label renders inside quoted brackets with `"`
escaped, so a name can say anything without becoming syntax.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from trace_ai.domain.actor import Actor
from trace_ai.domain.component import Component
from trace_ai.domain.data_flow import DataFlow, FlowDirection
from trace_ai.domain.enums import ObjectStatus
from trace_ai.domain.trust_boundary import TrustBoundary
from trace_ai.services.export.tm_bom import ExportError
from trace_ai.workflow.context_review import current_system_context

if TYPE_CHECKING:
    from pathlib import Path

    from trace_ai.services.assessment import AssessmentHandle

__all__ = ["export_mermaid", "write_mermaid"]


def _label(text: str) -> str:
    """A Mermaid-safe quoted label: quotes escaped so a name cannot become syntax."""
    return text.replace('"', "#quot;")


def export_mermaid(handle: AssessmentHandle) -> str:
    """Serialize the approved architecture as one Mermaid flowchart source.

    Refuses an assessment with no approved context, like every export (DEC-072).
    """
    try:
        context = current_system_context(handle)
    except ValueError as missing:
        raise ExportError(
            f"{handle.assessment_id} has no extracted context to export: {missing}"
        ) from None
    if not context.is_approved:
        raise ExportError(
            f"{handle.assessment_id} has no approved system context. Exports serialize approved "
            f"objects only (DEC-072); run the assessment through checkpoint 1 first."
        )

    repository = handle.objects
    approved_component_ids = set(context.component_ids)
    components = sorted(
        (
            component
            for component in repository.list(Component)
            if component.id in approved_component_ids and component.status is ObjectStatus.APPROVED
        ),
        key=lambda component: component.id,
    )
    component_ids = {component.id for component in components}
    actors = sorted(
        (actor for actor in repository.list(Actor) if actor.id in set(context.actor_ids)),
        key=lambda actor: actor.id,
    )
    flows = sorted(
        (
            flow
            for flow in repository.list(DataFlow)
            if flow.id in set(context.data_flow_ids)
            and flow.status is ObjectStatus.APPROVED
            and flow.source_component_id in component_ids
            and flow.destination_component_id in component_ids
        ),
        key=lambda flow: flow.id,
    )
    boundaries = sorted(
        (
            boundary
            for boundary in repository.list(TrustBoundary)
            if boundary.id in set(context.trust_boundary_ids)
            and boundary.status is ObjectStatus.APPROVED
        ),
        key=lambda boundary: boundary.id,
    )

    lines = ["flowchart LR"]

    bounded: set[str] = set()
    for boundary in boundaries:
        inside = [
            component_id
            for component_id in sorted(boundary.inside_component_ids)
            if component_id in component_ids
        ]
        if not inside:
            continue
        lines.append(f'    subgraph {boundary.id}["{_label(boundary.name)}"]')
        for component_id in inside:
            component = next(c for c in components if c.id == component_id)
            lines.append(f'        {component.id}["{_label(component.name)}"]')
            bounded.add(component_id)
        lines.append("    end")

    for component in components:
        if component.id not in bounded:
            lines.append(f'    {component.id}["{_label(component.name)}"]')

    for actor in actors:
        lines.append(f'    {actor.id}(["{_label(actor.name)}"])')

    for flow in flows:
        # `unknown` renders undirected and dotted: a directed arrow would draw a claim nobody
        # made, which is DEC-036's rule ("where absence would read as a negative answer, say
        # unknown explicitly") applied to an edge.
        if flow.direction is FlowDirection.BIDIRECTIONAL:
            arrow = "<-->"
        elif flow.direction is FlowDirection.UNKNOWN:
            arrow = "-.-"
        else:
            arrow = "-->"
        lines.append(
            f'    {flow.source_component_id} {arrow}|"{_label(flow.name)}"| '
            f"{flow.destination_component_id}"
        )

    return "\n".join(lines) + "\n"


def write_mermaid(handle: AssessmentHandle) -> Path:
    """Serialize and write the export to the assessment's outputs area, content-addressed."""
    from trace_ai.domain.hashing import content_hash

    source = export_mermaid(handle)
    digest = content_hash(source.encode("utf-8")).removeprefix("sha256:")[:12]
    return handle.artifacts.store_output(f"architecture-{digest}.mmd", source.encode("utf-8"))
