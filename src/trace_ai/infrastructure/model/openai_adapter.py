"""The OpenAI adapter: the second provider behind the seam (DEC-095).

DEC-014 designed the model interface provider-agnostic with one adapter behind it, and said so
plainly: populated, not proven. This module is the proof obligation discharged — a second
provider satisfying the same `StructuredModel` contract, held to it by the same conformance
suite (`tests/unit/test_adapter_conformance.py`), importing its SDK nowhere else
(`tests/unit/test_model_boundary.py`).

**The module is named `openai_adapter`, not `openai`.** The same shadowing rule as
`anthropic_adapter`: a module named after a package it imports is a bug waiting for the import
that triggers it.

**Creativity maps to `reasoning_effort`** (DEC-014's rule that each adapter maps the section 29
intent to the controls its provider exposes). More latitude means more room to deliberate before
committing, exactly as the Anthropic adapter reads it; on this provider that control is
`reasoning_effort`. The mapping is recorded on every result's metadata, because a wrong mapping
produces plausible output rather than an error.

**The wire surface is the Responses API** (DEC-095's amendment, #539). Chat Completions was the
original landing and its own entry records the deferral; Responses is where the provider's new
capability lands, and the migration is proven the way the adapter arrived — offline, under the
conformance suite, through stub-shaped requests. The seam contract is unchanged: `system`
becomes the request's `instructions`, the prompt is the one `input` message, creativity's
effort rides `reasoning.effort`, and an incomplete response reports why through
`incomplete_details` rather than a finish reason.

**Structured output is requested non-strict and validated here.** OpenAI's strict mode requires
every schema key listed as required and rewrites optionals as explicit nulls — a shape the
proposals' defaulted fields would then fail to validate. The schema is sent as a non-strict
`json_schema` text format (guidance the provider honors well), and this adapter validates
the text itself, exactly as the Anthropic adapter does after its grammar fallback: validation
is the application's either way, and `raw_output` survives a failure (data-model.md section 33).
A provider that rejects the schema format falls back to `json_object`, recorded as
`schema_grammar: "unsupported_omitted"` — a degradation that is visible, never silent.

**Prompt caching is the provider's, automatic, and reported disjoint.** OpenAI caches long
prompt prefixes without markers, so both cache hints are accepted and unused. The provider's
`input_tokens` *includes* the cached span, so the adapter subtracts: DEC-067 keeps the input
spans disjoint, and folding a cached read into full-rate input would misprice every cached call.
There is no cache-write premium on this provider; `cache_creation_tokens` is always zero.

**Exactly one attempt, never raises, client on first use** — the same three obligations as the
Anthropic adapter, for the same reasons: the retry budget is the orchestrator's, the ledger
needs a cost and duration for every attempt, and `import trace_ai` must not require a key.

**The adapter serves the OpenAI-compatible providers, not one provider** (DEC-135). OpenRouter
speaks the same Responses API at its own base URL under its own key, so `provider="openrouter"`
resolves here rather than to a third adapter: the SDK is the wire client, and a gateway with no
SDK of its own is exactly the case DEC-014's "adding a provider means adding an adapter and a
branch" was not meant to force. The gateway normalizes a requested reasoning effort to the
nearest level the routed model supports, so the recorded `effort` metadata is what was
*requested*; per-model divergence is the gateway's to absorb and the profile's rates to price.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any, Final

import openai
import pydantic

from trace_ai.config import Settings, get_settings
from trace_ai.infrastructure.model.adapter_support import (
    classify_http_error,
    error_locations,
    json_candidate,
)
from trace_ai.infrastructure.model.profiles import ModelProfile, resolve_profile
from trace_ai.infrastructure.model.seam import (
    Creativity,
    FailureReason,
    GenerationSettings,
    ModelCapability,
    ModelFailure,
    ModelOutcome,
    ModelSuccess,
    ModelUsage,
)

if TYPE_CHECKING:
    from pydantic import BaseModel

__all__ = ["REASONING_EFFORT_BY_CREATIVITY", "OpenAIModel"]

# Section 29's intent on this provider's deliberation control (DEC-014, DEC-095). Monotonic like
# the Anthropic mapping: more latitude, more room to explore before committing.
REASONING_EFFORT_BY_CREATIVITY: Final[dict[Creativity, str]] = {
    Creativity.LOW: "medium",
    Creativity.MODERATE: "high",
}

# What this adapter supports, declared rather than assumed (DEC-014). No adaptive thinking:
# reasoning depth is set per request, not delegated to the model's own judgment.
_CAPABILITIES: Final = frozenset(
    {
        ModelCapability.EFFORT,
        ModelCapability.STRUCTURED_OUTPUT,
        ModelCapability.PROMPT_CACHING,
    }
)

# Provider incomplete reasons that mean no usable object, mapped to why.
_INCOMPLETE_FAILURES: Final[dict[str, FailureReason]] = {
    "max_output_tokens": FailureReason.OUTPUT_TRUNCATED,
    "content_filter": FailureReason.REFUSED,
}

# The OpenAI-compatible providers this adapter serves (DEC-135): each names the base URL the
# client is built against — `None` is the SDK's default, the provider's own endpoint — and the
# `Settings` field holding its key. The pairing lives here rather than on the profile because a
# base URL is provider identity, not tuning: a profile that could point one provider's name at
# another host would make `ExecutionRecord`'s provenance lie.
_OPENAI_COMPATIBLE: Final[dict[str, tuple[str | None, str]]] = {
    "openai": (None, "openai_api_key"),
    "openrouter": ("https://openrouter.ai/api/v1", "openrouter_api_key"),
}


class OpenAIModel:
    """A `StructuredModel` backed by the OpenAI Responses API."""

    def __init__(
        self,
        profile: ModelProfile | str = "openai-experimental",
        *,
        settings: Settings | None = None,
        client: Any | None = None,
    ) -> None:
        self._profile = resolve_profile(profile) if isinstance(profile, str) else profile
        if self._profile.provider not in _OPENAI_COMPATIBLE:
            served = ", ".join(sorted(_OPENAI_COMPATIBLE))
            raise ValueError(
                f"profile {self._profile.name!r} names provider "
                f"{self._profile.provider!r}; this adapter serves the OpenAI-compatible "
                f"providers: {served}"
            )
        self._settings = settings
        self._client = client

    @property
    def name(self) -> str:
        return self._profile.model

    @property
    def capabilities(self) -> frozenset[ModelCapability]:
        return _CAPABILITIES

    @property
    def profile(self) -> ModelProfile:
        return self._profile

    def _api(self) -> Any:
        """The provider client, built on first use — `import trace_ai` needs no key."""
        if self._client is None:
            settings = self._settings if self._settings is not None else get_settings()
            base_url, key_field = _OPENAI_COMPATIBLE[self._profile.provider]
            self._client = openai.OpenAI(
                api_key=settings.require(key_field),
                base_url=base_url,
                max_retries=0,
            )
        return self._client

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

        Every provider condition is caught and returned as a `ModelFailure`, for the ledger's
        sake: the caller records a cost and duration for the attempt either way, and an escaping
        exception would leave a node that started and never finished.
        """
        # The provider caches prefixes automatically; there is no marker for either hint.
        del cache_prefix, system_cache_prefix
        resolved = settings if settings is not None else self._profile.settings
        effort = REASONING_EFFORT_BY_CREATIVITY[resolved.creativity]

        client = self._api()
        started = time.monotonic()

        request: dict[str, Any] = {
            "model": self._profile.model,
            "max_output_tokens": resolved.max_output_tokens,
            "input": [{"role": "user", "content": prompt}],
            "reasoning": {"effort": effort},
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": schema.__name__,
                    "schema": schema.model_json_schema(),
                    "strict": False,
                },
            },
        }
        if system is not None:
            request["instructions"] = system
        schema_grammar = "requested"

        try:
            response = self._send(client, request, timeout=resolved.timeout_seconds)
        except openai.BadRequestError as error:
            if "schema" not in str(error).casefold():
                return self._failed(FailureReason.INVALID_REQUEST, str(error), started)
            # The provider refuses the schema format. The rejection precedes the model — no
            # tokens billed, no attempt made — so resending without it is not a second attempt.
            # The prompt already teaches the schema, and this adapter validates the text itself
            # either way; the format was adherence help, not the validation. Recorded on the
            # outcome's metadata, because a silent degradation is invisible exactly when it
            # matters.
            request["text"] = {"format": {"type": "json_object"}}
            schema_grammar = "unsupported_omitted"
            try:
                response = self._send(client, request, timeout=resolved.timeout_seconds)
            except openai.APIError as retry_error:
                return self._classified(retry_error, started)
        except openai.APIError as error:
            return self._classified(error, started)

        usage = self._usage(response, time.monotonic() - started)

        refusal = _refusal_of(response)
        if refusal is not None:
            return ModelFailure(
                reason=FailureReason.REFUSED,
                message="the provider returned a refusal instead of a completion",
                usage=usage,
                raw_output=refusal,
            )

        status = getattr(response, "status", None)
        if status == "incomplete":
            details = getattr(response, "incomplete_details", None)
            reason = getattr(details, "reason", None)
            return ModelFailure(
                reason=_INCOMPLETE_FAILURES.get(
                    str(reason), FailureReason.SCHEMA_VALIDATION_FAILURE
                ),
                message=f"the provider stopped incomplete with reason={reason!r}",
                usage=usage,
                raw_output=_text_of(response),
            )

        raw = _text_of(response)
        if raw is None:
            return ModelFailure(
                reason=FailureReason.SCHEMA_VALIDATION_FAILURE,
                message=f"the response carried no message content to validate as {schema.__name__}",
                usage=usage,
            )

        try:
            parsed = schema.model_validate_json(json_candidate(raw))
        except pydantic.ValidationError as invalid:
            # Field locations and error types, never model output — the same section 27 rule and
            # the same retry-feedback reasoning as the Anthropic adapter.
            return ModelFailure(
                reason=FailureReason.SCHEMA_VALIDATION_FAILURE,
                message=(
                    f"the response did not validate as {schema.__name__}; "
                    f"the raw output is preserved (data-model.md section 33). "
                    f"Invalid at: {error_locations(invalid)}"
                ),
                usage=usage,
                raw_output=raw,
            )

        capabilities_used = {ModelCapability.EFFORT, ModelCapability.STRUCTURED_OUTPUT}
        # Reported only when the provider served a cached span (DEC-067): used, not merely
        # available.
        if usage.cache_read_tokens:
            capabilities_used.add(ModelCapability.PROMPT_CACHING)

        return ModelSuccess(
            value=parsed,
            usage=usage,
            capabilities_used=frozenset(capabilities_used),
            metadata={
                "effort": effort,
                "creativity": resolved.creativity.value,
                "schema_grammar": schema_grammar,
            },
        )

    def _send(self, client: Any, request: dict[str, Any], *, timeout: float) -> Any:
        return client.with_options(timeout=timeout).responses.create(**request)

    def _classified(self, error: openai.APIError, started: float) -> ModelFailure:
        """The exception ladder as a function, so the schema fallback shares it exactly."""
        if isinstance(error, openai.APITimeoutError):
            return self._failed(FailureReason.TIMEOUT, str(error), started)
        if isinstance(error, openai.APIConnectionError):
            return self._failed(FailureReason.CONNECTION_FAILURE, str(error), started)
        if isinstance(error, openai.AuthenticationError | openai.PermissionDeniedError):
            return self._failed(FailureReason.AUTHENTICATION_FAILURE, str(error), started)
        if isinstance(error, openai.BadRequestError):
            return self._failed(FailureReason.INVALID_REQUEST, str(error), started)
        if isinstance(error, openai.RateLimitError):
            return self._failed(FailureReason.TRANSIENT_PROVIDER_FAILURE, str(error), started)
        if isinstance(error, openai.APIStatusError):
            return self._failed(classify_http_error(error.status_code), str(error), started)
        return self._failed(FailureReason.CONNECTION_FAILURE, str(error), started)

    def _failed(self, reason: FailureReason, message: str, started: float) -> ModelFailure:
        """A failure that never produced a response, and therefore has a duration but no counts."""
        return ModelFailure(
            reason=reason,
            message=message,
            usage=ModelUsage(
                model=self._profile.model, duration_seconds=time.monotonic() - started
            ),
        )

    def _usage(self, response: Any, duration: float) -> ModelUsage:
        """The provider's usage figures, made disjoint and priced at this profile's rates.

        The provider's `input_tokens` includes the cached span, so the cached tokens are
        subtracted to keep DEC-067's input spans disjoint: `input_tokens` is uncached input at
        the full rate, `cache_read_tokens` is the cached span at its discounted rate, and there
        is no cache-write premium on this provider.
        """
        reported = getattr(response, "usage", None)
        prompt_tokens = int(getattr(reported, "input_tokens", 0) or 0)
        output_tokens = int(getattr(reported, "output_tokens", 0) or 0)
        details = getattr(reported, "input_tokens_details", None)
        cache_read = int(getattr(details, "cached_tokens", 0) or 0)
        input_tokens = max(prompt_tokens - cache_read, 0)
        return ModelUsage(
            model=str(getattr(response, "model", self._profile.model)),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_read_tokens=cache_read,
            cache_creation_tokens=0,
            estimated_cost=self._profile.cost_of(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cache_read_tokens=cache_read,
                cache_creation_tokens=0,
            ),
            duration_seconds=duration,
        )


def _message_parts(response: Any) -> list[Any]:
    """The content parts of the response's message items, in output order."""
    output = getattr(response, "output", None)
    if not isinstance(output, list):
        return []
    parts: list[Any] = []
    for item in output:
        if getattr(item, "type", None) != "message":
            continue
        content = getattr(item, "content", None)
        if isinstance(content, list):
            parts.extend(content)
    return parts


def _text_of(response: Any) -> str | None:
    """The response's output text, joined, for validation and for a failure to carry as raw
    output. Untrusted, read by a person debugging a schema failure, never parsed a second time."""
    texts = [
        text
        for part in _message_parts(response)
        if getattr(part, "type", None) == "output_text"
        and isinstance(text := getattr(part, "text", None), str)
        and text
    ]
    return "".join(texts) if texts else None


def _refusal_of(response: Any) -> str | None:
    """The refusal text, when any message part is one."""
    for part in _message_parts(response):
        if getattr(part, "type", None) == "refusal":
            refusal = getattr(part, "refusal", None)
            if isinstance(refusal, str) and refusal:
                return refusal
    return None
