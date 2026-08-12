"""Issue #349: prompt definitions persisted at first use, resolvable from a record's identity.

The acceptance criteria are the spine: section 29 is IMPLEMENTED (the conformance suite holds
the model to the document), and an execution record's prompt identity — the reference it stores
and the DEC-019 composed hash behind it — resolves to a persisted `PromptDefinition`. Around
them: idempotence (recomposition writes nothing new), history (a moved hash writes a second
snapshot beside the first, never over it), and the driver-facing wrapper behaving as an ordinary
registry.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from trace_ai.domain.assessment import default_configuration
from trace_ai.infrastructure.database.store import AssessmentStore
from trace_ai.services.assessment import AssessmentService
from trace_ai.services.prompts.definitions import (
    PersistingPromptRegistry,
    list_definitions,
    persist_definition,
    resolve_definition,
)
from trace_ai.services.prompts.registry import PromptRegistry

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

    from trace_ai.services.assessment import AssessmentHandle
    from trace_ai.services.prompts.registry import ComposedPrompt

PROMPT = ("extract-context", "v1")


@pytest.fixture
def handle(tmp_path: Path) -> Iterator[AssessmentHandle]:
    with AssessmentStore.at_root(tmp_path) as store:
        service = AssessmentService(store, artifact_root=tmp_path)
        created = service.create(
            "Prompts", default_configuration("offline-fake", "stride-scenario-based")
        )
        yield service.handle(created.id)


def compose(handle: AssessmentHandle, filler: str = "content") -> ComposedPrompt:
    """One real composition through the persisting registry, every marker filled."""
    registry = PersistingPromptRegistry(handle)
    substitutions = dict.fromkeys(registry.markers(*PROMPT), filler)
    return registry.compose(*PROMPT, substitutions)


def test_a_composition_persists_its_definition(handle: AssessmentHandle) -> None:
    composed = compose(handle)

    (definition,) = list_definitions(handle)
    assert definition.reference == composed.reference
    assert definition.content_hash == composed.metadata.content_hash
    assert definition.file_path == composed.metadata.file_path
    assert definition.expected_output_schema == composed.metadata.expected_output_schema


def test_the_records_prompt_identity_resolves_to_the_definition(
    handle: AssessmentHandle,
) -> None:
    """Issue #349's acceptance criterion, by both handles a record keeps."""
    composed = compose(handle)

    by_reference = resolve_definition(handle, reference=composed.reference)
    by_hash = resolve_definition(handle, content_hash=composed.metadata.content_hash)
    assert by_reference is not None and by_hash is not None
    assert by_reference == by_hash
    assert by_reference.content_hash == composed.metadata.content_hash

    assert resolve_definition(handle, content_hash="sha256:" + "0" * 64) is None
    with pytest.raises(ValueError, match="reference"):
        resolve_definition(handle)


def test_recomposition_writes_nothing_new(handle: AssessmentHandle) -> None:
    compose(handle)
    compose(handle)
    assert len(list_definitions(handle)) == 1


def test_a_moved_hash_writes_a_second_snapshot_beside_the_first(
    handle: AssessmentHandle,
) -> None:
    """History is append-only: a shared-block or substitution change records a new definition."""
    first = compose(handle, filler="one")
    second = compose(handle, filler="two")
    assert first.metadata.content_hash != second.metadata.content_hash

    definitions = list_definitions(handle)
    assert len(definitions) == 2
    assert {definition.content_hash for definition in definitions} == {
        first.metadata.content_hash,
        second.metadata.content_hash,
    }


def test_the_wrapper_is_an_ordinary_registry(handle: AssessmentHandle) -> None:
    """Same composed text, same hash, same reference — persistence is the only addition."""
    plain = PromptRegistry()
    substitutions = dict.fromkeys(plain.markers(*PROMPT), "content")

    composed_plain = plain.compose(*PROMPT, substitutions)
    composed_persisting = compose(handle)
    assert isinstance(PersistingPromptRegistry(handle), PromptRegistry)
    assert composed_persisting.metadata.content_hash == composed_plain.metadata.content_hash


def test_the_snapshot_survives_a_definition_round_trip(handle: AssessmentHandle) -> None:
    composed = compose(handle)
    definition = persist_definition(handle, composed)
    stored = resolve_definition(handle, reference=definition.reference)
    assert stored == definition
