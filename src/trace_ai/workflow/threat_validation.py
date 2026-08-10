"""The Threat Validation node: report, propose, and route -- never merge and never correct.

`agent-design.md` section 11 lists eight responsibilities for a deterministic node between threat
generation and control mapping. It carries one explicit constraint, and that constraint is the
whole shape of this module: **the merge decision stays explicit and traceable.** Duplicate threats
are *proposed* for merging, with the features that matched named on the proposal. Nothing here
mutates a threat, deletes one, or silently collapses two into one.

This follows `workflow/context_validation.py` deliberately, and for the same reason: a validator
that corrected its input would be making security judgments with no evidence and no reviewer, and
the corrections would be invisible, because a corrected object validates.

**Duplicate detection is deterministic feature comparison** (DEC-043). Normalized title, affected
component and asset sets, and category overlap, combined into a score with a stated threshold.
`agent-design.md` section 11 permits embeddings or a model-assisted comparison, and
`current-architecture.md` section 17 defers vector infrastructure, so an embedding approach has no
substrate. A model-assisted comparison would put a seventh model call in a node section 4
classifies as deterministic.

**No merge is executed here.** `agent-design.md` section 16 assigns merging to Finding
Consolidation, which is M4. What this node produces is a `MergeProposal`, and the reviewer or that
node decides.

**A low threat count is not a failure.** Section 10 says so directly and this node repeats it by
having no rule that could fire on one. A validator with a minimum count would be the mechanism by
which "quality over volume" quietly became the opposite.

**Errors are returned, not raised**, carrying an `ErrorClass` so the generating node routes on a
classification rather than a message.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from trace_ai.domain.context_claim import ClaimStatus
from trace_ai.domain.threat import KNOWN_THREAT_CATEGORIES
from trace_ai.domain.vocabulary import normalize_term

# One `ReviewTrigger`, not two. `agent-design.md` section 7 and section 10 list human-review
# triggers for two different nodes, and they are the same thing: a named reason, the objects that
# caused it, and a sentence a reviewer can read. A second class with `threat_ids` instead of
# `object_ids` would be the same record under a different name, and whatever renders a review
# package would have to know both.
from trace_ai.workflow.context_validation import ReviewTrigger
from trace_ai.workflow.errors import ErrorClass

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from trace_ai.domain.context_claim import ContextClaim
    from trace_ai.domain.system_context import SystemContext
    from trace_ai.domain.threat import Threat

__all__ = [
    "DUPLICATE_THRESHOLD",
    "SECTION_10_TRIGGERS",
    "MergeProposal",
    "ReviewTrigger",
    "ThreatValidationError",
    "ThreatValidationOutcome",
    "duplicate_groups",
    "validate_threats",
]

# `agent-design.md` section 10's human-review triggers, in the document's order.
SECTION_10_TRIGGERS: Final[tuple[str, ...]] = (
    "critical_threat_depends_on_uncertain_assumption",
    "threats_rely_on_contradictory_context",
    "likely_missing_core_component",
    "architecture_materially_incomplete",
)

# Above this, two threats are proposed as duplicates. Chosen so that an identical title alone is
# not enough and an identical target alone is not enough, but either together with the other half
# is. See DEC-043 for what each weight is doing and why the number is where it is.
DUPLICATE_THRESHOLD: Final = 0.75

# What each feature contributes. They sum to 1.0, so the score reads as a fraction.
_TITLE_WEIGHT: Final = 0.5
_TARGET_WEIGHT: Final = 0.35
_CATEGORY_WEIGHT: Final = 0.15

# A threat set larger than this, with fewer components than that, reads as an architecture the
# agent could not see much of. Both are reported as a trigger rather than as an error: they are
# reasons for a person to look, not statements that anything is wrong.
_THIN_ARCHITECTURE_COMPONENTS: Final = 2


@dataclass(frozen=True, slots=True)
class ThreatValidationError:
    """One problem with one threat, named precisely enough to fix without reading the validator."""

    threat_id: str
    field: str
    rule: str
    message: str
    error_class: ErrorClass = ErrorClass.SCHEMA_VALIDATION_FAILURE

    @property
    def retryable(self) -> bool:
        from trace_ai.workflow.errors import RETRYABLE

        return self.error_class in RETRYABLE

    def retry_instruction(self) -> str:
        """What to tell the next attempt, in terms the agent can act on."""
        return f"{self.threat_id}.{self.field}: {self.message}"


@dataclass(frozen=True, slots=True)
class MergeProposal:
    """Two threats that look like one, and the features that say so.

    A proposal, not a merge. `agent-design.md` section 11 requires the merge decision to stay
    explicit and traceable, and section 16 assigns the merge itself to Finding Consolidation.
    Both identifiers are carried, in sorted order, so the same pair is proposed the same way
    however the threats were ordered.
    """

    threat_ids: tuple[str, str]
    score: float
    matched_features: tuple[str, ...]
    detail: str


@dataclass(frozen=True, slots=True)
class ThreatValidationOutcome:
    """What validated, what did not, what looks duplicated, and why a person should look."""

    errors: tuple[ThreatValidationError, ...] = ()
    triggers: tuple[ReviewTrigger, ...] = ()
    merge_proposals: tuple[MergeProposal, ...] = ()
    unfamiliar_categories: tuple[str, ...] = ()
    """Categories outside `KNOWN_THREAT_CATEGORIES`. Reported, never rejected (DEC-041): the set
    illustrates and STRIDE has no category for several of ForgeFlow's expected threats."""

    @property
    def valid(self) -> bool:
        """Whether the threat set may move on to control mapping.

        A merge proposal does not block: two threats that overlap are still two threats worth
        mapping, and collapsing them before mapping would lose whichever one the merge did not
        keep.
        """
        return not self.blocking_errors

    @property
    def blocking_errors(self) -> tuple[ThreatValidationError, ...]:
        return tuple(
            error
            for error in self.errors
            if error.error_class is not ErrorClass.INSUFFICIENT_EVIDENCE
        )

    def retry_instructions(self) -> tuple[str, ...]:
        """Feedback for the next attempt, for the errors another attempt could fix."""
        return tuple(error.retry_instruction() for error in self.errors if error.retryable)


def _normalized(value: str) -> str:
    """A string reduced for comparison only. Never written back onto the object."""
    try:
        return normalize_term(value)
    except ValueError:
        return " ".join(value.split()).casefold()


def _title_tokens(title: str) -> frozenset[str]:
    return frozenset(_normalized(title).split("_")) - _STOP_WORDS


# Words that carry no distinguishing weight in a threat title. Small and deliberately dull: a
# longer list would start deciding which security words matter.
_STOP_WORDS: Final[frozenset[str]] = frozenset(
    {"a", "an", "the", "of", "to", "and", "or", "in", "on", "by", "for", "with", "via", "that"}
)


def _jaccard(left: Iterable[str], right: Iterable[str]) -> float:
    """Overlap of two sets, 0.0 to 1.0. Two empty sets are 0.0, not 1.0.

    The empty case matters: two threats that both carry no category are not thereby similar, and a
    convention returning 1.0 would make every uncategorised pair look like a duplicate.
    """
    first, second = set(left), set(right)
    if not first or not second:
        return 0.0
    return len(first & second) / len(first | second)


def _similarity(left: Threat, right: Threat) -> tuple[float, tuple[str, ...]]:
    """How alike two threats look, and which features said so."""
    title = _jaccard(_title_tokens(left.title), _title_tokens(right.title))
    targets = _jaccard(
        [*left.affected_component_ids, *left.affected_asset_ids],
        [*right.affected_component_ids, *right.affected_asset_ids],
    )
    categories = _jaccard(left.category, right.category)

    matched = tuple(
        name
        for name, value in (("title", title), ("targets", targets), ("category", categories))
        if value > 0.0
    )
    score = title * _TITLE_WEIGHT + targets * _TARGET_WEIGHT + categories * _CATEGORY_WEIGHT
    return score, matched


def _attack_path_problem(threat: Threat) -> str | None:
    """Whether the attack path revisits a step it already took.

    Section 11 rejects "empty or circular attack paths". Empty is the common case and is not an
    error here: `attack_path` is optional in `data-model.md` section 16, and a threat described
    through its preconditions and impact without an ordered path is a legitimate one. What is
    refused is a path that is *present* and loops, because a scenario that returns to a state it
    already reached does not progress, and nothing downstream can reason about where it ends.
    """
    seen: set[str] = set()
    for step in threat.attack_path:
        normalized = _normalized(step)
        if normalized in seen:
            return step
        seen.add(normalized)
    return None


def validate_threats(
    threats: Sequence[Threat],
    *,
    context: SystemContext,
    claims: Sequence[ContextClaim] = (),
    contradicted_claim_ids: Sequence[str] = (),
) -> ThreatValidationOutcome:
    """Validate a set of candidate threats. Returns problems and proposals; changes nothing.

    `threats` are read and never written. `context` supplies the identifiers a threat may
    reference — the approved baseline's lists, so an object the reviewer rejected is not among
    them. `claims` are read only to tell an assumption from a documented fact.
    """
    errors: list[ThreatValidationError] = []
    triggers: list[ReviewTrigger] = []

    known_components = set(context.component_ids)
    known_assets = set(context.asset_ids)
    known_actors = set(context.actor_ids)
    known_flows = set(context.data_flow_ids)
    claim_status = {claim.id: claim.status for claim in claims}
    contradicted = set(contradicted_claim_ids)

    for threat in threats:
        errors.extend(_reference_errors(threat, known_components, "affected_component_ids"))
        errors.extend(_reference_errors(threat, known_assets, "affected_asset_ids"))
        errors.extend(_reference_errors(threat, known_actors, "threat_actor_ids"))
        errors.extend(_reference_errors(threat, known_flows, "related_data_flow_ids"))

        if not threat.impact.strip():
            errors.append(
                ThreatValidationError(
                    threat_id=threat.id,
                    field="impact",
                    rule="threats state a plausible security impact "
                    "(agent-design.md section 10, Failure conditions)",
                    message="impact is empty. State what is disclosed, altered, destroyed, made "
                    "unavailable, or spent.",
                )
            )

        if (repeated := _attack_path_problem(threat)) is not None:
            errors.append(
                ThreatValidationError(
                    threat_id=threat.id,
                    field="attack_path",
                    rule="attack paths are not circular (agent-design.md section 11)",
                    message=f"the step {repeated!r} repeats a step already taken. A scenario that "
                    f"returns to a state it reached does not progress.",
                )
            )

        if not threat.affected_component_ids or not threat.affected_asset_ids:
            errors.append(
                ThreatValidationError(
                    threat_id=threat.id,
                    field="affected_component_ids",
                    rule="threats identify affected components and assets "
                    "(agent-design.md section 10)",
                    message="a threat naming no component or no asset cannot be mapped to a "
                    "requirement.",
                )
            )

        errors.extend(_assumption_errors(threat, claim_status))

    unfamiliar = sorted(
        {
            category
            for threat in threats
            for category in threat.category
            if category not in KNOWN_THREAT_CATEGORIES
        }
    )

    triggers.extend(_review_triggers(threats, context, claim_status, contradicted))

    return ThreatValidationOutcome(
        errors=tuple(errors),
        triggers=tuple(triggers),
        merge_proposals=_merge_proposals(threats),
        unfamiliar_categories=tuple(unfamiliar),
    )


def _reference_errors(threat: Threat, known: set[str], field: str) -> list[ThreatValidationError]:
    """Every identifier in `field` that the approved context does not contain."""
    return [
        ThreatValidationError(
            threat_id=threat.id,
            field=field,
            rule="threats reference objects in the approved context "
            "(agent-design.md section 10, Prohibited operations)",
            message=f"{identifier} is not in the approved context. A threat against a component "
            f"nobody documented is a threat against a system nobody is assessing.",
            error_class=ErrorClass.MISSING_REQUIRED_RELATIONSHIP,
        )
        for identifier in getattr(threat, field)
        if identifier not in known
    ]


def _assumption_errors(
    threat: Threat, claim_status: dict[str, ClaimStatus]
) -> list[ThreatValidationError]:
    """Section 11: flag a threat resting *entirely* on unsupported assumptions.

    Entirely, not partly. A scenario built on an assumption plus a documented fact is ordinary
    threat modelling and is exactly what `preconditions` are for. What section 11 names is a
    threat with nothing under it: every claim it cites is `assumed` or `unknown`, and it cites no
    evidence either.

    This is `insufficient_evidence`, which is **not retryable** (section 26). Asking again would
    invite the agent to supply support it does not have, and producing some is the only way to
    stop being retried.
    """
    if not threat.assumption_ids or threat.evidence_ids:
        return []

    statuses = [claim_status.get(claim_id) for claim_id in threat.assumption_ids]
    if not statuses or any(
        status is not None and status not in {ClaimStatus.ASSUMED, ClaimStatus.UNKNOWN}
        for status in statuses
    ):
        return []

    return [
        ThreatValidationError(
            threat_id=threat.id,
            field="assumption_ids",
            rule="threats do not rest entirely on unsupported assumptions "
            "(agent-design.md section 11)",
            message="every claim this threat cites is assumed or unknown, and it cites no "
            "evidence. It is a scenario about a system nobody described.",
            error_class=ErrorClass.INSUFFICIENT_EVIDENCE,
        )
    ]


def _review_triggers(
    threats: Sequence[Threat],
    context: SystemContext,
    claim_status: dict[str, ClaimStatus],
    contradicted: set[str],
) -> list[ReviewTrigger]:
    """Section 10's four human-review triggers. Reasons to look, not statements of error."""
    triggers: list[ReviewTrigger] = []

    uncertain = tuple(
        threat.id
        for threat in threats
        if threat.confidence.value == "high"
        and any(
            claim_status.get(claim_id) in {ClaimStatus.ASSUMED, ClaimStatus.UNKNOWN}
            for claim_id in threat.assumption_ids
        )
    )
    if uncertain:
        triggers.append(
            ReviewTrigger(
                name="critical_threat_depends_on_uncertain_assumption",
                object_ids=uncertain,
                detail="a high-confidence threat rests on a claim nobody documented",
            )
        )

    conflicted = tuple(threat.id for threat in threats if contradicted & set(threat.assumption_ids))
    if conflicted:
        triggers.append(
            ReviewTrigger(
                name="threats_rely_on_contradictory_context",
                object_ids=conflicted,
                detail="a cited claim is contradicted by another passage",
            )
        )

    referenced = {identifier for threat in threats for identifier in threat.affected_component_ids}
    unreferenced = sorted(set(context.component_ids) - referenced)
    if threats and unreferenced:
        triggers.append(
            ReviewTrigger(
                name="likely_missing_core_component",
                object_ids=(),
                detail=f"no threat references {unreferenced}. Either the component is not "
                f"exposed, or the analysis did not reach it.",
            )
        )

    if threats and len(context.component_ids) <= _THIN_ARCHITECTURE_COMPONENTS:
        triggers.append(
            ReviewTrigger(
                name="architecture_materially_incomplete",
                object_ids=(),
                detail=f"the approved context has {len(context.component_ids)} components and no "
                f"data flows"
                if not context.data_flow_ids
                else f"the approved context has {len(context.component_ids)} components",
            )
        )

    return triggers


def _merge_proposals(threats: Sequence[Threat]) -> tuple[MergeProposal, ...]:
    """Every pair scoring above the threshold, each proposed once.

    Pairwise, which is quadratic. For the tens of threats an assessment produces that is nothing,
    and DEC-043 records the point at which it stops being nothing.
    """
    proposals: list[MergeProposal] = []
    for index, left in enumerate(threats):
        for right in threats[index + 1 :]:
            score, matched = _similarity(left, right)
            if score < DUPLICATE_THRESHOLD:
                continue
            pair: tuple[str, str] = tuple(sorted((left.id, right.id)))  # type: ignore[assignment]
            proposals.append(
                MergeProposal(
                    threat_ids=pair,
                    score=round(score, 3),
                    matched_features=matched,
                    detail=f"{left.title!r} and {right.title!r} match on {', '.join(matched)}",
                )
            )
    return tuple(proposals)


def duplicate_groups(proposals: Sequence[MergeProposal]) -> tuple[tuple[str, ...], ...]:
    """Merge proposals collapsed into connected groups, for presentation only.

    Three threats that pair up transitively are one group a reviewer looks at once. This changes
    nothing and decides nothing: the proposals remain the record, and this is a convenience for
    whatever renders them.
    """
    adjacency: dict[str, set[str]] = defaultdict(set)
    for proposal in proposals:
        first, second = proposal.threat_ids
        adjacency[first].add(second)
        adjacency[second].add(first)

    seen: set[str] = set()
    groups: list[tuple[str, ...]] = []
    for start in sorted(adjacency):
        if start in seen:
            continue
        group: set[str] = set()
        stack = [start]
        while stack:
            current = stack.pop()
            if current in group:
                continue
            group.add(current)
            stack.extend(adjacency[current] - group)
        seen |= group
        groups.append(tuple(sorted(group)))
    return tuple(groups)
