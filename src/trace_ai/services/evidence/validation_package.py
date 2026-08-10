"""What the Evidence Validation agent sees: the conclusions under test and the passages behind them.

`agent-design.md` section 23 names four things for this agent — the specific conclusion being
tested, relevant evidence, contradictory evidence, and the evidence policy — and the emphasis is on
*specific*. This is the narrowest package in the pipeline by design, and the reason is stated in the
same section: fewer tokens, less cross-contamination, less irrelevant reasoning, less
prompt-injection exposure.

**One conclusion per assessment, and the package carries only what bears on them.** The evidence is
derived rather than caller-supplied here, unlike the threat and mapping packages: what bears on a
conclusion is exactly what that conclusion cites, plus the passages any recorded contradiction
names. There is no judgment to make, so there is no decision to concentrate in one place.

**A contradiction is an object, and it travels as one** (DEC-021). `SourceObservation` already
holds a contradiction's summary and the evidence references that disagree, and section 38's
question 8 — how should contradictory evidence be presented to agents — is answered by passing that
record rather than by inventing a shape for it. The agent names the record when it classifies
something `contradicted`, so the passages that disagree can always be recovered.

**Contradictions that bear on nothing in the package are still carried.** Section 14 makes
"contradictory evidence is ignored" a failure condition, and the only way an assessment can be
checked for having addressed a contradiction is if the contradiction was in front of it. A
contradiction filtered out because no conclusion cited its passages is one nobody can be held to.

**The evidence policy is the shared prompt block, not a payload field.** `prompts/shared/
evidence-policy-v1.md` is composed into the prompt by the registry, so this package does not carry
it: two copies would be two things to keep right, and the one that stopped being updated would be
the one the agent actually read.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from trace_ai.domain.context_claim import ContextClaim
from trace_ai.domain.control import Control
from trace_ai.domain.control_mapping import ControlMapping
from trace_ai.domain.evidence_assessment import SubjectType
from trace_ai.domain.source_observation import ObservationKind
from trace_ai.domain.threat import Threat
from trace_ai.services.context.input_package import fenced_excerpt

if TYPE_CHECKING:
    from collections.abc import Sequence

    from trace_ai.domain.base import DomainModel
    from trace_ai.domain.source_observation import SourceObservation
    from trace_ai.infrastructure.model.profiles import ModelProfile
    from trace_ai.services.evidence.index import EvidenceIndex

__all__ = [
    "EvidenceValidationInput",
    "UnknownSubjectError",
    "assemble_evidence_input",
]


class UnknownSubjectError(ValueError):
    """A conclusion was offered for testing that this package cannot describe."""

    def __init__(self, subject: object) -> None:
        super().__init__(
            f"{type(subject).__name__} is not an evidence-assessment subject. "
            f"`data-model.md` section 20 names five: {sorted(t.value for t in SubjectType)}."
        )


@dataclass(frozen=True, slots=True)
class EvidenceValidationInput:
    """The assembled package: a trusted region, a fenced untrusted region, and what is in them.

    Inert by construction, like every other agent package: strings, tuples, and mappings of
    primitives, with nothing to call.
    """

    trusted: str
    untrusted: str

    assessment_id: str
    subject_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    contradiction_ids: tuple[str, ...]
    quoted_text: dict[str, str]
    """Each cited passage's stored text, keyed by identifier.

    Carried so the node can run section 14's misquotation check without a second read of the
    store. It is not sent to the model in this form — the passages reach the model once, inside
    the fence, and this is the copy the application compares against."""

    metadata: dict[str, Any] = field(default_factory=dict)

    def referenceable_ids(self) -> frozenset[str]:
        """Every identifier an assessment may name."""
        return frozenset({*self.subject_ids, *self.evidence_ids, *self.contradiction_ids})

    def input_object_ids(self) -> tuple[str, ...]:
        """What went into the call, for `ExecutionRecord.input_object_ids` (section 27)."""
        return tuple(sorted(self.referenceable_ids()))

    def substitutions(self) -> dict[str, str]:
        """What the prompt registry substitutes into `validate-evidence-v1`."""
        return {"input.source_content": self.untrusted}


def _subject_entry(subject: DomainModel) -> dict[str, Any]:
    """One conclusion, described in the terms the agent has to judge it in.

    Deliberately narrow. The agent is asked whether the evidence supports *this assertion*, so the
    entry carries the assertion and its citations and nothing about the object's place in the
    workflow — no status, no reviewer field, no lineage. Those would be context about how far the
    conclusion has travelled, which is exactly the thing that must not raise a classification.
    """
    if isinstance(subject, ContextClaim):
        return {
            "id": subject.id,
            "subject_type": SubjectType.CONTEXT_CLAIM.value,
            "assertion": f"{subject.subject_id} {subject.predicate}: {subject.value}",
            "claim_status": subject.status.value,
            "rationale": subject.rationale,
            "evidence_ids": list(subject.evidence_ids),
        }
    if isinstance(subject, Control):
        return {
            "id": subject.id,
            "subject_type": SubjectType.CONTROL.value,
            "assertion": f"{subject.name}: {subject.description}",
            "control_type": subject.control_type.value,
            "implementation_status": subject.implementation_status.value,
            "limitations": list(subject.limitations),
            "evidence_ids": list(subject.evidence_ids),
        }
    if isinstance(subject, ControlMapping):
        return {
            "id": subject.id,
            "subject_type": SubjectType.CONTROL_MAPPING.value,
            "assertion": (
                f"{subject.requirement_id} is {subject.applicability_status.value} to "
                f"{subject.threat_id} and {subject.satisfaction_status.value}"
            ),
            "applicability_reason": subject.applicability_reason,
            "assumptions": list(subject.assumptions),
            "evidence_ids": list(subject.evidence_ids),
        }
    if isinstance(subject, Threat):
        return {
            "id": subject.id,
            "subject_type": SubjectType.THREAT.value,
            "assertion": f"{subject.title}: {subject.description}",
            "preconditions": list(subject.preconditions),
            "impact": subject.impact,
            "evidence_ids": list(subject.evidence_ids),
        }
    raise UnknownSubjectError(subject)


def _contradiction_entry(observation: SourceObservation) -> dict[str, Any]:
    """One recorded contradiction, with the passages that disagree (DEC-021, section 38 q8)."""
    return {
        "id": observation.id,
        "summary": observation.summary,
        "evidence_ids": list(observation.evidence_ids),
        "status": observation.status.value,
    }


def _trusted_region(
    *,
    assessment_id: str,
    subjects: list[dict[str, Any]],
    contradictions: list[dict[str, Any]],
    manifest: list[dict[str, Any]],
) -> str:
    """The half of the package the agent may take as instruction.

    Application objects only. Quoted source text appears once, inside the fence, and never here —
    which is why the manifest carries identifiers and locations and no excerpt.
    """
    return "\n".join(
        [
            "## Assessment",
            "",
            f"assessment_id: {assessment_id}",
            "",
            "## Conclusions under test",
            "",
            json.dumps(subjects, indent=2, sort_keys=True),
            "",
            "## Recorded contradictions",
            "",
            json.dumps(contradictions, indent=2, sort_keys=True),
            "",
            "## Evidence available",
            "",
            json.dumps(manifest, indent=2, sort_keys=True),
        ]
    )


def assemble_evidence_input(
    *,
    assessment_id: str,
    subjects: Sequence[DomainModel],
    index: EvidenceIndex,
    observations: Sequence[SourceObservation] = (),
    profile: ModelProfile,
) -> EvidenceValidationInput:
    """Build the evidence agent's input from the conclusions under test.

    Evidence is derived from the subjects and the contradictions rather than supplied: what bears
    on a conclusion is what it cites, and what a contradiction names. There is no judgment in that
    derivation, which is why it does not need concentrating in a caller the way the threat and
    mapping packages' evidence selection does.
    """
    entries = [_subject_entry(subject) for subject in subjects]

    contradictions = [
        observation
        for observation in observations
        if observation.kind is ObservationKind.CONTRADICTION
    ]
    contradiction_entries = [_contradiction_entry(observation) for observation in contradictions]

    cited: list[str] = []
    for source in (*entries, *contradiction_entries):
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

    trusted = _trusted_region(
        assessment_id=assessment_id,
        subjects=entries,
        contradictions=contradiction_entries,
        manifest=manifest,
    )

    size = len(trusted) + len(untrusted)
    return EvidenceValidationInput(
        trusted=trusted,
        untrusted=untrusted,
        assessment_id=assessment_id,
        subject_ids=tuple(entry["id"] for entry in entries),
        evidence_ids=tuple(excerpt["evidence_id"] for excerpt in excerpts),
        contradiction_ids=tuple(entry["id"] for entry in contradiction_entries),
        quoted_text={excerpt["evidence_id"]: excerpt["quoted_text"] for excerpt in excerpts},
        metadata={
            "subjects": len(entries),
            "contradictions": len(contradiction_entries),
            "evidence": len(excerpts),
            "characters": size,
            "budget_characters": profile.max_input_characters,
        },
    )
