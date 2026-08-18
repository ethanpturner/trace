"""The pipeline driver: every phase's node, composed once, driven by the orchestrator.

This is the composition point #260 adds. `current-architecture.md` section 5.2 puts the pipeline in
the application service, and until this module only the context slice honoured that — the M3 and M4
nodes existed and nothing in `src/` drove them. The driver registers a node for every name
`NODES_BY_PHASE` declares and hands the orchestrator a state at `assessment_initialization`; the
orchestrator walks the table from there (DEC-016), pauses at the two checkpoints (DEC-005,
DEC-017), and the harness DEC-073 specifies will call these same functions rather than composing a
second pipeline.

**Adapters, not new analysis.** Several phases pair a model node with deterministic validation and
persistence functions that until now only tests composed. The adapter classes here do that
composition and nothing else: every model call is the existing agent node's, every write goes
through the existing `persist_*` function, and a validation outcome with blocking errors stops the
run with its own error class rather than being retried into agreement (`agent-design.md` section
26 — the conclusion is never retried).

**A phase's two nodes may hand an object forward in memory.** `EvidenceValidationProposal` and
`ReportSections` are proposals — no identifier, nothing persisted (DEC-006) — so the deterministic
node that validates each one receives it through a holder the composition function shares between
the two adapters. The holder never has to survive a process exit: the only phases that pause are
the checkpoints, and both are single-node phases.

**Agent nodes record their own executions.** The adapters that wrap them say so with
`records_own_execution`, and the orchestrator leaves the accounting to the node — one
`ExecutionRecord` per model attempt, one budget spend per call, exactly as the nodes already
behave under `run_context_slice`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, ClassVar, Final

from trace_ai.domain.assessment import Assessment, AssessmentConfiguration
from trace_ai.domain.component import Component
from trace_ai.domain.context_claim import ContextClaim
from trace_ai.domain.control import Control
from trace_ai.domain.control_mapping import ControlMapping
from trace_ai.domain.critique import CritiqueSubjectType
from trace_ai.domain.documentation_gap import DocumentationGap
from trace_ai.domain.enums import ObjectStatus
from trace_ai.domain.evidence import EvidenceReference
from trace_ai.domain.evidence_assessment import EvidenceAssessment
from trace_ai.domain.execution import ExecutionType, WorkflowRun
from trace_ai.domain.finding import Finding
from trace_ai.domain.identifiers import parse_id
from trace_ai.domain.reviewer_decision import ReviewerDecision
from trace_ai.domain.source_document import IngestionStatus, SourceDocument
from trace_ai.domain.source_observation import ObservationKind, SourceObservation
from trace_ai.domain.threat import Threat
from trace_ai.services.context.parsers import seed_structured_documents
from trace_ai.services.context.pipeline import context_objects
from trace_ai.services.critique.input_package import select_review_group
from trace_ai.services.critique.precedent import select_precedents
from trace_ai.services.evaluation.metrics import compute_metrics, persist_metrics
from trace_ai.services.evaluation.report_metrics import compute_report_metrics
from trace_ai.services.evidence.index import EvidenceIndex
from trace_ai.services.evidence.indexing import index_document
from trace_ai.services.execution_ledger import ExecutionLedger, start_run
from trace_ai.services.findings.fingerprints import component_name_index
from trace_ai.services.prompts.definitions import PersistingPromptRegistry
from trace_ai.services.report.input_assembly import assemble_report_input
from trace_ai.services.requirements.loader import current_version, load_catalog
from trace_ai.workflow.checkpoint import resume
from trace_ai.workflow.context_extraction import ContextExtractionNode
from trace_ai.workflow.context_review import (
    ContextReviewNode,
    current_system_context,
    previous_approved_context,
    re_extraction_feedback,
)
from trace_ai.workflow.context_validation import validate_context
from trace_ai.workflow.critical_review import CriticalReviewNode, CriticalReviewOutcome
from trace_ai.workflow.critique_application import apply_critiques, persist_application
from trace_ai.workflow.critique_validation import (
    DEFAULT_MAXIMUM_REINVOCATIONS,
    DEFAULT_VOLUME_RATIO,
    persist_critiques,
    validate_critiques,
)
from trace_ai.workflow.errors import ErrorClass, WorkflowError
from trace_ai.workflow.evidence_assessment_validation import (
    persist_assessments,
    validate_assessments,
)
from trace_ai.workflow.evidence_validation import EvidenceValidationNode, EvidenceValidationOutcome
from trace_ai.workflow.finding_consolidation import consolidate, persist_consolidation
from trace_ai.workflow.finding_dedup import dedupe_findings, persist_dedup
from trace_ai.workflow.finding_review import FindingReviewNode
from trace_ai.workflow.limits import Budget
from trace_ai.workflow.mapping_validation import apply_downgrades, validate_mappings
from trace_ai.workflow.nodes import NodeContext, NodeResult
from trace_ai.workflow.orchestrator import Orchestrator, RunOutcome
from trace_ai.workflow.phases import Phase
from trace_ai.workflow.report_generation import (
    PROMPT_ID as REPORT_PROMPT_ID,
)
from trace_ai.workflow.report_generation import (
    PROMPT_VERSION as REPORT_PROMPT_VERSION,
)
from trace_ai.workflow.report_generation import (
    ReportGenerationNode,
)
from trace_ai.workflow.report_manifest import ReportValidationFailedError, publish_report
from trace_ai.workflow.requirement_control_mapping import RequirementControlMappingNode
from trace_ai.workflow.state import AssessmentState
from trace_ai.workflow.threat_analysis import ThreatAnalysisNode
from trace_ai.workflow.threat_validation import validate_threats

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence
    from datetime import datetime
    from typing import Any

    from trace_ai.domain.base import DomainModel
    from trace_ai.domain.proposals.report_sections import ReportSections
    from trace_ai.infrastructure.model.profiles import ModelProfile
    from trace_ai.infrastructure.model.seam import StructuredModel
    from trace_ai.services.assessment import AssessmentHandle, AssessmentService
    from trace_ai.services.critique.input_package import SelectedObjects
    from trace_ai.services.prompts import PromptRegistry
    from trace_ai.services.report.input_assembly import ReportInput
    from trace_ai.workflow.nodes import Node

__all__ = ["KNOWN_ABLATIONS", "build_nodes", "resume_assessment", "run_assessment"]

WORKFLOW_VERSION = "0.1"

KNOWN_ABLATIONS: Final = frozenset(
    {"no-evidence-validation", "no-critical-review", "no-context-approval"}
)
"""DEC-074's ablation family, closed. An unknown name is refused rather than ignored.

Ablations are the evaluation harness's (DEC-012, DEC-073): they arrive as an argument from the
one caller that constructs ablated runs, never from assessment configuration, and the run they
produce is marked non-authoritative from birth. Replaying recorded reviewer decisions is not an
ablation and needs no entry here.
"""


def _blocking_stop(what: str, blocking: Sequence[object]) -> WorkflowError:
    """A validation outcome's blocking errors as the classified error that stops the run.

    The class is the first blocking error's own — validators name their classes precisely so the
    stop is routable — and the message carries counts, never quoted content, per section 27's
    safe-message rule.
    """
    first = blocking[0]
    error_class = getattr(first, "error_class", ErrorClass.UNEXPECTED_APPLICATION_FAILURE)
    return WorkflowError(
        error_class,
        f"{what} reported {len(blocking)} blocking error(s); "
        f"the first is classified {error_class.value}",
    )


def _sorted_by_id(objects: Sequence[Any]) -> list[Any]:
    """Deterministic iteration order for per-object loops, so a replayed run replays.

    Keyed on the identifier's *number*, not its text: DEC-018 widens past 999 rather than wrapping,
    so a lexical sort puts `evd-1000` before `evd-999` and silently reorders a moderate corpus --
    which, because DEC-018 assigns identifiers in iteration order on a rerun, changes which
    identifier attaches to which object. Prefix then number is the allocation order.
    """
    return sorted(objects, key=lambda item: (parse_id(item.id).prefix, parse_id(item.id).number))


# -- one-node phases ---------------------------------------------------------------------------


@dataclass(slots=True)
class AssessmentInitializationNode:
    """Phase 1: the run's subject exists and may be assessed."""

    name: ClassVar[str] = "assessment-initialization"
    phase: ClassVar[Phase] = Phase.ASSESSMENT_INITIALIZATION
    execution_type: ClassVar[ExecutionType] = ExecutionType.DETERMINISTIC
    version: str = "0.1"

    def run(self, context: NodeContext) -> NodeResult:
        assessment = context.handle.objects.get(Assessment, context.handle.assessment_id)
        if assessment.status is ObjectStatus.ARCHIVED:
            raise WorkflowError(
                ErrorClass.REVIEWER_INPUT_REQUIRED,
                f"assessment {assessment.id} is archived; an archived assessment is not assessed",
            )
        return NodeResult(
            consumed_object_ids=[assessment.id],
            metadata={
                "assessment_status": assessment.status.value,
                "workflow_version": assessment.workflow_version,
                "model_profile": assessment.configuration.model_profile,
            },
        )


@dataclass(slots=True)
class DocumentIngestionNode:
    """Phase 2, first node: the documents `source add` registered are present and readable.

    Ingestion itself happened at registration time — `services/ingestion/loader.py` stores and
    validates each document as it arrives. What this node adds is the phase's guarantee: a run
    with nothing to read stops here, classified, rather than extracting a context from nothing.
    """

    name: ClassVar[str] = "document-ingestion"
    phase: ClassVar[Phase] = Phase.DOCUMENT_INGESTION
    execution_type: ClassVar[ExecutionType] = ExecutionType.DETERMINISTIC
    version: str = "0.1"

    def run(self, context: NodeContext) -> NodeResult:
        documents = context.handle.objects.list(SourceDocument)
        if not documents:
            raise WorkflowError(
                ErrorClass.MISSING_REQUIRED_RELATIONSHIP,
                "this assessment has no source documents; register them with `trace source add` "
                "before running",
            )
        failed = [doc.id for doc in documents if doc.ingestion_status is IngestionStatus.FAILED]
        if failed:
            raise WorkflowError(
                ErrorClass.MISSING_REQUIRED_RELATIONSHIP,
                f"{len(failed)} source document(s) failed ingestion: {', '.join(sorted(failed))}",
            )
        return NodeResult(
            consumed_object_ids=[doc.id for doc in documents],
            state_changes={"source_document_ids": sorted(doc.id for doc in documents)},
            metadata={"document_count": len(documents)},
        )


@dataclass(slots=True)
class EvidenceIndexingNode:
    """Phase 2, second node: every registered document is indexed, exactly once.

    `index_document` refuses a document it has already indexed — indexing twice would mint a
    second set of evidence references for the same passages — so this node indexes only what is
    still `registered` and is therefore safe to run on an assessment `source add` already indexed.
    """

    name: ClassVar[str] = "evidence-indexing"
    phase: ClassVar[Phase] = Phase.DOCUMENT_INGESTION
    execution_type: ClassVar[ExecutionType] = ExecutionType.DETERMINISTIC
    version: str = "0.1"

    def run(self, context: NodeContext) -> NodeResult:
        handle = context.handle
        produced: list[str] = []
        for document in _sorted_by_id(handle.objects.list(SourceDocument)):
            if document.ingestion_status is IngestionStatus.REGISTERED:
                produced.extend(reference.id for reference in index_document(handle, document))

        reference_ids = handle.objects.ids(EvidenceReference)
        if not reference_ids:
            raise WorkflowError(
                ErrorClass.MISSING_REQUIRED_RELATIONSHIP,
                "no evidence references exist after indexing; there is nothing to extract a "
                "context from",
            )
        return NodeResult(
            produced_object_ids=produced,
            metadata={"evidence_reference_count": len(reference_ids)},
        )


@dataclass(slots=True)
class ContextExtractionAdapter:
    """Phase 3: the existing extraction agent node, constructed with what this run knows."""

    ledger: ExecutionLedger
    profile: ModelProfile
    registry: PromptRegistry
    assessment_name: str
    budget: Budget | None = None
    structured_input: dict[str, Any] | None = None
    version: str = "0.1"

    name: ClassVar[str] = "context-extraction"
    phase: ClassVar[Phase] = Phase.CONTEXT_EXTRACTION
    execution_type: ClassVar[ExecutionType] = ExecutionType.MODEL
    records_own_execution: ClassVar[bool] = True

    def run(self, context: NodeContext) -> NodeResult:
        handle = context.handle
        # DEC-070: parse machine-readable artifacts before the agent runs, so the seeded objects
        # join the baseline, the parsers' excerpts are available to the fence, and the agent
        # extends rather than re-derives. Seeding precedes the evidence listing on purpose.
        seeded = seed_structured_documents(handle)
        available = handle.objects.ids(EvidenceReference)
        node = ContextExtractionNode(
            ledger=self.ledger,
            index=EvidenceIndex(handle),
            profile=self.profile,
            registry=self.registry,
            evidence_ids=available,
            assessment_name=self.assessment_name,
            structured_input=self.structured_input,
            budget=self.budget,
            seeded=seeded,
            reviewer_feedback=re_extraction_feedback(handle),
        )
        return node.run(context)


@dataclass(slots=True)
class ContextValidationAdapter:
    """Phase 4: report on the extracted context; correct nothing (`agent-design.md` section 8).

    The outcome is not persisted — the review package derives it again when a reviewer asks —
    and blocking errors do not stop the run, because the reviewer at checkpoint 1 is the person
    who decides what an error means. What blocking errors stop is approval, and that refusal is
    `workflow/context_review.py`'s.

    The one thing this adapter does persist is DEC-068's privilege-extremes Questions: an
    unrepresented attack-surface extreme is silence, a Question is the DEC-009 outlet for it, and
    the question flows into checkpoint 1 through the same open-questions surface everything else
    uses. Idempotent — a re-derived outcome raises no second copy of a question that is already
    open.
    """

    version: str = "0.1"

    name: ClassVar[str] = "context-validation"
    phase: ClassVar[Phase] = Phase.CONTEXT_VALIDATION
    execution_type: ClassVar[ExecutionType] = ExecutionType.DETERMINISTIC

    GENERATED_BY: ClassVar[str] = "context-validation-v1"

    def run(self, context: NodeContext) -> NodeResult:
        from trace_ai.domain.question import Question, QuestionPriority, QuestionStatus

        handle = context.handle
        system_context = current_system_context(handle)
        available: set[str] = set(handle.objects.ids(EvidenceReference))
        outcome = validate_context(
            system_context,
            context_objects(handle),
            available_evidence=available,
            previous=previous_approved_context(handle, system_context),
        )

        raised: list[str] = []
        existing = {
            question.question
            for question in handle.objects.list(Question)
            if question.generated_by == self.GENERATED_BY
        }
        with handle.objects.transaction() as repository:
            for extreme in outcome.privilege_extremes:
                if extreme.detail in existing:
                    continue
                question = Question.model_validate(
                    {
                        "id": repository.allocate("qst"),
                        "assessment_id": handle.assessment_id,
                        "question": extreme.detail,
                        "rationale": (
                            f"The context represents no {extreme.extreme.replace('_', ' ')} "
                            f"actor (DEC-068). The extremes of the attack surface are where "
                            f"analysis most often goes silent, and whether this one is out of "
                            f"scope is a judgment about the world, not the documents."
                        ),
                        "priority": QuestionPriority.MEDIUM,
                        "blocking": False,
                        "status": QuestionStatus.OPEN,
                        "generated_by": self.GENERATED_BY,
                    }
                )
                repository.save(question)
                raised.append(question.id)

        return NodeResult(
            produced_object_ids=raised,
            consumed_object_ids=[*context.state.context_claim_ids],
            metadata={
                "blocking_error_count": len(outcome.blocking_errors),
                "error_count": len(outcome.errors),
                "trigger_count": len(outcome.triggers),
                "zone_mismatch_count": len(outcome.zone_mismatches),
                "cross_claim_observation_count": len(outcome.cross_claim_observations),
                "privilege_extreme_questions": len(raised),
            },
        )


@dataclass(slots=True)
class ThreatAnalysisAdapter:
    """Phase 6, first node: the threat agent, over the approved context."""

    ledger: ExecutionLedger
    profile: ModelProfile
    registry: PromptRegistry
    assessment_name: str
    budget: Budget | None = None
    version: str = "0.1"

    name: ClassVar[str] = "threat-analysis"
    phase: ClassVar[Phase] = Phase.THREAT_GENERATION
    execution_type: ClassVar[ExecutionType] = ExecutionType.MODEL
    records_own_execution: ClassVar[bool] = True

    def run(self, context: NodeContext) -> NodeResult:
        handle = context.handle
        assessment = handle.objects.get(Assessment, handle.assessment_id)
        node = ThreatAnalysisNode(
            ledger=self.ledger,
            index=EvidenceIndex(handle),
            profile=self.profile,
            registry=self.registry,
            context=current_system_context(handle),
            evidence_ids=handle.objects.ids(EvidenceReference),
            assessment_name=self.assessment_name,
            threat_methodology=assessment.configuration.threat_methodology,
            budget=self.budget,
        )
        return node.run(context)


@dataclass(slots=True)
class ThreatValidationAdapter:
    """Phase 6, second node: deterministic checks over the persisted threat set."""

    version: str = "0.1"

    name: ClassVar[str] = "threat-validation"
    phase: ClassVar[Phase] = Phase.THREAT_GENERATION
    execution_type: ClassVar[ExecutionType] = ExecutionType.DETERMINISTIC

    def run(self, context: NodeContext) -> NodeResult:
        handle = context.handle
        threats = _sorted_by_id(handle.objects.list(Threat))
        outcome = validate_threats(
            threats,
            context=current_system_context(handle),
            claims=handle.objects.list(ContextClaim),
            components=handle.objects.list(Component),
        )
        if not outcome.valid:
            raise _blocking_stop("threat validation", outcome.blocking_errors)
        # DEC-063: coverage is warn-only. It names the uncovered applicable categories per
        # component and the run proceeds; nothing here retries the threat agent against it.
        coverage = {
            gap.component_id: list(gap.uncovered) for gap in outcome.coverage_gaps if gap.uncovered
        }
        return NodeResult(
            consumed_object_ids=[threat.id for threat in threats],
            metadata={
                "threat_count": len(threats),
                "trigger_count": len(outcome.triggers),
                "merge_proposal_count": len(outcome.merge_proposals),
                "unfamiliar_categories": list(outcome.unfamiliar_categories),
                "coverage_gaps": coverage,
                "implausible_threats": [
                    {"threat": observation.threat_id, "category": observation.category}
                    for observation in outcome.implausible_threats
                ],
            },
        )


@dataclass(slots=True)
class RequirementControlMappingAdapter:
    """Phase 7, first node: the mapping agent, once per threat, results accumulated.

    One node instance per threat is the existing design; the loop lives here because
    `AssessmentState.advance` replaces list fields rather than appending, so per-threat
    `state_changes` have to be gathered before they reach the state.
    """

    ledger: ExecutionLedger
    profile: ModelProfile
    registry: PromptRegistry
    budget: Budget | None = None
    version: str = "0.1"

    name: ClassVar[str] = "requirement-and-control-mapping"
    phase: ClassVar[Phase] = Phase.REQUIREMENT_AND_CONTROL_MAPPING
    execution_type: ClassVar[ExecutionType] = ExecutionType.MODEL
    records_own_execution: ClassVar[bool] = True

    def run(self, context: NodeContext) -> NodeResult:
        handle = context.handle
        assessment = handle.objects.get(Assessment, handle.assessment_id)
        catalog = load_catalog(assessment.requirements_catalog_version or current_version())
        system_context = current_system_context(handle)
        evidence_ids = handle.objects.ids(EvidenceReference)
        index = EvidenceIndex(handle)

        produced: list[str] = []
        consumed: list[str] = []
        mapping_ids: list[str] = []
        gap_ids: list[str] = []
        for threat in _sorted_by_id(handle.objects.list(Threat)):
            node = RequirementControlMappingNode(
                ledger=self.ledger,
                index=index,
                profile=self.profile,
                registry=self.registry,
                context=system_context,
                catalog=catalog,
                threat=threat,
                evidence_ids=evidence_ids,
                budget=self.budget,
            )
            result = node.run(context)
            produced.extend(result.produced_object_ids)
            consumed.append(threat.id)
            mapping_ids.extend(result.state_changes.get("control_mapping_ids", []))  # type: ignore[arg-type]
            gap_ids.extend(result.state_changes.get("documentation_gap_ids", []))  # type: ignore[arg-type]

        return NodeResult(
            produced_object_ids=produced,
            consumed_object_ids=consumed,
            state_changes={
                "control_mapping_ids": mapping_ids,
                "documentation_gap_ids": gap_ids,
            },
            metadata={"catalog_version": catalog.version, "threat_count": len(consumed)},
        )


@dataclass(slots=True)
class MappingValidationAdapter:
    """Phase 7, second node: validate the mapping set and persist the downgrades it corrected."""

    version: str = "0.1"

    name: ClassVar[str] = "mapping-validation"
    phase: ClassVar[Phase] = Phase.REQUIREMENT_AND_CONTROL_MAPPING
    execution_type: ClassVar[ExecutionType] = ExecutionType.DETERMINISTIC

    def run(self, context: NodeContext) -> NodeResult:
        handle = context.handle
        assessment = handle.objects.get(Assessment, handle.assessment_id)
        catalog = load_catalog(assessment.requirements_catalog_version or current_version())
        mappings = _sorted_by_id(handle.objects.list(ControlMapping))
        outcome = validate_mappings(
            mappings,
            catalog_version=catalog.version,
            requirements=catalog.requirements,
            threats=handle.objects.list(Threat),
            controls=handle.objects.list(Control),
            observations=handle.objects.list(SourceObservation),
        )
        if not outcome.valid:
            raise _blocking_stop("mapping validation", outcome.blocking_errors)

        applied = apply_downgrades(mappings, outcome)
        downgraded = [
            after
            for after, before in zip(applied, mappings, strict=True)
            if after.model_dump() != before.model_dump()
        ]
        if downgraded:
            with handle.objects.transaction():
                for mapping in downgraded:
                    handle.objects.save(mapping)

        return NodeResult(
            consumed_object_ids=[mapping.id for mapping in mappings],
            metadata={
                "mapping_count": len(mappings),
                "downgrade_count": len(outcome.downgrades),
                "suppression_count": len(outcome.suppressions),
                "duplicate_count": len(outcome.duplicates),
                "conflict_count": len(outcome.conflicts),
                "trigger_count": len(outcome.triggers),
            },
        )


@dataclass(slots=True)
class _EvidenceHandoff:
    """The proposal the model node produced, on its way to the node that validates it.

    A proposal has no identifier and is never persisted (DEC-006), so the handoff is in memory.
    It never needs to survive a process exit: no pause phase sits between the two nodes.
    """

    outcome: EvidenceValidationOutcome | None = None
    subjects: list[DomainModel] = field(default_factory=list)
    subject_ids: list[str] = field(default_factory=list)
    observations: list[SourceObservation] = field(default_factory=list)


@dataclass(slots=True)
class EvidenceValidationAdapter:
    """Phase 8, first node: the evidence agent, over every assessable subject."""

    ledger: ExecutionLedger
    profile: ModelProfile
    registry: PromptRegistry
    handoff: _EvidenceHandoff
    budget: Budget | None = None
    version: str = "0.1"

    name: ClassVar[str] = "evidence-validation"
    phase: ClassVar[Phase] = Phase.EVIDENCE_VALIDATION
    execution_type: ClassVar[ExecutionType] = ExecutionType.MODEL
    records_own_execution: ClassVar[bool] = True

    def run(self, context: NodeContext) -> NodeResult:
        handle = context.handle
        assessable = [
            *_sorted_by_id(handle.objects.list(ContextClaim)),
            *_sorted_by_id(handle.objects.list(Control)),
            *_sorted_by_id(handle.objects.list(ControlMapping)),
            *_sorted_by_id(handle.objects.list(Threat)),
        ]
        subjects: list[DomainModel] = list(assessable)
        observations = [
            observation
            for observation in _sorted_by_id(handle.objects.list(SourceObservation))
            if observation.kind is ObservationKind.CONTRADICTION
        ]
        node = EvidenceValidationNode(
            ledger=self.ledger,
            index=EvidenceIndex(handle),
            profile=self.profile,
            registry=self.registry,
            subjects=subjects,
            observations=observations,
            budget=self.budget,
        )
        outcome = node.propose(context)
        self.handoff.outcome = outcome
        self.handoff.subjects = subjects
        self.handoff.subject_ids = [subject.id for subject in assessable]
        self.handoff.observations = observations
        return outcome.result


@dataclass(slots=True)
class EvidenceAssessmentValidationAdapter:
    """Phase 8, second node: validate the proposal against what was supplied, then persist."""

    handoff: _EvidenceHandoff
    version: str = "0.1"

    name: ClassVar[str] = "evidence-assessment-validation"
    phase: ClassVar[Phase] = Phase.EVIDENCE_VALIDATION
    execution_type: ClassVar[ExecutionType] = ExecutionType.DETERMINISTIC

    def run(self, context: NodeContext) -> NodeResult:
        handle = context.handle
        outcome = self.handoff.outcome
        if outcome is None:  # pragma: no cover - the table orders the two nodes
            raise WorkflowError(
                ErrorClass.UNEXPECTED_APPLICATION_FAILURE,
                "evidence-assessment-validation ran before evidence-validation proposed anything",
            )
        result = validate_assessments(
            outcome.proposal,
            subjects=self.handoff.subjects,
            references=handle.objects.list(EvidenceReference),
            observations=self.handoff.observations,
            supplied_contradiction_ids=outcome.package.contradiction_ids,
        )
        if not result.valid:
            raise _blocking_stop("evidence assessment validation", result.blocking_errors)
        written, updated = persist_assessments(handle, outcome.proposal, result)
        return NodeResult(
            produced_object_ids=[assessment.id for assessment in written],
            consumed_object_ids=list(self.handoff.subject_ids),
            metadata={
                "assessment_count": len(written),
                "control_transition_count": len(updated),
            },
        )


@dataclass(slots=True)
class _CritiqueHandoff:
    """Each review group's proposal, on its way to validation (same shape as `_EvidenceHandoff`)."""

    outcomes: list[tuple[SelectedObjects, CriticalReviewOutcome]] = field(default_factory=list)


@dataclass(slots=True)
class CriticalReviewAdapter:
    """Phase 9, first node: the critic, once per threat's review group (DEC-049)."""

    ledger: ExecutionLedger
    profile: ModelProfile
    registry: PromptRegistry
    handoff: _CritiqueHandoff
    budget: Budget | None = None
    version: str = "0.1"

    name: ClassVar[str] = "critical-review"
    phase: ClassVar[Phase] = Phase.CRITICAL_REVIEW
    execution_type: ClassVar[ExecutionType] = ExecutionType.MODEL
    records_own_execution: ClassVar[bool] = True

    def run(self, context: NodeContext) -> NodeResult:
        handle = context.handle
        mappings = handle.objects.list(ControlMapping)
        controls = handle.objects.list(Control)
        assessments = handle.objects.list(EvidenceAssessment)
        gaps = handle.objects.list(DocumentationGap)

        # DEC-064: rationale-bearing dismissals from this assessment's prior runs, matched per
        # lineage below. Empty on a first run — findings are consolidated after this phase — and
        # populated on a revision, which is the decided dormancy.
        findings = handle.objects.list(Finding)
        decisions = handle.objects.list(ReviewerDecision)
        component_names = component_name_index(handle)

        consumed: list[str] = []
        self.handoff.outcomes.clear()
        # One index for the whole phase, not one per threat: it caches the source documents and
        # files it reads, so building a fresh one each iteration threw that cache away and re-read
        # every source once per threat.
        index = EvidenceIndex(handle)
        for threat in _sorted_by_id(handle.objects.list(Threat)):
            selected = select_review_group(
                threat,
                mappings=mappings,
                controls=controls,
                assessments=assessments,
                documentation_gaps=gaps,
            )
            node = CriticalReviewNode(
                ledger=self.ledger,
                index=index,
                profile=self.profile,
                registry=self.registry,
                selected=selected,
                precedents=select_precedents(
                    selected=selected,
                    findings=findings,
                    decisions=decisions,
                    component_names=component_names,
                ),
                budget=self.budget,
            )
            outcome = node.propose(context)
            self.handoff.outcomes.append((selected, outcome))
            consumed.append(threat.id)

        return NodeResult(
            consumed_object_ids=consumed,
            metadata={"review_group_count": len(consumed)},
        )


@dataclass(slots=True)
class CritiqueValidationAdapter:
    """Phase 9, second node: validate each group's critiques and persist the survivors."""

    handoff: _CritiqueHandoff
    version: str = "0.1"

    name: ClassVar[str] = "critique-validation"
    phase: ClassVar[Phase] = Phase.CRITICAL_REVIEW
    execution_type: ClassVar[ExecutionType] = ExecutionType.DETERMINISTIC

    # Every subject type the critique package presents. EVIDENCE_ASSESSMENT was missing until
    # the live capture produced a critique of one and the validator refused an object that was
    # sitting in the store (#324): the package deliberately shows the critic the assessments, so
    # the map must let a critique land on them.
    _SUBJECT_MODELS: ClassVar[dict[CritiqueSubjectType, type[DomainModel]]] = {
        CritiqueSubjectType.THREAT: Threat,
        CritiqueSubjectType.CONTROL: Control,
        CritiqueSubjectType.CONTROL_MAPPING: ControlMapping,
        CritiqueSubjectType.EVIDENCE_ASSESSMENT: EvidenceAssessment,
        CritiqueSubjectType.DOCUMENTATION_GAP: DocumentationGap,
    }

    def run(self, context: NodeContext) -> NodeResult:
        handle = context.handle
        produced: list[str] = []
        for selected, outcome in self.handoff.outcomes:
            subjects: list[DomainModel] = [
                selected.threat,
                *selected.mappings,
                *selected.controls,
                *selected.assessments,
                *selected.documentation_gaps,
            ]
            validated = validate_critiques(
                outcome.proposal,
                subjects=subjects,
                subject_models=self._SUBJECT_MODELS,
                reviewed_object_count=outcome.group.reviewed_object_count,
                maximum_reinvocations=DEFAULT_MAXIMUM_REINVOCATIONS,
                volume_ratio=DEFAULT_VOLUME_RATIO,
            )
            if not validated.valid:
                raise _blocking_stop("critique validation", validated.blocking_errors)
            critiques = persist_critiques(handle, outcome.proposal, validated)
            produced.extend(critique.id for critique in critiques)

        return NodeResult(
            produced_object_ids=produced,
            metadata={"critique_count": len(produced)},
        )


@dataclass(slots=True)
class FindingConsolidationAdapter:
    """Phase 10: consolidate, deduplicate, and apply the persisted critiques to the findings.

    Critique application lives here rather than in phase 9 because its recommendations land on
    findings, and findings first exist here. The order inside the phase is fixed by the data:
    consolidation mints the findings, dedup needs their store identifiers to pick survivors, and
    application revises whatever survived.
    """

    version: str = "0.1"

    name: ClassVar[str] = "finding-consolidation"
    phase: ClassVar[Phase] = Phase.FINDING_CONSOLIDATION
    execution_type: ClassVar[ExecutionType] = ExecutionType.DETERMINISTIC

    def run(self, context: NodeContext) -> NodeResult:
        handle = context.handle
        from trace_ai.domain.critique import Critique
        from trace_ai.domain.question import Question

        outcome = consolidate(
            threats=handle.objects.list(Threat),
            mappings=handle.objects.list(ControlMapping),
            assessments=handle.objects.list(EvidenceAssessment),
            assessment_id=handle.assessment_id,
        )
        stored = persist_consolidation(handle, outcome)
        deduped = dedupe_findings(stored.findings)
        persist_dedup(handle, deduped)

        applied = apply_critiques(
            _sorted_by_id(handle.objects.list(Critique)),
            findings=handle.objects.list(Finding),
            documentation_gaps=handle.objects.list(DocumentationGap),
            assessments=handle.objects.list(EvidenceAssessment),
        )
        persist_application(handle, applied)

        from trace_ai.domain.base import now
        from trace_ai.workflow.reason_codes import revisit_due_findings

        candidates = [
            finding.id
            for finding in _sorted_by_id(handle.objects.list(Finding))
            if finding.duplicate_of_id is None and finding.status is ObjectStatus.CANDIDATE
        ]
        # DEC-061/DEC-079: an approved finding whose accepted-risk review-by date has passed
        # re-enters checkpoint 2 this run. Its `accept` stands until re-decided; the run-scoped
        # completion is what re-prompts it. Expiry is evaluated here, against the run's date.
        revisit = revisit_due_findings(handle, now().date())
        candidates = candidates + sorted(revisit - set(candidates))
        return NodeResult(
            produced_object_ids=[finding.id for finding in stored.findings],
            state_changes={
                "candidate_finding_ids": candidates,
                "documentation_gap_ids": sorted(
                    gap.id for gap in handle.objects.list(DocumentationGap)
                ),
                "open_question_ids": sorted(
                    question.id for question in handle.objects.list(Question)
                ),
            },
            metadata={
                "finding_count": len(stored.findings),
                "candidate_count": len(candidates),
            },
        )


@dataclass(slots=True)
class _ReportHandoff:
    """The assembled input and generated sections, between the report phase's two nodes."""

    assembled: ReportInput | None = None
    sections: ReportSections | None = None


@dataclass(slots=True)
class ReportGenerationAdapter:
    """Phase 12, first node: the report agent, over approved objects only."""

    ledger: ExecutionLedger
    profile: ModelProfile
    registry: PromptRegistry
    handoff: _ReportHandoff
    budget: Budget | None = None
    version: str = "0.1"

    name: ClassVar[str] = "report-generation"
    phase: ClassVar[Phase] = Phase.REPORT_GENERATION
    execution_type: ClassVar[ExecutionType] = ExecutionType.MODEL
    records_own_execution: ClassVar[bool] = True

    def run(self, context: NodeContext) -> NodeResult:
        assembled = assemble_report_input(
            context.handle,
            prompt_versions={REPORT_PROMPT_ID: f"{REPORT_PROMPT_ID}-{REPORT_PROMPT_VERSION}"},
            model=self.profile.model,
            model_configuration=self.profile.name,
            authoritative=True,
        )
        node = ReportGenerationNode(
            ledger=self.ledger,
            profile=self.profile,
            registry=self.registry,
            assembled=assembled,
            budget=self.budget,
        )
        outcome = node.generate(context)
        self.handoff.assembled = assembled
        self.handoff.sections = outcome.sections
        return outcome.result


@dataclass(slots=True)
class ReportRenderingAdapter:
    """Phase 12, second node: deterministic render, validation, and the manifest (DEC-035).

    `generated_at` pins the one timestamp the rendered document carries. A replayed run passes
    the recording's stamp so two replays produce byte-identical reports; a live run leaves it
    unset and gets `now()`.
    """

    ledger: ExecutionLedger
    handoff: _ReportHandoff
    generated_at: datetime | None = None
    version: str = "0.1"

    name: ClassVar[str] = "report-rendering"
    phase: ClassVar[Phase] = Phase.REPORT_GENERATION
    execution_type: ClassVar[ExecutionType] = ExecutionType.DETERMINISTIC
    records_own_execution: ClassVar[bool] = True

    def run(self, context: NodeContext) -> NodeResult:
        assembled = self.handoff.assembled
        sections = self.handoff.sections
        if assembled is None or sections is None:  # pragma: no cover - the table orders the nodes
            raise WorkflowError(
                ErrorClass.UNEXPECTED_APPLICATION_FAILURE,
                "report-rendering ran before report-generation produced sections",
            )
        try:
            published = publish_report(
                context.handle,
                assembled,
                sections,
                ledger=self.ledger,
                workflow_run_id=context.state.workflow_run_id,
                generated_at=self.generated_at,
            )
        except ReportValidationFailedError as error:
            raise WorkflowError(
                ErrorClass.SCHEMA_VALIDATION_FAILURE,
                "the rendered report failed its consistency validation; the failed sections are "
                "preserved under traces/",
            ) from error

        # The report-quality metrics (#329), from the same validation passes that gated
        # publication. Persisted here rather than in the evaluation node because the outcomes
        # are in hand now and are not persisted state; the evaluation node's summary lists its
        # own rows, and the harness reads every row from the repository.
        run = context.handle.objects.get(WorkflowRun, context.state.workflow_run_id)
        report_results = compute_report_metrics(
            context.handle,
            run,
            sections_outcome=published.sections_outcome,
            rendered_outcome=published.rendered_outcome,
            rendered_markdown=published.report.markdown,
            approved_count=len(assembled.approved_findings),
            prose_passages=(
                sections.executive_summary,
                sections.system_overview,
                sections.risk_summary,
                *(entry.text for entry in sections.limitations),
            ),
        )
        with context.handle.objects.transaction():
            for result in report_results:
                context.handle.objects.save(result)

        return NodeResult(
            produced_object_ids=[result.id for result in report_results],
            metadata={
                "report_path": published.manifest["report"]["path"],
                "report_hash": published.manifest["report"]["content_hash"],
            },
        )


@dataclass(slots=True)
class EvaluationAdapter:
    """Phase 13: the run's own metrics, computed and persisted; benchmark metrics need a truth set."""

    version: str = "0.1"

    name: ClassVar[str] = "evaluation"
    phase: ClassVar[Phase] = Phase.EVALUATION
    execution_type: ClassVar[ExecutionType] = ExecutionType.DETERMINISTIC

    def run(self, context: NodeContext) -> NodeResult:
        handle = context.handle
        run = handle.objects.get(WorkflowRun, context.state.workflow_run_id)
        results = compute_metrics(handle, run)
        persist_metrics(handle, run, results)
        return NodeResult(
            produced_object_ids=[result.id for result in results],
            metadata={"metric_count": len(results)},
        )


# -- ablation stand-ins ------------------------------------------------------------------------


@dataclass(slots=True)
class AblatedNode:
    """A declared node's stand-in under an ablation: same name, same phase, no work.

    The table still requires every declared name registered — an ablation is a *named removal on
    a marked run*, not a silent skip — so the stand-in exists to be registered and to record that
    the phase's work did not happen.
    """

    name: str
    phase: Phase
    ablation: str
    version: str = "0.1"

    execution_type: ClassVar[ExecutionType] = ExecutionType.DETERMINISTIC

    def run(self, context: NodeContext) -> NodeResult:
        return NodeResult(metadata={"ablated_by": self.ablation})


@dataclass(slots=True)
class AblatedContextApprovalNode:
    """Checkpoint 1 under `no-context-approval`: approve as generated, recorded as such.

    The extracted context is approved verbatim with every object decided by the ablation's named
    reviewer, because downstream structure makes an unapproved context impossible to analyse
    (`UnapprovedContextError`) — the ablation removes the human filter, not the approval record.
    A blocking validation error still refuses: an ablation does not overrule a blocker, it only
    removes the person who would have read it.
    """

    version: str = "0.1"

    name: ClassVar[str] = "human-context-review"
    phase: ClassVar[Phase] = Phase.HUMAN_CONTEXT_REVIEW
    execution_type: ClassVar[ExecutionType] = ExecutionType.DETERMINISTIC
    REVIEWER: ClassVar[str] = "ablation:no-context-approval"

    def run(self, context: NodeContext) -> NodeResult:
        from trace_ai.workflow.context_review import (
            ApprovalRefusedError,
            approve_context,
            build_context_review_package,
            decide_object,
        )
        from trace_ai.workflow.context_validation import validate_context

        handle = context.handle
        from trace_ai.domain.enums import ReviewDisposition

        decided: list[str] = []
        for obj in context_objects(handle):
            _, decision = decide_object(
                handle, obj, ReviewDisposition.APPROVE, reviewer_id=self.REVIEWER
            )
            decided.append(decision.subject_id)
        reviewed = current_system_context(handle)
        validation = validate_context(
            reviewed,
            context_objects(handle),
            available_evidence=set(handle.objects.ids(EvidenceReference)),
            previous=previous_approved_context(handle, reviewed),
        )
        package = build_context_review_package(
            handle, index=EvidenceIndex(handle), validation=validation
        )
        try:
            approved, _decision = approve_context(handle, package, reviewer_id=self.REVIEWER)
        except ApprovalRefusedError as refused:
            raise WorkflowError(
                ErrorClass.REVIEWER_INPUT_REQUIRED,
                f"the ablated approval was refused with {len(refused.blockers)} blocker(s); "
                f"an ablation removes the reviewer, not the blockers",
            ) from refused
        return NodeResult(
            consumed_object_ids=decided,
            state_changes={"system_context_version": approved.version},
            metadata={"ablated_by": "no-context-approval", "approved_as_generated": len(decided)},
        )


# Which registered node names each ablation removes. Kept beside `KNOWN_ABLATIONS`, and
# `_apply_ablations` asserts every requested ablation matched at least one -- a name that has drifted
# out of step with the node it removes would otherwise substitute nothing and run the full pipeline
# while marking the run non-authoritative, which is a measurement that lies rather than one that
# stops.
_ABLATION_NODE_NAMES: Final = {
    "no-evidence-validation": frozenset({"evidence-validation", "evidence-assessment-validation"}),
    "no-critical-review": frozenset({"critical-review", "critique-validation"}),
    "no-context-approval": frozenset({"human-context-review"}),
}


def _apply_ablations(nodes: list[Node], ablations: Sequence[str]) -> list[Node]:
    """Substitute stand-ins for the nodes each ablation removes. Unknown names were refused."""
    substitutions: dict[str, int] = dict.fromkeys(ablations, 0)
    replaced: list[Node] = []
    for node in nodes:
        substituted = False
        for ablation in ablations:
            if node.name not in _ABLATION_NODE_NAMES.get(ablation, frozenset()):
                continue
            if ablation == "no-context-approval":
                replaced.append(AblatedContextApprovalNode())
            else:
                replaced.append(AblatedNode(name=node.name, phase=node.phase, ablation=ablation))
            substitutions[ablation] += 1
            substituted = True
            break
        if not substituted:
            replaced.append(node)

    unmatched = sorted(ablation for ablation, count in substitutions.items() if count == 0)
    if unmatched:
        raise ValueError(
            f"ablation(s) {unmatched} substituted no node; the removal map is stale (a node name "
            f"changed). A run marked non-authoritative that in fact ran the full pipeline is worse "
            f"than one that stops, so this refuses rather than silently ablating nothing."
        )
    return replaced


# -- composition -------------------------------------------------------------------------------


def build_nodes(
    handle: AssessmentHandle,
    *,
    ledger: ExecutionLedger,
    profile: ModelProfile,
    budget: Budget | None = None,
    structured_input: dict[str, Any] | None = None,
    generated_at: datetime | None = None,
    ablations: Sequence[str] = (),
) -> list[Node]:
    """Every node the fourteen phases declare, constructed against one run's dependencies.

    With `ablations`, the removed nodes are substituted by named stand-ins rather than omitted —
    the table still sees every declared name, and the removal is a property of a marked run, not
    a silent gap in registration (DEC-012, DEC-073).
    """
    # Issue #349: every composition a run makes snapshots its PromptDefinition into the
    # assessment's traces/prompts/, so an execution record's prompt identity resolves to a
    # persisted definition. The nodes see an ordinary registry.
    registry = PersistingPromptRegistry(handle)
    assessment = handle.objects.get(Assessment, handle.assessment_id)
    evidence_handoff = _EvidenceHandoff()
    critique_handoff = _CritiqueHandoff()
    report_handoff = _ReportHandoff()
    nodes: list[Node] = [
        AssessmentInitializationNode(),
        DocumentIngestionNode(),
        EvidenceIndexingNode(),
        ContextExtractionAdapter(
            ledger=ledger,
            profile=profile,
            registry=registry,
            assessment_name=assessment.name,
            budget=budget,
            structured_input=structured_input,
        ),
        ContextValidationAdapter(),
        ContextReviewNode(),
        ThreatAnalysisAdapter(
            ledger=ledger,
            profile=profile,
            registry=registry,
            assessment_name=assessment.name,
            budget=budget,
        ),
        ThreatValidationAdapter(),
        RequirementControlMappingAdapter(
            ledger=ledger,
            profile=profile,
            registry=registry,
            budget=budget,
        ),
        MappingValidationAdapter(),
        EvidenceValidationAdapter(
            ledger=ledger,
            profile=profile,
            registry=registry,
            handoff=evidence_handoff,
            budget=budget,
        ),
        EvidenceAssessmentValidationAdapter(handoff=evidence_handoff),
        CriticalReviewAdapter(
            ledger=ledger,
            profile=profile,
            registry=registry,
            handoff=critique_handoff,
            budget=budget,
        ),
        CritiqueValidationAdapter(handoff=critique_handoff),
        FindingConsolidationAdapter(),
        FindingReviewNode(),
        ReportGenerationAdapter(
            ledger=ledger,
            profile=profile,
            registry=registry,
            handoff=report_handoff,
            budget=budget,
        ),
        ReportRenderingAdapter(ledger=ledger, handoff=report_handoff, generated_at=generated_at),
        EvaluationAdapter(),
    ]
    if ablations:
        unknown = sorted(set(ablations) - KNOWN_ABLATIONS)
        if unknown:
            raise ValueError(
                f"unknown ablation(s) {unknown}; the family is closed (DEC-074): "
                f"{', '.join(sorted(KNOWN_ABLATIONS))}"
            )
        nodes = _apply_ablations(nodes, ablations)
    return nodes


def run_assessment(
    service: AssessmentService,
    assessment_id: str,
    *,
    model: StructuredModel,
    profile: ModelProfile,
    budget: Budget | None = None,
    structured_input: dict[str, Any] | None = None,
    generated_at: datetime | None = None,
    ablations: Sequence[str] = (),
    stop_before: Phase | None = None,
) -> RunOutcome:
    """Run a fresh assessment from initialization until it pauses, completes, or stops.

    The budget defaults to the assessment's own configuration (`Budget.from_configuration`), which
    is where DEC-012 left the ceilings: limits are configuration, checkpoints are not.

    The caller is the service, not a bare handle, because the deliverable's lifecycle moves with
    the run: a pause writes `begin_review` in the same transaction as the run row (DEC-031), and a
    failed run leaves the assessment in `draft` by never reaching that transaction.
    """
    handle = service.handle(assessment_id)
    assessment = handle.objects.get(Assessment, assessment_id)
    # A fresh run reaches checkpoint 1 and, on pausing, moves the assessment to `pending_review`
    # (DEC-031). That move is only valid from `draft`, so an assessment left at `pending_review` (a
    # prior run abandoned mid-review) or `approved` (a revision) must return to `draft` first --
    # otherwise the pause raised `InvalidStatusTransitionError` deep in the loop and left the run
    # row, the state file, and the assessment disagreeing. `begin_revision` is the named verb for
    # the approved case; `resume_from_review` for the pending case.
    if assessment.status is ObjectStatus.PENDING_REVIEW:
        service.resume_from_review(assessment_id)
    elif assessment.status is ObjectStatus.APPROVED:
        service.begin_revision(assessment_id)
    spend = budget if budget is not None else Budget.from_configuration(assessment.configuration)
    run = start_run(
        handle,
        workflow_version=WORKFLOW_VERSION,
        model_profile=profile.name,
        ablations=ablations,
    )
    ledger = ExecutionLedger(handle, run)
    orchestrator = Orchestrator(
        handle,
        ledger=ledger,
        nodes=build_nodes(
            handle,
            ledger=ledger,
            profile=profile,
            budget=spend,
            structured_input=structured_input,
            generated_at=generated_at,
            ablations=ablations,
        ),
        budget=spend,
        model=model,
        on_pause=_begin_review_on_pause(service, assessment_id),
    )
    outcome = orchestrator.run(
        AssessmentState.begin(assessment_id=assessment_id, workflow_run_id=run.id),
        stop_before=stop_before,
    )
    _emit_external_tracing(handle, assessment.configuration, run.id)
    return outcome


def resume_assessment(
    service: AssessmentService,
    assessment_id: str,
    *,
    model: StructuredModel,
    profile: ModelProfile,
    workflow_run_id: str | None = None,
    budget: Budget | None = None,
    generated_at: datetime | None = None,
    stop_before: Phase | None = None,
) -> RunOutcome:
    """Resume a paused run in a fresh process (DEC-017: resuming is a read).

    The checkpoint node runs again and decides nothing new: with every subject decided it comes
    back empty and the run advances; with any subject still waiting the run pauses again, which is
    the partial-progress case DEC-017 allows.

    Resuming ends the review session: an assessment sitting at `pending_review` returns to `draft`
    before the run continues (DEC-031's `resume_from_review`), and if the checkpoint still blocks,
    the re-pause moves it right back. `trace findings approve` concludes the review through the
    same verb, so an assessment already back in `draft` is left alone.
    """
    from trace_ai.domain.execution import RunStatus
    from trace_ai.workflow.checkpoint import load_state

    handle = service.handle(assessment_id)
    run = _resumable_run(handle, workflow_run_id)
    if run.status is RunStatus.PAUSED:
        # A checkpoint pause: the checkpoint node re-runs and decides nothing new.
        state, _pending = resume(handle, run.id)
        assessment = handle.objects.get(Assessment, assessment_id)
        if assessment.status is ObjectStatus.PENDING_REVIEW:
            service.resume_from_review(assessment_id)
    elif run.status is RunStatus.FAILED:
        # A failed run: restart from the phase it stopped in. The phases before it completed, so
        # their objects exist and are not re-run; only the failed phase re-executes.
        state = load_state(handle, run.id).restarted()
        assessment = handle.objects.get(Assessment, assessment_id)
    else:
        raise ValueError(
            f"{run.id} is {run.status.value}, not paused or failed; there is nothing to resume"
        )
    spend = budget if budget is not None else Budget.from_configuration(assessment.configuration)
    ledger = ExecutionLedger(handle, run)
    if run.status is RunStatus.FAILED:
        # Clear the failed run's completion stamp and error before it runs again, so its row is a
        # running run's rather than a completed one carrying a `running` status.
        ledger.reopen()
    orchestrator = Orchestrator(
        handle,
        ledger=ledger,
        nodes=build_nodes(
            handle,
            ledger=ledger,
            profile=profile,
            budget=spend,
            generated_at=generated_at,
            ablations=run.ablations,
        ),
        budget=spend,
        model=model,
        on_pause=_begin_review_on_pause(service, assessment_id),
    )
    outcome = orchestrator.run(state, stop_before=stop_before)
    _emit_external_tracing(handle, assessment.configuration, run.id)
    return outcome


def _emit_external_tracing(
    handle: AssessmentHandle, configuration: AssessmentConfiguration, workflow_run_id: str
) -> None:
    """Export the run's execution records as spans when the assessment opted in (#538).

    Runs after the orchestrator returns, whatever the outcome — a paused, failed, or completed
    run's records all export, because observability of a failure is the point. The flag is the
    assessment's (`enable_external_tracing`, default off, DEC-012's limits-are-configuration
    side); the destination is the operator's (`Settings.tracing_endpoint`). Emission failures
    are logged and swallowed inside `emit_run`: the local ledger stays authoritative
    (section 5.17), and no run fails because its observability endpoint did.
    """
    if not configuration.enable_external_tracing:
        return
    from trace_ai.config import get_settings
    from trace_ai.infrastructure.tracing import emit_run, emitter_from_settings

    emitter = emitter_from_settings(get_settings())
    if emitter is None:
        import logging

        logging.getLogger(__name__).info(
            "external tracing is enabled but no tracing endpoint is configured; nothing emitted",
            extra={"workflow_run_id": workflow_run_id},
        )
        return
    emit_run(handle, workflow_run_id, emitter)


def _begin_review_on_pause(
    service: AssessmentService, assessment_id: str
) -> Callable[[AssessmentState], None]:
    """DEC-031's half of a pause: the assessment moves to `pending_review` with the run row."""

    def on_pause(_state: AssessmentState) -> None:
        service.begin_review(assessment_id)

    return on_pause


def _resumable_run(handle: AssessmentHandle, workflow_run_id: str | None) -> WorkflowRun:
    """The run a resume acts on: a named one, or the most recent paused-or-failed one.

    A paused run resumes at its checkpoint; a failed run restarts from the phase it stopped in
    (DEC-017, both are a read in a new process). A named run is returned whatever its status, so a
    caller that knows the identifier can inspect the refusal a resume would give it.
    """
    from trace_ai.domain.execution import RunStatus

    if workflow_run_id is not None:
        return handle.objects.get(WorkflowRun, workflow_run_id)
    resumable = [
        run
        for run in handle.objects.list(WorkflowRun)
        if run.status in (RunStatus.PAUSED, RunStatus.FAILED)
    ]
    if not resumable:
        raise ValueError(
            f"assessment {handle.assessment_id} has no paused or failed workflow run to resume"
        )
    return resumable[-1]
