"""The shared enumerated types every domain object refers to by name.

`docs/architecture/data-model.md` section 4 defines these seven, and it is authoritative for
their members. Each is a `StrEnum` whose values are the exact lowercase strings the document
uses, so a serialized object round-trips into the corpus vocabulary rather than into a private
one: a persisted `status: approved` reads the same in the database, in a report, and in the
document that specifies it.

`tests/unit/test_domain_enums.py` parses section 4 and fails if a member is added or removed
there without the same change here. The document leads; this module follows.
"""

from __future__ import annotations

from enum import StrEnum

__all__ = [
    "ConfidenceLevel",
    "EvidenceStrength",
    "ObjectStatus",
    "ReviewDisposition",
    "Severity",
    "SourceOrigin",
    "ValidationStatus",
]


class ObjectStatus(StrEnum):
    """An object's lifecycle state (section 4.1).

    Not every object needs every status; the vocabulary is shared, not universally applicable.
    """

    DRAFT = "draft"
    CANDIDATE = "candidate"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"
    ARCHIVED = "archived"


class ConfidenceLevel(StrEnum):
    """Model confidence, categorically (section 4.2).

    Three values and no numeric score, per DEC-022. A decimal alongside a three-value enum
    invites reading confidence as probability, and conflates model confidence with evidence
    strength -- which is `EvidenceStrength`, and lives elsewhere for a reason.
    """

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class EvidenceStrength(StrEnum):
    """How strongly a piece of evidence supports one claim (section 4.3).

    Relational, not intrinsic (DEC-022): the same passage can be direct evidence for one claim
    and merely contextual for another, which is why this is carried by
    `EvidenceAssessment.evidence_strengths` and never by the `EvidenceReference` itself.
    """

    DIRECT = "direct"
    INDIRECT = "indirect"
    CONTEXTUAL = "contextual"
    CONTRADICTORY = "contradictory"


class SourceOrigin(StrEnum):
    """Where a piece of information came from (section 4.4).

    The distinction that matters downstream is between origins that are material under review
    and origins that are not. `uploaded_document` and `structured_input` are untrusted data;
    `requirements_catalog` and `reviewer_edit` are not.
    """

    UPLOADED_DOCUMENT = "uploaded_document"
    STRUCTURED_INPUT = "structured_input"
    USER_RESPONSE = "user_response"
    REQUIREMENTS_CATALOG = "requirements_catalog"
    SYSTEM_GENERATED = "system_generated"
    REVIEWER_EDIT = "reviewer_edit"
    EXTERNAL_TOOL = "external_tool"


class Severity(StrEnum):
    """Finding severity (section 4.5).

    `UNASSIGNED` is the value a finding is created with, and no pipeline node changes it: the
    reviewer assigns severity at the finding checkpoint (DEC-030), because it is a risk judgment
    in business context rather than an evidence judgment, and the source documents do not carry
    the context. It is also the one required `Finding` field the material under review cannot
    answer, which is why an approval carrying `UNASSIGNED` is rejected.
    """

    INFORMATIONAL = "informational"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    UNASSIGNED = "unassigned"


class RiskTreatment(StrEnum):
    """The reviewer's chosen response to a finding's risk (section 4.8, DEC-060).

    A closed vocabulary in the DEC-036 sense — the values are named, not illustrated, like
    `DataFlow.direction` — so extending it is a design change. Findings are created `UNDECIDED`,
    and unlike severity `UNDECIDED` may survive approval: treatment is often the system owner's
    call to make after reading the report, and a gate would manufacture a business decision nobody
    took (DEC-060). The one gate is that `ACCEPT` without a `treatment_rationale` is refused, the
    residual-risk statement being the thing an accepted risk cannot be recorded without.

    The values name the *chosen response*, present-tense, not work already done: there is no
    `eliminated`, because a weakness that no longer exists produces no finding.
    """

    UNDECIDED = "undecided"
    MITIGATE = "mitigate"
    ACCEPT = "accept"
    TRANSFER = "transfer"
    AVOID = "avoid"


class ReviewDisposition(StrEnum):
    """What the system records a reviewer as having done (section 4.6).

    There is deliberately no `change_severity`. A severity change is an `EDIT` carrying
    `prior_value` and `updated_value` on `ReviewerDecision` (DEC-023). `current-architecture.md`
    section 5.12 lists changing severity among the reviewer's actions; that list names actions a
    reviewer takes and this one names dispositions the system records, and the two do not
    correspond one to one (DEC-030).

    `CONVERT_TO_QUESTION` and `CONVERT_TO_DOCUMENTATION_GAP` are the DEC-009 escape hatches: a
    proposed finding that rests on silence rather than evidence becomes one of these instead of
    being approved or discarded.
    """

    APPROVE = "approve"
    REJECT = "reject"
    EDIT = "edit"
    DEFER = "defer"
    REQUEST_MORE_ANALYSIS = "request_more_analysis"
    CONVERT_TO_QUESTION = "convert_to_question"
    CONVERT_TO_DOCUMENTATION_GAP = "convert_to_documentation_gap"


class ValidationStatus(StrEnum):
    """Whether evidence supports a claim, control, or finding (section 4.7).

    `UNSUPPORTED` and `CONTRADICTED` are not the same statement, and neither means the thing is
    absent. Evidence that says nothing is `UNSUPPORTED`; evidence that says the opposite is
    `CONTRADICTED`; material never examined is `NOT_EVALUATED`. Collapsing the three is how
    missing documentation turns into an asserted weakness, which DEC-009 exists to prevent.
    """

    SUPPORTED = "supported"
    PARTIALLY_SUPPORTED = "partially_supported"
    UNSUPPORTED = "unsupported"
    CONTRADICTED = "contradicted"
    REQUIRES_CONFIRMATION = "requires_confirmation"
    NOT_EVALUATED = "not_evaluated"
