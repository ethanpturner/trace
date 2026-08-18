"""Persisting prompt definitions at first use, and resolving them back (issue #349).

Before this module, a prompt existed as a file plus a hashing registry, and an
`ExecutionRecord`'s prompt identity — the `extract-context-v1` reference and the DEC-019 hash
behind it — had no queryable counterpart. Now every composition a run makes writes the
`PromptDefinition` snapshot into the assessment's own `traces/prompts/` area, once per distinct
composed hash, so the record's reference resolves to what was actually sent: which file, which
declared schemas, which composed hash.

Snapshots live in the artifact store rather than the object store deliberately. DEC-034 keeps
authored configuration outside the identifier scheme — a `PromptDefinition` is named, not
minted, and is not scoped to an assessment — while DEC-020's per-assessment boundary means the
record of *what this assessment used* belongs with the assessment. `traces/` is exactly the area
that already holds per-run process records, and a JSON file per `(reference, hash)` is
append-only by construction: a shared-block edit that moves the hash writes a second snapshot
beside the first instead of overwriting history.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from trace_ai.domain.prompt_definition import PromptDefinition
from trace_ai.services.prompts.registry import PromptRegistry

if TYPE_CHECKING:
    from pathlib import Path

    from trace_ai.services.assessment import AssessmentHandle
    from trace_ai.services.prompts.registry import ComposedPrompt

__all__ = [
    "PersistingPromptRegistry",
    "list_definitions",
    "persist_definition",
    "resolve_definition",
]


def _definitions_area(handle: AssessmentHandle) -> Path:
    area = handle.artifacts.area("traces") / "prompts"
    area.mkdir(parents=True, exist_ok=True)
    return area


def persist_definition(handle: AssessmentHandle, composed: ComposedPrompt) -> PromptDefinition:
    """Write the definition this composition used, once per distinct composed hash.

    Idempotent: the filename carries the reference and the hash's leading hex, so recomposing
    the same prompt writes nothing new, and a changed composition (a shared-block edit, a schema
    change) records a second snapshot rather than replacing the first.
    """
    metadata = composed.metadata
    definition = PromptDefinition.model_validate(
        {
            "id": metadata.id,
            "version": metadata.version,
            "name": metadata.name,
            "purpose": metadata.purpose,
            "file_path": metadata.file_path,
            "expected_input_schema": metadata.expected_input_schema,
            "expected_output_schema": metadata.expected_output_schema,
            "model_constraints": list(metadata.model_constraints),
            "status": metadata.status,
            "content_hash": metadata.content_hash,
            "template_hash": metadata.template_hash,
        }
    )
    digest = definition.content_hash.removeprefix("sha256:")[:12]
    target = _definitions_area(handle) / f"{definition.reference}-{digest}.json"
    if not target.exists():
        target.write_text(definition.model_dump_json(indent=2), encoding="utf-8")
    return definition


def list_definitions(handle: AssessmentHandle) -> list[PromptDefinition]:
    """Every definition this assessment composed, in filename order."""
    return [
        PromptDefinition.model_validate_json(path.read_text(encoding="utf-8"))
        for path in sorted(_definitions_area(handle).glob("*.json"))
    ]


def resolve_definition(
    handle: AssessmentHandle,
    *,
    reference: str | None = None,
    content_hash: str | None = None,
    template_hash: str | None = None,
) -> PromptDefinition | None:
    """The definition behind an execution record's prompt identity, or `None`.

    Resolvable by any handle the record keeps: the `prompt_version` reference
    (`extract-context-v1`), the DEC-019 composed hash, or the DEC-094 template hash — the one
    that answers "which template produced this" across corpora. Every given handle must match —
    a reference whose hash moved mid-assessment is two definitions, and the caller asking with
    more than one is asking about one of them.
    """
    if reference is None and content_hash is None and template_hash is None:
        raise ValueError(
            "resolve_definition needs a reference, a content_hash, a template_hash, or several"
        )
    for definition in list_definitions(handle):
        if reference is not None and definition.reference != reference:
            continue
        if content_hash is not None and definition.content_hash != content_hash:
            continue
        if template_hash is not None and definition.template_hash != template_hash:
            continue
        return definition
    return None


class PersistingPromptRegistry(PromptRegistry):
    """The registry, with DEC-019's hash given a persisted counterpart per composition.

    Behaviour is the parent's exactly; the one addition is that every successful composition
    snapshots its `PromptDefinition` into the bound assessment's `traces/prompts/`. The driver
    binds one of these per run, so the six agents persist their definitions at first use without
    any node knowing the mechanism exists.
    """

    def __init__(self, handle: AssessmentHandle, root: Path | None = None) -> None:
        super().__init__(root)
        self._handle = handle

    def compose(
        self,
        prompt_id: str,
        version: str,
        substitutions: dict[str, str] | None = None,
    ) -> ComposedPrompt:
        composed = super().compose(prompt_id, version, substitutions)
        persist_definition(self._handle, composed)
        return composed
