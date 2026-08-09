"""The context slice: assembling what the extractor sees, and validating what it returns."""

from trace_ai.services.context.input_package import (
    FENCE_CLOSE,
    FENCE_OPEN,
    PRECEDENCE_RULE,
    ExtractorInput,
    assemble_extractor_input,
    neutralize_fence,
)

__all__ = [
    "FENCE_CLOSE",
    "FENCE_OPEN",
    "PRECEDENCE_RULE",
    "ExtractorInput",
    "assemble_extractor_input",
    "neutralize_fence",
]
