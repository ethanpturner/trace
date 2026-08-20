"""The live-run response journal: every live response written where a re-drive can read it (#623).

An interruption between phases resumes cleanly (DEC-017), but an interruption inside a phase loses
every model call the phase already paid for, because an ordinary `run` or `resume` records nothing
— the recording wrapper in `services/evaluation/capture.py` is mounted only by `trace capture`.
`JournalingModel` closes that gap: it wraps the live model for every ordinary run and writes each
consumed response into the assessment's `traces/journal/` area, shaped exactly as
`load_recorded_responses` reads it back, plus one key that module ignores — `call_sha256`, a hash
of the request that produced the response, so a replay can tell "the same call again" from "a call
that merely asks for the same schema".

**Replay is operator-asserted, never automatic** (DEC-139). A resume replays the journal only when
the operator names it with `--replay-journal`; a stale journal must not silently answer an edited
input. `JournalReplayModel` serves an entry only when the requested schema *and* the request hash
match, marks each served entry spent with a sidecar file so it can never answer twice across
resumes, and sends everything the journal cannot answer to the live model — which the journaling
wrapper then records at the next index. A journaled entry that matches nothing is skipped aloud
and left unspent; divergence costs money, never a wrong answer.

Failures are not journaled, for the reason the capture wrapper gives: a replay has no way to serve
one and does not need to — a live retry that recovered replays as a first-attempt success. The
journal inherits `traces/`'s retention and privacy posture; it invents no new one.
"""

from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from trace_ai.infrastructure.model.agents import agent_for_schema
from trace_ai.infrastructure.model.recorded import parse_recorded_response
from trace_ai.infrastructure.model.seam import (
    ModelOutcome,
    ModelSuccess,
    ModelUsage,
)

if TYPE_CHECKING:
    from pathlib import Path

    from pydantic import BaseModel

    from trace_ai.infrastructure.filesystem.artifact_store import ArtifactStore
    from trace_ai.infrastructure.model.seam import (
        GenerationSettings,
        ModelCapability,
        StructuredModel,
    )

__all__ = [
    "JournalEntry",
    "JournalReplayModel",
    "JournalingModel",
    "SpentJournalEntryError",
    "call_hash",
    "journal_dir",
    "read_journal_entry",
    "spent_marker",
]


def journal_dir(artifacts: ArtifactStore) -> Path:
    """Where this assessment's journal lives: a directory inside its own `traces/` area."""
    return artifacts.area("traces") / "journal"


def call_hash(*, prompt: str, system: str | None) -> str:
    """One hash over the whole request, so a replayed entry answers only the call that made it.

    The system prompt is hashed with the user prompt: an edit to a composed prompt file changes
    the request as surely as an edited source document does, and a hash over the prompt alone
    would let a stale entry answer it.
    """
    digest = hashlib.sha256()
    digest.update((system or "").encode("utf-8"))
    digest.update(b"\x00")
    digest.update(prompt.encode("utf-8"))
    return digest.hexdigest()


def spent_marker(entry_path: Path) -> Path:
    """The sidecar that marks a journal entry as already replayed."""
    return entry_path.with_name(entry_path.name + ".spent")


class SpentJournalEntryError(ValueError):
    """An operator named a journal entry an earlier resume already replayed.

    Serving it again would hand the run a response another attempt consumed — the replay
    equivalent of retrying the conclusion — so the refusal is loud rather than silent.
    """

    def __init__(self, entry_path: Path) -> None:
        super().__init__(
            f"{entry_path.name} is spent: an earlier resume already replayed it. A journal entry "
            f"answers one call once; name the unspent entries, or omit --replay-journal to run "
            f"the calls live."
        )


@dataclass(frozen=True, slots=True)
class JournalEntry:
    """One journaled response: where it lives, what it answers, and what it carries."""

    path: Path
    response: BaseModel
    usage: ModelUsage | None
    call_sha256: str | None
    """Absent on an envelope the journal did not write — an operator can point `--replay-journal`
    at a hand-assembled file, and an entry with no hash matches on schema alone, which is exactly
    the looser contract the operator asserted by assembling it."""

    def answers(self, *, schema: type[BaseModel], request_hash: str) -> bool:
        if not isinstance(self.response, schema):
            return False
        return self.call_sha256 is None or self.call_sha256 == request_hash


def read_journal_entry(path: Path) -> JournalEntry:
    """One entry off disk, refused if spent, validated exactly as a recording is.

    The envelope is the recording envelope, so `parse_recorded_response` does the validation —
    including the rehearsal refusal — and the journal's own `call_sha256` key is read beside it.
    """
    if spent_marker(path).exists():
        raise SpentJournalEntryError(path)
    text = path.read_text(encoding="utf-8")
    recorded = parse_recorded_response(text, described_as=path.name)
    raw = json.loads(text)
    hash_value = raw.get("call_sha256") if isinstance(raw, dict) else None
    return JournalEntry(
        path=path,
        response=recorded.response,
        usage=recorded.usage,
        call_sha256=str(hash_value) if hash_value is not None else None,
    )


def _usage_dict(usage: ModelUsage) -> dict[str, object]:
    """The envelope's `usage` mapping, Decimal cost as a string so JSON keeps its precision."""
    return {
        "model": usage.model,
        "input_tokens": usage.input_tokens,
        "output_tokens": usage.output_tokens,
        "cache_read_tokens": usage.cache_read_tokens,
        "cache_creation_tokens": usage.cache_creation_tokens,
        "estimated_cost": str(usage.estimated_cost),
        "duration_seconds": usage.duration_seconds,
    }


class JournalingModel:
    """A `StructuredModel` that writes every live response this run consumes into the journal.

    Entry indices continue past what the directory already holds, so a resumed run appends after
    the interrupted attempt's entries rather than overwriting them — `ArtifactStore` refuses an
    overwrite for good reason, and the journal never needs one.
    """

    def __init__(self, inner: StructuredModel, directory: Path) -> None:
        self._inner = inner
        self._directory = directory

    @property
    def name(self) -> str:
        return self._inner.name

    @property
    def capabilities(self) -> frozenset[ModelCapability]:
        return self._inner.capabilities

    def generate[T: BaseModel](
        self,
        *,
        prompt: str,
        schema: type[T],
        settings: GenerationSettings | None = None,
        system: str | None = None,
        cache_prefix: str | None = None,
        system_cache_prefix: str | None = None,
    ) -> ModelOutcome[T]:
        outcome = self._inner.generate(
            prompt=prompt,
            schema=schema,
            settings=settings,
            system=system,
            cache_prefix=cache_prefix,
            system_cache_prefix=system_cache_prefix,
        )
        if isinstance(outcome, ModelSuccess):
            self._directory.mkdir(parents=True, exist_ok=True)
            index = len(list(self._directory.glob("[0-9]*.json"))) + 1
            slug = agent_for_schema(type(outcome.value).__name__) or "response"
            path = self._directory / f"{index:02d}-{slug}.json"
            envelope: dict[str, object] = {
                "schema": type(outcome.value).__name__,
                "usage": _usage_dict(outcome.usage),
                "response": outcome.value.model_dump(mode="json"),
                "call_sha256": call_hash(prompt=prompt, system=system),
            }
            path.write_text(json.dumps(envelope, indent=2) + "\n", encoding="utf-8")
            print(f"journaled {path.name}", file=sys.stderr)
        return outcome


class JournalReplayModel:
    """Serves matching journal entries in order, and sends everything else to the live model.

    The scan pops from the front: entries recorded by phases that already completed — which a
    resumed run never re-asks — are skipped aloud and left unspent, and the first entry whose
    schema and request hash both match is served and marked spent. A call nothing in the journal
    answers goes live, so a diverged journal costs money rather than serving a stale conclusion.
    """

    def __init__(self, entries: list[JournalEntry], inner: StructuredModel) -> None:
        self._entries = list(entries)
        self._inner = inner

    @property
    def name(self) -> str:
        return self._inner.name

    @property
    def capabilities(self) -> frozenset[ModelCapability]:
        return self._inner.capabilities

    def generate[T: BaseModel](
        self,
        *,
        prompt: str,
        schema: type[T],
        settings: GenerationSettings | None = None,
        system: str | None = None,
        cache_prefix: str | None = None,
        system_cache_prefix: str | None = None,
    ) -> ModelOutcome[T]:
        request_hash = call_hash(prompt=prompt, system=system)
        while self._entries:
            entry = self._entries[0]
            if entry.answers(schema=schema, request_hash=request_hash):
                self._entries.pop(0)
                spent_marker(entry.path).write_text(
                    "replayed; a journal entry answers one call once\n", encoding="utf-8"
                )
                print(f"replayed {entry.path.name} (no spend)", file=sys.stderr)
                usage_model = entry.usage.model if entry.usage is not None else self._inner.name
                return ModelSuccess(
                    # `answers` verified the isinstance; the cast states what it proved.
                    value=cast("T", entry.response),
                    usage=ModelUsage(model=usage_model),
                    metadata={"replayed_from_journal": entry.path.name},
                )
            if isinstance(entry.response, schema):
                # The schema matches and the request does not: this call is not the one the
                # entry recorded. Serving it anyway is what --replay-journal exists to prevent,
                # so the whole remaining journal is set aside and the run continues live —
                # popping past a same-schema mismatch could spend an entry a later call needs.
                skipped = ", ".join(item.path.name for item in self._entries)
                print(
                    f"journal diverged at {entry.path.name}: the request differs from the one "
                    f"it recorded; continuing live ({skipped} left unspent)",
                    file=sys.stderr,
                )
                self._entries.clear()
                break
            self._entries.pop(0)
            print(f"skipped {entry.path.name} (a completed phase's entry)", file=sys.stderr)
        return self._inner.generate(
            prompt=prompt,
            schema=schema,
            settings=settings,
            system=system,
            cache_prefix=cache_prefix,
            system_cache_prefix=system_cache_prefix,
        )
