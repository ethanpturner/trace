"""The finding review file: checkpoint 2 as a document a person edits and hands back (#351).

The context checkpoint's pattern (`services/context/review_file.py`), applied to findings. The
same three properties carry over, because they are what make the format safe:

**The file is derived, exactly like the review package** (`data-model.md` section 31). It is
written on export and read on apply; nothing stores it, and nothing reads it back to
reconstruct state.

**Applying a file produces the same `ReviewerDecision` rows as the equivalent flags**, because
both call the same functions in `workflow/finding_review.py`. The file is a way of *saying*
what to do, not a second implementation of doing it — which is what makes every action in that
module's reviewer set reachable from the command line without a flag per field.

**An unchanged file applies nothing.** Every action is a difference from what was exported — a
`decision:` filled in, a severity changed from the exported value, a conversion block given
content — so exporting and reapplying without editing writes no rows.

One structural difference from the context file: a finding entry can carry a **conversion**
(DEC-051's escape hatches) or a **decision**, never both. A conversion supersedes the finding,
and a decision recorded against a superseded object would be a judgment about something no
longer under review; the file refuses the combination rather than ordering it.
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, Any

import yaml

from trace_ai.domain.enums import ReviewDisposition, RiskTreatment, Severity
from trace_ai.domain.finding import Finding
from trace_ai.domain.question import QuestionPriority
from trace_ai.workflow.context_review import ReviewerActionError
from trace_ai.workflow.finding_review import (
    add_remediation_guidance,
    add_reviewer_rationale,
    approve_finding,
    assign_risk_treatment,
    change_severity,
    convert_to_documentation_gap,
    convert_to_question,
    defer_finding,
    edit_finding,
    merge_by_reviewer,
    reject_finding,
    request_more_analysis,
)

if TYPE_CHECKING:
    from trace_ai.domain.reviewer_decision import ReviewerDecision
    from trace_ai.services.assessment import AssessmentHandle
    from trace_ai.services.findings.review_package import FindingReviewPackage

__all__ = [
    "FINDING_EDITABLE_FIELDS",
    "FindingReviewFileError",
    "apply_finding_review_file",
    "export_finding_review_file",
    "read_finding_review_file",
    "write_finding_review_file",
]

# What a reviewer may change by editing the file. `recommendation` routes through
# `add_remediation_guidance` — the action with the non-empty rule — rather than a bare edit.
FINDING_EDITABLE_FIELDS: tuple[str, ...] = ("title", "description", "recommendation")

# The dispositions a reviewer may write into the `decision:` slot. `edit` is absent because an
# edit is expressed by changing a field; the conversions are absent because each has its own
# block carrying the content the conversion needs.
_DECISIONS = {
    ReviewDisposition.APPROVE.value,
    ReviewDisposition.REJECT.value,
    ReviewDisposition.DEFER.value,
    ReviewDisposition.REQUEST_MORE_ANALYSIS.value,
}

_HEADER = """\
# Finding review
#
# Fill in `decision:` with `approve`, `reject`, `defer`, or `request_more_analysis` (the last
# requires `rationale:` — a request carrying no feedback is a repetition). Change `severity:`
# to assign one; approval requires it (DEC-030). Change `treatment:` (and its rationale and
# review-by date) to assign a risk treatment — `accept` requires the rationale to approve.
# Edit any field under `editable:`. Write under `reviewer_rationale:` to append reviewer notes.
#
# To reclassify instead of deciding, fill exactly one conversion block: `convert_to_question:`
# (question and rationale required) or `convert_to_documentation_gap:` (importance and severity
# required). A converted finding takes no `decision:`.
#
# To merge duplicates the automatic rule did not catch, add an entry under `merges:` naming the
# `survivor:`, the `merged:` list, and a `rationale:` (required — the stated reason is the whole
# explanation, DEC-054). Merges apply before everything else.
#
# Leave anything you have no view on exactly as it is: an unchanged entry applies nothing.
"""


class FindingReviewFileError(ValueError):
    """A review file the application will not apply, with the reason named."""


def export_finding_review_file(package: FindingReviewPackage) -> dict[str, Any]:
    """The editable document for one checkpoint-2 package."""
    document: dict[str, Any] = {
        "assessment_id": package.assessment_id,
        "reviewer": None,
    }
    document["findings"] = [
        {
            "id": item.finding.id,
            "title": item.finding.title,
            "validation_status": item.finding.validation_status.value,
            "severity": item.finding.severity.value,
            "decision": None,
            "rationale": None,
            "override_rationale": None,
            "reviewer_rationale": None,
            "treatment": item.finding.risk_treatment.value,
            "treatment_rationale": item.finding.treatment_rationale,
            "treatment_review_by": (
                item.finding.treatment_review_by.isoformat()
                if item.finding.treatment_review_by
                else None
            ),
            "editable": {
                field: item.finding.model_dump(mode="json")[field]
                for field in FINDING_EDITABLE_FIELDS
            },
            "convert_to_question": {
                "question": None,
                "rationale": None,
                "priority": QuestionPriority.MEDIUM.value,
                "blocking": False,
            },
            "convert_to_documentation_gap": {
                "importance": None,
                "severity": None,
                "requested_evidence": [],
            },
        }
        for item in package.findings
    ]
    document["merges"] = []
    return document


def write_finding_review_file(package: FindingReviewPackage) -> str:
    """The exported document as YAML, with the instructions a reviewer needs at the top."""
    body = yaml.safe_dump(
        export_finding_review_file(package), sort_keys=False, allow_unicode=True, width=100
    )
    return f"{_HEADER}\n{body}"


def read_finding_review_file(text: str) -> dict[str, Any]:
    """Parse an edited file, refusing anything that is not the document this module writes."""
    loaded: Any = yaml.safe_load(text)
    if not isinstance(loaded, dict):
        raise FindingReviewFileError("a review file is a mapping; this parsed as something else")
    if "assessment_id" not in loaded:
        raise FindingReviewFileError(
            "this file names no assessment. Export one with `trace findings review --export`."
        )
    return loaded


def apply_finding_review_file(
    handle: AssessmentHandle,
    document: dict[str, Any],
    *,
    reviewer_id: str,
    workflow_run_id: str | None = None,
) -> list[ReviewerDecision]:
    """Apply an edited file, returning the decisions it produced in the order it produced them.

    Merges apply first — a decision should land on the survivor, not on a finding about to be
    marked a duplicate. Within each finding the order is: severity, treatment, edits, reviewer
    rationale, then the conversion or the decision. Content changes land before the judgment
    about the content, for the context file's reason: deciding first would record a judgment
    about the version the reviewer replaced.
    """
    if document.get("assessment_id") != handle.assessment_id:
        raise FindingReviewFileError(
            f"this file is for {document.get('assessment_id')}, not {handle.assessment_id}. "
            f"Applying it would record one reviewer's decisions against another assessment."
        )

    decisions: list[ReviewerDecision] = []

    for entry in document.get("merges") or []:
        survivor = str(entry.get("survivor") or "")
        merged = [str(identifier) for identifier in entry.get("merged") or []]
        rationale = str(entry.get("rationale") or "")
        if not survivor or not merged:
            raise FindingReviewFileError(
                "a merge entry names a survivor and at least one merged finding"
            )
        try:
            _, _, merge_decisions = merge_by_reviewer(
                handle,
                survivor,
                merged,
                reviewer_id=reviewer_id,
                rationale=rationale,
                workflow_run_id=workflow_run_id,
            )
        except ReviewerActionError as refused:
            raise FindingReviewFileError(f"merge into {survivor}: {refused}") from None
        decisions.extend(merge_decisions)

    findings = {finding.id: finding for finding in handle.objects.list(Finding)}
    for entry in document.get("findings") or []:
        decisions.extend(
            _apply_finding_entry(
                handle,
                entry,
                findings,
                reviewer_id=reviewer_id,
                workflow_run_id=workflow_run_id,
            )
        )
    return decisions


def _filled(block: dict[str, Any] | None, *fields: str) -> bool:
    """Whether a conversion block carries content in any of the named fields."""
    if not block:
        return False
    return any(
        value is not None and value != [] and str(value).strip() != ""
        for value in (block.get(field) for field in fields)
    )


def _apply_finding_entry(
    handle: AssessmentHandle,
    entry: dict[str, Any],
    findings: dict[str, Finding],
    *,
    reviewer_id: str,
    workflow_run_id: str | None,
) -> list[ReviewerDecision]:
    identifier = str(entry.get("id") or "")
    finding = findings.get(identifier)
    if finding is None:
        raise FindingReviewFileError(f"{identifier} is not a finding in this assessment")

    produced: list[ReviewerDecision] = []
    rationale = str(entry.get("rationale") or "").strip() or None

    try:
        # -- severity: a changed value assigns one (DEC-030).
        severity = entry.get("severity")
        if severity and str(severity) != finding.severity.value:
            finding, decision = change_severity(
                handle,
                finding,
                Severity(str(severity)),
                reviewer_id=reviewer_id,
                rationale=rationale,
                workflow_run_id=workflow_run_id,
            )
            produced.append(decision)

        # -- treatment: any of the three fields differing assigns the treatment as a whole.
        treatment = entry.get("treatment")
        treatment_rationale = entry.get("treatment_rationale") or None
        review_by_raw = entry.get("treatment_review_by") or None
        review_by = date.fromisoformat(str(review_by_raw)) if review_by_raw else None
        if treatment and (
            str(treatment) != finding.risk_treatment.value
            or treatment_rationale != finding.treatment_rationale
            or review_by != finding.treatment_review_by
        ):
            finding, decision = assign_risk_treatment(
                handle,
                finding,
                RiskTreatment(str(treatment)),
                rationale=treatment_rationale,
                review_by=review_by,
                reviewer_id=reviewer_id,
                workflow_run_id=workflow_run_id,
            )
            produced.append(decision)

        # -- edits: title and description directly; recommendation through the guidance action.
        editable = entry.get("editable") or {}
        changes = {
            field: value
            for field, value in editable.items()
            if field in ("title", "description")
            and finding.model_dump(mode="json").get(field) != value
        }
        if changes:
            finding, decision = edit_finding(
                handle,
                finding,
                changes,
                reviewer_id=reviewer_id,
                rationale=rationale,
                workflow_run_id=workflow_run_id,
            )
            produced.append(decision)
        guidance = editable.get("recommendation")
        if guidance is not None and str(guidance) != finding.recommendation:
            finding, decision = add_remediation_guidance(
                handle,
                finding,
                str(guidance),
                reviewer_id=reviewer_id,
                rationale=rationale,
                workflow_run_id=workflow_run_id,
            )
            produced.append(decision)

        # -- reviewer rationale: appended, so any non-empty text is an action.
        reviewer_note = (entry.get("reviewer_rationale") or "").strip()
        if reviewer_note:
            finding, decision = add_reviewer_rationale(
                handle,
                finding,
                reviewer_note,
                reviewer_id=reviewer_id,
                workflow_run_id=workflow_run_id,
            )
            produced.append(decision)

        # -- conversion or decision, never both (module docstring).
        question_block = entry.get("convert_to_question")
        gap_block = entry.get("convert_to_documentation_gap")
        wants_question = _filled(question_block, "question", "rationale")
        wants_gap = _filled(gap_block, "importance", "severity", "requested_evidence")
        disposition = entry.get("decision")

        if (wants_question or wants_gap) and disposition:
            raise FindingReviewFileError(
                f"{identifier} carries both a conversion and a decision. A conversion "
                f"supersedes the finding, so decide it or convert it, not both."
            )
        if wants_question and wants_gap:
            raise FindingReviewFileError(
                f"{identifier} fills both conversion blocks. A finding becomes a question or "
                f"a gap, not both."
            )

        if wants_question:
            block = question_block or {}
            question_text = str(block.get("question") or "").strip()
            question_rationale = str(block.get("rationale") or "").strip()
            if not question_text or not question_rationale:
                raise FindingReviewFileError(
                    f"{identifier}: a conversion to a question needs both the question and "
                    f"its rationale"
                )
            _, _, decision = convert_to_question(
                handle,
                finding,
                question=question_text,
                question_rationale=question_rationale,
                priority=QuestionPriority(str(block.get("priority") or "medium")),
                blocking=bool(block.get("blocking")),
                reviewer_id=reviewer_id,
                rationale=rationale,
                workflow_run_id=workflow_run_id,
            )
            produced.append(decision)
            findings[identifier] = finding
            return produced

        if wants_gap:
            block = gap_block or {}
            importance = str(block.get("importance") or "").strip()
            gap_severity = str(block.get("severity") or "").strip()
            if not importance or not gap_severity:
                raise FindingReviewFileError(
                    f"{identifier}: a conversion to a documentation gap needs importance and "
                    f"a severity for the gap (DEC-045)"
                )
            _, _, decision = convert_to_documentation_gap(
                handle,
                finding,
                importance=importance,
                severity=Severity(gap_severity),
                requested_evidence=[str(item) for item in block.get("requested_evidence") or []],
                reviewer_id=reviewer_id,
                rationale=rationale,
                workflow_run_id=workflow_run_id,
            )
            produced.append(decision)
            findings[identifier] = finding
            return produced

        if disposition:
            if disposition not in _DECISIONS:
                raise FindingReviewFileError(
                    f"{identifier}: {disposition!r} is not a decision. Write one of "
                    f"{', '.join(sorted(_DECISIONS))}, fill a conversion block, or edit a "
                    f"field to record a change."
                )
            if disposition == ReviewDisposition.APPROVE.value:
                override = (entry.get("override_rationale") or "").strip() or None
                finding, decision = approve_finding(
                    handle,
                    finding,
                    reviewer_id=reviewer_id,
                    rationale=rationale,
                    override_rationale=override,
                    workflow_run_id=workflow_run_id,
                )
            elif disposition == ReviewDisposition.REJECT.value:
                finding, decision = reject_finding(
                    handle,
                    finding,
                    reviewer_id=reviewer_id,
                    rationale=rationale,
                    workflow_run_id=workflow_run_id,
                )
            elif disposition == ReviewDisposition.DEFER.value:
                finding, decision = defer_finding(
                    handle,
                    finding,
                    reviewer_id=reviewer_id,
                    rationale=rationale,
                    workflow_run_id=workflow_run_id,
                )
            else:
                finding, decision = request_more_analysis(
                    handle,
                    finding,
                    reviewer_id=reviewer_id,
                    rationale=rationale or "",
                    workflow_run_id=workflow_run_id,
                )
            produced.append(decision)
    except ReviewerActionError as refused:
        raise FindingReviewFileError(f"{identifier}: {refused}") from None

    findings[identifier] = finding
    return produced
