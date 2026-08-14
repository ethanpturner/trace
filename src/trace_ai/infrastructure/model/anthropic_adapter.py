"""The Anthropic adapter: the only module in this repository that imports a provider SDK.

DEC-014 keeps the model interface provider-agnostic and puts provider code behind the seam. This is
what "behind the seam" means concretely — every Anthropic-shaped decision lives here, and
`tests/unit/test_model_boundary.py` asserts that no module outside this package imports `anthropic`.

**The module is named `anthropic_adapter`, not `anthropic`.** `CLAUDE.md` records why: a module
named after something its own package imports is a shadowing bug waiting for the import that
triggers it, and this one would import the very package it was named after.

**Creativity maps to effort and adaptive thinking** (DEC-014). `temperature`, `top_p`, and `top_k`
are rejected on the current Anthropic models, so the intent in `agent-design.md` section 29 has to
land on the controls that exist. It maps to *deliberation*, which reads backwards for one moment and
then does not: more latitude means more room to explore before committing, and on this provider that
is effort. A low-creativity agent still reasons carefully — it is grounded by its prompt and its
evidence rules, not by being given less room to think.

**Exactly one attempt.** `max_retries=0` is set on the client for the reason DEC-014 gives: the
retry budget belongs to the orchestrator, and an adapter that retried would break the
`ExecutionRecord` retry count and the cost ceiling. Nothing in this module loops.

**The adapter validates the response text itself, never the SDK.** `messages.parse` validates each
text block client-side and raises `pydantic.ValidationError` when the text does not fit the schema
— which is exactly the shape of a `max_tokens`-truncated response, and an exception the
`anthropic.*` ladder cannot catch. Raised, it would discard the response and with it the raw output
`data-model.md` section 33 requires preserved. So this adapter sends the same wire request through
`messages.create` (the schema transformed by the SDK's own `transform_schema`, merged into
`output_config` exactly as `parse` would merge it), checks `stop_reason` first so truncation
reports as truncation, and only then validates the text — returning a `ModelFailure` that carries
it either way.

**The client is constructed on first use, never at import.** Building it at import time would make
`import trace_ai` require a key, which is exactly what `Settings.require()` exists to avoid — and
would break a bare `uv run pytest` on a machine with no `.env`.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any, Final

import anthropic
import pydantic

from trace_ai.config import Settings, get_settings
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

__all__ = ["EFFORT_BY_CREATIVITY", "AnthropicModel"]

# `agent-design.md` section 29's intent, mapped to the controls this provider exposes (DEC-014).
# Monotonic on purpose: more latitude, more room to explore before committing. The mapping is
# recorded on every result's metadata, because a wrong mapping is invisible -- an agent given the
# wrong latitude produces plausible output rather than an error.
EFFORT_BY_CREATIVITY: Final[dict[Creativity, str]] = {
    Creativity.LOW: "high",
    Creativity.MODERATE: "max",
}

# What this adapter supports, declared rather than assumed (DEC-014).
_CAPABILITIES: Final = frozenset(
    {
        ModelCapability.ADAPTIVE_THINKING,
        ModelCapability.EFFORT,
        ModelCapability.STRUCTURED_OUTPUT,
        ModelCapability.PROMPT_CACHING,
    }
)

# Provider stop reasons that mean no usable object, mapped to why.
_STOP_REASON_FAILURES: Final[dict[str, FailureReason]] = {
    "max_tokens": FailureReason.OUTPUT_TRUNCATED,
    "refusal": FailureReason.REFUSED,
}


class AnthropicModel:
    """A `StructuredModel` backed by the Anthropic Messages API."""

    def __init__(
        self,
        profile: ModelProfile | str = "primary-development",
        *,
        settings: Settings | None = None,
        client: Any | None = None,
    ) -> None:
        self._profile = resolve_profile(profile) if isinstance(profile, str) else profile
        if self._profile.provider != "anthropic":
            raise ValueError(
                f"profile {self._profile.name!r} names provider "
                f"{self._profile.provider!r}; this adapter serves 'anthropic'"
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
        """The provider client, built on first use.

        The key is read through `Settings.require()`, so an unset one raises `MissingSettingError`
        with instructions rather than surfacing later as a provider authentication error against a
        key nobody set.
        """
        if self._client is None:
            settings = self._settings if self._settings is not None else get_settings()
            self._client = anthropic.Anthropic(
                api_key=settings.require("anthropic_api_key"),
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
    ) -> ModelOutcome[T]:
        """One attempt at a validated instance of `schema`.

        Every provider condition is caught and returned as a `ModelFailure`. That is not defensive
        breadth: the caller has to record a cost and a duration for the attempt either way, and an
        exception escaping here would leave the execution ledger with a node that started and never
        finished. Validation runs here rather than in the SDK for the same reason — the SDK's
        client-side parse raises past that guarantee and takes the raw output with it.
        """
        resolved = settings if settings is not None else self._profile.settings
        effort = EFFORT_BY_CREATIVITY[resolved.creativity]

        # Built before the schema is touched, so an unconfigured key surfaces as
        # `MissingSettingError` with its fix — the operator's most likely slip (#319) — rather
        # than as whatever the schema transformation happens to say first.
        client = self._api()
        started = time.monotonic()

        try:
            wire_schema = anthropic.transform_schema(schema)
        except ValueError as error:
            return self._failed(
                FailureReason.INVALID_REQUEST,
                f"the schema {schema.__name__} could not be transformed for the provider's "
                f"structured-output format: {error}",
                started,
            )

        request: dict[str, Any] = {
            "model": self._profile.model,
            "max_tokens": resolved.max_output_tokens,
            "messages": [{"role": "user", "content": prompt}],
            "output_config": {
                "effort": effort,
                "format": {"type": "json_schema", "schema": wire_schema},
            },
            "thinking": {"type": "adaptive"},
        }
        if system is not None:
            request["system"] = system

        try:
            response = client.with_options(timeout=resolved.timeout_seconds).messages.create(
                **request
            )
        except anthropic.APITimeoutError as error:
            return self._failed(FailureReason.TIMEOUT, str(error), started)
        except anthropic.APIConnectionError as error:
            return self._failed(FailureReason.CONNECTION_FAILURE, str(error), started)
        except anthropic.AuthenticationError as error:
            return self._failed(FailureReason.AUTHENTICATION_FAILURE, str(error), started)
        except anthropic.PermissionDeniedError as error:
            return self._failed(FailureReason.AUTHENTICATION_FAILURE, str(error), started)
        except anthropic.BadRequestError as error:
            return self._failed(FailureReason.INVALID_REQUEST, str(error), started)
        except anthropic.RateLimitError as error:
            return self._failed(FailureReason.TRANSIENT_PROVIDER_FAILURE, str(error), started)
        except anthropic.APIStatusError as error:
            reason = (
                FailureReason.TRANSIENT_PROVIDER_FAILURE
                if error.status_code >= 500
                else FailureReason.INVALID_REQUEST
            )
            return self._failed(reason, str(error), started)

        usage = self._usage(response, time.monotonic() - started)
        stop_reason = getattr(response, "stop_reason", None)

        if isinstance(stop_reason, str) and stop_reason in _STOP_REASON_FAILURES:
            return ModelFailure(
                reason=_STOP_REASON_FAILURES[stop_reason],
                message=f"the provider stopped with stop_reason={stop_reason!r}",
                usage=usage,
                raw_output=_text_of(response),
            )

        raw = _text_of(response)
        if raw is None:
            return ModelFailure(
                reason=FailureReason.SCHEMA_VALIDATION_FAILURE,
                message=f"the response carried no text block to validate as {schema.__name__}",
                usage=usage,
            )

        try:
            parsed = schema.model_validate_json(raw)
        except pydantic.ValidationError:
            # The validation error's own text embeds fragments of the model output, which is
            # untrusted; the message stays safe (section 27) and the raw output carries the detail.
            return ModelFailure(
                reason=FailureReason.SCHEMA_VALIDATION_FAILURE,
                message=(
                    f"the response did not validate as {schema.__name__}; "
                    f"the raw output is preserved (data-model.md section 33)"
                ),
                usage=usage,
                raw_output=raw,
            )

        return ModelSuccess(
            value=parsed,
            usage=usage,
            capabilities_used=frozenset(
                {
                    ModelCapability.EFFORT,
                    ModelCapability.ADAPTIVE_THINKING,
                    ModelCapability.STRUCTURED_OUTPUT,
                }
            ),
            metadata={"effort": effort, "creativity": resolved.creativity.value},
        )

    def _failed(self, reason: FailureReason, message: str, started: float) -> ModelFailure:
        """A failure that never produced a response, and therefore has tokens but no counts."""
        return ModelFailure(
            reason=reason,
            message=message,
            usage=ModelUsage(
                model=self._profile.model, duration_seconds=time.monotonic() - started
            ),
        )

    def _usage(self, response: Any, duration: float) -> ModelUsage:
        """The provider's usage figures, priced with this profile's published rates.

        The provider's `input_tokens` already excludes both cache spans, so the three input
        counts arrive disjoint (DEC-067) and are kept that way: reads and writes are their own
        fields and their own weights in the cost.
        """
        reported = getattr(response, "usage", None)
        input_tokens = int(getattr(reported, "input_tokens", 0) or 0)
        output_tokens = int(getattr(reported, "output_tokens", 0) or 0)
        cache_read = int(getattr(reported, "cache_read_input_tokens", 0) or 0)
        cache_creation = int(getattr(reported, "cache_creation_input_tokens", 0) or 0)
        return ModelUsage(
            model=str(getattr(response, "model", self._profile.model)),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_read_tokens=cache_read,
            cache_creation_tokens=cache_creation,
            estimated_cost=self._profile.cost_of(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cache_read_tokens=cache_read,
                cache_creation_tokens=cache_creation,
            ),
            duration_seconds=duration,
        )


def _text_of(response: Any) -> str | None:
    """The response's text blocks, joined, for a failure to carry as raw output.

    Untrusted, like every other thing a model said. It exists to be read by a person debugging a
    schema failure, and is never parsed a second time.
    """
    blocks = getattr(response, "content", None)
    if not isinstance(blocks, list):
        return None
    text = "\n".join(
        block.text
        for block in blocks
        if getattr(block, "type", None) == "text" and isinstance(getattr(block, "text", None), str)
    )
    return text or None
