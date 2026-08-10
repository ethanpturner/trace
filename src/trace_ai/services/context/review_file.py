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

from typing import TYPE_CHECKING, Any

import yaml

from trace_ai.domain.context_claim import ClaimStatus, ContextClaim
from trace_ai.domain.enums import ReviewDisposition
from trace_ai.domain.question import Question
from trace_ai.workflow.context_review import (
    CONTEXT_OBJECT_TYPES,
    ReviewerActionError,
    answer_question,
    apply_edit,
    confirm_assumption,
    decide_object,
)

if TYPE_CHECKING:
    from trace_ai.domain.reviewer_decision import ReviewerDecision
    from trace_ai.services.assessment import AssessmentHandle
    from trace_ai.workflow.context_review import ContextReviewPackage

__all__ = [
    "EDITABLE_FIELDS",
    "ReviewFileError",
    "apply_review_file",
    "export_review_file",
    "read_review_file",
    "write_review_file",
]

# What a reviewer may change by editing the file. Deliberately narrow: these are the fields a
# person reads an architecture document to correct. Identifiers, statuses, evidence links, and
# timestamps are not here — each has its own action, and each has a rule the file cannot express.
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
# Identifiers, statuses, evidence links, and timestamps are the application's and are shown for
# reference. Changing one here has no effect.
"""


class ReviewFileError(ValueError):
    """A review file the application will not apply, with the reason named."""


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
            "evidence": [excerpt.evidence_id for excerpt in presented.excerpts],
            "editable": {
                field: presented.claim.model_dump(mode="json")[field]
                for field in EDITABLE_FIELDS["claims"]
            },
        }
        for presented in package.claims
    ]

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
    """Parse an edited file, refusing anything that is not the document this module writes."""
    loaded: Any = yaml.safe_load(text)
    if not isinstance(loaded, dict):
        raise ReviewFileError("a review file is a mapping; this parsed as something else")
    if "assessment_id" not in loaded:
        raise ReviewFileError(
            "this file names no assessment. Export one with `trace context review --export`."
        )
    return loaded


def apply_review_file(
    handle: AssessmentHandle,
    document: dict[str, Any],
    *,
    reviewer_id: str,
    workflow_run_id: str | None = None,
) -> list[ReviewerDecision]:
    """Apply an edited file, returning the decisions it produced in the order it produced them.

    Every action goes through `workflow/context_review.py`, so a file and the equivalent flags
    write identical rows. Refusals are refusals: a file that would dangle a data-flow endpoint is
    rejected in the validation node's words, the same as the flag would be.
    """
    if document.get("assessment_id") != handle.assessment_id:
        raise ReviewFileError(
            f"this file is for {document.get('assessment_id')}, not {handle.assessment_id}. "
            f"Applying it would record one reviewer's decisions against another assessment."
        )

    decisions: list[ReviewerDecision] = []
    by_id = {obj.id: obj for _, model in CONTEXT_OBJECT_TYPES for obj in handle.objects.list(model)}
    by_id.update({claim.id: claim for claim in handle.objects.list(ContextClaim)})
    questions = {question.id: question for question in handle.objects.list(Question)}

    for group, _ in (*CONTEXT_OBJECT_TYPES, ("claims", ContextClaim)):
        for entry in document.get(group) or []:
            decisions.extend(
                _apply_entry(
                    handle,
                    group,
                    entry,
                    by_id,
                    reviewer_id=reviewer_id,
                    workflow_run_id=workflow_run_id,
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

    return decisions


def _apply_entry(
    handle: AssessmentHandle,
    group: str,
    entry: dict[str, Any],
    by_id: dict[str, Any],
    *,
    reviewer_id: str,
    workflow_run_id: str | None,
) -> list[ReviewerDecision]:
    """One entry's actions, in a fixed order: edit, then confirm, then decide.

    The order matters and is not arbitrary. An edit changes content and a decision records a
    judgment about the object; applying the decision first would record a judgment about the
    version the reviewer replaced.
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
