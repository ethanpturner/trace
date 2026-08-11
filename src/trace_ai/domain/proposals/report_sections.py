"""`ReportSections`: the four prose passages the Report Generation agent may write (DEC-035).

DEC-035 fixes the split: sixteen report sections, twelve rendered deterministically from approved
objects, and exactly four written by a model — `executive_summary`, `system_overview`,
`risk_summary`, and `limitations`. This model is the agent's whole output surface. A section
assigned to the renderer is deliberately not a field here, and `extra="forbid"` (inherited from
`DomainModel`) makes an invented one a validation failure rather than a fifth section.

**Prose only, and the schema checks it.** DEC-035's constraint on the three prose fields is "no
headings, no Markdown tables, no links, no anchors" — the shapes through which a model could
smuggle document structure into passages the renderer owns, or point a reader somewhere the
approved objects do not go. The validator refuses each by the mark it would leave in Markdown.

**Limitations are required by identifier.** The assembler computes `required_limitations` from
the run's own state and hands the agent the identifier and the facts for each; the agent writes
the words. `check_required` compares by identifier — one entry per requirement, no more, no
fewer, none invented — which is what makes omitting a limitation a schema failure rather than a
judgment call. It takes the required list as an argument because the requirement lives in the
input, not in this object.

This is a proposal (`agent-design.md` section 22): no identifier, no status, nothing the
application owns. The validated sections are consumed by the rendering step; nothing here is
persisted as an object of its own.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Final

from pydantic import Field, field_validator

from trace_ai.domain.base import DomainModel

if TYPE_CHECKING:
    from collections.abc import Iterable

__all__ = ["MODEL_WRITTEN_SECTIONS", "LimitationEntry", "ReportSections"]

# The four model-written sections, in DEC-035's table order. The renderer owns the other twelve.
MODEL_WRITTEN_SECTIONS: Final[tuple[str, ...]] = (
    "executive_summary",
    "system_overview",
    "risk_summary",
    "limitations",
)

# The marks Markdown structure leaves, each refused with its name. A heading is checked at line
# start; a table row and an anchor are unambiguous anywhere; a link is the `](` joint, which prose
# has no other use for.
_FORBIDDEN: Final[tuple[tuple[str, re.Pattern[str]], ...]] = (
    ("a heading", re.compile(r"(?m)^\s{0,3}#")),
    ("a Markdown table", re.compile(r"(?m)^\s*\|")),
    ("a link", re.compile(r"\]\(")),
    ("an anchor element", re.compile(r"<a\s", re.IGNORECASE)),
)


class LimitationEntry(DomainModel):
    """One written limitation, tied by identifier to the requirement that demanded it."""

    limitation_id: str = Field(min_length=1)
    text: str = Field(min_length=1)


class ReportSections(DomainModel):
    """The agent's output: four named passages, and no document (DEC-035)."""

    executive_summary: str = Field(min_length=1)
    system_overview: str = Field(min_length=1)
    risk_summary: str = Field(min_length=1)
    limitations: list[LimitationEntry]
    """One entry per required limitation. The set is checked by `check_required` against the
    input's list, because only the input knows what the run's state implies."""

    @field_validator("executive_summary", "system_overview", "risk_summary")
    @classmethod
    def _prose_only(cls, value: str) -> str:
        """DEC-035: no headings, no tables, no links, no anchors in a model-written passage."""
        for name, pattern in _FORBIDDEN:
            if pattern.search(value):
                raise ValueError(
                    f"a model-written section contains {name}, which belongs to the renderer "
                    f"(DEC-035). The agent writes prose inside a document it does not own."
                )
        return value

    @field_validator("limitations")
    @classmethod
    def _limitations_are_prose_too(cls, value: list[LimitationEntry]) -> list[LimitationEntry]:
        for entry in value:
            for name, pattern in _FORBIDDEN:
                if pattern.search(entry.text):
                    raise ValueError(
                        f"limitation {entry.limitation_id!r} contains {name}, which belongs to "
                        f"the renderer (DEC-035)."
                    )
        return value

    def check_required(self, required_ids: Iterable[str]) -> None:
        """One entry per required limitation — no more, no fewer, none invented (DEC-035).

        Raises with the identifiers on the wrong side, so a retry can say exactly what to fix
        (`agent-design.md` section 26: feedback or it is a repetition).
        """
        required = set(required_ids)
        written = [entry.limitation_id for entry in self.limitations]
        if len(set(written)) != len(written):
            raise ValueError(f"limitations lists an identifier twice: {written}")
        missing = sorted(required - set(written))
        invented = sorted(set(written) - required)
        if missing or invented:
            raise ValueError(
                f"limitations must carry exactly the required identifiers: "
                f"missing {missing}, not required {invented}. The assembler derives the list "
                f"from the run's state; the agent writes the words and changes the set never."
            )
