"""The context slice: assembling what the extractor sees, running it, and reviewing what it returns.

Only `input_package` is re-exported here. `pipeline` and `review_file` are imported from their own
modules, and that is not a style preference: `workflow/context_extraction.py` imports
`input_package`, so a package `__init__` that also imported `pipeline` — which imports the
extraction node — would make importing the node import itself. Re-exporting the whole slice would
cost a circular import for the convenience of a shorter path.
"""

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
