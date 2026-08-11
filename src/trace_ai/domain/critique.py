"""`Critique`: a structured challenge to one object, with a target and a recommendation.

`data-model.md` section 24 is authoritative for the fields. `agent-design.md` section 15 opens by
saying what this is not — "the critic is not an adversarial chatbot. It is a structured
quality-control agent" — and its two hardest failure conditions are structural: critiques lacking
target objects and critiques lacking actionable recommendations. Both are enforced here rather than
in prompt wording, because section 15 makes them invalid *output* and a schema is what can refuse
output.

**Every critique names a target, and the target's type is closed** (DEC-049). Section 24 types
`subject_type` as a string and its purpose names three kinds — "a generated threat, mapping, or
finding" — while section 15's responsibilities require more targets than three. DEC-049 fixes the
set. A free string would make a critique unjoinable to what it criticises, which is section 15's
"the critic's output cannot be traced to specific issues" failure condition arriving through the
schema rather than through the model.

**`missing_high_impact_threat` is not a critique type here** (DEC-049). Section 15 lists it among
the things the critic looks for and lists "candidate missing-threat proposals" among its outputs,
and both collide with its own failure condition: a missing threat has no target object. Section
27's loop-prevention worked example is the same case from the other side — the critic may recommend
that a threat be reconsidered and may not start a threat-generation loop. The capability is
excluded rather than deferred; DEC-049 records what is lost.

**`severity_overstated` and `severity_understated` are reachable, but barely** (DEC-030, DEC-045).
Critical review runs before checkpoint 2, where the reviewer assigns a finding's severity, so
`Finding.severity` is `unassigned` everywhere the critic can see it — and a critique of a severity
nobody has assigned is a critique of a default. `DocumentationGap` is the exception: DEC-045 has
the mapping step assign a gap's severity and forbids `unassigned`, so a gap's rating is a real
judgment and criticising it is a real critique. The validator below refuses the pair against an
`unassigned` severity by name.

**A critique recommends; it never states an outcome.** There is no approval field, no resulting
status, and no way to say what happened. Section 15 prohibits directly approving findings and
DEC-005 reserves approval for the human checkpoint; `RecommendedAction` is a suggestion the
Finding Consolidation node and the reviewer act on.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Final, Self

from pydantic import Field, model_validator

from trace_ai.domain.base import DomainModel
from trace_ai.domain.enums import ConfidenceLevel, ObjectStatus, Severity
from trace_ai.domain.identifiers import (
    PREFIX_BY_TERM,
    AssessmentId,
    CritiqueId,
    EvidenceReferenceId,
    parse_id,
)

__all__ = [
    "SEVERITY_CRITIQUE_TYPES",
    "Critique",
    "CritiqueSubjectType",
    "CritiqueType",
    "RecommendedAction",
]


class CritiqueSubjectType(StrEnum):
    """What a critique may be about (DEC-049).

    Six values, and the reason there are six rather than section 24's three is section 15: a
    critique about an ignored inherited control targets the control or the mapping that ignored
    it, and one about a mislabelled documentation gap targets the gap. `finding` is here because
    section 24's purpose names it; nothing produces one until M4.
    """

    THREAT = "threat"
    CONTROL = "control"
    CONTROL_MAPPING = "control_mapping"
    EVIDENCE_ASSESSMENT = "evidence_assessment"
    DOCUMENTATION_GAP = "documentation_gap"
    FINDING = "finding"


class CritiqueType(StrEnum):
    """What kind of challenge this is (section 24's examples, closed by DEC-049).

    Eleven of section 24's twelve. `missing_high_impact_threat` is absent; see the module
    docstring and DEC-049.
    """

    UNSUPPORTED_CLAIM = "unsupported_claim"
    MISSING_EVIDENCE = "missing_evidence"
    IGNORED_INHERITED_CONTROL = "ignored_inherited_control"
    """The DEC-026 backstop: a platform control the documentation establishes, not credited."""

    DUPLICATE = "duplicate"
    SEVERITY_OVERSTATED = "severity_overstated"
    SEVERITY_UNDERSTATED = "severity_understated"
    MISSING_PRECONDITION = "missing_precondition"
    WEAK_ATTACK_PATH = "weak_attack_path"
    GENERIC_RECOMMENDATION = "generic_recommendation"
    DOCUMENTATION_GAP_ONLY = "documentation_gap_only"
    """The DEC-009 backstop: a weakness asserted where the documentation is merely silent."""

    CONTRADICTORY_ANALYSIS = "contradictory_analysis"


class RecommendedAction(StrEnum):
    """What the critic suggests be done (section 24's five, named in its field description).

    Closed, and every value is a recommendation rather than an outcome. Nothing here says what
    happened; Finding Consolidation and the reviewer decide that.
    """

    KEEP = "keep"
    REVISE = "revise"
    REJECT = "reject"
    MERGE = "merge"
    INVESTIGATE = "investigate"


# The two types that criticise a severity. Both need one to exist first (DEC-030, DEC-045).
SEVERITY_CRITIQUE_TYPES: Final[frozenset[CritiqueType]] = frozenset(
    {CritiqueType.SEVERITY_OVERSTATED, CritiqueType.SEVERITY_UNDERSTATED}
)


class Critique(DomainModel):
    """A structured challenge to one generated object (section 24)."""

    id: CritiqueId
    assessment_id: AssessmentId

    subject_type: CritiqueSubjectType
    subject_id: str
    """The object challenged. Its prefix must match `subject_type`; whether it exists is checked
    where the assessment's objects are known, not here."""

    critique_type: CritiqueType

    description: str = Field(min_length=1)
    """The criticism. Required and non-empty: section 15 makes a critique that cannot be traced to
    a specific issue invalid output, and an empty description is that with a target attached."""

    rationale: str = Field(min_length=1)
    """Why the criticism holds. Required: without it a critique is an assertion the reviewer has
    to take on trust, which is what the critic exists to stop other agents doing."""

    evidence_ids: list[EvidenceReferenceId] = Field(default_factory=list)

    recommended_action: RecommendedAction
    """What to do about it. Required, and a recommendation rather than an outcome."""

    confidence: ConfidenceLevel
    status: ObjectStatus
    generated_by: str = Field(min_length=1)

    @model_validator(mode="after")
    def _subject_id_matches_subject_type(self) -> Self:
        """`subject_id` names an object of the type `subject_type` declares.

        Prefix-checked, which is what makes the closed enum worth having: a critique stored against
        the wrong kind of object is untraceable in exactly the way section 15's last failure
        condition describes.
        """
        parsed = parse_id(self.subject_id)
        expected = PREFIX_BY_TERM.get(self.subject_type.value)
        if expected is not None and parsed.prefix != expected:
            raise ValueError(
                f"subject_type is {self.subject_type.value!r}, whose identifiers begin "
                f"{expected!r}, but subject_id {self.subject_id!r} names a {parsed.object_type}."
            )
        return self

    def check_severity_is_assigned(self, severity: Severity | None) -> None:
        """Refuse a severity critique against a severity nobody assigned (DEC-030).

        A method rather than a validator because the subject's severity is not on this object: the
        critique names an identifier, and only a caller holding the assessment's objects can look
        the value up. Called by the critique validation node.

        `severity_overstated` against `unassigned` is a critique of a default. DEC-030 has the
        reviewer assign a finding's severity at checkpoint 2, which runs *after* critical review,
        so on a `Finding` the answer is always `unassigned` in this phase. `DocumentationGap` is
        where the pair is genuinely reachable: DEC-045 has the mapping step assign a gap's rating
        and forbids `unassigned`, so there is a judgment to disagree with.
        """
        if self.critique_type not in SEVERITY_CRITIQUE_TYPES:
            return
        if severity is None:
            raise ValueError(
                f"critique_type {self.critique_type.value!r} against {self.subject_id!r}, which "
                f"carries no severity. Only a finding and a documentation gap have one."
            )
        if severity is Severity.UNASSIGNED:
            raise ValueError(
                f"critique_type {self.critique_type.value!r} against {self.subject_id!r}, whose "
                f"severity is 'unassigned'. The reviewer assigns a finding's severity at "
                f"checkpoint 2, which runs after critical review (DEC-030), so there is no "
                f"judgment here to overstate or understate."
            )
