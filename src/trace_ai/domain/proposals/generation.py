"""`GenerationMetadata`: what produced a proposed object, recorded once rather than per object.

`data-model.md` section 34 requires model-generated objects to carry generation metadata and then
says how: the MVP should prefer *linked execution records* to duplicating that metadata onto every
object. This is the link — one metadata object per model response, naming the execution record that
holds the tokens, the cost, and the timings.

`generated_by` is the agent version, `context-extraction-v1` (`agent-design.md` section 33), not the
model. The model is `model_name`, and the two are different things: the same agent version can run
against a different model, and an evaluation comparing runs needs to tell which changed.
"""

from __future__ import annotations

from datetime import datetime
from typing import Final

from pydantic import Field

from trace_ai.domain.base import DomainModel
from trace_ai.domain.identifiers import ExecutionRecordId, WorkflowRunId

__all__ = ["CONTEXT_EXTRACTION_AGENT", "GenerationMetadata"]

# The agent version `agent-design.md` section 33 names for the first agent. Agent version and
# prompt version are separate: section 33 lets a minor wording change move the prompt version
# without moving the agent's.
CONTEXT_EXTRACTION_AGENT: Final = "context-extraction-v1"


class GenerationMetadata(DomainModel):
    """Section 34's fields, attached to one model response."""

    generated_by: str = Field(min_length=1)
    """The agent version, such as `context-extraction-v1`. Not the model."""

    workflow_run_id: WorkflowRunId
    execution_record_id: ExecutionRecordId
    """The record holding tokens, cost, and timings — the reason this object is a link rather than
    a copy of that data."""

    model_name: str = Field(min_length=1)
    prompt_version: str = Field(min_length=1)
    """The composed prompt's reference, `extract-context-v1`, which the registry produces."""

    generated_at: datetime
