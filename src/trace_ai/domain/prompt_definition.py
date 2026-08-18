"""`PromptDefinition`: a versioned prompt as a record, not only a file (section 29, issue #349).

`data-model.md` section 29 is authoritative for the fields. The prompt body stays in its
version-controlled file — `services/prompts/` composes and hashes it (DEC-019: the hash covers
the **composed** text, shared blocks merged in) — and this object is the queryable counterpart:
an `ExecutionRecord` names the prompt it ran with, and this record says what that reference was
made of, from which file, with which hash.

**Identity is `(id, version)`, and `id` is a name** (DEC-034). Authored configuration carries a
lowercase slug outside the identifier scheme — `extract-context`, not a prefixed number — and is
referenced by version. It is not scoped to an assessment and no persistence layer mints its
identity; what an assessment persists is a snapshot of the definition it composed, written to its
own `traces/` area at first use.
"""

from __future__ import annotations

from pydantic import Field

from trace_ai.domain.base import DomainModel
from trace_ai.domain.hashing import ContentHash

__all__ = ["PromptDefinition"]


class PromptDefinition(DomainModel):
    """A versioned prompt used by a model-assisted workflow node (section 29)."""

    id: str = Field(min_length=1)
    """The prompt's *name*: a lowercase slug, outside the identifier scheme (DEC-034)."""

    version: str = Field(min_length=1)
    name: str = Field(min_length=1)
    purpose: str = Field(min_length=1)

    file_path: str = Field(min_length=1)
    """The version-controlled prompt file, repository-relative. The body lives there; this
    record carries the metadata and the composed hash."""

    expected_input_schema: str = Field(min_length=1)
    expected_output_schema: str = Field(min_length=1)
    model_constraints: list[str] = Field(default_factory=list)
    status: str = Field(min_length=1)
    """Draft, active, retired — the file's own front-matter vocabulary."""

    content_hash: ContentHash
    """`sha256:<hex>` over the **composed** prompt text (DEC-019), never over the file alone:
    an edit to a shared block moves the hash of every prompt that includes it. Substituted
    values are inside it, so this hash identifies one composition — what was actually sent."""

    template_hash: ContentHash
    """`sha256:<hex>` over the pre-substitution composition — shared blocks merged, markers
    unfilled (DEC-094). The cross-corpus identity: every composition of the same prompt version
    shares it, so "which template produced this" is answerable across assessments, and a
    shared-block edit still moves it in every prompt that includes the block."""

    @property
    def reference(self) -> str:
        """`extract-context-v1`: what `WorkflowRun.prompt_versions` and execution records name."""
        return f"{self.id}-{self.version}"
