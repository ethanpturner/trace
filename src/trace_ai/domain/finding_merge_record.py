"""`FindingMergeRecord`: one finding merge, made traceable after the process that decided it exits.

`data-model.md` section 21a is authoritative for the fields; DEC-052 is the decision behind the
object. `agent-design.md` section 11 requires a merge decision to remain explicit and traceable,
and a decision held only in a node's return value stops being either when the run ends — which is
why this is a persisted object rather than a dataclass on an outcome, the way DEC-043's threat
`MergeProposal` is. A proposal that merges nothing can afford to be ephemeral; a merge cannot.

**The identifier fields are `FindingId`-typed, and that is half of the DEC-009 enforcement.** A
record naming a `DocumentationGap` fails validation here, so a merge across the finding/gap
boundary is unrepresentable rather than merely forbidden. The other half is the merge operation in
`workflow/finding_dedup.py`, which refuses non-`Finding` input before a record is ever built.

**`decision` says who decided, not who noticed.** `structural` is a merge the deterministic
identifier rule decided. `model_assisted` is a merge a reviewer decided from a model-proposed
candidate pair — the node never writes it, because DEC-052 confines any semantic comparison to
proposing pairs.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Self

from pydantic import Field, model_validator

from trace_ai.domain.base import DomainModel
from trace_ai.domain.identifiers import AssessmentId, FindingId, FindingMergeRecordId

__all__ = ["MERGE_FEATURES", "FindingMergeRecord", "MergeDecision"]


class MergeDecision(StrEnum):
    """Which kind of decision performed the merge (section 21a)."""

    STRUCTURAL = "structural"
    MODEL_ASSISTED = "model_assisted"


# The feature vocabulary section 21a names. The first two decide a structural merge; the rest
# corroborate and decide nothing on their own (DEC-052).
MERGE_FEATURES: tuple[str, ...] = (
    "threats",
    "requirements",
    "control_mappings",
    "components",
    "assets",
)


class FindingMergeRecord(DomainModel):
    """One merge: the survivor, what was merged into it, and why (section 21a)."""

    id: FindingMergeRecordId
    assessment_id: AssessmentId

    surviving_finding_id: FindingId
    merged_finding_ids: list[FindingId] = Field(min_length=1)
    """Non-empty by schema: a merge that merged nothing is not a merge, and writing a record for
    one would make `duplicate_finding_rate` count events that never happened."""

    matched_features: list[str] = Field(min_length=1)
    decision: MergeDecision
    detail: str = Field(min_length=1)

    generated_by: str = Field(min_length=1)
    created_at: datetime

    @model_validator(mode="after")
    def _survivor_is_not_merged(self) -> Self:
        """The survivor is what the merge kept, so it cannot also be something it removed."""
        if self.surviving_finding_id in self.merged_finding_ids:
            raise ValueError(
                f"{self.surviving_finding_id} is recorded both as the survivor and as merged "
                f"into it. A finding cannot be a duplicate of itself."
            )
        if len(set(self.merged_finding_ids)) != len(self.merged_finding_ids):
            raise ValueError(
                f"merged_finding_ids lists a finding twice: {self.merged_finding_ids}. One "
                f"record per merge, one entry per merged finding."
            )
        return self

    @model_validator(mode="after")
    def _features_are_from_the_vocabulary(self) -> Self:
        """Section 21a names the feature vocabulary, and a value outside it names nothing.

        Closed rather than open (DEC-036 notwithstanding) because the values are not descriptive
        terms a document might use — they name the comparisons `finding_dedup` actually ran, and
        an unrecognized one would claim a comparison no code performs.
        """
        unknown = [feature for feature in self.matched_features if feature not in MERGE_FEATURES]
        if unknown:
            raise ValueError(
                f"matched_features {unknown} are not comparisons the dedup rule makes; "
                f"section 21a names {list(MERGE_FEATURES)}."
            )
        if len(set(self.matched_features)) != len(self.matched_features):
            raise ValueError(f"matched_features lists a feature twice: {self.matched_features}")
        return self
