"""The pipeline as declared data: fourteen phases and the transitions permitted between them.

DEC-016 orchestrates with plain Python, "a node protocol, an explicit table of permitted
transitions, and a persisted `WorkflowRun` row", and says a transition not named in the table is an
error rather than an undefined behaviour. This module is the table.

**Phases are `current-architecture.md` section 5.3's fourteen**, which is the list DEC-016 counts.
`agent-design.md` section 3 draws a finer-grained graph — seventeen nodes — and the two are not in
conflict once the relationship is stated: a *phase* is the unit a transition moves between, and one
phase may run several nodes. Threat generation runs the Threat Analysis agent and then the Threat
Validation node; document ingestion runs the loader and then evidence indexing. `NODES_BY_PHASE`
records which nodes belong to which phase, so the two documents describe one pipeline rather than
two.

**The pipeline is a sequence, and the table says so.** There is no analytical branching — DEC-016
gives that as a reason a graph framework helps least here — so every phase names exactly one
successor, except the terminal one, which names none. That makes the table look redundant against a
list, and it is not: what it buys is that *any other* transition is refused by name. A pipeline
whose order lives in the order the calls happen to be written has no way to refuse anything.

**A phase may not transition to itself.** `agent-design.md` section 27 requires the orchestrator to
prevent uncontrolled loops, and a self-transition is the smallest one. A retry is a second execution
*within* a phase and is bounded separately; it is not a transition.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Final

__all__ = [
    "NODES_BY_PHASE",
    "PAUSE_PHASES",
    "TRANSITIONS",
    "Phase",
    "TransitionError",
    "check_transition",
    "successor",
]


class Phase(StrEnum):
    """`current-architecture.md` section 5.3's fourteen workflow phases, in order."""

    ASSESSMENT_INITIALIZATION = "assessment_initialization"
    DOCUMENT_INGESTION = "document_ingestion"
    CONTEXT_EXTRACTION = "context_extraction"
    CONTEXT_VALIDATION = "context_validation"
    HUMAN_CONTEXT_REVIEW = "human_context_review"
    """Checkpoint 1. A structural node, not a runtime conditional (DEC-005)."""

    THREAT_GENERATION = "threat_generation"
    REQUIREMENT_AND_CONTROL_MAPPING = "requirement_and_control_mapping"
    EVIDENCE_VALIDATION = "evidence_validation"
    CRITICAL_REVIEW = "critical_review"
    FINDING_CONSOLIDATION = "finding_consolidation"
    HUMAN_FINDING_REVIEW = "human_finding_review"
    """Checkpoint 2. The reviewer assigns severity here (DEC-030)."""

    REPORT_GENERATION = "report_generation"
    EVALUATION = "evaluation"
    ASSESSMENT_COMPLETION = "assessment_completion"


# The two structural checkpoints (DEC-005). Named here because several things need to ask whether a
# phase is one -- and because a list of two is the honest way to say "structural": there is no
# configuration that adds a third or removes one (DEC-012).
PAUSE_PHASES: Final[frozenset[Phase]] = frozenset(
    {Phase.HUMAN_CONTEXT_REVIEW, Phase.HUMAN_FINDING_REVIEW}
)

# Which `agent-design.md` section 3 nodes run in which phase. Documentation of the mapping between
# the two granularities, and the thing a node registry is checked against: a node claiming a phase
# that does not list it is a node nobody decided to put there.
NODES_BY_PHASE: Final[dict[Phase, tuple[str, ...]]] = {
    Phase.ASSESSMENT_INITIALIZATION: ("assessment-initialization",),
    Phase.DOCUMENT_INGESTION: ("document-ingestion", "evidence-indexing"),
    Phase.CONTEXT_EXTRACTION: ("context-extraction",),
    Phase.CONTEXT_VALIDATION: ("context-validation",),
    Phase.HUMAN_CONTEXT_REVIEW: ("human-context-review",),
    Phase.THREAT_GENERATION: ("threat-analysis", "threat-validation"),
    Phase.REQUIREMENT_AND_CONTROL_MAPPING: (
        "requirement-and-control-mapping",
        "mapping-validation",
    ),
    # Two nodes each, for the reason the mapping and threat phases have two: an agent and the
    # deterministic node behind it. Section 3's diagram drew neither validation node until
    # DEC-048; both were built anyway, and both are the only path to persistence for what their
    # agent proposes.
    Phase.EVIDENCE_VALIDATION: ("evidence-validation", "evidence-assessment-validation"),
    Phase.CRITICAL_REVIEW: ("critical-review", "critique-validation"),
    Phase.FINDING_CONSOLIDATION: ("finding-consolidation",),
    Phase.HUMAN_FINDING_REVIEW: ("human-finding-review",),
    Phase.REPORT_GENERATION: ("report-generation", "report-rendering"),
    Phase.EVALUATION: ("evaluation",),
    Phase.ASSESSMENT_COMPLETION: (),
}

# Every permitted transition. One successor each, because the pipeline has no analytical branching;
# the value is a set so a future branch is a data change rather than a redesign.
TRANSITIONS: Final[dict[Phase, frozenset[Phase]]] = {
    Phase.ASSESSMENT_INITIALIZATION: frozenset({Phase.DOCUMENT_INGESTION}),
    Phase.DOCUMENT_INGESTION: frozenset({Phase.CONTEXT_EXTRACTION}),
    Phase.CONTEXT_EXTRACTION: frozenset({Phase.CONTEXT_VALIDATION}),
    Phase.CONTEXT_VALIDATION: frozenset({Phase.HUMAN_CONTEXT_REVIEW}),
    Phase.HUMAN_CONTEXT_REVIEW: frozenset({Phase.THREAT_GENERATION}),
    Phase.THREAT_GENERATION: frozenset({Phase.REQUIREMENT_AND_CONTROL_MAPPING}),
    Phase.REQUIREMENT_AND_CONTROL_MAPPING: frozenset({Phase.EVIDENCE_VALIDATION}),
    Phase.EVIDENCE_VALIDATION: frozenset({Phase.CRITICAL_REVIEW}),
    Phase.CRITICAL_REVIEW: frozenset({Phase.FINDING_CONSOLIDATION}),
    Phase.FINDING_CONSOLIDATION: frozenset({Phase.HUMAN_FINDING_REVIEW}),
    Phase.HUMAN_FINDING_REVIEW: frozenset({Phase.REPORT_GENERATION}),
    Phase.REPORT_GENERATION: frozenset({Phase.EVALUATION}),
    Phase.EVALUATION: frozenset({Phase.ASSESSMENT_COMPLETION}),
    Phase.ASSESSMENT_COMPLETION: frozenset(),
}


class TransitionError(RuntimeError):
    """An attempted transition the table does not permit.

    The message names both ends, because the useful question after this is raised is which of the
    two is wrong — the phase the run thinks it is in, or the one something tried to move it to.
    """

    def __init__(self, source: Phase, destination: Phase) -> None:
        permitted = sorted(phase.value for phase in TRANSITIONS[source])
        allowed = ", ".join(permitted) if permitted else "nothing — it is terminal"
        super().__init__(
            f"{source.value} -> {destination.value} is not a permitted transition. "
            f"{source.value} may transition to: {allowed}."
        )
        self.source = source
        self.destination = destination


def check_transition(source: Phase, destination: Phase) -> None:
    """Raise unless the table permits moving from `source` to `destination`."""
    if destination not in TRANSITIONS[source]:
        raise TransitionError(source, destination)


def successor(phase: Phase) -> Phase | None:
    """The one phase that may follow `phase`, or `None` at the end of the pipeline.

    Returns a single value rather than a set because the pipeline has one path. A phase that ever
    gains a second successor makes this ambiguous, which is the right time for it to stop
    compiling rather than to start choosing.
    """
    permitted = TRANSITIONS[phase]
    if not permitted:
        return None
    if len(permitted) > 1:
        raise TransitionError(phase, phase)
    return next(iter(permitted))
