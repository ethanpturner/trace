"""The provider-agnostic seam: what the application knows about talking to a model.

`current-architecture.md` section 9 requires a model abstraction rather than provider calls
scattered through the codebase, and DEC-014 settles what sits behind it. Everything in this module
is provider-neutral; `anthropic_adapter.py` is the only place a provider SDK is imported.

**An adapter makes exactly one attempt.** DEC-014 assigns the retry budget to the orchestrator, and
a hidden loop inside an adapter would break both the `ExecutionRecord` retry count and the cost
ceiling. That is why `generate` returns a failure object rather than raising: a failure is a result
with a cost and a duration, and the caller needs both to decide what to do next.

**A schema failure keeps the raw output.** `data-model.md` section 33 requires an invalid output be
preserved for debugging rather than discarded, so `ModelFailure` carries what the model actually
said. It is the one place model text survives validation, and it is untrusted like any other model
output.

**Creativity is an intent, not a knob** (DEC-014, `agent-design.md` section 29). The seam carries
how much latitude an agent should have; each adapter maps that to whatever its provider exposes.
Nothing here names a sampling parameter, because a seam that did would be one provider's interface
wearing a neutral name.

**Capabilities are declared, not assumed.** DEC-014 makes the seam capability-aware rather than
lowest-common-denominator: an adapter says what it supports, the application uses a capability where
it exists and proceeds where it does not, and what was actually used is recorded on the result so an
evaluation is interpretable against the conditions that produced it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from pydantic import BaseModel

__all__ = [
    "Creativity",
    "FailureReason",
    "GenerationSettings",
    "ModelCapability",
    "ModelFailure",
    "ModelOutcome",
    "ModelSuccess",
    "ModelUsage",
    "StructuredModel",
]


class Creativity(StrEnum):
    """How much latitude an agent should have (`agent-design.md` section 29).

    The two values are the ones the section 29 table uses since DEC-085 resolved its "low to
    moderate" rows to one value each. They are **provider-neutral intent**: they say how much
    room the agent has to range beyond the obvious reading, and they name no control. An adapter
    maps them; a caller does not.
    """

    LOW = "low"
    """Structured analytical work: context extraction, mapping, evidence validation — and report
    generation, which summarises approved objects and invents nothing (DEC-085)."""

    MODERATE = "moderate"
    """Threat analysis and critical review (DEC-085). Breadth helps both — proposing threats and
    imagining how a conclusion fails — and must not override architectural grounding."""


class ModelCapability(StrEnum):
    """An optional provider capability the application may use where it exists (DEC-014)."""

    PROMPT_CACHING = "prompt_caching"
    """A stable prefix served at a fraction of input cost. Trace's shape fits it unusually well."""

    ADAPTIVE_THINKING = "adaptive_thinking"
    """The provider decides how much to reason per request rather than taking a token budget."""

    EFFORT = "effort"
    """A named depth setting the adapter maps `Creativity` onto."""

    STRUCTURED_OUTPUT = "structured_output"
    """Schema-validated output at the provider, rather than parsed out of free text."""


class FailureReason(StrEnum):
    """Why one attempt produced no validated object.

    The vocabulary exists so the retry policy can route on a value rather than on exception text
    (#67 owns the policy; this only classifies). The division that matters is between a failure the
    same call might survive and one it will not: `retryable` says which, and it is a property of the
    reason rather than a caller's judgment.
    """

    SCHEMA_VALIDATION_FAILURE = "schema_validation_failure"
    """The model answered and the answer did not fit the schema."""

    OUTPUT_TRUNCATED = "output_truncated"
    """The response hit the output ceiling mid-object."""

    REFUSED = "refused"
    """The provider declined the request. Not retryable: the same call refuses again."""

    TRANSIENT_PROVIDER_FAILURE = "transient_provider_failure"
    """Rate limit, overload, or a server error. The same call may succeed later."""

    TIMEOUT = "timeout"
    """The attempt exceeded its deadline."""

    CONNECTION_FAILURE = "connection_failure"
    """The request never reached the provider."""

    INVALID_REQUEST = "invalid_request"
    """The provider rejected the request as malformed. A bug here, not a condition to wait out."""

    AUTHENTICATION_FAILURE = "authentication_failure"
    """Credentials were absent, wrong, or unauthorized."""


# Reasons a second identical attempt could survive. Everything else is a statement about the
# request rather than about the moment it was made.
_RETRYABLE: frozenset[FailureReason] = frozenset(
    {
        FailureReason.SCHEMA_VALIDATION_FAILURE,
        FailureReason.TRANSIENT_PROVIDER_FAILURE,
        FailureReason.TIMEOUT,
        FailureReason.CONNECTION_FAILURE,
    }
)


@dataclass(frozen=True, slots=True)
class GenerationSettings:
    """What the application asks for, in provider-neutral terms.

    The defaults are the conservative ones `agent-design.md` section 29 assigns to structured
    analytical agents: `Creativity.LOW`, which is the value the section 29 table gives Context
    Extraction, Requirement Mapping, and Evidence Validation.
    """

    creativity: Creativity = Creativity.LOW
    max_output_tokens: int = 64_000
    """Sized so one attempt cannot be truncated by a ceiling nobody chose — and measured, not
    guessed: at 16,000 the live ForgeFlow extraction truncated on all three attempts (#324),
    because adaptive thinking spends from the same output budget as the proposal it precedes.
    A ceiling is not a purchase; only produced tokens are billed. An agent proposing a
    context extraction returns a large object; a small default would show up as a truncation
    failure that looks like a model problem."""

    timeout_seconds: float = 1_800.0
    """One attempt's deadline. Long, because the retry budget is the orchestrator's and a timeout
    here is a real failure rather than an impatience — and sized with the output ceiling: the
    16,000-token live extraction generated for ~140 seconds, so a full 64,000-token attempt
    needs headroom a 600-second deadline did not give."""

    def __post_init__(self) -> None:
        if self.max_output_tokens < 1:
            raise ValueError("max_output_tokens must be positive")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")


@dataclass(frozen=True, slots=True)
class ModelUsage:
    """What one attempt consumed, in the fields the execution ledger needs.

    `data-model.md` sections 26 and 27 give `WorkflowRun` and `ExecutionRecord` token counts, cost,
    and duration. They are collected here so a caller never reaches into a provider response —
    which is the same boundary DEC-014 draws for everything else.
    """

    model: str
    input_tokens: int = 0
    """Uncached input processed at the full rate. The three input spans are disjoint (DEC-067):
    cache reads and cache writes are their own counts, never folded in — folding them in is
    exactly how cost and tokens come to describe different spans of work."""

    output_tokens: int = 0
    cache_read_tokens: int = 0
    """Input tokens served from a provider-side cache, where the adapter reports them. They are
    counted separately because they are priced separately and because a cache that silently stops
    working looks exactly like one that is working."""

    cache_creation_tokens: int = 0
    """Input tokens written into the provider's cache, priced at its premium (DEC-067)."""

    estimated_cost: Decimal = Decimal(0)
    """Estimated, and named so. It is computed from published rates the adapter holds, not returned
    by the provider, so it is a projection that can drift from an invoice."""

    duration_seconds: float = 0.0


@dataclass(frozen=True, slots=True)
class ModelSuccess[T: "BaseModel"]:
    """A validated object, and what it cost to get it."""

    value: T
    usage: ModelUsage
    capabilities_used: frozenset[ModelCapability] = frozenset()
    """Which optional capabilities this call actually used (DEC-014), recorded so an evaluation
    result is interpretable against the conditions that produced it."""

    metadata: dict[str, Any] = field(default_factory=dict)
    """Adapter-specific detail worth keeping on the execution record — the effort level chosen,
    whether thinking ran. Never provider objects, only values."""

    @property
    def succeeded(self) -> bool:
        return True


@dataclass(frozen=True, slots=True)
class ModelFailure:
    """One attempt that produced no validated object, and everything known about why."""

    reason: FailureReason
    message: str
    usage: ModelUsage
    raw_output: str | None = None
    """What the model said, when it said anything. Required by `data-model.md` section 33 to be
    preserved rather than discarded — and untrusted, like all model output: it is a debugging
    artifact, not a value to parse a second time."""

    @property
    def succeeded(self) -> bool:
        return False

    @property
    def retryable(self) -> bool:
        """Whether a second identical attempt could survive. The retry *policy* is #67's."""
        return self.reason in _RETRYABLE


type ModelOutcome[T: "BaseModel"] = ModelSuccess[T] | ModelFailure


@runtime_checkable
class StructuredModel(Protocol):
    """The only path from application code to a model.

    One method, one attempt, no exceptions for provider conditions. An implementation that raises
    on a rate limit, or retries internally, is not one of these however well it type-checks.
    """

    @property
    def name(self) -> str:
        """What produced the output, for the execution record. A model identifier, not a class."""
        ...

    @property
    def capabilities(self) -> frozenset[ModelCapability]:
        """The optional capabilities this implementation supports (DEC-014)."""
        ...

    def generate[T: "BaseModel"](
        self,
        *,
        prompt: str,
        schema: type[T],
        settings: GenerationSettings | None = None,
        system: str | None = None,
        cache_prefix: str | None = None,
        system_cache_prefix: str | None = None,
    ) -> ModelOutcome[T]:
        """One attempt at a validated instance of `schema`.

        `settings` is optional so the Protocol matches its implementations (WS11): the adapters fall
        back to the profile's own settings when a caller passes none, and a `@runtime_checkable`
        Protocol checks attribute presence, not signatures, so a Protocol that disagreed with the
        implementations would hide the disagreement rather than catch it.

        `cache_prefix` is the stable leading span of `prompt` — the shared blocks, the body template,
        and the schema, before the per-call source content — that an adapter supporting prompt
        caching may mark for reuse across the calls that share it (WS10). An adapter that does not,
        or a `cache_prefix` that is not a prefix of `prompt`, ignores it; a provider-neutral hint,
        never a provider knob (DEC-014).

        `system_cache_prefix` is the same hint for `system` (DEC-105): the leading span of the
        trusted region that is byte-identical across a node's calls — for mapping, the
        requirements catalog, which DEC-024 names as the pipeline's largest stable prefix. It
        matters when `system` itself varies per call: a marker inside `prompt` alone never hits
        then, because the varying system region precedes it in the cacheable sequence. The same
        ignore rules apply.
        """
        ...
