"""The mutating reviewer actions at checkpoint 1, and the revision they produce.

`agent-design.md` section 9 lists ten things a reviewer may do. Nine of them change something, and
`data-model.md` section 2.5 says why each has to leave a record: reviewer edits are the evaluation
signal that shows where the workflow was inaccurate. An edit that overwrote generated content
without saying so would destroy the measurement and look like a clean extraction.

The rule the file is organised around is DEC-023's three mechanisms, applied to nine actions:

- **A reviewer edit mutates in place** and writes a `ReviewerDecision` carrying only the fields that
  changed, before and after. The generated value stays recoverable from the decision.
- **`supersedes_id` is not for edits.** It records a generated object replacing a generated one, and
  its case is re-extraction (DEC-038).
- **`SystemContext` is the only versioned object**, and DEC-040 fixes when: approval mints the
  successor, so version 1 is always the generated baseline and version 2 is what a person approved.

Everything runs offline against `DeterministicModel`. The context being reviewed comes out of the
real extraction node, so the objects a reviewer edits here are objects the pipeline made.
"""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from trace_ai.config import PROJECT_ROOT
from trace_ai.domain.actor import Actor
from trace_ai.domain.assessment import default_configuration
from trace_ai.domain.asset import Asset
from trace_ai.domain.component import Component
from trace_ai.domain.context_claim import ClaimStatus, ContextClaim
from trace_ai.domain.data_flow import DataFlow, FlowDirection
from trace_ai.domain.enums import (
    ConfidenceLevel,
    ObjectStatus,
    ReviewDisposition,
    SourceOrigin,
)
from trace_ai.domain.evidence import EvidenceReference
from trace_ai.domain.proposals import ContextExtractionProposal
from trace_ai.domain.question import Question, QuestionPriority, QuestionStatus
from trace_ai.domain.reviewer_decision import ReviewerDecision
from trace_ai.domain.source_document import TrustLevel
from trace_ai.domain.source_observation import ObservationKind, SourceObservation
from trace_ai.domain.system_context import SystemContext
from trace_ai.domain.trust_boundary import TrustBoundary
from trace_ai.infrastructure.database.store import AssessmentStore
from trace_ai.infrastructure.model import DeterministicModel, ModelUsage
from trace_ai.infrastructure.model.profiles import resolve_profile
from trace_ai.services.assessment import AssessmentHandle, AssessmentService
from trace_ai.services.evidence.index import EvidenceIndex
from trace_ai.services.evidence.indexing import index_document
from trace_ai.services.execution_ledger import ExecutionLedger, start_run
from trace_ai.services.ingestion.loader import DocumentLoader
from trace_ai.services.prompts import PromptRegistry
from trace_ai.workflow.context_extraction import ContextExtractionNode
from trace_ai.workflow.context_review import (
    ReviewerActionError,
    add_context_object,
    answer_question,
    apply_edit,
    approve_context,
    attach_evidence,
    build_context_review_package,
    confirm_assumption,
    current_system_context,
    decide_object,
    re_extraction_feedback,
    request_re_extraction,
    resolve_contradiction,
)
from trace_ai.workflow.context_validation import validate_context
from trace_ai.workflow.limits import Budget, LimitExceededError
from trace_ai.workflow.nodes import NodeContext
from trace_ai.workflow.state import AssessmentState

FORGEFLOW = PROJECT_ROOT / "demo" / "forgeflow" / "input"
PROFILE = resolve_profile("primary-development")
REVIEWER = "eturner"

USAGE = ModelUsage(
    model="claude-opus-5",
    input_tokens=12_000,
    output_tokens=1_500,
    estimated_cost=Decimal("0.0975"),
)


class Usable(DeterministicModel):
    """The fake, with usage attached so the ledger has something to record."""

    def generate(self, **kwargs: Any) -> Any:
        outcome = super().generate(**kwargs)
        if hasattr(outcome, "usage") and outcome.usage.input_tokens == 0:
            return type(outcome)(
                **{**{f: getattr(outcome, f) for f in outcome.__slots__}, "usage": USAGE}
            )
        return outcome


def payload(first: str, second: str) -> dict[str, Any]:
    """One extraction covering every object family a reviewer can act on."""
    return {
        "system": {
            "system_name": "ForgeFlow",
            "system_purpose": "AI-assisted pull-request review",
        },
        "components": [
            {
                "key": "webhook",
                "name": "Webhook Receiver",
                "component_type": "service",
                "internet_accessible": True,
                "evidence_ids": [first],
            },
            {
                "key": "worker",
                "name": "Analysis Worker",
                "component_type": "background_worker",
                "evidence_ids": [first],
            },
        ],
        "actors": [
            {
                "key": "customer",
                "name": "Customer User",
                "actor_type": "end_user",
                "evidence_ids": [first],
            }
        ],
        "assets": [
            {
                "key": "source",
                "name": "Customer Source Code",
                "asset_type": "source_code",
                "component_keys": ["worker"],
                "evidence_ids": [first],
            }
        ],
        "data_flows": [
            {
                "key": "enqueue",
                "name": "Analysis job enqueue",
                "source_component_key": "webhook",
                "destination_component_key": "worker",
                "direction": FlowDirection.ONE_WAY,
                "evidence_ids": [first],
            }
        ],
        "trust_boundaries": [
            {
                "key": "public",
                "name": "Public internet boundary",
                "boundary_type": "internet_to_application",
                "inside_component_keys": ["webhook"],
                "evidence_ids": [first],
            }
        ],
        "claims": [
            {
                "key": "region",
                "subject_type": "system",
                "predicate": "processing_region",
                "value": "us-east-1",
                "status": ClaimStatus.ASSUMED,
                "confidence": ConfidenceLevel.LOW,
                "rationale": "Taken from the structured input and not confirmed in prose.",
            },
            {
                "key": "retention",
                "subject_type": "system",
                "predicate": "artifact_retention",
                "value": None,
                "status": ClaimStatus.CONTRADICTED,
                "confidence": ConfidenceLevel.HIGH,
                "rationale": "Two documents disagree.",
                "evidence_ids": [first, second],
            },
            {
                "key": "validation",
                "subject_type": "component",
                "subject_key": "webhook",
                "predicate": "request_validation",
                "value": "documented as validated",
                "status": ClaimStatus.DOCUMENTED,
                "confidence": ConfidenceLevel.MEDIUM,
                "evidence_ids": [first],
            },
        ],
        "questions": [
            {
                "key": "hmac",
                "question": "Does webhook validation include HMAC signature verification?",
                "rationale": "Without it the receiver accepts forged deliveries.",
                "priority": QuestionPriority.HIGH,
                "blocking": True,
            }
        ],
        "observations": [
            {
                "key": "retention-conflict",
                "kind": ObservationKind.CONTRADICTION,
                "summary": (
                    "One document says source files are deleted after analysis; another states a "
                    "30-day retention target."
                ),
                "evidence_ids": [first, second],
                "subject_claim_keys": ["retention"],
            }
        ],
    }


@pytest.fixture
def reviewed(tmp_path: Path) -> Iterator[tuple[AssessmentHandle, ExecutionLedger]]:
    """An assessment with a context extracted and sitting at checkpoint 1."""
    with AssessmentStore.at_root(tmp_path) as store:
        service = AssessmentService(store, artifact_root=tmp_path)
        created = service.create(
            "ForgeFlow", default_configuration("primary-development", "stride-scenario-based")
        )
        handle = service.handle(created.id)
        loader = DocumentLoader(handle)
        for name in ("architecture-overview.md", "operations-guide.md"):
            index_document(
                handle,
                loader.load_document(
                    FORGEFLOW / name,
                    origin=SourceOrigin.UPLOADED_DOCUMENT,
                    trust_level=TrustLevel.UNTRUSTED,
                ),
            )

        run = start_run(handle, workflow_version="0.1", model_profile="primary-development")
        ledger = ExecutionLedger(handle, run)
        evidence = sorted(reference.id for reference in handle.objects.list(EvidenceReference))
        node = ContextExtractionNode(
            ledger=ledger,
            index=EvidenceIndex(handle),
            profile=PROFILE,
            registry=PromptRegistry(),
            evidence_ids=evidence,
            assessment_name="ForgeFlow",
        )
        node.run(
            NodeContext(
                handle=handle,
                state=AssessmentState.begin(
                    assessment_id=handle.assessment_id, workflow_run_id=run.id
                ),
                model=Usable(
                    [ContextExtractionProposal.model_validate(payload(evidence[0], evidence[1]))]
                ),
            )
        )
        yield handle, ledger


def evidence_ids(handle: AssessmentHandle) -> list[str]:
    return sorted(reference.id for reference in handle.objects.list(EvidenceReference))


def package_for(handle: AssessmentHandle) -> Any:
    objects = [
        obj
        for model in (Component, Actor, Asset, DataFlow, TrustBoundary, ContextClaim)
        for obj in handle.objects.list(model)
    ]
    validation = validate_context(
        current_system_context(handle), objects, available_evidence=set(evidence_ids(handle))
    )
    return build_context_review_package(handle, index=EvidenceIndex(handle), validation=validation)


def component(handle: AssessmentHandle, name: str) -> Component:
    return next(item for item in handle.objects.list(Component) if item.name == name)


def claim(handle: AssessmentHandle, predicate: str) -> ContextClaim:
    return next(item for item in handle.objects.list(ContextClaim) if item.predicate == predicate)


def decisions_for(handle: AssessmentHandle, subject_id: str) -> list[ReviewerDecision]:
    return [
        decision
        for decision in handle.objects.list(ReviewerDecision)
        if decision.subject_id == subject_id
    ]


# ------------------------------------------------------------------------------------------
# Edit
# ------------------------------------------------------------------------------------------


def test_an_edit_mutates_in_place_and_records_only_what_changed(reviewed: Any) -> None:
    """DEC-023's first mechanism. The object keeps its identifier and the decision carries the
    delta, which is what makes reviewer edit rate computable per field rather than per object."""
    handle, ledger = reviewed
    original = component(handle, "Webhook Receiver")

    edited, decision = apply_edit(
        handle,
        original,
        {"description": "Internet-facing receiver for GitHub webhook events."},
        reviewer_id=REVIEWER,
        rationale="The extraction left the description empty.",
        workflow_run_id=ledger.run.id,
    )

    assert edited.id == original.id, "an edit is in place; a new identifier would be a new object"
    assert handle.objects.find(Component, original.id) == edited

    assert decision.disposition is ReviewDisposition.EDIT
    assert set(decision.prior_value or {}) == {"description"}
    assert set(decision.updated_value or {}) == {"description"}
    assert decision.reviewer_id == REVIEWER
    assert decision.workflow_run_id == ledger.run.id


def test_the_generated_value_is_recoverable_after_the_object_has_changed(reviewed: Any) -> None:
    """The property section 2.5 is actually asking for. "Recorded rather than silently
    overwriting" is worth nothing if the overwritten value is gone — the point of the record is
    that a later reader can see what the model said and what the person changed it to."""
    handle, _ = reviewed
    original = component(handle, "Analysis Worker")
    generated_name = original.name

    edited, decision = apply_edit(
        handle,
        original,
        {"name": "Pull-Request Analysis Worker", "ownership": "Platform Engineering"},
        reviewer_id=REVIEWER,
    )

    assert edited.name != generated_name
    assert (decision.prior_value or {})["name"] == generated_name
    assert (decision.updated_value or {})["name"] == "Pull-Request Analysis Worker"
    assert (decision.prior_value or {})["ownership"] is None
    assert set(decision.prior_value or {}) == set(decision.updated_value or {})


def test_an_edit_that_changes_nothing_is_refused(reviewed: Any) -> None:
    """`capture_edit` refuses it: a decision that changed nothing is an approval, not an edit."""
    handle, _ = reviewed
    original = component(handle, "Webhook Receiver")

    with pytest.raises(ValueError, match="no edit to record"):
        apply_edit(handle, original, {"name": original.name}, reviewer_id=REVIEWER)


def test_an_edit_goes_through_the_schema(reviewed: Any) -> None:
    """`model_validate`, never `model_copy` (DEC-023). This is the one path a human-supplied value
    takes into a domain object, so it is the one that least tolerates skipping validation."""
    handle, _ = reviewed
    flow = handle.objects.list(DataFlow)[0]

    with pytest.raises(ValueError, match="direction"):
        apply_edit(handle, flow, {"direction": "sideways"}, reviewer_id=REVIEWER)

    with pytest.raises(ValueError, match="extra_forbidden"):
        apply_edit(handle, flow, {"invented_field": True}, reviewer_id=REVIEWER)


def test_no_edit_writes_supersedes_id(reviewed: Any) -> None:
    """DEC-023 reserves `supersedes_id` for a generated object replacing a generated one, and its
    case is re-extraction. A reviewer edit that used it would make the two indistinguishable."""
    handle, _ = reviewed
    target = claim(handle, "processing_region")

    edited, _ = apply_edit(handle, target, {"value": "us-west-2"}, reviewer_id=REVIEWER)

    assert edited.supersedes_id is None
    assert all(item.supersedes_id is None for item in handle.objects.list(ContextClaim))


# ------------------------------------------------------------------------------------------
# Approve and reject
# ------------------------------------------------------------------------------------------


def test_approving_an_object_sets_its_status_and_carries_no_delta(reviewed: Any) -> None:
    """The status change and the disposition say the same thing. `ReviewerDecision` refuses a delta
    on an approval, because a change to the object's content is an edit and this is not one."""
    handle, _ = reviewed
    target = component(handle, "Webhook Receiver")

    decided, decision = decide_object(
        handle, target, ReviewDisposition.APPROVE, reviewer_id=REVIEWER
    )

    assert decided.status is ObjectStatus.APPROVED
    assert decision.disposition is ReviewDisposition.APPROVE
    assert decision.prior_value is None
    assert decision.updated_value is None


def test_rejecting_an_object_records_it_and_keeps_the_object(reviewed: Any) -> None:
    """A rejected object stays in the store — `data-model.md` section 2.6 keeps current state and
    history separate, and deleting the object would delete the record of the model having proposed
    it. What changes is that the approved baseline will not name it."""
    handle, _ = reviewed
    target = component(handle, "Analysis Worker")

    decided, decision = decide_object(
        handle,
        target,
        ReviewDisposition.REJECT,
        reviewer_id=REVIEWER,
        rationale="Not a separate component; it is part of the API service.",
    )

    assert decided.status is ObjectStatus.REJECTED
    assert handle.objects.find(Component, target.id) is not None
    assert decision.rationale


def test_an_actor_decision_is_the_whole_record_of_it(reviewed: Any) -> None:
    """`data-model.md` section 13's table gives `Actor` no `status` and DEC-037 declined to add one,
    so an actor's approval lives entirely in the decision."""
    handle, _ = reviewed
    actor = handle.objects.list(Actor)[0]

    decided, decision = decide_object(
        handle, actor, ReviewDisposition.APPROVE, reviewer_id=REVIEWER
    )

    assert not hasattr(decided, "status")
    assert decisions_for(handle, actor.id) == [decision]


def test_an_edit_cannot_be_disguised_as_an_approval(reviewed: Any) -> None:
    handle, _ = reviewed
    target = component(handle, "Webhook Receiver")

    with pytest.raises(ReviewerActionError, match="not an approve-or-reject decision"):
        decide_object(handle, target, ReviewDisposition.EDIT, reviewer_id=REVIEWER)


# ------------------------------------------------------------------------------------------
# Add
# ------------------------------------------------------------------------------------------


def test_a_reviewer_added_object_carries_reviewer_edit_as_its_origin(reviewed: Any) -> None:
    """DEC-039. Without the field, a component a person created and one the extractor produced are
    the same row, and "the reviewer had to add three components the extractor missed" — the
    sharpest form of the correction signal section 2.5 names — is not computable."""
    handle, _ = reviewed

    added, decision = add_context_object(
        handle,
        Component,
        {"name": "Managed Redis Queue", "component_type": "managed_cache"},
        reviewer_id=REVIEWER,
        rationale="Named throughout the architecture overview and not extracted.",
    )

    assert added.source_origin is SourceOrigin.REVIEWER_EDIT
    assert added.id.startswith("cmp-")
    assert added.status is ObjectStatus.APPROVED, (
        "nobody needs to approve what they just wrote, and a candidate would make the checkpoint "
        "wait on a decision about the reviewer's own object"
    )
    assert decision.subject_id == added.id


def test_the_extractors_objects_keep_the_document_as_their_origin(reviewed: Any) -> None:
    """The other half of DEC-039: the field is only a signal because it distinguishes."""
    handle, _ = reviewed
    for item in handle.objects.list(Component):
        assert item.source_origin is SourceOrigin.UPLOADED_DOCUMENT


@pytest.mark.parametrize(
    ("model", "fields"),
    [
        (Component, {"name": "Managed PostgreSQL", "component_type": "managed_database"}),
        (Actor, {"name": "ForgeFlow Administrator", "actor_type": "administrator"}),
        (Asset, {"name": "GitHub App Private Key", "asset_type": "api_key"}),
        (
            TrustBoundary,
            {"name": "AI-provider boundary", "boundary_type": "organization_to_third_party"},
        ),
    ],
)
def test_every_addable_object_family_takes_the_same_path(
    reviewed: Any, model: type[Any], fields: dict[str, Any]
) -> None:
    handle, _ = reviewed
    added, decision = add_context_object(handle, model, fields, reviewer_id=REVIEWER)

    assert added.source_origin is SourceOrigin.REVIEWER_EDIT
    assert decision.disposition is ReviewDisposition.APPROVE
    assert handle.objects.find(model, added.id) == added


def test_the_identifier_is_allocated_by_the_store(reviewed: Any) -> None:
    """DEC-018. A reviewer-supplied identifier could collide with a number the counter has not
    reached yet, and the collision is invisible until two objects answer to one name."""
    handle, _ = reviewed
    existing = {item.id for item in handle.objects.list(Component)}

    added, _ = add_context_object(
        handle,
        Component,
        {"name": "Central Logging Platform", "component_type": "external_service"},
        reviewer_id=REVIEWER,
    )

    assert added.id not in existing


def test_only_a_context_object_family_can_be_added(reviewed: Any) -> None:
    handle, _ = reviewed
    with pytest.raises(ReviewerActionError, match="not one of the context object types"):
        add_context_object(handle, Question, {"question": "?"}, reviewer_id=REVIEWER)


# ------------------------------------------------------------------------------------------
# Correcting a data flow
# ------------------------------------------------------------------------------------------


def test_a_data_flow_correction_is_applied_when_both_endpoints_exist(reviewed: Any) -> None:
    handle, _ = reviewed
    flow = handle.objects.list(DataFlow)[0]
    worker = component(handle, "Analysis Worker")
    webhook = component(handle, "Webhook Receiver")

    corrected, decision = apply_edit(
        handle,
        flow,
        {"source_component_id": worker.id, "destination_component_id": webhook.id},
        reviewer_id=REVIEWER,
        rationale="The flow runs the other way.",
    )

    assert corrected.source_component_id == worker.id
    assert set(decision.prior_value or {}) == {
        "source_component_id",
        "destination_component_id",
    }


def test_a_correction_that_would_dangle_an_endpoint_is_refused_in_the_validators_words(
    reviewed: Any,
) -> None:
    """The acceptance the issue asks for: the reviewer is refused with the same error the Context
    Validation node would have produced later. The check runs against
    `SystemContext.validate_against`, which is the function that node calls, so the two cannot
    drift into saying different things about the same mistake.
    """
    handle, _ = reviewed
    flow = handle.objects.list(DataFlow)[0]

    with pytest.raises(ReviewerActionError) as caught:
        apply_edit(handle, flow, {"destination_component_id": "cmp-994"}, reviewer_id=REVIEWER)

    message = str(caught.value)
    assert "destination_component_id cmp-994 is not in component_ids" in message
    assert handle.objects.find(DataFlow, flow.id) == flow, "the edit was persisted anyway"

    # The same sentence the validation node reports, reached the other way.
    broken = DataFlow.model_validate(flow.model_dump() | {"destination_component_id": "cmp-994"})
    objects: list[Any] = [*handle.objects.list(Component), broken]
    outcome = validate_context(current_system_context(handle), objects)
    assert any(
        "destination_component_id cmp-994 is not in component_ids" in error.message
        for error in outcome.errors
    )


def test_an_edit_unrelated_to_a_pre_existing_problem_is_not_blamed_for_it(reviewed: Any) -> None:
    """Comparing before and after rather than checking the result outright. A context that was
    already inconsistent must not make the next unrelated edit the reviewer's fault."""
    handle, _ = reviewed
    stale = current_system_context(handle)
    with handle.objects.transaction() as repository:
        repository.save(
            SystemContext.model_validate(
                stale.model_dump() | {"component_ids": [*stale.component_ids, "cmp-993"]}
            )
        )

    target = component(handle, "Webhook Receiver")
    edited, _ = apply_edit(handle, target, {"ownership": "Platform"}, reviewer_id=REVIEWER)

    assert edited.ownership == "Platform"


# ------------------------------------------------------------------------------------------
# Confirming an assumption
# ------------------------------------------------------------------------------------------


def test_confirming_an_assumption_moves_it_to_user_confirmed(reviewed: Any) -> None:
    """`agent-design.md` section 14 puts `user_confirmed` at the top of the evidence hierarchy: the
    reviewer is the evidence. It is the one status change that adds authority without adding a
    citation, which is why it is recorded rather than inferred."""
    handle, _ = reviewed
    assumed = claim(handle, "processing_region")
    assert assumed.status is ClaimStatus.ASSUMED

    confirmed, decision = confirm_assumption(
        handle,
        assumed,
        reviewer_id=REVIEWER,
        rationale="Confirmed with the platform team; the single region is correct.",
    )

    assert confirmed.status is ClaimStatus.USER_CONFIRMED
    assert confirmed.evidence_ids == [], "the reviewer is the evidence; no citation was invented"
    assert decision.disposition is ReviewDisposition.EDIT
    assert (decision.prior_value or {})["status"] == ClaimStatus.ASSUMED
    assert decision.reviewer_id == REVIEWER


def test_confirming_a_confirmed_claim_is_refused(reviewed: Any) -> None:
    handle, _ = reviewed
    confirmed, _ = confirm_assumption(
        handle, claim(handle, "processing_region"), reviewer_id=REVIEWER
    )

    with pytest.raises(ReviewerActionError, match="already user_confirmed"):
        confirm_assumption(handle, confirmed, reviewer_id=REVIEWER)


# ------------------------------------------------------------------------------------------
# Resolving a contradiction
# ------------------------------------------------------------------------------------------


def test_resolving_a_contradiction_records_the_choice_and_the_reasoning(reviewed: Any) -> None:
    """`forgeflow-scenario.md` section 16 states the requirement negatively — do not quietly choose
    the safer statement. This is the positive form: the choice is made, and it is made in writing."""
    handle, _ = reviewed
    (observation,) = handle.objects.list(SourceObservation)

    resolved = resolve_contradiction(
        handle,
        observation,
        resolution="30 days",
        rationale="The operations guide is authoritative; the product overview is marketing copy.",
        reviewer_id=REVIEWER,
    )

    assert resolved.observation.reviewer_notes
    assert resolved.observation.status is ObjectStatus.APPROVED
    (settled,) = resolved.claims
    assert settled.value == "30 days"
    assert settled.status is ClaimStatus.USER_CONFIRMED
    assert settled.rationale
    assert len(resolved.decisions) == 2, "the observation and the claim each get their own delta"


def test_the_unselected_statement_remains_retrievable(reviewed: Any) -> None:
    """Both passages stay cited on the observation. A resolution that dropped the losing statement
    would leave a record saying a contradiction existed and no way to see what it was — which is
    the silent choice with an audit row next to it."""
    handle, _ = reviewed
    (observation,) = handle.objects.list(SourceObservation)
    cited = list(observation.evidence_ids)
    assert len(cited) == 2

    resolved = resolve_contradiction(
        handle,
        observation,
        resolution="30 days",
        rationale="The operations guide is authoritative.",
        reviewer_id=REVIEWER,
    )

    assert resolved.observation.evidence_ids == cited
    index = EvidenceIndex(handle)
    for evidence_id in cited:
        assert index.get(evidence_id).quoted_text.strip()


def test_a_resolution_without_reasoning_is_refused(reviewed: Any) -> None:
    handle, _ = reviewed
    (observation,) = handle.objects.list(SourceObservation)

    with pytest.raises(ReviewerActionError, match="must carry a rationale"):
        resolve_contradiction(
            handle, observation, resolution="30 days", rationale="  ", reviewer_id=REVIEWER
        )


def test_only_a_contradiction_is_resolved_by_choosing(reviewed: Any) -> None:
    """An injection attempt has no two statements to choose between."""
    handle, _ = reviewed
    (observation,) = handle.objects.list(SourceObservation)
    with handle.objects.transaction() as repository:
        planted = SourceObservation.model_validate(
            observation.model_dump()
            | {
                "kind": ObservationKind.INJECTION_ATTEMPT,
                "evidence_ids": observation.evidence_ids[:1],
            }
        )
        repository.save(planted)

    with pytest.raises(ReviewerActionError, match="only a contradiction"):
        resolve_contradiction(
            handle, planted, resolution="x", rationale="because", reviewer_id=REVIEWER
        )


# ------------------------------------------------------------------------------------------
# Answering a question
# ------------------------------------------------------------------------------------------


def test_answering_a_question_sets_the_three_fields_together(reviewed: Any) -> None:
    """`data-model.md` section 22's answer fields move as a group and `Question` enforces it: a
    response with no origin is an answer nobody is accountable for."""
    handle, _ = reviewed
    (question,) = handle.objects.list(Question)

    answered, decision = answer_question(
        handle,
        question,
        response="Yes — the receiver verifies the GitHub HMAC signature before parsing.",
        reviewer_id=REVIEWER,
    )

    assert answered.status is QuestionStatus.ANSWERED
    assert answered.response_origin is SourceOrigin.USER_RESPONSE
    assert answered.answered_at is not None
    assert answered.response
    assert decision.disposition is ReviewDisposition.EDIT


def test_answering_a_blocking_question_clears_it_from_the_blocking_set(reviewed: Any) -> None:
    """The blocking set is derived from open questions, so answering is what empties it — there is
    no separate flag to clear, and therefore no way for the two to disagree."""
    handle, _ = reviewed
    (question,) = handle.objects.list(Question)
    assert question.blocking
    assert package_for(handle).blocking_questions

    answer_question(handle, question, response="Yes, HMAC is verified.", reviewer_id=REVIEWER)

    package = package_for(handle)
    assert package.blocking_questions == ()
    assert question.id not in {item.id for item in package.questions}


def test_an_empty_answer_is_refused(reviewed: Any) -> None:
    """A question the reviewer cannot answer is dismissed, which is a different status and a
    different record."""
    handle, _ = reviewed
    (question,) = handle.objects.list(Question)

    with pytest.raises(ReviewerActionError, match="needs an answer"):
        answer_question(handle, question, response="   ", reviewer_id=REVIEWER)


def test_a_question_is_answered_once(reviewed: Any) -> None:
    handle, _ = reviewed
    (question,) = handle.objects.list(Question)
    answered, _ = answer_question(handle, question, response="Yes.", reviewer_id=REVIEWER)

    with pytest.raises(ReviewerActionError, match="not open"):
        answer_question(handle, answered, response="Actually, no.", reviewer_id=REVIEWER)


# ------------------------------------------------------------------------------------------
# Adding evidence
# ------------------------------------------------------------------------------------------


def test_adding_evidence_links_a_reference_and_leaves_its_text_alone(reviewed: Any) -> None:
    """`data-model.md` section 8 requires a correction to create a new evidence reference. DEC-019
    hashes `quoted_text` and the indexer records the line range it came from, so editing the text
    in place would leave it disagreeing with both its own hash and its own location — and the
    disagreement would surface as an unverifiable citation rather than as the edit that caused it.
    """
    handle, _ = reviewed
    index = EvidenceIndex(handle)
    target = claim(handle, "processing_region")
    extra = evidence_ids(handle)[4]
    before = index.get(extra)

    linked, decision = attach_evidence(
        handle,
        target,
        [extra],
        index=index,
        reviewer_id=REVIEWER,
        rationale="The deployment section states the region.",
    )

    assert extra in linked.evidence_ids
    assert index.get(extra).quoted_text == before.quoted_text
    assert index.get(extra).content_hash == before.content_hash
    assert index.verify(extra).ok
    assert "evidence_ids" in (decision.prior_value or {})


def test_evidence_that_does_not_resolve_cannot_be_linked(reviewed: Any) -> None:
    """A citation nobody can follow is `agent-design.md` section 14's named failure condition, and
    it looks exactly like one that checks out."""
    handle, _ = reviewed
    with pytest.raises(ReviewerActionError, match="do not resolve"):
        attach_evidence(
            handle,
            claim(handle, "processing_region"),
            ["evd-994"],
            index=EvidenceIndex(handle),
            reviewer_id=REVIEWER,
        )


def test_linking_evidence_that_is_already_cited_is_refused(reviewed: Any) -> None:
    """There is no change to record, and a decision recording no change is the thing
    `capture_edit` exists to refuse."""
    handle, _ = reviewed
    target = claim(handle, "request_validation")

    with pytest.raises(ReviewerActionError, match="already cites"):
        attach_evidence(
            handle,
            target,
            list(target.evidence_ids),
            index=EvidenceIndex(handle),
            reviewer_id=REVIEWER,
        )


# ------------------------------------------------------------------------------------------
# Re-extraction
# ------------------------------------------------------------------------------------------


def test_the_rejection_rationale_reaches_the_next_runs_prompt(reviewed: Any) -> None:
    """DEC-038 makes re-extraction a new `WorkflowRun`; DEC-040 settles that the reviewer's
    rationale may travel with it. It goes in the **trusted** half, outside the source-content
    fence: DEC-013 puts `reviewer_edit` among the origins that are not material under review, and
    the reviewer is the operator rather than a document being assessed.

    `agent-design.md` section 26 is why it has to travel at all — a repeated attempt carries
    feedback or it is a repetition.
    """
    handle, ledger = reviewed
    request_re_extraction(
        handle,
        package_for(handle),
        reviewer_id=REVIEWER,
        rationale="The comment service and the webhook receiver were merged into one component.",
        workflow_run_id=ledger.run.id,
    )

    feedback = re_extraction_feedback(handle)
    assert feedback is not None
    assert "merged into one component" in feedback

    second = start_run(handle, workflow_version="0.1", model_profile="primary-development")
    model = Usable(
        [
            ContextExtractionProposal.model_validate(
                payload(evidence_ids(handle)[0], evidence_ids(handle)[1])
            )
        ]
    )
    node = ContextExtractionNode(
        ledger=ExecutionLedger(handle, second),
        index=EvidenceIndex(handle),
        profile=PROFILE,
        registry=PromptRegistry(),
        evidence_ids=evidence_ids(handle),
        assessment_name="ForgeFlow",
        reviewer_feedback=feedback,
    )
    result = node.run(
        NodeContext(
            handle=handle,
            state=AssessmentState.begin(
                assessment_id=handle.assessment_id, workflow_run_id=second.id
            ),
            model=model,
        )
    )

    (call,) = model.calls
    assert call.system is not None
    assert "merged into one component" in call.system
    assert "merged into one component" not in call.prompt, (
        "the reviewer's instruction reached the untrusted half"
    )
    assert "<source-content" not in call.system
    assert result.metadata["carried_reviewer_feedback"] is True


def test_a_re_extraction_consumes_the_runs_model_budget(reviewed: Any) -> None:
    """`agent-design.md` section 27's ceilings apply to a re-extraction like any other run, which
    is what stops repeated attempts from being free. A budget with no calls left stops the node
    before it spends anything."""
    handle, ledger = reviewed
    request_re_extraction(
        handle,
        package_for(handle),
        reviewer_id=REVIEWER,
        rationale="Try again with the boundaries filled in.",
        workflow_run_id=ledger.run.id,
    )

    second = start_run(handle, workflow_version="0.1", model_profile="primary-development")
    budget = Budget(maximum_model_calls=1)
    model = Usable(
        [
            ContextExtractionProposal.model_validate(
                payload(evidence_ids(handle)[0], evidence_ids(handle)[1])
            )
        ]
    )
    node = ContextExtractionNode(
        ledger=ExecutionLedger(handle, second),
        index=EvidenceIndex(handle),
        profile=PROFILE,
        registry=PromptRegistry(),
        evidence_ids=evidence_ids(handle),
        assessment_name="ForgeFlow",
        reviewer_feedback=re_extraction_feedback(handle),
        budget=budget,
    )
    context = NodeContext(
        handle=handle,
        state=AssessmentState.begin(assessment_id=handle.assessment_id, workflow_run_id=second.id),
        model=model,
    )

    node.run(context)
    assert budget.remaining().model_calls_remaining == 0

    with pytest.raises(LimitExceededError):
        node.run(context)


def test_no_re_extraction_request_means_no_feedback_to_carry(reviewed: Any) -> None:
    handle, _ = reviewed
    assert re_extraction_feedback(handle) is None


# ------------------------------------------------------------------------------------------
# The revised context version
# ------------------------------------------------------------------------------------------


def test_approving_after_edits_mints_version_two_and_keeps_version_one(reviewed: Any) -> None:
    """DEC-040. Version 1 is the generated baseline and is never approved; version 2 is what a
    person approved. Two revisions, always — so the difference between them is the reviewer's work
    and is readable by diff rather than lost to an in-place stamp."""
    handle, _ = reviewed
    apply_edit(
        handle,
        component(handle, "Webhook Receiver"),
        {"description": "Internet-facing receiver for GitHub webhook events."},
        reviewer_id=REVIEWER,
    )
    answer_question(
        handle,
        handle.objects.list(Question)[0],
        response="Yes, HMAC is verified.",
        reviewer_id=REVIEWER,
    )

    approved, _ = approve_context(handle, package_for(handle), reviewer_id=REVIEWER)

    revisions = {revision.version: revision for revision in handle.objects.list(SystemContext)}
    assert set(revisions) == {1, 2}
    assert approved.version == 2
    assert approved.approved_by == REVIEWER
    assert approved.approved_at is not None
    assert not revisions[1].is_approved
    assert revisions[1].approved_at is None


def test_a_reviewer_added_object_reaches_the_approved_baseline(reviewed: Any) -> None:
    """The membership of the approved revision is recomputed from the store rather than copied.
    An added object that never reached the baseline would be approved by nobody and reasoned from
    by nothing, which is DEC-037's objection to an unreferenced actor in a different place."""
    handle, _ = reviewed
    added, _ = add_context_object(
        handle,
        Component,
        {"name": "Managed Redis Queue", "component_type": "managed_cache"},
        reviewer_id=REVIEWER,
    )
    answer_question(
        handle, handle.objects.list(Question)[0], response="Yes, HMAC.", reviewer_id=REVIEWER
    )

    approved, _ = approve_context(handle, package_for(handle), reviewer_id=REVIEWER)

    assert added.id in approved.component_ids
    assert added.id not in handle.objects.list(SystemContext)[0].component_ids


def test_a_reviewer_rejected_object_stays_out_of_the_approved_baseline(reviewed: Any) -> None:
    """`current-architecture.md` section 5.6 says threat analysis reasons from the approved
    baseline. A component the reviewer rejected sitting in that baseline would be reasoned from
    anyway, and the rejection would be a row nothing consulted."""
    handle, _ = reviewed
    target = component(handle, "Analysis Worker")
    decide_object(handle, target, ReviewDisposition.REJECT, reviewer_id=REVIEWER)
    answer_question(
        handle, handle.objects.list(Question)[0], response="Yes, HMAC.", reviewer_id=REVIEWER
    )

    approved, _ = approve_context(handle, package_for(handle), reviewer_id=REVIEWER)

    assert target.id not in approved.component_ids
    assert handle.objects.find(Component, target.id) is not None, "the object itself was deleted"


@pytest.mark.parametrize(
    ("family", "model"),
    [
        ("components", Component),
        ("actors", Actor),
        ("assets", Asset),
        ("data_flows", DataFlow),
        ("trust_boundaries", TrustBoundary),
        ("claims", ContextClaim),
    ],
)
def test_the_revision_rule_is_the_same_for_every_object_family(
    reviewed: Any, family: str, model: type[Any]
) -> None:
    """One test per object family, as the issue asks. The rule under test is DEC-023's: **no object
    but `SystemContext` is versioned**. An edit anywhere leaves exactly one row for that object,
    under the same identifier, with the history on the decision.
    """
    handle, _ = reviewed
    target = handle.objects.list(model)[0]
    changes: dict[str, Any] = {
        "components": {"description": "Corrected by the reviewer."},
        "actors": {"trust_level": "Authenticated customer"},
        "assets": {"owner": "Platform Engineering"},
        "data_flows": {"protocol": "HTTPS"},
        "trust_boundaries": {"description": "Corrected by the reviewer."},
        "claims": {"rationale": "Confirmed with the platform team."},
    }[family]

    edited, decision = apply_edit(handle, target, changes, reviewer_id=REVIEWER)

    assert edited.id == target.id
    assert len([item for item in handle.objects.list(model) if item.id == target.id]) == 1
    assert not hasattr(edited, "version"), f"{model.__name__} grew a version number"
    assert decision.disposition is ReviewDisposition.EDIT
    assert decision.subject_id == target.id


def test_every_reviewer_action_leaves_a_decision(reviewed: Any) -> None:
    """`agent-design.md` section 9's list, walked. Section 2.5's requirement is that the *action*
    is recorded, not that the object remembers it, so the count of decisions is the assertion."""
    handle, ledger = reviewed
    index = EvidenceIndex(handle)

    apply_edit(
        handle,
        component(handle, "Webhook Receiver"),
        {"description": "Edited."},
        reviewer_id=REVIEWER,
    )
    decide_object(
        handle,
        component(handle, "Analysis Worker"),
        ReviewDisposition.APPROVE,
        reviewer_id=REVIEWER,
    )
    decide_object(
        handle, handle.objects.list(Actor)[0], ReviewDisposition.REJECT, reviewer_id=REVIEWER
    )
    add_context_object(
        handle,
        Component,
        {"name": "Managed Redis Queue", "component_type": "managed_cache"},
        reviewer_id=REVIEWER,
    )
    confirm_assumption(handle, claim(handle, "processing_region"), reviewer_id=REVIEWER)
    resolve_contradiction(
        handle,
        handle.objects.list(SourceObservation)[0],
        resolution="30 days",
        rationale="The operations guide is authoritative.",
        reviewer_id=REVIEWER,
    )
    answer_question(
        handle, handle.objects.list(Question)[0], response="Yes, HMAC.", reviewer_id=REVIEWER
    )
    attach_evidence(
        handle,
        claim(handle, "request_validation"),
        [evidence_ids(handle)[5]],
        index=index,
        reviewer_id=REVIEWER,
    )
    approve_context(
        handle, package_for(handle), reviewer_id=REVIEWER, workflow_run_id=ledger.run.id
    )

    decisions = handle.objects.list(ReviewerDecision)
    assert len(decisions) == 10, "one action produced no record"
    assert all(decision.reviewer_id == REVIEWER for decision in decisions)
    assert {decision.disposition for decision in decisions} == {
        ReviewDisposition.EDIT,
        ReviewDisposition.APPROVE,
        ReviewDisposition.REJECT,
    }
