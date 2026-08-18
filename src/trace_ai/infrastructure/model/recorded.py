"""Recorded model responses: an envelope in, a proposal and its usage out.

`--model-profile offline-fake --response recorded.json` is the supported way to run without a
provider, and past the context slice a run consumes responses of more than one schema — threats,
mappings, evidence assessments, critiques, report sections.

**The recording format is an envelope** (#461): `{"schema": <ProposalName>, "usage": {...},
"response": {...}}`. The `schema` names which proposal the `response` is, so a recording validates
against exactly that schema and a mismatch reports pydantic's field-level errors — where before the
schema was inferred by trying all six, which failed every recording at once when any proposal gained
a required field and grew ambiguous as proposals were added. The `usage` is optional and, when
present, is what `DeterministicModel` replays, so an offline ledger can carry the cost, tokens, and
duration the recording captured rather than zeros.

**A bare proposal is still read, as a legacy file.** A recording with no envelope falls back to the
old structural inference: it must validate against exactly one known schema, and it replays with no
usage. This keeps envelope-less recordings working while the corpus migrates.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Final

from pydantic import ValidationError

from trace_ai.infrastructure.model.agents import AGENTS
from trace_ai.infrastructure.model.seam import ModelUsage

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from pydantic import BaseModel

__all__ = [
    "RESPONSE_SCHEMAS",
    "RecordedResponse",
    "load_recorded_responses",
    "parse_recorded_response",
]

RESPONSE_SCHEMAS: Final[tuple[type[BaseModel], ...]] = tuple(spec.schema for spec in AGENTS)
"""One schema per agent, in pipeline order, derived from the one `AGENTS` table (WS11) so it cannot
disagree with the routing table. The order is presentation only; matching is exact."""

_SCHEMA_BY_NAME: Final[dict[str, type[BaseModel]]] = {
    schema.__name__: schema for schema in RESPONSE_SCHEMAS
}


@dataclass(frozen=True, slots=True)
class RecordedResponse:
    """One recorded model response: the proposal, and the usage to replay for it if any.

    `usage` is `None` for a legacy bare recording and for a migrated envelope that carries no
    captured usage; `DeterministicModel` then reports zeros, exactly as it did before the envelope
    existed. A live capture writes real usage, and the offline ledger then reflects it."""

    response: BaseModel
    usage: ModelUsage | None = None


def _infer_schema(text: str, described_as: str) -> BaseModel:
    """The one proposal a bare recording is, by trying every schema (the legacy path)."""
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


def _usage_from_dict(raw: dict[str, Any]) -> ModelUsage:
    """A `ModelUsage` from an envelope's `usage` mapping, defaulting every field it omits."""
    return ModelUsage(
        model=str(raw.get("model", "recorded")),
        input_tokens=int(raw.get("input_tokens", 0)),
        output_tokens=int(raw.get("output_tokens", 0)),
        cache_read_tokens=int(raw.get("cache_read_tokens", 0)),
        cache_creation_tokens=int(raw.get("cache_creation_tokens", 0)),
        estimated_cost=Decimal(str(raw.get("estimated_cost", "0"))),
        duration_seconds=float(raw.get("duration_seconds", 0.0)),
    )


def _is_envelope(data: object) -> bool:
    return isinstance(data, dict) and "schema" in data and "response" in data


def parse_recorded_response(
    text: str, *, described_as: str = "recorded response", allow_rehearsal: bool = False
) -> RecordedResponse:
    """The proposal and usage this recording carries, or an error naming why it is not one.

    An envelope validates its `response` against the schema its `schema` names and reports the
    field-level errors on a mismatch. A bare proposal falls back to structural inference and carries
    no usage.

    An envelope marked `rehearsal` is refused unless the caller says it is rehearsing: a rehearsal
    staging file records the deterministic substitute, not a provider, and every other reader —
    the replay, the evaluate harness, a promoted recording — must refuse it rather than replay a
    response no model ever gave (#534, DEC-091).
    """
    try:
        data = json.loads(text)
    except json.JSONDecodeError as error:
        raise ValueError(f"{described_as} is not valid JSON: {error}") from error

    if not _is_envelope(data):
        return RecordedResponse(response=_infer_schema(text, described_as))

    if data.get("rehearsal") and not allow_rehearsal:
        raise ValueError(
            f"{described_as} is a rehearsal artifact: it was staged by `trace capture "
            f"--rehearse` from the deterministic substitute and records no live response. It "
            f"cannot be promoted into recorded/ or replayed as a recording."
        )

    name = data["schema"]
    schema = _SCHEMA_BY_NAME.get(name)
    if schema is None:
        known = ", ".join(sorted(_SCHEMA_BY_NAME))
        raise ValueError(
            f"{described_as} names schema {name!r}, which is not a recorded-response schema "
            f"({known})"
        )
    try:
        response = schema.model_validate(data["response"])
    except ValidationError as error:
        raise ValueError(f"{described_as} does not validate as {name}: {error}") from error

    usage_raw = data.get("usage")
    usage = _usage_from_dict(usage_raw) if isinstance(usage_raw, dict) else None
    return RecordedResponse(response=response, usage=usage)


def load_recorded_responses(
    paths: Sequence[Path], *, allow_rehearsal: bool = False
) -> list[RecordedResponse]:
    """Parse each file, in the order given — which is the order the run will consume them."""
    return [
        parse_recorded_response(
            path.read_text(encoding="utf-8"),
            described_as=str(path.name),
            allow_rehearsal=allow_rehearsal,
        )
        for path in paths
    ]
