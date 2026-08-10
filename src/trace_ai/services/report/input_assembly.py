"""The report input: approved analysis, assembled once, for the agent and the renderer alike.

`agent-design.md` section 19 gives the Report Generation agent only approved or explicitly
reportable objects, and `design-principles.md` section 17 makes the report a representation of
approved analysis rather than an independent source of truth. Both consumers — the model-assisted
agent (#105) and the deterministic renderer (#106) — read this one assembly, so the two cannot
disagree about what was approved.

**Findings come solely from the approved-set accessor** (DEC-055). Rejected, deferred,
superseded, and merged candidates have no path into this structure: nothing here queries findings
by any other status, and the accessor itself refuses an approved finding no reviewer decided.

**The empty case is a value, not an absent key.** `zero_approved_findings` is carried explicitly
so downstream code renders the template's authored empty-findings wording (DEC-035) rather than
skipping a section that then reads as never considered.

**`required_limitations` is derived here** (DEC-035): one entry per limitation the run's own
state implies — documents that failed ingestion, unanswered blocking questions, a
non-authoritative run, an empty approved set, findings resting on stated assumptions. The agent
writes the words for each identifier; the validator checks the set; this module owns the list.

**Deterministic and repeatable.** Everything is ordered by identifier, nothing reads a clock, and
two assemblies over identical approved state are equal — which is what makes a report comparable
with the one rendered yesterday, and the assembly itself makes no model call.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from trace_ai.domain.actor import Actor
from trace_ai.domain.assessment import Assessment
from trace_ai.domain.asset import Asset
from trace_ai.domain.component import Component
from trace_ai.domain.context_claim import ClaimStatus, ContextClaim
from trace_ai.domain.control import Control
from trace_ai.domain.data_flow import DataFlow
from trace_ai.domain.documentation_gap import DocumentationGap
from trace_ai.domain.enums import ObjectStatus, ValidationStatus
from trace_ai.domain.evidence import EvidenceReference
from trace_ai.domain.question import Question, QuestionStatus, order_for_review
from trace_ai.domain.source_document import IngestionStatus, SourceDocument
from trace_ai.domain.system_context import SystemContext
from trace_ai.domain.threat import Threat
from trace_ai.domain.trust_boundary import TrustBoundary
from trace_ai.services.findings.approved import approved_findings

if TYPE_CHECKING:
    from collections.abc import Mapping

    from trace_ai.domain.finding import Finding
    from trace_ai.services.assessment import AssessmentHandle

__all__ = [
    "REPORT_TEMPLATE",
    "ReportInput",
    "ReportVersions",
    "RequiredLimitation",
    "assemble_report_input",
]

# The template identifier DEC-035 fixes. The renderer holds the sections to it;
# `tests/unit/test_report_template.py` holds the template, the decision table, and
# `current-architecture.md` section 5.13 in agreement.
REPORT_TEMPLATE: Final = "report-v1"

# The claim statuses report section 10 renders: what was assumed or inferred, with the DEC-022
# rationale, so a reader can see what the analysis rests on beyond the documents.
_ASSUMPTION_STATUSES: Final = frozenset({ClaimStatus.ASSUMED, ClaimStatus.INFERRED})


@dataclass(frozen=True, slots=True)
class ReportVersions:
    """The six version identifiers `evaluation-plan.md` section 3 requires on every evaluation.

    Architecture, workflow, and catalog come from the `Assessment`; prompts, model, and model
    configuration are the run's and are supplied by the caller that knows them.
    """

    architecture_version: str
    workflow_version: str
    prompt_versions: tuple[tuple[str, str], ...]
    """Every prompt version used in the run, by name, as sorted pairs — a tuple rather than a
    dict so the whole structure stays hashable and order-stable."""

    requirements_catalog_version: str
    model: str
    model_configuration: str


@dataclass(frozen=True, slots=True)
class RequiredLimitation:
    """One limitation the run's state implies, which the agent must write and may not drop.

    The identifier is stable and derived — `lim-<kind>` or `lim-<kind>-<object>` — so the
    validator can check the written set by identifier (DEC-035) and two runs over the same state
    require the same list.
    """

    limitation_id: str
    facts: str


@dataclass(frozen=True, slots=True)
class ReportInput:
    """Everything the report is made from, assembled once from approved state.

    The agent reads the prose-relevant parts; the renderer reads all of it; neither assembles
    anything of its own. Every collection is ordered by identifier.
    """

    assessment: Assessment
    system_context: SystemContext | None
    approved_findings: tuple[Finding, ...]
    approved_documentation_gaps: tuple[DocumentationGap, ...]
    open_questions: tuple[Question, ...]
    confirmed_controls: tuple[Control, ...]
    threats: tuple[Threat, ...]
    components: tuple[Component, ...]
    actors: tuple[Actor, ...]
    assets: tuple[Asset, ...]
    data_flows: tuple[DataFlow, ...]
    trust_boundaries: tuple[TrustBoundary, ...]
    assumption_claims: tuple[ContextClaim, ...]
    source_documents: tuple[SourceDocument, ...]
    evidence_references: tuple[EvidenceReference, ...]
    """Every reference cited by an object above — the evidence appendix's rows (section 15)."""

    zero_approved_findings: bool
    """The empty case as a value (DEC-035): the template's authored wording renders, and no
    section is skipped."""

    required_limitations: tuple[RequiredLimitation, ...]
    template: str
    versions: ReportVersions
    authoritative: bool


def _by_id[ModelT](items: list[ModelT]) -> tuple[ModelT, ...]:
    return tuple(sorted(items, key=lambda item: str(getattr(item, "id", ""))))


def _required_limitations(
    *,
    failed_documents: list[SourceDocument],
    blocking_questions: list[Question],
    findings: list[Finding],
    zero_findings: bool,
    authoritative: bool,
) -> tuple[RequiredLimitation, ...]:
    """The list DEC-035 has the assembler derive: identifiers and facts, never wording."""
    required: list[RequiredLimitation] = []

    if zero_findings:
        required.append(
            RequiredLimitation(
                limitation_id="lim-empty-findings",
                facts=(
                    "No candidate weakness reached the assessment's bar. This is not a "
                    "statement that the system is secure; what could not be determined is "
                    "recorded as documentation gaps and open questions."
                ),
            )
        )
    for document in failed_documents:
        required.append(
            RequiredLimitation(
                limitation_id=f"lim-ingestion-{document.id}",
                facts=f"{document.filename} ({document.id}) failed ingestion and was not analysed.",
            )
        )
    for question in blocking_questions:
        required.append(
            RequiredLimitation(
                limitation_id=f"lim-blocking-{question.id}",
                facts=(
                    f"{question.id} is open and blocking: the assessment cannot conclude "
                    f"soundly without the answer."
                ),
            )
        )
    for finding in findings:
        if finding.assumptions:
            required.append(
                RequiredLimitation(
                    limitation_id=f"lim-assumptions-{finding.id}",
                    facts=(
                        f"{finding.id} rests on stated assumptions: "
                        f"{'; '.join(finding.assumptions)}"
                    ),
                )
            )
    if not authoritative:
        required.append(
            RequiredLimitation(
                limitation_id="lim-non-authoritative",
                facts=(
                    "The run applied an evaluation ablation (DEC-012) and its results are not "
                    "authoritative."
                ),
            )
        )

    return tuple(sorted(required, key=lambda item: item.limitation_id))


def assemble_report_input(
    handle: AssessmentHandle,
    *,
    prompt_versions: Mapping[str, str],
    model: str,
    model_configuration: str,
    authoritative: bool = True,
) -> ReportInput:
    """Gather the approved state, once, for everything downstream. Deterministic; no model.

    `prompt_versions`, `model`, and `model_configuration` are the run's and come from the caller
    that knows them; architecture, workflow, and catalog versions come from the `Assessment`
    (evaluation-plan section 3 requires all six).
    """
    repository = handle.objects
    assessment = repository.get(Assessment, handle.assessment_id)

    revisions = sorted(repository.list(SystemContext), key=lambda item: item.version)
    approved_context = next(
        (revision for revision in reversed(revisions) if revision.is_approved), None
    )

    findings = sorted(approved_findings(handle), key=lambda finding: finding.id)
    gaps = repository.list(DocumentationGap, status=ObjectStatus.APPROVED.value)
    open_questions = order_for_review(
        question for question in repository.list(Question) if question.status is QuestionStatus.OPEN
    )
    confirmed = [
        control
        for control in repository.list(Control)
        if control.validation_status is ValidationStatus.SUPPORTED
    ]
    threats = [
        threat for threat in repository.list(Threat) if threat.status is ObjectStatus.APPROVED
    ]
    assumptions = [
        claim for claim in repository.list(ContextClaim) if claim.status in _ASSUMPTION_STATUSES
    ]
    documents = repository.list(SourceDocument)

    cited: set[str] = set()
    for finding in findings:
        cited.update(finding.evidence_ids)
    for gap in gaps:
        cited.update(gap.evidence_ids)
    for threat in threats:
        cited.update(threat.evidence_ids)
    for control in confirmed:
        cited.update(control.evidence_ids)
    for claim in assumptions:
        cited.update(claim.evidence_ids)
    evidence = [
        reference for reference in repository.list(EvidenceReference) if reference.id in cited
    ]

    failed = [
        document for document in documents if document.ingestion_status is IngestionStatus.FAILED
    ]
    blocking = [question for question in open_questions if question.blocking]

    return ReportInput(
        assessment=assessment,
        system_context=approved_context,
        approved_findings=tuple(findings),
        approved_documentation_gaps=_by_id(gaps),
        open_questions=tuple(open_questions),
        confirmed_controls=_by_id(confirmed),
        threats=_by_id(threats),
        components=_by_id(repository.list(Component)),
        actors=_by_id(repository.list(Actor)),
        assets=_by_id(repository.list(Asset)),
        data_flows=_by_id(repository.list(DataFlow)),
        trust_boundaries=_by_id(repository.list(TrustBoundary)),
        assumption_claims=_by_id(assumptions),
        source_documents=_by_id(documents),
        evidence_references=_by_id(evidence),
        zero_approved_findings=not findings,
        required_limitations=_required_limitations(
            failed_documents=sorted(failed, key=lambda item: item.id),
            blocking_questions=blocking,
            findings=findings,
            zero_findings=not findings,
            authoritative=authoritative,
        ),
        template=REPORT_TEMPLATE,
        versions=ReportVersions(
            architecture_version=assessment.architecture_version,
            workflow_version=assessment.workflow_version,
            prompt_versions=tuple(sorted(prompt_versions.items())),
            requirements_catalog_version=assessment.requirements_catalog_version or "none-loaded",
            model=model,
            model_configuration=model_configuration,
        ),
        authoritative=authoritative,
    )
