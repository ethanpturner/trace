"""One character budget for every model-input package (WS10).

Before this, the packages counted their input four different ways. The context extractor and the
threat analyser charged the untrusted excerpts against the whole `max_input_characters` and dropped
whatever sorted last; the threat analyser first subtracted an estimate that covered only the
architecture JSON. Evidence validation and critique counted nothing and rendered every excerpt
unconditionally. Mapping measured the whole payload after assembly and hard-raised with no
degradation. And *none* of them charged the response-format schema the prompt teaches — the single
largest fixed input the extractor sends, roughly twenty-four thousand characters, uncounted against
a budget it plainly consumes.

This module is the one place that accounting lives. `schema_overhead` prices the schema export;
`fill_untrusted` charges the trusted region and that overhead as fixed cost, then greedy-fills the
untrusted excerpts against what is left and names what did not fit rather than dropping it silently
(DEC-024, the same rule the fence follows on overrun). It never raises: whether a shed excerpt is
tolerable degradation or a stop condition is the caller's to decide — the mapping package cannot
shed its catalog and raises `PayloadTooLargeError` when the irreducible part overflows, while the
others treat a shed excerpt as a named exclusion. The fill preserves the caller's excerpt order, so
a package that does not overflow produces byte-identical output to before, and the recorded runs the
evaluation harness replays are unmoved.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

    from pydantic import BaseModel

    from trace_ai.infrastructure.model.profiles import ModelProfile

__all__ = ["BudgetOutcome", "fill_untrusted", "schema_overhead"]


def schema_overhead(schema: type[BaseModel]) -> int:
    """A provider-neutral character count for the response schema the prompt teaches.

    The prompt substitutes each agent's schema export into its body, so the schema consumes the
    input budget exactly as the excerpts do. This prices it with the same `model_json_schema`
    export the nodes render, without reaching behind the model seam for a provider's wire schema:
    the number is an accounting estimate, not the bytes on the wire, and DEC-014 keeps
    provider-shaped transforms in the adapter.
    """
    return len(json.dumps(schema.model_json_schema()))


@dataclass(frozen=True, slots=True)
class BudgetOutcome:
    """The result of filling the untrusted region against the residual allowance."""

    blocks: tuple[str, ...]
    """The included excerpt blocks, in the caller's original order."""

    included_ids: tuple[str, ...]
    excluded_ids: tuple[str, ...]
    used_characters: int
    residual_characters: int
    overhead_characters: int
    budget_characters: int

    @property
    def untrusted(self) -> str:
        """The blocks joined exactly as each package joined them before this module existed."""
        return "\n\n".join(self.blocks)

    def metadata(self) -> dict[str, int]:
        """The budget keys every package records, so their accounting reads the same way."""
        return {
            "evidence_included": len(self.included_ids),
            "evidence_excluded": len(self.excluded_ids),
            "characters": self.used_characters,
            "overhead_characters": self.overhead_characters,
            "residual_characters": self.residual_characters,
            "budget_characters": self.budget_characters,
        }


def fill_untrusted(
    rendered: Sequence[tuple[str, str]],
    *,
    profile: ModelProfile,
    overhead_characters: int,
) -> BudgetOutcome:
    """Greedy-fill the untrusted excerpts against the budget left after fixed overhead.

    `rendered` is `(evidence_id, block)` pairs in the order they should appear in the prompt.
    `overhead_characters` is the fixed cost the untrusted region shares the budget with — the
    trusted region plus the schema export, charged by the caller. Excerpts are placed in order and
    any that would overflow the residual are excluded and named; the order of the included blocks is
    preserved, so a package that does not overflow renders exactly what it rendered before.
    """
    residual = max(profile.max_input_characters - overhead_characters, 0)
    blocks: list[str] = []
    included: list[str] = []
    excluded: list[str] = []
    used = 0
    for evidence_id, block in rendered:
        if used + len(block) > residual:
            excluded.append(evidence_id)
            continue
        blocks.append(block)
        included.append(evidence_id)
        used += len(block)
    return BudgetOutcome(
        blocks=tuple(blocks),
        included_ids=tuple(included),
        excluded_ids=tuple(excluded),
        used_characters=used,
        residual_characters=residual,
        overhead_characters=overhead_characters,
        budget_characters=profile.max_input_characters,
    )
