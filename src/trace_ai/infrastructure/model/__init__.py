"""The model seam: one path from application code to a provider (DEC-014).

`AnthropicModel` is deliberately absent from this namespace. Importing it here would pull the
provider SDK into every module that touches the seam, which is the coupling the seam exists to
prevent — import it from `trace_ai.infrastructure.model.anthropic_adapter` at the one place that
constructs it.
"""

from trace_ai.infrastructure.model.fake import (
    DeterministicModel,
    RecordedCall,
    ResponsesExhaustedError,
)
from trace_ai.infrastructure.model.profiles import (
    DEFAULT_PROFILE,
    PROFILES,
    ModelProfile,
    UnknownModelProfileError,
    resolve_profile,
)
from trace_ai.infrastructure.model.replay import CacheKey, ReplayCache, cache_key
from trace_ai.infrastructure.model.seam import (
    Creativity,
    FailureReason,
    GenerationSettings,
    ModelCapability,
    ModelFailure,
    ModelOutcome,
    ModelSuccess,
    ModelUsage,
    StructuredModel,
)

__all__ = [
    "DEFAULT_PROFILE",
    "PROFILES",
    "CacheKey",
    "Creativity",
    "DeterministicModel",
    "FailureReason",
    "GenerationSettings",
    "ModelCapability",
    "ModelFailure",
    "ModelOutcome",
    "ModelProfile",
    "ModelSuccess",
    "ModelUsage",
    "RecordedCall",
    "ReplayCache",
    "ResponsesExhaustedError",
    "StructuredModel",
    "UnknownModelProfileError",
    "cache_key",
    "resolve_profile",
]
