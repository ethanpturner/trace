"""Checkpoint 2's review surface: what a conclusion rests on, as structured data first.

`design-principles.md` section 5 requires the review surface to show what a conclusion was
generated from — supporting *and* contradictory evidence, assumptions, confidence, open
questions, and agent critiques — and DEC-005's second checkpoint only preserves reviewer
authority if the reviewer can actually see all of that. This module assembles it. The pause, the
reviewer actions, and the recorded decisions are the checkpoint's (#102), not this module's.

**Structured data first, formatting second** (DEC-032's interface decision). `build` returns
dataclasses over domain objects and `render_markdown` is a separate pass over the result, so the
same package can back the command line, a file round-trip, and a later web view without being
assembled twice. Nothing here calls a model, and the package is derived from the run rather than
stored in it (DEC-017's rule for checkpoint 1, unchanged here).

**Severity assignment is a first-class part of the surface** (DEC-030). Findings arrive carrying
`unassigned` and may not be approved that way, so the package says which findings await a
severity rather than leaving it one field among thirty.

**A zero-finding assessment is presented as a result, not a failure.** "Quality over finding
volume" is a binding constraint, and the summary states in words that no findings were proposed
— an empty section with no sentence reads as something having gone wrong, which is exactly the
pressure toward finding-count this project refuses.

**Gaps are shown beside findings, visibly distinct.** The reviewer is the last chance to catch a
DEC-009 misclassification that survived consolidation, in either direction, and catching one
requires seeing both kinds on one surface with the distinction stated.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, ClassVar

from trace_ai.domain.catalog_gap_candidate import CatalogGapCandidate
from trace_ai.domain.control_mapping import ControlMapping
from trace_ai.domain.critique import Critique
from trace_ai.domain.documentation_gap import DocumentationGap
from trace_ai.domain.enums import ObjectStatus, Severity
from trace_ai.domain.evidence_assessment import EvidenceAssessment, SubjectType
from trace_ai.domain.finding import Finding
from trace_ai.domain.question import Question, QuestionStatus, order_for_review
from trace_ai.domain.source_document import SourceDocument
from trace_ai.domain.source_observation import SourceObservation
from trace_ai.domain.threat import Threat
from trace_ai.services.evidence.index import EvidenceNotFoundError
from trace_ai.workflow.context_review import QuotedExcerpt

if TYPE_CHECKING:
    from collections.abc import Sequence

    from trace_ai.services.assessment import AssessmentHandle
    from trace_ai.services.evidence.index import EvidenceIndex
    from trace_ai.workflow.critique_application import CritiqueApplicationOutcome

__all__ = [
    "CritiquePresentation",
    "FindingPresentation",
    "FindingReviewPackage",
    "GapPresentation",
    "ReviewSummary",
    "build_finding_review_package",
    "render_markdown",
]


@dataclass(frozen=True, slots=True)
class CritiquePresentation:
    """One critique raised against a finding, with what was done about it.

    `outcome` comes from the application records (DEC-053) when the caller has them; without
    them it says so, because presenting "nothing recorded" as "nothing happened" would be a
    claim nobody made.
    """

    critique: Critique
    outcome: str


@dataclass(frozen=True, slots=True)
class FindingPresentation:
    """One provisional finding with everything the reviewer needs to judge it.

    Contradictory evidence sits beside supporting evidence rather than being omitted: a
    conclusion whose contradictions are hidden is a conclusion the reviewer cannot actually
    review (`design-principles.md` section 5).
    """

    finding: Finding
    supporting: tuple[QuotedExcerpt, ...]
    contradictory: tuple[QuotedExcerpt, ...]
    threats: tuple[Threat, ...]
    mappings: tuple[ControlMapping, ...]
    critiques: tuple[CritiquePresentation, ...]
    questions: tuple[Question, ...]

    @property
    def awaiting_severity(self) -> bool:
        """DEC-030: the reviewer assigns severity here, and approval requires one."""
        return self.finding.severity is Severity.UNASSIGNED

    @property
    def evidence_statement(self) -> str:
        """What this conclusion rests on, in one sentence the package always carries."""
        if self.supporting:
            count = len(self.supporting)
            cited = f"{count} evidence citation{'s' if count != 1 else ''}"
            if self.finding.low_confidence_justification:
                return (
                    f"{cited}, and a low-confidence justification: "
                    f"{self.finding.low_confidence_justification}"
                )
            return cited
        return (
            "no citation resolved to a stored passage; the finding cannot be confirmed from "
            "this package"
        )


@dataclass(frozen=True, slots=True)
class GapPresentation:
    """One provisional documentation gap, on the same surface and visibly not a finding."""

    gap: DocumentationGap
    excerpts: tuple[QuotedExcerpt, ...]

    KIND: ClassVar[str] = "documentation gap — asserts nothing about the implementation"


@dataclass(frozen=True, slots=True)
class ReviewSummary:
    """The header: counts, and a sentence for the case counts misrepresent."""

    finding_count: int
    documentation_gap_count: int
    open_question_count: int
    awaiting_severity_count: int
    statement: str


@dataclass(frozen=True, slots=True)
class FindingReviewPackage:
    """Everything checkpoint 2 shows, derived from the run and stored nowhere (DEC-017)."""

    summary: ReviewSummary
    findings: tuple[FindingPresentation, ...]
    documentation_gaps: tuple[GapPresentation, ...]
    questions: tuple[Question, ...]
    """Open questions across the assessment, blocking first (`order_for_review`)."""

    catalog_gap_candidates: tuple[CatalogGapCandidate, ...] = ()
    """Informational only (DEC-065): concerns no requirement covers, shown because under DEC-004
    the reviewer and the catalog owner are the same person. Not subjects — the checkpoint's
    completion condition never counts them and no `ReviewerDecision` is asked for."""

    reasons_by_object_id: dict[str, tuple[str, ...]] = field(default_factory=dict)
    """Routing reasons per finding (DEC-062), derived from persisted state and stored nowhere. The
    same substrate checkpoint 1 carries: a subject absent from the map has no reasons, which is
    routine rather than exempt, and the values are `ReasonCode` strings."""

    def reasons_for(self, object_id: str) -> tuple[str, ...]:
        return self.reasons_by_object_id.get(object_id, ())


def _location(index: EvidenceIndex, evidence_ids: Sequence[str]) -> tuple[QuotedExcerpt, ...]:
    """The cited passages with document, location, and verbatim text (DEC-015).

    An unresolvable citation is reported in place rather than dropped: the package is the last
    surface before a reviewer confirms the conclusion the citation supports.
    """
    rendered: list[QuotedExcerpt] = []
    for evidence_id in evidence_ids:
        try:
            reference = index.get(evidence_id)
        except EvidenceNotFoundError:
            rendered.append(
                QuotedExcerpt(
                    evidence_id=evidence_id,
                    document=None,
                    location="unresolved",
                    text=(
                        f"{evidence_id} does not resolve to a stored passage. The conclusion "
                        f"it supports cannot be confirmed from it."
                    ),
                )
            )
            continue

        document = index.handle.objects.find(SourceDocument, reference.source_document_id)
        parts = []
        if reference.section_title:
            parts.append(reference.section_title)
        if reference.start_line is not None:
            end = reference.end_line if reference.end_line is not None else reference.start_line
            parts.append(f"lines {reference.start_line}-{end}")
        rendered.append(
            QuotedExcerpt(
                evidence_id=reference.id,
                document=getattr(document, "filename", None),
                location=", ".join(parts),
                text=reference.quoted_text,
            )
        )
    return tuple(rendered)


def _outcomes_by_critique(application: CritiqueApplicationOutcome | None) -> dict[str, str]:
    """Critique identifier to what was done, from the DEC-053 application records."""
    if application is None:
        return {}
    outcomes: dict[str, str] = {}
    for record in application.applied:
        outcomes[record.critique_id] = record.change
    for deferred in application.deferred:
        outcomes[deferred.critique_id] = f"deferred: {deferred.reason}"
    for unapplied in application.unapplied:
        outcomes[unapplied.critique_id] = f"not applied: {unapplied.reason}"
    return outcomes


def _critiques_for(
    finding: Finding,
    critiques: Sequence[Critique],
    assessments: Sequence[EvidenceAssessment],
    outcomes: dict[str, str],
) -> tuple[CritiquePresentation, ...]:
    """The critiques in this finding's lineage: about it, its threats, its mappings, or the
    assessments over its mappings — the same gathering rule `finding_lineage` uses."""
    mapping_ids = set(finding.control_mapping_ids)
    subject_ids = {finding.id, *finding.threat_ids, *mapping_ids}
    subject_ids.update(
        assessed.id
        for assessed in assessments
        if assessed.subject_type is SubjectType.CONTROL_MAPPING
        and assessed.subject_id in mapping_ids
    )
    return tuple(
        CritiquePresentation(
            critique=critique,
            outcome=outcomes.get(critique.id, "no application record supplied; shown as raised"),
        )
        for critique in critiques
        if critique.subject_id in subject_ids
    )


def _contradictory(
    finding: Finding,
    assessments: Sequence[EvidenceAssessment],
    observations: Sequence[SourceObservation],
    index: EvidenceIndex,
) -> tuple[QuotedExcerpt, ...]:
    """The contradiction evidence recorded against this finding's mappings (DEC-021).

    An `EvidenceAssessment` names its contradictions as `SourceObservation` identifiers, and each
    observation cites the passages that disagree. Those passages are the contradictory evidence
    the surface must show beside the supporting kind.
    """
    mapping_ids = set(finding.control_mapping_ids)
    observation_ids = {
        observation_id
        for assessed in assessments
        if assessed.subject_type is SubjectType.CONTROL_MAPPING
        and assessed.subject_id in mapping_ids
        for observation_id in assessed.contradictions
    }
    evidence_ids = [
        evidence_id
        for observation in observations
        if observation.id in observation_ids
        for evidence_id in observation.evidence_ids
    ]
    return _location(index, evidence_ids)


def build_finding_review_package(
    handle: AssessmentHandle,
    *,
    index: EvidenceIndex,
    application: CritiqueApplicationOutcome | None = None,
) -> FindingReviewPackage:
    """Assemble checkpoint 2's package from the persisted objects. Deterministic; no model.

    The provisional finding set is the candidates that are nobody's duplicate: rejected,
    superseded, and merged-away findings are retained in the store and are not up for review.
    `application` carries the DEC-053 records so each critique can be shown with its outcome;
    without it the critiques still appear, marked as lacking one.
    """
    from trace_ai.domain.base import now
    from trace_ai.workflow.reason_codes import revisit_due_findings

    repository = handle.objects

    provisional = [
        finding
        for finding in repository.list(Finding, status=ObjectStatus.CANDIDATE.value)
        if finding.duplicate_of_id is None
    ]
    # DEC-061/DEC-079: an approved finding whose accepted-risk review-by date has passed is a
    # subject again this run, so it is shown here to be re-decided. It keeps its `accept` until the
    # reviewer acts; presenting it is what stops the pause being a dead end at `findings show`.
    shown = {finding.id for finding in provisional}
    revisit_ids = revisit_due_findings(handle, now().date())
    provisional += [
        finding
        for finding in repository.list(Finding)
        if finding.id in revisit_ids and finding.id not in shown
    ]
    gaps = repository.list(DocumentationGap, status=ObjectStatus.CANDIDATE.value)
    open_questions = order_for_review(
        question for question in repository.list(Question) if question.status is QuestionStatus.OPEN
    )
    critiques = repository.list(Critique)
    assessments = repository.list(EvidenceAssessment)
    observations = repository.list(SourceObservation)
    threats = {threat.id: threat for threat in repository.list(Threat)}
    mappings = {mapping.id: mapping for mapping in repository.list(ControlMapping)}
    outcomes = _outcomes_by_critique(application)

    presented: list[FindingPresentation] = []
    for finding in provisional:
        related_ids = {finding.id, *finding.threat_ids}
        presented.append(
            FindingPresentation(
                finding=finding,
                supporting=_location(index, finding.evidence_ids),
                contradictory=_contradictory(finding, assessments, observations, index),
                threats=tuple(threats[thr] for thr in finding.threat_ids if thr in threats),
                mappings=tuple(
                    mappings[mid] for mid in finding.control_mapping_ids if mid in mappings
                ),
                critiques=_critiques_for(finding, critiques, assessments, outcomes),
                questions=tuple(
                    question
                    for question in open_questions
                    if question.related_object_id in related_ids
                ),
            )
        )

    gap_presentations = tuple(
        GapPresentation(gap=gap, excerpts=_location(index, gap.evidence_ids)) for gap in gaps
    )

    awaiting = sum(1 for item in presented if item.awaiting_severity)
    if not presented:
        statement = (
            "No provisional findings were proposed. A successful assessment may produce no "
            "findings; what could not be determined is recorded as documentation gaps and "
            "questions below."
        )
    else:
        statement = (
            f"{len(presented)} provisional finding{'s' if len(presented) != 1 else ''} for "
            f"review. {awaiting} await{'s' if awaiting == 1 else ''} a severity, which the "
            f"reviewer assigns before approval (DEC-030)."
        )

    return FindingReviewPackage(
        summary=ReviewSummary(
            finding_count=len(presented),
            documentation_gap_count=len(gap_presentations),
            open_question_count=len(open_questions),
            awaiting_severity_count=awaiting,
            statement=statement,
        ),
        findings=tuple(presented),
        documentation_gaps=gap_presentations,
        questions=tuple(open_questions),
        catalog_gap_candidates=tuple(repository.list(CatalogGapCandidate)),
        reasons_by_object_id=_finding_routing_reasons(
            handle, {presentation.finding.id for presentation in presented}
        ),
    )


def _finding_routing_reasons(
    handle: AssessmentHandle, finding_ids: set[str]
) -> dict[str, tuple[str, ...]]:
    """The per-finding routing reasons (DEC-062), derived from persisted state at build time.

    `low_confidence` and `revisit_due` are the codes a finding carries; `injection_flag` derives
    from the cited source and attaches to the context objects (issue #274), not here. Restricted to
    the presented findings so a reason never appears for a finding the reviewer is not shown.
    """
    from trace_ai.domain.base import now
    from trace_ai.workflow.reason_codes import (
        ReasonCode,
        low_confidence_subjects,
        revisit_due_findings,
    )

    reasons: dict[str, list[str]] = {}
    low_confidence = low_confidence_subjects(handle) & finding_ids
    revisit: set[str] = revisit_due_findings(handle, now().date()) & finding_ids
    for object_id in low_confidence:
        reasons.setdefault(object_id, []).append(ReasonCode.LOW_CONFIDENCE.value)
    for object_id in revisit:
        reasons.setdefault(object_id, []).append(ReasonCode.REVISIT_DUE.value)
    return {object_id: tuple(codes) for object_id, codes in reasons.items()}


def render_markdown(package: FindingReviewPackage) -> str:
    """Format an assembled package. A separate pass over the data, touching no store.

    The renderer holds no opinion the package does not: everything it writes is read from the
    structured result, so the command line, a file round-trip, and a later web view show one
    package rather than three assemblies.
    """
    lines: list[str] = ["# Finding review", "", package.summary.statement, ""]
    lines.append(
        f"Provisional findings: {package.summary.finding_count} · documentation gaps: "
        f"{package.summary.documentation_gap_count} · open questions: "
        f"{package.summary.open_question_count}"
    )
    lines.append("")

    for item in package.findings:
        finding = item.finding
        lines.append(f"## {finding.id}: {finding.title}")
        reasons = package.reasons_for(finding.id)
        if reasons:
            lines.append(f"*Routing: {', '.join(reasons)}* (DEC-062)")
        lines.append("")
        severity = (
            "unassigned — assignment required before approval (DEC-030)"
            if item.awaiting_severity
            else finding.severity.value
        )
        lines.extend(
            [
                finding.summary,
                "",
                finding.description,
                "",
                f"- Severity: {severity}",
                f"- Confidence: {finding.confidence.value}",
                f"- Validation status: {finding.validation_status.value}",
                f"- Affected components: {', '.join(finding.affected_component_ids) or 'none'}",
                f"- Affected assets: {', '.join(finding.affected_asset_ids) or 'none'}",
                f"- Impact: {finding.impact}",
                f"- Recommendation: {finding.recommendation}",
                f"- Evidence: {item.evidence_statement}",
            ]
        )
        for label, entries in (
            ("Assumptions", finding.assumptions),
            ("Limitations", finding.limitations),
        ):
            if entries:
                lines.append(f"- {label}: " + "; ".join(entries))
        lines.append("")

        for threat in item.threats:
            lines.append(f"Threat {threat.id}: {threat.title}")
        for mapping in item.mappings:
            lines.append(
                f"Mapping {mapping.id}: {mapping.requirement_id} — {mapping.applicability_reason}"
            )
        lines.append("")

        if item.supporting:
            lines.append("### Supporting evidence")
            lines.extend(["", *(excerpt.rendered() for excerpt in item.supporting), ""])
        if item.contradictory:
            lines.append("### Contradictory evidence")
            lines.extend(["", *(excerpt.rendered() for excerpt in item.contradictory), ""])
        if item.critiques:
            lines.append("### Critiques")
            lines.append("")
            for raised in item.critiques:
                lines.append(
                    f"- {raised.critique.id} ({raised.critique.critique_type.value}, "
                    f"recommended {raised.critique.recommended_action.value}): "
                    f"{raised.critique.description} Outcome: {raised.outcome}"
                )
            lines.append("")
        if item.questions:
            lines.append("### Open questions")
            lines.append("")
            for question in item.questions:
                marker = "blocking" if question.blocking else question.priority.value
                lines.append(f"- {question.id} ({marker}): {question.question}")
            lines.append("")

    if package.documentation_gaps:
        lines.append("## Documentation gaps")
        lines.append("")
        lines.append(f"Each entry is a {GapPresentation.KIND}.")
        lines.append("")
        for gap_item in package.documentation_gaps:
            gap = gap_item.gap
            lines.extend(
                [
                    f"### {gap.id}: {gap.title}",
                    "",
                    gap.description,
                    "",
                    f"- Why it matters: {gap.importance}",
                    f"- Severity of the gap: {gap.severity.value}",
                ]
            )
            if gap.requested_evidence:
                lines.append("- Requested evidence: " + "; ".join(gap.requested_evidence))
            if gap_item.excerpts:
                lines.extend(["", *(excerpt.rendered() for excerpt in gap_item.excerpts)])
            lines.append("")

    if package.questions:
        lines.append("## Open questions")
        lines.append("")
        for question in package.questions:
            marker = "blocking" if question.blocking else question.priority.value
            lines.append(f"- {question.id} ({marker}): {question.question}")
        lines.append("")

    if package.catalog_gap_candidates:
        lines.append("## Catalog-gap candidates (informational — no decision required)")
        lines.append("")
        lines.append(
            "Concerns the analysis met that no requirement in the active catalog covers "
            "(DEC-065). Raw material for the next catalog version; none is a finding and none "
            "awaits a decision here. `trace assessment candidates` lists them any time."
        )
        lines.append("")
        for candidate in package.catalog_gap_candidates:
            lines.append(f"### {candidate.id}: {candidate.concern}")
            lines.extend(
                [
                    "",
                    f"- Suggested category: {candidate.suggested_category}",
                    f"- Raised by: {candidate.generated_by}",
                    f"- Evidence: {', '.join(candidate.evidence_ids)}",
                ]
            )
            for considered in candidate.nearest_requirements:
                lines.append(f"- Nearest: {considered.requirement_id} — {considered.why_not}")
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"
