"""Checkpoint 2: the finding-approval checkpoint and the reviewer's actions (DEC-054).

The machinery is the shared `CheckpointNode` (DEC-005, DEC-017): the node waits on the state's
provisional findings, advances only when every one has a `ReviewerDecision`, pauses by persisting
the run and letting the process exit, and resumes as a read in a new process. Nothing here adds a
flag, consults configuration, or offers a second path past an undecided finding.

**The eleven section 18 actions are functions here, recorded as seven dispositions.** Approve,
reject, defer, request more analysis, and the two conversions each map to their disposition. The
rest are recorded as what they do: a severity change, a reviewer rationale, and remediation
guidance are `edit`s carrying the delta (DEC-023, DEC-030), and a merge is an `edit` per merged
finding plus the same `FindingMergeRecord` the automatic path writes (DEC-052, DEC-054) — there
is deliberately no `merge` disposition, for the reason there is no `change_severity` one:
section 18 names actions a reviewer takes, section 4.6 names dispositions the system records,
and the two do not correspond one to one.

**Two approvals are refused by rule.** A finding still carrying `severity: unassigned` — the
reviewer assigns severity here and approval without one would let reviewer-assigned severity
degrade into nobody assigning it (DEC-030) — and a finding already merged into a survivor, whose
canonical finding is the one to decide.

**Approving nothing is a valid outcome.** A reviewer who rejects every candidate has decided
every candidate; the checkpoint completes and the report proceeds with an empty approved set.
Quality over finding volume is a constraint on this node as much as on consolidation.

**Reviewer identity is DEC-023's local string.** Every decision carries `reviewer_id`; there is
no authentication, role, or tenancy to consult (DEC-004), and nothing here pretends otherwise.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Final

from trace_ai.domain.base import now
from trace_ai.domain.conversions import finding_to_documentation_gap, finding_to_question
from trace_ai.domain.enums import ObjectStatus, ReviewDisposition, RiskTreatment, Severity
from trace_ai.domain.execution import ExecutionType
from trace_ai.domain.finding import Finding
from trace_ai.domain.finding_merge_record import MERGE_FEATURES, MergeDecision
from trace_ai.domain.outcomes import FINDING_VALIDATION_STATUSES
from trace_ai.domain.reviewer_decision import ReviewerDecision
from trace_ai.services.findings.fingerprints import (
    component_name_index,
    fingerprinted_finding,
    fingerprinted_gap,
    gap_identity_indexes,
)
from trace_ai.workflow.checkpoint import CheckpointNode, decided_in_run, decided_object_ids
from trace_ai.workflow.context_review import ReviewerActionError
from trace_ai.workflow.finding_dedup import DuplicateGroup, merge_findings, shared_features
from trace_ai.workflow.phases import Phase

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import date, datetime

    from trace_ai.domain.assessment import Assessment
    from trace_ai.domain.documentation_gap import DocumentationGap
    from trace_ai.domain.finding_merge_record import FindingMergeRecord
    from trace_ai.domain.question import Question, QuestionPriority
    from trace_ai.services.assessment import AssessmentHandle, AssessmentService
    from trace_ai.workflow.nodes import NodeContext, NodeResult

__all__ = [
    "FindingReviewNode",
    "add_remediation_guidance",
    "add_reviewer_rationale",
    "approve_finding",
    "assign_risk_treatment",
    "change_severity",
    "conclude_finding_review",
    "convert_to_documentation_gap",
    "convert_to_question",
    "defer_finding",
    "edit_finding",
    "finding_review_subjects",
    "merge_by_reviewer",
    "reject_finding",
    "request_more_analysis",
]

# What `generated_by` records on objects the reviewer's conversions create.
GENERATED_BY: Final = "human-finding-review-v1"


def finding_review_subjects(context: NodeContext) -> list[str]:
    """What checkpoint 2 waits on: the provisional findings, in presentation order.

    Read from the state rather than the store, because the state is what the run carries across
    the pause (DEC-017) and a resumed invocation must wait on the same list the paused one named.
    Gaps and questions are shown at this checkpoint and are not subjects: the completion
    condition is a decision per provisional finding, and a question is answered, not decided.
    """
    return list(context.state.candidate_finding_ids)


@dataclass(slots=True)
class FindingReviewNode:
    """Checkpoint 2 as a workflow node: the shared checkpoint over the provisional findings.

    Unlike checkpoint 1 there is no baseline object to gate on — the whole condition is a
    `ReviewerDecision` per subject, which the shared node already is. The wrapper exists so the
    phase registry's `human-finding-review` names a node, and so the metadata says which
    checkpoint this is.
    """

    version: str = "0.1"
    checkpoint: CheckpointNode = field(init=False, repr=False)
    execution_type: ExecutionType = field(default=ExecutionType.HUMAN_CHECKPOINT, init=False)

    def __post_init__(self) -> None:
        self.checkpoint = CheckpointNode(
            checkpoint_type=Phase.HUMAN_FINDING_REVIEW,
            subjects=finding_review_subjects,
            version=self.version,
        )

    @property
    def name(self) -> str:
        return self.checkpoint.name

    @property
    def phase(self) -> Phase:
        return Phase.HUMAN_FINDING_REVIEW

    def run(self, context: NodeContext) -> NodeResult:
        return self.checkpoint.run(context)


# ------------------------------------------------------------------------------------------
# Shared plumbing: one decision writer, whatever the caller (DEC-017)
# ------------------------------------------------------------------------------------------


def _edited(finding: Finding, changes: dict[str, Any], at: datetime) -> Finding:
    """The finding with `changes` applied, built through the schema (DEC-023).

    `model_validate`, never `model_copy`: this is the path a human-supplied value enters a domain
    object, so it is the one that least tolerates skipping the schema.
    """
    return Finding.model_validate({**finding.model_dump(), **changes, "updated_at": at})


def _decision_about(
    handle: AssessmentHandle,
    finding: Finding,
    *,
    disposition: ReviewDisposition,
    reviewer_id: str,
    rationale: str | None,
    workflow_run_id: str | None,
    at: datetime,
) -> ReviewerDecision:
    return ReviewerDecision.model_validate(
        {
            "id": handle.objects.allocate("dec"),
            "assessment_id": finding.assessment_id,
            "subject_type": "finding",
            "subject_id": finding.id,
            "disposition": disposition,
            "rationale": rationale,
            "reviewer_id": reviewer_id,
            "created_at": at,
            "workflow_run_id": workflow_run_id,
        }
    )


def _decide(
    handle: AssessmentHandle,
    finding: Finding,
    *,
    status: ObjectStatus,
    disposition: ReviewDisposition,
    reviewer_id: str,
    rationale: str | None,
    workflow_run_id: str | None,
    at: datetime | None,
) -> tuple[Finding, ReviewerDecision]:
    stamp = at if at is not None else now()
    decided = _edited(finding, {"status": status}, stamp)
    with handle.objects.transaction() as repository:
        decision = _decision_about(
            handle,
            decided,
            disposition=disposition,
            reviewer_id=reviewer_id,
            rationale=rationale,
            workflow_run_id=workflow_run_id,
            at=stamp,
        )
        repository.save(decided)
        repository.save(decision)
    return decided, decision


# The validation statuses under which an approval needs no override: the evidence carries the
# conclusion (data-model.md section 21, DEC-013). Derived from the same table `Finding` consults,
# not restated.
_CARRIED: Final = FINDING_VALIDATION_STATUSES


def approve_finding(
    handle: AssessmentHandle,
    finding: Finding,
    *,
    reviewer_id: str,
    rationale: str | None = None,
    override_rationale: str | None = None,
    workflow_run_id: str | None = None,
    at: datetime | None = None,
) -> tuple[Finding, ReviewerDecision]:
    """Approve one provisional finding — the only path to `approved` anywhere (DEC-005).

    The deterministic gate (DEC-055) enforces data-model section 21's approved-finding
    conditions here, the last enforcement point before the conclusion becomes official:

    - **Severity is assigned** (DEC-030). Refused outright; assign through `change_severity`.
    - **The finding is canonical.** A duplicate merged into a survivor is refused outright.
    - **The evidence carries the conclusion.** A `validation_status` outside `supported` and
      `partially_supported` — unreachable through the schema, and the gate does not assume the
      schema was upstream of every caller — is approvable only with an explicit
      `override_rationale`, recorded on the decision with an `override:` prefix so overrides
      stay retrievable. The silent path is refused.
    - **The remediation is actionable.** No recommendation and no acceptance criteria is refused
      outright, as is a finding citing no evidence — a finding indistinguishable from a
      documentation gap must not become official as one (DEC-009).
    """
    if finding.severity is Severity.UNASSIGNED:
        raise ReviewerActionError(
            f"{finding.id} carries severity 'unassigned' and cannot be approved (DEC-030). "
            f"The reviewer assigns severity at this checkpoint; change it first, then approve."
        )
    if finding.risk_treatment is RiskTreatment.ACCEPT and not (
        finding.treatment_rationale and finding.treatment_rationale.strip()
    ):
        raise ReviewerActionError(
            f"{finding.id} accepts its risk with no treatment_rationale and cannot be approved "
            f"(DEC-060). An accepted risk records the residual-risk statement: what remains "
            f"exposed and why that is tolerable. Assign the rationale, then approve. Every other "
            f"treatment, and an undecided one, approves without it."
        )
    if finding.duplicate_of_id is not None:
        raise ReviewerActionError(
            f"{finding.id} was merged into {finding.duplicate_of_id}; the canonical finding is "
            f"the one to approve. A duplicate approved alongside its survivor would be the same "
            f"conclusion reported twice."
        )
    if not finding.evidence_ids:
        raise ReviewerActionError(
            f"{finding.id} cites no evidence and cannot be approved. A finding that rests on "
            f"nothing quotable is indistinguishable from a documentation gap, and approving it "
            f"would collapse the DEC-009 separation at the last place it is enforced."
        )
    if not finding.recommendation.strip() and not finding.acceptance_criteria:
        raise ReviewerActionError(
            f"{finding.id} carries no recommendation and no acceptance criteria. An approved "
            f"finding requires actionable remediation or acceptance criteria (data-model.md "
            f"section 21); add one through the edit actions, then approve."
        )

    decision_rationale = rationale
    if finding.validation_status not in _CARRIED:
        if not override_rationale or not override_rationale.strip():
            raise ReviewerActionError(
                f"{finding.id} has validation_status {finding.validation_status.value!r}, which "
                f"the evidence does not carry, and cannot be approved silently. Approving it "
                f"anyway requires an explicit override_rationale, which is recorded on the "
                f"ReviewerDecision (DEC-055)."
            )
        decision_rationale = f"override: {override_rationale.strip()}"

    return _decide(
        handle,
        finding,
        status=ObjectStatus.APPROVED,
        disposition=ReviewDisposition.APPROVE,
        reviewer_id=reviewer_id,
        rationale=decision_rationale,
        workflow_run_id=workflow_run_id,
        at=at,
    )


def conclude_finding_review(service: AssessmentService, assessment_id: str) -> Assessment:
    """Move the assessment forward once every provisional finding has a decision.

    The transition is `AssessmentService.resume_from_review` — the existing named verb for
    "every pending object has a `ReviewerDecision`; the run continues" (DEC-017, DEC-031). The
    assessment returns to `draft` and the run proceeds to report generation; `approve` stays
    the pipeline-completion verb and is not this function's to call. It refuses while any
    provisional finding lacks a decision, which is the checkpoint's completion condition
    restated where the deliverable's lifecycle advances.
    """
    from trace_ai.domain.base import now
    from trace_ai.domain.execution import WorkflowRun
    from trace_ai.workflow.reason_codes import revisit_due_findings

    handle = service.handle(assessment_id)
    provisional = [
        finding
        for finding in handle.objects.list(Finding, status=ObjectStatus.CANDIDATE.value)
        if finding.duplicate_of_id is None
    ]
    # DEC-061/DEC-079: an expired accepted-risk finding is a subject this run too, and "decided" is
    # the current run's decision — so an approval carried from a prior run does not conclude it. The
    # subjects and the scoping match the checkpoint node's, or the two would disagree about done.
    runs = handle.objects.list(WorkflowRun)
    subjects = {finding.id for finding in provisional} | revisit_due_findings(handle, now().date())
    decided = decided_in_run(handle, runs[-1].id) if runs else decided_object_ids(handle)
    undecided = sorted(subjects - decided)
    if undecided:
        raise ReviewerActionError(
            f"the finding checkpoint is not complete: {undecided} await a ReviewerDecision. "
            f"The assessment advances when every provisional finding has one (DEC-005)."
        )
    return service.resume_from_review(assessment_id)


def reject_finding(
    handle: AssessmentHandle,
    finding: Finding,
    *,
    reviewer_id: str,
    rationale: str | None = None,
    workflow_run_id: str | None = None,
    at: datetime | None = None,
) -> tuple[Finding, ReviewerDecision]:
    """Reject one provisional finding. Retained, never deleted (section 18)."""
    return _decide(
        handle,
        finding,
        status=ObjectStatus.REJECTED,
        disposition=ReviewDisposition.REJECT,
        reviewer_id=reviewer_id,
        rationale=rationale,
        workflow_run_id=workflow_run_id,
        at=at,
    )


def edit_finding(
    handle: AssessmentHandle,
    finding: Finding,
    changes: dict[str, Any],
    *,
    reviewer_id: str,
    rationale: str | None = None,
    workflow_run_id: str | None = None,
    at: datetime | None = None,
) -> tuple[Finding, ReviewerDecision]:
    """Edit a finding in place and record the delta (DEC-023).

    The decision's `prior_value` holds the generated values of exactly the changed fields, so
    the original is recoverable after the object has moved on, and reviewer edit rate stays
    computable per field. The delta is captured by `ReviewerDecision.capture_edit`, which takes
    both states — a call site cannot record that nothing changed.

    An edit that changes an identity field — the cited requirements or the affected components —
    recomputes `content_fingerprint`, because it is then a claim about different ground (DEC-066).
    Every other edit leaves the fingerprint alone, and the recomputation lands in the captured
    delta like any other consequence of the edit, so an identity change is itself observable.
    """
    stamp = at if at is not None else now()
    edited = _edited(finding, changes, stamp)
    if (edited.requirement_ids, edited.affected_component_ids) != (
        finding.requirement_ids,
        finding.affected_component_ids,
    ):
        edited = fingerprinted_finding(edited, component_name_index(handle))
    with handle.objects.transaction() as repository:
        decision = ReviewerDecision.capture_edit(
            decision_id=repository.allocate("dec"),
            before=finding,
            after=edited,
            subject_type="finding",
            subject_id=finding.id,
            created_at=stamp,
            rationale=rationale,
            reviewer_id=reviewer_id,
            workflow_run_id=workflow_run_id,
        )
        repository.save(edited)
        repository.save(decision)
    return edited, decision


def change_severity(
    handle: AssessmentHandle,
    finding: Finding,
    severity: Severity,
    *,
    reviewer_id: str,
    rationale: str | None = None,
    workflow_run_id: str | None = None,
    at: datetime | None = None,
) -> tuple[Finding, ReviewerDecision]:
    """Assign or change severity — an `edit`, not a disposition of its own (DEC-030).

    Assigning back to `unassigned` is refused: it would un-decide the one field approval
    requires, and no step after this one would ever supply it again.
    """
    if severity is Severity.UNASSIGNED:
        raise ReviewerActionError(
            f"severity cannot be set back to 'unassigned' on {finding.id}. The reviewer is the "
            f"only step that assigns it (DEC-030); unassigning it here leaves a field nothing "
            f"downstream will ever fill."
        )
    return edit_finding(
        handle,
        finding,
        {"severity": severity},
        reviewer_id=reviewer_id,
        rationale=rationale,
        workflow_run_id=workflow_run_id,
        at=at,
    )


def assign_risk_treatment(
    handle: AssessmentHandle,
    finding: Finding,
    treatment: RiskTreatment,
    *,
    rationale: str | None = None,
    review_by: date | None = None,
    reviewer_id: str,
    workflow_run_id: str | None = None,
    at: datetime | None = None,
) -> tuple[Finding, ReviewerDecision]:
    """Assign the reviewer's risk treatment — an `edit`, not a disposition of its own (DEC-060).

    The neighbouring judgment to severity, and recorded the same way (DEC-023, DEC-030): the delta
    carries the change, no `ReviewDisposition` value is added. The accept-needs-a-rationale rule
    belongs to the approval gate, not here — a reviewer may set `accept` and supply the
    residual-risk statement in the same call or a later one, and the approval is refused until it
    is present, exactly as an unassigned severity refuses approval without blocking assignment.
    """
    changes: dict[str, Any] = {"risk_treatment": treatment}
    if rationale is not None:
        changes["treatment_rationale"] = rationale
    if review_by is not None:
        changes["treatment_review_by"] = review_by
    return edit_finding(
        handle,
        finding,
        changes,
        reviewer_id=reviewer_id,
        rationale=rationale,
        workflow_run_id=workflow_run_id,
        at=at,
    )


def add_reviewer_rationale(
    handle: AssessmentHandle,
    finding: Finding,
    rationale: str,
    *,
    reviewer_id: str,
    workflow_run_id: str | None = None,
    at: datetime | None = None,
) -> tuple[Finding, ReviewerDecision]:
    """Record the reviewer's explanation on the finding — an `edit` of `reviewer_notes`."""
    if not rationale.strip():
        raise ReviewerActionError("a reviewer rationale says something or it is not one")
    combined = f"{finding.reviewer_notes}\n{rationale}" if finding.reviewer_notes else rationale
    return edit_finding(
        handle,
        finding,
        {"reviewer_notes": combined},
        reviewer_id=reviewer_id,
        rationale=rationale,
        workflow_run_id=workflow_run_id,
        at=at,
    )


def add_remediation_guidance(
    handle: AssessmentHandle,
    finding: Finding,
    guidance: str,
    *,
    reviewer_id: str,
    rationale: str | None = None,
    workflow_run_id: str | None = None,
    at: datetime | None = None,
) -> tuple[Finding, ReviewerDecision]:
    """Replace the recommendation with the reviewer's — an `edit`, with the original recoverable
    from `prior_value` (section 2.5: recorded, therefore not silent)."""
    if not guidance.strip():
        raise ReviewerActionError("remediation guidance says what to do or it is not guidance")
    return edit_finding(
        handle,
        finding,
        {"recommendation": guidance},
        reviewer_id=reviewer_id,
        rationale=rationale,
        workflow_run_id=workflow_run_id,
        at=at,
    )


def defer_finding(
    handle: AssessmentHandle,
    finding: Finding,
    *,
    reviewer_id: str,
    rationale: str | None = None,
    workflow_run_id: str | None = None,
    at: datetime | None = None,
) -> tuple[Finding, ReviewerDecision]:
    """Defer the decision. The finding stays a candidate; the deferral is the record."""
    stamp = at if at is not None else now()
    with handle.objects.transaction() as repository:
        decision = _decision_about(
            handle,
            finding,
            disposition=ReviewDisposition.DEFER,
            reviewer_id=reviewer_id,
            rationale=rationale,
            workflow_run_id=workflow_run_id,
            at=stamp,
        )
        repository.save(decision)
    return finding, decision


def request_more_analysis(
    handle: AssessmentHandle,
    finding: Finding,
    *,
    reviewer_id: str,
    rationale: str,
    workflow_run_id: str | None = None,
    at: datetime | None = None,
) -> tuple[Finding, ReviewerDecision]:
    """Ask for more analysis, with the reason. A request carrying no feedback is a repetition
    (`agent-design.md` section 26), so `rationale` is required here."""
    if not rationale.strip():
        raise ReviewerActionError(
            "a request for more analysis must say what is missing. A repeated attempt carries "
            "feedback or it is a repetition (agent-design.md section 26)."
        )
    stamp = at if at is not None else now()
    with handle.objects.transaction() as repository:
        decision = _decision_about(
            handle,
            finding,
            disposition=ReviewDisposition.REQUEST_MORE_ANALYSIS,
            reviewer_id=reviewer_id,
            rationale=rationale,
            workflow_run_id=workflow_run_id,
            at=stamp,
        )
        repository.save(decision)
    return finding, decision


def convert_to_question(
    handle: AssessmentHandle,
    finding: Finding,
    *,
    question: str,
    question_rationale: str,
    priority: QuestionPriority,
    blocking: bool,
    reviewer_id: str,
    rationale: str | None = None,
    workflow_run_id: str | None = None,
    at: datetime | None = None,
) -> tuple[Question, Finding, ReviewerDecision]:
    """Reclassify a finding as the question that would settle it (DEC-051's helper, recorded).

    The DEC-009 escape hatch in one direction: a conclusion whose answer is obtainable becomes
    the request for that answer, the source is superseded and retrievable, and the decision
    carries the disposition.
    """
    stamp = at if at is not None else now()
    with handle.objects.transaction() as repository:
        asked, superseded = finding_to_question(
            finding,
            question_id=repository.allocate("qst"),
            question=question,
            rationale=question_rationale,
            priority=priority,
            blocking=blocking,
            generated_by=GENERATED_BY,
        )
        decision = _decision_about(
            handle,
            superseded,
            disposition=ReviewDisposition.CONVERT_TO_QUESTION,
            reviewer_id=reviewer_id,
            rationale=rationale,
            workflow_run_id=workflow_run_id,
            at=stamp,
        )
        repository.save(asked)
        repository.save(superseded)
        repository.save(decision)
    return asked, superseded, decision


def convert_to_documentation_gap(
    handle: AssessmentHandle,
    finding: Finding,
    *,
    importance: str,
    severity: Severity,
    requested_evidence: Sequence[str] = (),
    reviewer_id: str,
    rationale: str | None = None,
    workflow_run_id: str | None = None,
    at: datetime | None = None,
) -> tuple[DocumentationGap, Finding, ReviewerDecision]:
    """Reclassify a finding as the gap it always was (DEC-051's helper, recorded).

    The severity here rates the gap, not a weakness (DEC-045), and the caller states it — the
    finding's own severity is `unassigned` or rates something else entirely.
    """
    stamp = at if at is not None else now()
    requirement_by_mapping, component_names_by_mapping = gap_identity_indexes(handle)
    with handle.objects.transaction() as repository:
        gap, superseded = finding_to_documentation_gap(
            finding,
            gap_id=repository.allocate("gap"),
            importance=importance,
            severity=severity,
            requested_evidence=requested_evidence,
            generated_by=GENERATED_BY,
        )
        # A conversion creates the gap, and creation is where DEC-066 sets the fingerprint. The
        # converted gap's related identifiers carry the finding's mappings, so the same
        # mapping-based resolution applies.
        gap = fingerprinted_gap(
            gap,
            requirement_by_mapping=requirement_by_mapping,
            component_names_by_mapping=component_names_by_mapping,
        )
        decision = _decision_about(
            handle,
            superseded,
            disposition=ReviewDisposition.CONVERT_TO_DOCUMENTATION_GAP,
            reviewer_id=reviewer_id,
            rationale=rationale,
            workflow_run_id=workflow_run_id,
            at=stamp,
        )
        repository.save(gap)
        repository.save(superseded)
        repository.save(decision)
    return gap, superseded, decision


def _reviewer_group(
    findings: Sequence[Finding], survivor_id: str, merged_ids: Sequence[str]
) -> DuplicateGroup:
    """The reviewer's chosen group, with whatever features actually match recorded honestly.

    Features are computed, not asserted: a reviewer merge may match none (DEC-054), and a record
    claiming features the identifiers do not show would be the traceability failure section 11
    exists to prevent.
    """
    by_id = {finding.id: finding for finding in findings}
    missing = [fid for fid in (survivor_id, *merged_ids) if fid not in by_id]
    if missing:
        raise ReviewerActionError(
            f"{missing} are not findings in this assessment; a merge names findings that exist"
        )

    shared_by_feature: dict[str, set[str]] = {feature: set() for feature in MERGE_FEATURES}
    for merged_id in merged_ids:
        for feature, values in shared_features(by_id[survivor_id], by_id[merged_id]).items():
            shared_by_feature[feature] |= values

    return DuplicateGroup(
        finding_ids=(survivor_id, *merged_ids),
        matched_features=tuple(feature for feature in MERGE_FEATURES if shared_by_feature[feature]),
        shared={
            feature: tuple(sorted(values))
            for feature, values in shared_by_feature.items()
            if values
        },
    )


def merge_by_reviewer(
    handle: AssessmentHandle,
    survivor_id: str,
    merged_ids: Sequence[str],
    *,
    reviewer_id: str,
    rationale: str,
    workflow_run_id: str | None = None,
    at: datetime | None = None,
) -> tuple[list[Finding], FindingMergeRecord, list[ReviewerDecision]]:
    """Merge findings on the reviewer's judgment: the same operation, the same record (DEC-054).

    Reuses `finding_dedup.merge_findings`, so the survivor takes the same unions and the record
    has the same shape as an automated merge, with `decision: reviewer`. The `ReviewerDecision`
    rows are `edit`s carrying the deltas — `duplicate_of_id` on each merged finding, the unions
    on the survivor where they changed — because a merge is recorded as what it does; there is
    deliberately no `merge` disposition (DEC-054, following DEC-030's severity reasoning).

    `rationale` is required: a reviewer merge has no matched-feature rule behind it, so the
    stated reason is the whole explanation the record points to.
    """
    if not rationale.strip():
        raise ReviewerActionError(
            "a reviewer merge states why the findings are one finding. The structural rule's "
            "reason is its features; a reviewer's reason is this rationale (DEC-054)."
        )
    stamp = at if at is not None else now()
    findings = handle.objects.list(Finding)
    group = _reviewer_group(findings, survivor_id, list(merged_ids))
    before = {finding.id: finding for finding in findings}

    with handle.objects.transaction() as repository:
        changed, record = merge_findings(
            findings,
            group,
            record_id=repository.allocate("mrg"),
            decision=MergeDecision.REVIEWER,
            generated_by=GENERATED_BY,
            stamped=stamp,
        )
        # The survivor took the unions, so its identity fields may have widened; the fingerprint
        # follows them (DEC-066). Idempotent on the marked duplicates, whose identity is unchanged.
        names = component_name_index(handle)
        changed = [fingerprinted_finding(finding, names) for finding in changed]
        decisions: list[ReviewerDecision] = []
        for finding in changed:
            repository.save(finding)
            # `updated_at` moves on everything the merge touched; a decision recording only
            # that would be an edit that cannot say what changed.
            if finding.model_dump(exclude={"updated_at"}) == before[finding.id].model_dump(
                exclude={"updated_at"}
            ):
                continue
            decisions.append(
                ReviewerDecision.capture_edit(
                    decision_id=repository.allocate("dec"),
                    before=before[finding.id],
                    after=finding,
                    subject_type="finding",
                    subject_id=finding.id,
                    created_at=stamp,
                    rationale=rationale,
                    reviewer_id=reviewer_id,
                    workflow_run_id=workflow_run_id,
                )
            )
        repository.save(record)
        for decision in decisions:
            repository.save(decision)

    return changed, record, decisions
