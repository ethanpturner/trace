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
wrapper then records at the next index. Divergence costs money, never a wrong answer.

**A served entry is carried forward into the active run's journal** (DEC-144). Spending an entry
in the source and recording nothing in the destination left a re-drive's own journal full of
holes: a second re-drive found the prefix spent and the remainder positioned against a
consumption order that no longer existed, and re-bought the whole run. The carried copy states
the usage the call cost when it was bought and names the entry it came from, so the journal keeps
one complete consumption order per generation without a later reader mistaking a replay for a
purchase. **The match is keyed on the request, not on position** (DEC-144): the scan reads the
remaining entries in order and serves the first whose schema and hash both match, and a call
nothing answers goes live leaving every entry unspent for a later call to claim.

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
    "append_journal_entry",
    "call_hash",
    "journal_dir",
    "journal_entry_paths",
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


def _entry_index(path: Path) -> int:
    """The numbered prefix a journal filename carries, or 0 for a name that has none."""
    digits = ""
    for character in path.name:
        if not character.isdigit():
            break
        digits += character
    return int(digits) if digits else 0


def journal_entry_paths(directory: Path) -> list[Path]:
    """This journal's entries in consumption order, ordered by number rather than by name.

    A journal that outlives two re-drives passes a hundred entries, and at three digits the
    lexicographic order a bare `sorted()` gives puts `100-` between `10-` and `11-`. The order
    is the contract the replay scan reads, so it is computed from the number.
    """
    return sorted(directory.glob("[0-9]*.json"), key=lambda path: (_entry_index(path), path.name))


def append_journal_entry(
    directory: Path,
    *,
    response: BaseModel,
    usage: dict[str, object] | None,
    call_sha256: str,
    replayed_from: str | None = None,
) -> Path:
    """Write one entry at the next index and return where it landed.

    The index is one past the highest the directory already holds rather than one past the count:
    a resumed run appends after the interrupted attempt's entries, and a gap left by a removed
    file must not send the next write onto a name that already exists — `ArtifactStore` refuses an
    overwrite for good reason, and this directory has no such guard.
    """
    directory.mkdir(parents=True, exist_ok=True)
    existing = journal_entry_paths(directory)
    index = (_entry_index(existing[-1]) if existing else 0) + 1
    slug = agent_for_schema(type(response).__name__) or "response"
    path = directory / f"{index:02d}-{slug}.json"
    envelope: dict[str, object] = {"schema": type(response).__name__}
    if usage is not None:
        envelope["usage"] = usage
    envelope["response"] = response.model_dump(mode="json")
    envelope["call_sha256"] = call_sha256
    if replayed_from is not None:
        # Provenance, not accounting: the usage beside it is what the call cost when it was
        # bought, and the run that carried it forward records no spend for it at all.
        envelope["replayed_from"] = replayed_from
    path.write_text(json.dumps(envelope, indent=2) + "\n", encoding="utf-8")
    return path


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
            path = append_journal_entry(
                self._directory,
                response=outcome.value,
                usage=_usage_dict(outcome.usage),
                call_sha256=call_hash(prompt=prompt, system=system),
            )
            print(f"journaled {path.name}", file=sys.stderr)
        return outcome


class JournalReplayModel:
    """Serves matching journal entries, and sends everything else to the live model.

    The scan reads the remaining entries in order and serves the first whose schema and request
    hash both match; an entry it passes over stays in the queue, unspent, for a later call to
    claim (DEC-144). Nothing is discarded by being scanned past, because the request hash — not
    the position — is what proves an entry answers this call: an entry recorded by a phase that
    already completed simply never matches, and a run whose inputs were edited matches nothing
    and buys every call. A call the journal cannot answer goes live, so a diverged journal costs
    money rather than serving a stale conclusion.

    `carry_forward` names the active run's journal directory. A served entry is copied there
    before it is returned, so this run's journal records the whole consumption order rather than
    only the calls it bought, and a re-drive of a re-drive needs no hand-assembled journal.
    """

    def __init__(
        self,
        entries: list[JournalEntry],
        inner: StructuredModel,
        *,
        carry_forward: Path | None = None,
    ) -> None:
        self._entries = list(entries)
        self._inner = inner
        self._carry_forward = carry_forward
        self._reported: set[Path] = set()

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
        for position, entry in enumerate(self._entries):
            if not entry.answers(schema=schema, request_hash=request_hash):
                continue
            self._entries.pop(position)
            spent_marker(entry.path).write_text(
                "replayed; a journal entry answers one call once\n", encoding="utf-8"
            )
            carried = self._carry(entry, request_hash)
            where = f" -> {carried.name}" if carried is not None else ""
            print(f"replayed {entry.path.name} (no spend){where}", file=sys.stderr)
            usage_model = entry.usage.model if entry.usage is not None else self._inner.name
            return ModelSuccess(
                # `answers` verified the isinstance; the cast states what it proved.
                value=cast("T", entry.response),
                usage=ModelUsage(model=usage_model),
                metadata={"replayed_from_journal": entry.path.name},
            )
        self._report_divergence(schema)
        return self._inner.generate(
            prompt=prompt,
            schema=schema,
            settings=settings,
            system=system,
            cache_prefix=cache_prefix,
            system_cache_prefix=system_cache_prefix,
        )

    def _carry(self, entry: JournalEntry, request_hash: str) -> Path | None:
        """Copy a served entry into the active run's journal, or nothing if none was named.

        The copy records the request hash that matched rather than the one the source carried:
        a hand-assembled entry with no hash answered this call on schema alone, and the copy
        states which call that was, so the next generation replays under the tighter contract.
        """
        if self._carry_forward is None:
            return None
        return append_journal_entry(
            self._carry_forward,
            response=entry.response,
            usage=_usage_dict(entry.usage) if entry.usage is not None else None,
            call_sha256=request_hash,
            replayed_from=entry.path.name,
        )

    def _report_divergence(self, schema: type[BaseModel]) -> None:
        """Name an entry that carries this call's schema and a different request, once each.

        Nothing is set aside — the entry stays for a later call — but the operator hears that a
        journal they named is not answering, which is the difference between a journal that ran
        out and one whose inputs moved under it.
        """
        for entry in self._entries:
            if not isinstance(entry.response, schema) or entry.path in self._reported:
                continue
            self._reported.add(entry.path)
            print(
                f"journal diverged at {entry.path.name}: it carries this call's schema and a "
                f"different request; continuing live, and it stays unspent",
                file=sys.stderr,
            )
