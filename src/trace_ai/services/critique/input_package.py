"""What the Critical Review agent sees: one threat's lineage, and nothing wider.

`agent-design.md` section 23 gives this agent "a bounded group of related objects, relevant
evidence, validation results", and DEC-049 fixes the bound: one threat, the `ControlMapping`
objects citing it, the `Control` objects those reference, the `EvidenceAssessment` objects over any
of them, and the `DocumentationGap` objects raised alongside. That is `data-model.md` section 32's
lineage chain, assembled.

**The bound is what makes the critic a critic rather than a second assessment.** Section 15's last
prohibition is that the agent must not "act as an unrestricted second full assessment", and that is
a statement about scope, not about volume — an agent shown everything will re-derive everything.
Shown one chain, the only thing it can do is compare the objects in it, which is what its twelve
concerns actually ask for.

**The group carries the analysis, not just the objects.** A mapping's `applicability_reason`, an
assessment's `rationale`, a control's `is_documented_inheritance` — the critic is checking
reasoning, so the reasoning has to be in front of it. This is the one package that deliberately
carries other agents' prose.

**Suppressions and downgrades travel too** (DEC-025, DEC-046). They are the record of conclusions
that were *not* drawn, and a critic looking for `documentation_gap_only` — a weakness asserted
where the documentation is silent — needs to see that the mapping already considered and declined
that reading. Without them the critic re-raises what the pipeline already handled, which is
section 15's superficial-criticism failure condition with a specific cause.

**Precedent is context, never subject** (DEC-064). Rationale-bearing dismissals matched to this
lineage render as a distinct, labelled block inside the trusted region — the rationale is the
reviewer's own words, not source content, so the untrusted fence discipline is unchanged. The
precedents' identifiers are deliberately absent from `referenceable_ids`: a critique may cite a
precedent's rationale in its explanation, and a critique targeting a precedent fails reference
validation, which is how "context, never subject" is enforced rather than requested.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from trace_ai.services.context.input_package import fenced_excerpt

if TYPE_CHECKING:
    from collections.abc import Sequence

    from trace_ai.domain.control import Control
    from trace_ai.domain.control_mapping import ControlMapping
    from trace_ai.domain.documentation_gap import DocumentationGap
    from trace_ai.domain.evidence_assessment import EvidenceAssessment
    from trace_ai.domain.threat import Threat
    from trace_ai.infrastructure.model.profiles import ModelProfile
    from trace_ai.services.critique.precedent import DismissalPrecedent, PrecedentSelection
    from trace_ai.services.evidence.index import EvidenceIndex

__all__ = ["PRECEDENT_HEADING", "ReviewGroup", "assemble_review_group", "select_review_group"]

PRECEDENT_HEADING = "Reviewer precedent (context, not subjects)"
"""The marked block's heading (DEC-064). A test greps for it, so it lives as a constant."""


@dataclass(frozen=True, slots=True)
class ReviewGroup:
    """One threat's lineage, assembled: a trusted region, a fenced region, and what is in them."""

    trusted: str
    untrusted: str

    assessment_id: str
    threat_id: str
    mapping_ids: tuple[str, ...]
    control_ids: tuple[str, ...]
    assessment_ids: tuple[str, ...]
    documentation_gap_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def reviewed_object_count(self) -> int:
        """How many objects the critic was shown, for the volume ratio the node checks."""
        return (
            1
            + len(self.mapping_ids)
            + len(self.control_ids)
            + len(self.assessment_ids)
            + len(self.documentation_gap_ids)
        )

    def referenceable_ids(self) -> frozenset[str]:
        """Every identifier a critique may name as its target or cite as evidence."""
        return frozenset(
            {
                self.threat_id,
                *self.mapping_ids,
                *self.control_ids,
                *self.assessment_ids,
                *self.documentation_gap_ids,
                *self.evidence_ids,
            }
        )

    def input_object_ids(self) -> tuple[str, ...]:
        """What went into the call, for `ExecutionRecord.input_object_ids` (section 27)."""
        return tuple(sorted(self.referenceable_ids()))

    def substitutions(self) -> dict[str, str]:
        """What the prompt registry substitutes into `challenge-analysis-v1`."""
        return {"input.source_content": self.untrusted}


@dataclass(frozen=True, slots=True)
class SelectedObjects:
    """The objects DEC-049's rule selects for one threat, before rendering."""

    threat: Threat
    mappings: tuple[ControlMapping, ...]
    controls: tuple[Control, ...]
    assessments: tuple[EvidenceAssessment, ...]
    documentation_gaps: tuple[DocumentationGap, ...]


def select_review_group(
    threat: Threat,
    *,
    mappings: Sequence[ControlMapping],
    controls: Sequence[Control],
    assessments: Sequence[EvidenceAssessment],
    documentation_gaps: Sequence[DocumentationGap] = (),
) -> SelectedObjects:
    """DEC-049's selection rule, as a function so a test can assert what it excludes.

    Everything is reached from the threat: mappings by `threat_id`, controls by being cited by
    those mappings, assessments by having one of the selected objects as their subject, and gaps
    by naming one of them in `related_object_ids`. An object that no path from the threat reaches
    is not in the group, and that is the whole content of "bounded".
    """
    selected_mappings = tuple(mapping for mapping in mappings if mapping.threat_id == threat.id)
    cited = {control_id for mapping in selected_mappings for control_id in mapping.control_ids}
    selected_controls = tuple(control for control in controls if control.id in cited)

    subjects = {
        threat.id,
        *(mapping.id for mapping in selected_mappings),
        *(control.id for control in selected_controls),
    }
    selected_assessments = tuple(
        assessed for assessed in assessments if assessed.subject_id in subjects
    )
    selected_gaps = tuple(
        gap for gap in documentation_gaps if subjects & set(gap.related_object_ids)
    )

    return SelectedObjects(
        threat=threat,
        mappings=selected_mappings,
        controls=selected_controls,
        assessments=selected_assessments,
        documentation_gaps=selected_gaps,
    )


def _threat_entry(threat: Threat) -> dict[str, Any]:
    return {
        "id": threat.id,
        "title": threat.title,
        "description": threat.description,
        "category": list(threat.category),
        "affected_component_ids": list(threat.affected_component_ids),
        "affected_asset_ids": list(threat.affected_asset_ids),
        "preconditions": list(threat.preconditions),
        "attack_path": list(threat.attack_path),
        "impact": threat.impact,
        "confidence": threat.confidence.value,
        "evidence_ids": list(threat.evidence_ids),
    }


def _mapping_entry(mapping: ControlMapping) -> dict[str, Any]:
    """One mapping, with the reasoning attached. The critic is checking the reasoning."""
    return {
        "id": mapping.id,
        "requirement_id": mapping.requirement_id,
        "control_ids": list(mapping.control_ids),
        "applicability_status": mapping.applicability_status.value,
        "applicability_reason": mapping.applicability_reason,
        "satisfaction_status": mapping.satisfaction_status.value,
        "assumptions": list(mapping.assumptions),
        "confidence": mapping.confidence.value,
        "evidence_ids": list(mapping.evidence_ids),
        # DEC-025 and DEC-046: conclusions already declined. A critic that could not see these
        # would re-raise what the pipeline handled, which is superficial criticism with a cause.
        "suppressed_conclusion": mapping.suppressed_conclusion,
        "suppressed_by": mapping.suppressed_by,
        "downgraded_from": (
            mapping.downgraded_from.value if mapping.downgraded_from is not None else None
        ),
        "downgrade_reason": mapping.downgrade_reason,
    }


def _control_entry(control: Control) -> dict[str, Any]:
    return {
        "id": control.id,
        "name": control.name,
        "description": control.description,
        "control_type": control.control_type.value,
        "implementation_status": control.implementation_status.value,
        "validation_status": control.validation_status.value,
        "provider_component_id": control.provider_component_id,
        "protected_component_ids": list(control.protected_component_ids),
        "protected_asset_ids": list(control.protected_asset_ids),
        "limitations": list(control.limitations),
        # DEC-026's distinction, carried rather than reconstructed. `ignored_inherited_control`
        # is one of the critic's two most important types and it turns on exactly this value.
        "is_documented_inheritance": control.is_documented_inheritance,
        "evidence_ids": list(control.evidence_ids),
    }


def _assessment_entry(assessed: EvidenceAssessment) -> dict[str, Any]:
    return {
        "id": assessed.id,
        "subject_type": assessed.subject_type.value,
        "subject_id": assessed.subject_id,
        "validation_status": assessed.validation_status.value,
        "rationale": assessed.rationale,
        "evidence_strengths": {
            key: value.value for key, value in assessed.evidence_strengths.items()
        },
        "missing_evidence": list(assessed.missing_evidence),
        "contradictions": list(assessed.contradictions),
        "confidence": assessed.confidence.value,
        "recommendation": assessed.recommendation.value,
        "evidence_ids": list(assessed.evidence_ids),
    }


def _precedent_entry(precedent: DismissalPrecedent) -> dict[str, Any]:
    """One dismissal, with what matched stated rather than asserted (DEC-064).

    The rationale is the reviewer's recorded reason — the one text in the pipeline written by the
    human whose judgment the critic is meant to anticipate. The block asks whether that reason
    applies here; it never carries the verdict as an instruction.
    """
    return {
        "dismissed_finding_id": precedent.finding_id,
        "dismissed_finding_title": precedent.finding_title,
        "decision_id": precedent.decision_id,
        "disposition": precedent.disposition,
        "reviewer_rationale": precedent.rationale,
        "shared_requirement_ids": list(precedent.shared_requirement_ids),
        "matched_component_names": list(precedent.matched_component_names),
    }


def _gap_entry(gap: DocumentationGap) -> dict[str, Any]:
    return {
        "id": gap.id,
        "title": gap.title,
        "description": gap.description,
        "importance": gap.importance,
        "severity": gap.severity.value,
        "related_object_ids": list(gap.related_object_ids),
        "requested_evidence": list(gap.requested_evidence),
        "evidence_ids": list(gap.evidence_ids),
    }


def _trusted_region(*, assessment_id: str, sections: dict[str, Any]) -> str:
    """The half of the package the agent may take as instruction. Application objects only."""
    lines = ["## Assessment", "", f"assessment_id: {assessment_id}"]
    for heading, payload in sections.items():
        lines += ["", f"## {heading}", "", json.dumps(payload, indent=2, sort_keys=True)]
    return "\n".join(lines)


def assemble_review_group(
    *,
    assessment_id: str,
    selected: SelectedObjects,
    index: EvidenceIndex,
    profile: ModelProfile,
    precedents: PrecedentSelection | None = None,
) -> ReviewGroup:
    """Render one selected group into the package the critic receives.

    Evidence is derived from the selected objects rather than supplied: what bears on a review
    group is what the objects in it cite, and there is no judgment in that.

    `precedents` is DEC-064's block, rendered only when the selection is non-empty so a first
    run's package is unchanged. Precedent evidence is never added to the fence and precedent
    identifiers never join `referenceable_ids` — context, not subjects.
    """
    threat = _threat_entry(selected.threat)
    mappings = [_mapping_entry(mapping) for mapping in selected.mappings]
    controls = [_control_entry(control) for control in selected.controls]
    assessments = [_assessment_entry(assessed) for assessed in selected.assessments]
    gaps = [_gap_entry(gap) for gap in selected.documentation_gaps]

    cited: list[str] = []
    for source in (threat, *mappings, *controls, *assessments, *gaps):
        for evidence_id in source["evidence_ids"]:
            if evidence_id not in cited:
                cited.append(evidence_id)

    excerpts = index.render_for_prompt(cited)
    untrusted = "\n\n".join(fenced_excerpt(excerpt) for excerpt in excerpts)

    manifest = [
        {
            "evidence_id": excerpt["evidence_id"],
            "document": excerpt.get("source_filename"),
            "location": {
                key: value
                for key, value in (excerpt.get("location") or {}).items()
                if value is not None
            },
        }
        for excerpt in excerpts
    ]

    sections: dict[str, Any] = {
        "Threat under review": threat,
        "Requirement and control mappings": mappings,
        "Controls": controls,
        "Evidence assessments": assessments,
        "Documentation gaps": gaps,
        "Evidence available": manifest,
    }
    if precedents is not None and precedents:
        block: dict[str, Any] = {
            "note": (
                "Prior findings in this assessment a reviewer dismissed with a stated reason, "
                "matched to this lineage. Context only: test whether each rationale applies "
                "here; do not inherit the verdict, and do not target these identifiers."
            ),
            "dismissals": [_precedent_entry(precedent) for precedent in precedents.precedents],
        }
        if precedents.excluded_finding_ids:
            # DEC-080: the cap names what it excluded rather than truncating silently, the
            # same rule the evidence fence follows on a budget overrun.
            block["excluded_by_cap"] = list(precedents.excluded_finding_ids)
        sections[PRECEDENT_HEADING] = block

    trusted = _trusted_region(assessment_id=assessment_id, sections=sections)

    return ReviewGroup(
        trusted=trusted,
        untrusted=untrusted,
        assessment_id=assessment_id,
        threat_id=selected.threat.id,
        mapping_ids=tuple(entry["id"] for entry in mappings),
        control_ids=tuple(entry["id"] for entry in controls),
        assessment_ids=tuple(entry["id"] for entry in assessments),
        documentation_gap_ids=tuple(entry["id"] for entry in gaps),
        evidence_ids=tuple(excerpt["evidence_id"] for excerpt in excerpts),
        metadata={
            "mappings": len(mappings),
            "controls": len(controls),
            "evidence_assessments": len(assessments),
            "documentation_gaps": len(gaps),
            "evidence": len(excerpts),
            "precedents": 0 if precedents is None else len(precedents.precedents),
            "precedents_excluded_by_cap": (
                0 if precedents is None else len(precedents.excluded_finding_ids)
            ),
            "characters": len(trusted) + len(untrusted),
            "budget_characters": profile.max_input_characters,
        },
    )
