"""Recorded model responses: files in, proposals out, schema inferred structurally.

`--model-profile offline-fake --response recorded.json` is the supported way to run without a
provider, and past the context slice a run consumes responses of more than one schema — threats,
mappings, evidence assessments, critiques, report sections. A recording stays a pure capture of
one model response; nothing in the file says which agent produced it, because the schemas are
mutually exclusive by construction (`extra="forbid"` on every proposal) and the file's shape says
it alone.

Inference is exact-match, not best-effort: a recording must validate against exactly one known
schema. Zero matches is a broken recording; more than one means the recording is too empty to say
which call it answers (every proposal with only defaulted fields validates), and replaying it
would be a guess wearing a recording's clothes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from pydantic import ValidationError

from trace_ai.domain.proposals import ContextExtractionProposal
from trace_ai.domain.proposals.critical_review import CriticalReviewProposal
from trace_ai.domain.proposals.evidence_validation import EvidenceValidationProposal
from trace_ai.domain.proposals.mapping import MappingProposal
from trace_ai.domain.proposals.report_sections import ReportSections
from trace_ai.domain.proposals.threat_analysis import ThreatAnalysisProposal

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from pydantic import BaseModel

__all__ = ["RESPONSE_SCHEMAS", "load_recorded_responses", "parse_recorded_response"]

RESPONSE_SCHEMAS: Final[tuple[type[BaseModel], ...]] = (
    ContextExtractionProposal,
    ThreatAnalysisProposal,
    MappingProposal,
    EvidenceValidationProposal,
    CriticalReviewProposal,
    ReportSections,
)
"""One schema per agent, in pipeline order. The order is presentation only; matching is exact."""


def parse_recorded_response(text: str, *, described_as: str = "recorded response") -> BaseModel:
    """The one proposal this recording is, or an error naming why it is not one."""
    matches: list[BaseModel] = []
    for schema in RESPONSE_SCHEMAS:
        try:
            matches.append(schema.model_validate_json(text))
        except ValidationError:
            continue
    if not matches:
        known = ", ".join(schema.__name__ for schema in RESPONSE_SCHEMAS)
        raise ValueError(
            f"{described_as} validates against none of the recorded-response schemas ({known})"
        )
    if len(matches) > 1:
        ambiguous = ", ".join(type(match).__name__ for match in matches)
        raise ValueError(
            f"{described_as} validates against more than one schema ({ambiguous}); a recording "
            f"this empty cannot say which model call it answers"
        )
    return matches[0]


def load_recorded_responses(paths: Sequence[Path]) -> list[BaseModel]:
    """Parse each file, in the order given — which is the order the run will consume them."""
    return [
        parse_recorded_response(path.read_text(encoding="utf-8"), described_as=str(path.name))
        for path in paths
    ]
