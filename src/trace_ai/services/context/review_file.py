"""The review file: a checkpoint a person can edit in an editor and hand back.

`docs/product/roadmap.md` Stage 2 permits the first review experience to be command line based *or*
to use simple structured files, and for the context checkpoint the answer is both. A reviewer with
forty claims to work through is not going to pass forty flags, and an evaluation harness replaying
a recorded review needs a file rather than an argument vector.

**The file is derived, exactly like the review package** (`data-model.md` section 31). It is written
on export and read on apply; nothing stores it, and nothing reads it back to reconstruct state. A
file that were authoritative would be a second copy of objects that already exist.

**Applying a file produces the same `ReviewerDecision` rows as the equivalent flags**, because both
call the same functions in `workflow/context_review.py`. That is the property worth having: the
file is a way of *saying* what to do, not a second implementation of doing it.

**An unchanged file applies nothing.** Every action is expressed as a difference from what was
exported — a `decision:` a reviewer filled in, an `answer:` they typed, a field they altered — so
exporting and reapplying without editing writes no rows. A format where the exported state was
itself an instruction would record a decision for every object each time somebody looked.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import yaml
from pydantic import BaseModel, ConfigDict, Field
from pydantic import ValidationError as PydanticValidationError

from trace_ai.domain.context_claim import ClaimStatus, ContextClaim
from trace_ai.domain.enums import ReviewDisposition
from trace_ai.domain.question import Question
from trace_ai.domain.source_observation import SourceObservation
from trace_ai.services.evidence.index import EvidenceIndex
from trace_ai.workflow.context_review import (
    CONTEXT_OBJECT_TYPES,
    ReviewerActionError,
    add_context_object,
    answer_question,
    apply_edit,
    attach_evidence,
    confirm_assumption,
    decide_object,
    resolve_contradiction,
)

if TYPE_CHECKING:
    from trace_ai.domain.reviewer_decision import ReviewerDecision
    from trace_ai.services.assessment import AssessmentHandle
    from trace_ai.workflow.context_review import ContextReviewPackage

__all__ = [
    "EDITABLE_FIELDS",
    "AppliedReviewFile",
    "ReviewFileError",
    "apply_review_file",
    "export_review_file",
    "read_review_file",
    "write_review_file",
]

# What a reviewer may change by editing the file. Deliberately narrow: these are the fields a
# person reads an architecture document to correct. Identifiers, statuses, and timestamps are not
# here — each has a rule the file cannot express. Evidence links have their own slot
# (`attach_evidence:`), because linking is an action with its own resolution rule, not an edit.
EDITABLE_FIELDS: dict[str, tuple[str, ...]] = {
    "components": (
        "name",
        "description",
        "component_type",
        "technology",
        "ownership",
        "deployment_zone",
        "internet_accessible",
        "externally_managed",
        "data_classifications",
        "authentication_mechanisms",
        "authorization_mechanisms",
    ),
    "actors": ("name", "actor_type", "trust_level", "capabilities", "authentication_method"),
    "assets": (
        "name",
        "asset_type",
        "description",
        "confidentiality_impact",
        "integrity_impact",
        "availability_impact",
        "data_classification",
        "owner",
    ),
    "data_flows": (
        "name",
        "direction",
        "protocol",
        "data_types",
        "authentication",
        "encryption_in_transit",
        "internet_exposed",
        "source_component_id",
        "destination_component_id",
    ),
    "trust_boundaries": ("name", "boundary_type", "description", "controls"),
    "claims": ("predicate", "value", "rationale"),
}

# The dispositions a reviewer may write into the `decision:` slot. `edit` is absent because an edit
# is expressed by changing a field, not by naming one.
_DISPOSITIONS = {ReviewDisposition.APPROVE.value, ReviewDisposition.REJECT.value}

_HEADER = """\
# ForgeFlow context review
#
# Fill in `decision:` with `approve` or `reject`, edit any field listed under `editable:`, answer a
# question by writing under `answer:`, and set `confirm: true` on a claim you can vouch for. Leave
# anything you have no view on exactly as it is: an unchanged entry applies nothing.
#
# List evidence identifiers under an entry's `attach_evidence:` to link existing references to it.
# Settle a contradiction by filling both `resolution:` and `rationale:` under `contradictions:`.
# Add an object the extractor missed under `additions:`, as
#   - type: components            # or actors, assets, data_flows, trust_boundaries
#     fields: {name: ..., ...}    # the object's own fields; the identifier is allocated for you
#
# Identifiers, statuses, and timestamps are the application's and are shown for reference.
# Changing one here has no effect.
"""


class ReviewFileError(ValueError):
    """A review file the application will not apply, with the reason named."""


@dataclass(frozen=True, slots=True)
class AppliedReviewFile:
    """The result of applying a file: the decisions it produced, and the additions it skipped.

    Skipped additions are returned rather than swallowed. An addition whose name already exists is
    the idempotent re-apply case *and* the reviewer-namesake case, indistinguishable by name, so it
    is not an error -- but a reviewer who typed a new component that silently vanished should be able
    to see that it did.
    """

    decisions: list[ReviewerDecision] = field(default_factory=list)
    skipped_additions: list[str] = field(default_factory=list)


class _Entry(BaseModel):
    """A review-file entry that forbids unknown keys, so a misspelled field is caught rather than
    silently ignored -- the same `extra="forbid"` guarantee every domain object has."""

    model_config = ConfigDict(extra="forbid")


class _ObjectEntry(_Entry):
    id: str
    decision: str | None = None
    attach_evidence: list[str] = Field(default_factory=list)
    editable: dict[str, Any] = Field(default_factory=dict)


class _ClaimEntry(_Entry):
    id: str
    status: str | None = None
    confidence: str | None = None
    decision: str | None = None
    confirm: bool = False
    attach_evidence: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    editable: dict[str, Any] = Field(default_factory=dict)


class _ContradictionEntry(_Entry):
    id: str
    summary: str | None = None
    claims: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    resolution: str | None = None
    rationale: str | None = None


class _AdditionEntry(_Entry):
    type: str | None = None
    fields: dict[str, Any] = Field(default_factory=dict)


class _QuestionEntry(_Entry):
    id: str
    question: str | None = None
    priority: str | None = None
    blocking: bool | None = None
    answer: str | None = None


class _ReviewFileDocument(BaseModel):
    """The whole file, keyed exactly as `export_review_file` writes it.

    `extra="forbid"` at every level is the fix: a reviewer who writes `question:` for `questions:`,
    or `decison:` for `decision:` inside an entry, gets a named error rather than losing their work
    silently at a structural checkpoint. The read-only display fields (status, summary, priority)
    are listed because the exported file carries them; they are ignored on apply.
    """

    model_config = ConfigDict(extra="forbid")

    assessment_id: str
    system_context_version: int | None = None
    reviewer: str | None = None
    components: list[_ObjectEntry] = Field(default_factory=list)
    actors: list[_ObjectEntry] = Field(default_factory=list)
    assets: list[_ObjectEntry] = Field(default_factory=list)
    data_flows: list[_ObjectEntry] = Field(default_factory=list)
    trust_boundaries: list[_ObjectEntry] = Field(default_factory=list)
    claims: list[_ClaimEntry] = Field(default_factory=list)
    contradictions: list[_ContradictionEntry] = Field(default_factory=list)
    additions: list[_AdditionEntry] = Field(default_factory=list)
    questions: list[_QuestionEntry] = Field(default_factory=list)


def export_review_file(package: ContextReviewPackage) -> dict[str, Any]:
    """The editable document for one review package."""
    document: dict[str, Any] = {
        "assessment_id": package.system_context.assessment_id,
        "system_context_version": package.system_context.version,
        "reviewer": None,
    }

    for group, _ in CONTEXT_OBJECT_TYPES:
        objects: list[Any] = list(package.objects_by_type[group])
        document[group] = [
            {
                "id": obj.id,
                "decision": None,
                "attach_evidence": [],
                "editable": {
                    field: obj.model_dump(mode="json")[field]
                    for field in EDITABLE_FIELDS[group]
                    if field in type(obj).model_fields
                },
            }
            for obj in objects
        ]

    document["claims"] = [
        {
            "id": presented.claim.id,
            "status": presented.claim.status.value,
            "confidence": presented.claim.confidence.value,
            "decision": None,
            "confirm": False,
            "attach_evidence": [],
            "evidence": [excerpt.evidence_id for excerpt in presented.excerpts],
            # A contradicted claim's value and rationale are settled through `contradictions:`,
            # not edited here — an edit would choose a side without recording why, and a stale
            # snapshot re-applied after the resolution would quietly revert it.
            "editable": {
                field: presented.claim.model_dump(mode="json")[field]
                for field in EDITABLE_FIELDS["claims"]
                if not (
                    presented.claim.status is ClaimStatus.CONTRADICTED
                    and field in ("value", "rationale")
                )
            },
        }
        for presented in package.claims
    ]

    document["contradictions"] = [
        {
            "id": observation.id,
            "summary": observation.summary,
            "claims": list(observation.subject_claim_ids),
            "evidence": list(observation.evidence_ids),
            "resolution": None,
            "rationale": None,
        }
        for observation in package.contradictions
    ]

    document["additions"] = []

    document["questions"] = [
        {
            "id": question.id,
            "question": question.question,
            "priority": question.priority.value,
            "blocking": question.blocking,
            "answer": None,
        }
        for question in package.questions
    ]

    return document


def write_review_file(package: ContextReviewPackage) -> str:
    """The exported document as YAML, with the instructions a reviewer needs at the top."""
    body = yaml.safe_dump(
        export_review_file(package), sort_keys=False, allow_unicode=True, width=100
    )
    return f"{_HEADER}\n{body}"


def read_review_file(text: str) -> dict[str, Any]:
    """Parse an edited file, refusing anything that is not the document this module writes.

    Validated against `_ReviewFileDocument` with `extra="forbid"`, so an unknown or misspelled key --
    `question` for `questions`, `decison` for `decision` -- is named rather than silently dropped. A
    dropped instruction at a structural checkpoint is a reviewer's decision lost with no signal,
    which is the one failure a review interface must not have. The validated dict is returned; the
    apply path reads it by key as before.
    """
    loaded: Any = yaml.safe_load(text)
    if not isinstance(loaded, dict):
        raise ReviewFileError("a review file is a mapping; this parsed as something else")
    if "assessment_id" not in loaded:
        raise ReviewFileError(
            "this file names no assessment. Export one with `trace context review --export`."
        )
    try:
        _ReviewFileDocument.model_validate(loaded)
    except PydanticValidationError as invalid:
        raise ReviewFileError(_render_validation_error(invalid)) from None
    return loaded


def _render_validation_error(error: PydanticValidationError) -> str:
    """A review-file validation error as a short, safe summary naming the offending keys.

    Pydantic's default rendering can quote the offending value; a review file may carry
    document-derived text, so the message names the field location and the error type only.
    """
    parts = []
    for detail in error.errors():
        location = ".".join(str(part) for part in detail["loc"]) or "(root)"
        if detail["type"] == "extra_forbidden":
            parts.append(f"{location}: unknown key (a misspelled field is not applied)")
        else:
            parts.append(f"{location}: {detail['type']}")
    return "this file is not a review document: " + "; ".join(parts)


def apply_review_file(
    handle: AssessmentHandle,
    document: dict[str, Any],
    *,
    reviewer_id: str,
    workflow_run_id: str | None = None,
) -> AppliedReviewFile:
    """Apply an edited file, returning the decisions it produced and the additions it skipped.

    Every action goes through `workflow/context_review.py`, so a file and the equivalent flags
    write identical rows. Refusals are refusals: a file that would dangle a data-flow endpoint is
    rejected in the validation node's words, the same as the flag would be.

    The whole application is one transaction: a refusal partway through rolls back everything, so a
    file never lands half-applied. The store's nested-transaction support (savepoints) means the
    per-action transactions inside `context_review` compose under this outer one.
    """
    if document.get("assessment_id") != handle.assessment_id:
        raise ReviewFileError(
            f"this file is for {document.get('assessment_id')}, not {handle.assessment_id}. "
            f"Applying it would record one reviewer's decisions against another assessment."
        )

    decisions: list[ReviewerDecision] = []
    skipped_additions: list[str] = []
    by_id = {obj.id: obj for _, model in CONTEXT_OBJECT_TYPES for obj in handle.objects.list(model)}
    by_id.update({claim.id: claim for claim in handle.objects.list(ContextClaim)})
    questions = {question.id: question for question in handle.objects.list(Question)}
    index = EvidenceIndex(handle)

    models_by_group = dict(CONTEXT_OBJECT_TYPES)
    with handle.objects.transaction():
        for entry in document.get("additions") or []:
            group = str(entry.get("type") or "")
            model = models_by_group.get(group)
            if model is None:
                raise ReviewFileError(
                    f"{group or '(no type)'} is not a type an addition may name. Write one of: "
                    f"{', '.join(name for name, _ in CONTEXT_OBJECT_TYPES)}."
                )
            # An addition naming an object that already exists is skipped, not duplicated: the
            # common cause is the same edited file applied twice, and the rare cause — a reviewer
            # adding a namesake of an extracted object — is a duplicate either way. The skipped
            # name is returned rather than swallowed, so a reviewer whose addition vanished sees it.
            name = (entry.get("fields") or {}).get("name")
            if name and any(
                getattr(obj, "name", None) == name for obj in handle.objects.list(model)
            ):
                skipped_additions.append(str(name))
                continue
            try:
                _, decision = add_context_object(
                    handle,
                    model,
                    dict(entry.get("fields") or {}),
                    reviewer_id=reviewer_id,
                    workflow_run_id=workflow_run_id,
                )
            except (ReviewerActionError, PydanticValidationError) as refused:
                raise ReviewFileError(f"additions: {refused}") from None
            decisions.append(decision)

        for group, _ in (*CONTEXT_OBJECT_TYPES, ("claims", ContextClaim)):
            for entry in document.get(group) or []:
                decisions.extend(
                    _apply_entry(
                        handle,
                        group,
                        entry,
                        by_id,
                        index=index,
                        reviewer_id=reviewer_id,
                        workflow_run_id=workflow_run_id,
                    )
                )

        for entry in document.get("contradictions") or []:
            decisions.extend(
                _apply_contradiction(
                    handle, entry, reviewer_id=reviewer_id, workflow_run_id=workflow_run_id
                )
            )

        for entry in document.get("questions") or []:
            answer = (entry.get("answer") or "").strip()
            if not answer:
                continue
            question = questions.get(str(entry.get("id") or ""))
            if question is None:
                raise ReviewFileError(f"{entry.get('id')} is not a question in this assessment")
            _, decision = answer_question(
                handle,
                question,
                response=answer,
                reviewer_id=reviewer_id,
                workflow_run_id=workflow_run_id,
            )
            decisions.append(decision)

    return AppliedReviewFile(decisions=decisions, skipped_additions=skipped_additions)


def _apply_entry(
    handle: AssessmentHandle,
    group: str,
    entry: dict[str, Any],
    by_id: dict[str, Any],
    *,
    index: EvidenceIndex,
    reviewer_id: str,
    workflow_run_id: str | None,
) -> list[ReviewerDecision]:
    """One entry's actions, in a fixed order: edit, then attach, then confirm, then decide.

    The order matters and is not arbitrary. An edit changes content, an attachment changes what
    the object rests on, and a decision records a judgment about the object; applying the decision
    first would record a judgment about the version the reviewer replaced.
    """
    identifier = str(entry.get("id") or "")
    obj = by_id.get(identifier)
    if obj is None:
        raise ReviewFileError(f"{identifier} is not an object in this assessment")

    produced: list[ReviewerDecision] = []

    changes = {
        field: value
        for field, value in (entry.get("editable") or {}).items()
        if field in EDITABLE_FIELDS[group] and obj.model_dump(mode="json").get(field) != value
    }
    if changes:
        obj, decision = apply_edit(
            handle,
            obj,
            changes,
            reviewer_id=reviewer_id,
            workflow_run_id=workflow_run_id,
        )
        by_id[identifier] = obj
        produced.append(decision)

    # Filtered to what the object does not already cite, so a file applied twice attaches once —
    # the same property every other slot has: expressing a difference, not repeating a state.
    attach = [
        evidence_id
        for evidence_id in entry.get("attach_evidence") or []
        if evidence_id not in getattr(obj, "evidence_ids", ())
    ]
    if attach:
        try:
            obj, decision = attach_evidence(
                handle,
                obj,
                attach,
                index=index,
                reviewer_id=reviewer_id,
                workflow_run_id=workflow_run_id,
            )
        except ReviewerActionError as refused:
            raise ReviewFileError(f"{identifier}: {refused}") from None
        by_id[identifier] = obj
        produced.append(decision)

    if entry.get("confirm"):
        if not isinstance(obj, ContextClaim):
            raise ReviewFileError(f"{identifier} is not a claim, so there is nothing to confirm")
        if obj.status is not ClaimStatus.USER_CONFIRMED:
            obj, decision = confirm_assumption(
                handle, obj, reviewer_id=reviewer_id, workflow_run_id=workflow_run_id
            )
            by_id[identifier] = obj
            produced.append(decision)

    disposition = entry.get("decision")
    if disposition:
        if disposition not in _DISPOSITIONS:
            raise ReviewFileError(
                f"{identifier}: {disposition!r} is not a decision. Write "
                f"{' or '.join(sorted(_DISPOSITIONS))}, or edit a field to record a change."
            )
        try:
            obj, decision = decide_object(
                handle,
                obj,
                ReviewDisposition(disposition),
                reviewer_id=reviewer_id,
                workflow_run_id=workflow_run_id,
            )
        except ReviewerActionError as refused:
            raise ReviewFileError(f"{identifier}: {refused}") from None
        by_id[identifier] = obj
        produced.append(decision)

    return produced


def _apply_contradiction(
    handle: AssessmentHandle,
    entry: dict[str, Any],
    *,
    reviewer_id: str,
    workflow_run_id: str | None,
) -> list[ReviewerDecision]:
    """One contradiction entry: both slots filled resolves it; both empty leaves it alone.

    One slot without the other is refused rather than half-applied, because a resolution with no
    rationale is exactly the silent choice `resolve_contradiction` exists to prevent, and a
    rationale with no resolution settles nothing.
    """
    resolution = entry.get("resolution")
    rationale = str(entry.get("rationale") or "").strip()
    if resolution is None and not rationale:
        return []
    if resolution is None or not rationale:
        raise ReviewFileError(
            f"{entry.get('id')}: a contradiction is settled by filling both `resolution:` and "
            f"`rationale:`; one without the other records nothing defensible"
        )

    identifier = str(entry.get("id") or "")
    observation = handle.objects.find(SourceObservation, identifier)
    if observation is None:
        raise ReviewFileError(f"{identifier} is not an observation in this assessment")
    if (observation.reviewer_notes or "").strip():
        if observation.reviewer_notes == rationale:
            return []  # the same file applied twice; the resolution already stands
        raise ReviewFileError(
            f"{identifier} is already resolved with a different rationale. Resolving it again "
            f"would silently replace a recorded judgment; edit the observation instead."
        )

    try:
        resolved = resolve_contradiction(
            handle,
            observation,
            resolution=resolution,
            rationale=rationale,
            reviewer_id=reviewer_id,
            workflow_run_id=workflow_run_id,
        )
    except ReviewerActionError as refused:
        raise ReviewFileError(f"{identifier}: {refused}") from None
    return list(resolved.decisions)
