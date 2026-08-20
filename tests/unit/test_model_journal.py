"""The live-run response journal (#623, DEC-137).

Every live response an ordinary run consumes is journaled in the recording-envelope shape, and a
resume replays the journal only when the operator names it — an entry answers exactly the call
that recorded it, exactly once. Divergence goes live: the journal may cost money it could have
saved, and may never serve a stale conclusion.
"""

from __future__ import annotations

import json
from decimal import Decimal
from typing import TYPE_CHECKING

import pytest

from trace_ai.domain.proposals.critical_review import CriticalReviewProposal
from trace_ai.domain.proposals.report_sections import ReportSections
from trace_ai.infrastructure.model.journal import (
    JournalingModel,
    JournalReplayModel,
    SpentJournalEntryError,
    call_hash,
    read_journal_entry,
    spent_marker,
)
from trace_ai.infrastructure.model.recorded import load_recorded_responses
from trace_ai.infrastructure.model.seam import (
    FailureReason,
    ModelFailure,
    ModelOutcome,
    ModelSuccess,
    ModelUsage,
)

if TYPE_CHECKING:
    from pathlib import Path

    from pydantic import BaseModel

    from trace_ai.infrastructure.model.seam import GenerationSettings, ModelCapability


def _sections() -> ReportSections:
    return ReportSections(
        executive_summary="A summary.",
        system_overview="An overview.",
        risk_summary="The risks.",
        limitations=[],
    )


class _StubModel:
    """A seam-shaped stand-in whose outcomes and received calls the test controls and reads."""

    def __init__(self, outcomes: list[ModelOutcome[BaseModel]]) -> None:
        self._outcomes = list(outcomes)
        self.calls: list[str] = []

    @property
    def name(self) -> str:
        return "stub-model"

    @property
    def capabilities(self) -> frozenset[ModelCapability]:
        return frozenset()

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
        self.calls.append(prompt)
        outcome = self._outcomes.pop(0)
        return outcome  # type: ignore[return-value]


def _success(value: BaseModel, *, cost: str = "0.25") -> ModelSuccess[BaseModel]:
    usage = ModelUsage(
        model="live-model", input_tokens=100, output_tokens=50, estimated_cost=Decimal(cost)
    )
    return ModelSuccess(value=value, usage=usage)


def test_a_live_success_is_journaled_in_the_recording_envelope(tmp_path: Path) -> None:
    journal = tmp_path / "journal"
    model = JournalingModel(_StubModel([_success(_sections())]), journal)

    outcome = model.generate(prompt="p", schema=ReportSections, system="s")

    assert isinstance(outcome, ModelSuccess)
    written = sorted(journal.glob("[0-9]*.json"))
    assert [path.name for path in written] == ["01-report-generation.json"]
    recorded = load_recorded_responses(written)
    assert isinstance(recorded[0].response, ReportSections)
    assert recorded[0].usage is not None
    assert recorded[0].usage.estimated_cost == Decimal("0.25")
    envelope = json.loads(written[0].read_text(encoding="utf-8"))
    assert envelope["call_sha256"] == call_hash(prompt="p", system="s")


def test_indices_continue_past_what_the_directory_holds(tmp_path: Path) -> None:
    """A resumed run appends after the interrupted attempt's entries, never over them."""
    journal = tmp_path / "journal"
    first = JournalingModel(_StubModel([_success(_sections())]), journal)
    first.generate(prompt="p1", schema=ReportSections)

    second = JournalingModel(_StubModel([_success(_sections())]), journal)
    second.generate(prompt="p2", schema=ReportSections)

    names = [path.name for path in sorted(journal.glob("[0-9]*.json"))]
    assert names == ["01-report-generation.json", "02-report-generation.json"]


def test_a_failure_is_not_journaled(tmp_path: Path) -> None:
    """A replay has no way to serve a failure: a recovered retry replays as a first success."""
    journal = tmp_path / "journal"
    failure = ModelFailure(
        reason=FailureReason.TRANSIENT_PROVIDER_FAILURE,
        message="overloaded",
        usage=ModelUsage(model="live-model"),
    )
    model = JournalingModel(_StubModel([failure]), journal)

    outcome = model.generate(prompt="p", schema=ReportSections)

    assert isinstance(outcome, ModelFailure)
    assert not journal.exists() or not list(journal.glob("[0-9]*.json"))


def _journaled(tmp_path: Path, *, prompt: str, system: str | None = None) -> Path:
    """One entry on disk, written by the journaling wrapper itself."""
    journal = tmp_path / "journal"
    model = JournalingModel(_StubModel([_success(_sections())]), journal)
    model.generate(prompt=prompt, schema=ReportSections, system=system)
    return sorted(journal.glob("[0-9]*.json"))[-1]


def test_replay_serves_the_matching_call_once_and_marks_it_spent(tmp_path: Path) -> None:
    path = _journaled(tmp_path, prompt="p", system="s")
    live = _StubModel([])
    replay = JournalReplayModel([read_journal_entry(path)], live)

    outcome = replay.generate(prompt="p", schema=ReportSections, system="s")

    assert isinstance(outcome, ModelSuccess)
    assert isinstance(outcome.value, ReportSections)
    assert outcome.metadata["replayed_from_journal"] == path.name
    assert spent_marker(path).exists()
    assert live.calls == []


def test_a_replayed_call_records_zero_usage_under_the_original_model(tmp_path: Path) -> None:
    """The money was spent by the run that journaled the entry, and is recorded there."""
    path = _journaled(tmp_path, prompt="p")
    replay = JournalReplayModel([read_journal_entry(path)], _StubModel([]))

    outcome = replay.generate(prompt="p", schema=ReportSections)

    assert isinstance(outcome, ModelSuccess)
    assert outcome.usage.model == "live-model"
    assert outcome.usage.estimated_cost == Decimal(0)
    assert outcome.usage.output_tokens == 0


def test_a_completed_phases_entry_is_skipped_and_left_unspent(tmp_path: Path) -> None:
    """A resumed run never re-asks an earlier phase's call; its entries pass by aloud."""
    earlier = _journaled(tmp_path, prompt="earlier phase")
    later = _journaled(tmp_path, prompt="p")
    live = _StubModel([_success(CriticalReviewProposal(critiques=[]))])
    replay = JournalReplayModel([read_journal_entry(earlier), read_journal_entry(later)], live)

    outcome = replay.generate(prompt="p", schema=CriticalReviewProposal)

    # The call asks a schema neither entry carries; both are skipped, and the call goes live.
    assert isinstance(outcome, ModelSuccess)
    assert live.calls == ["p"]
    assert not spent_marker(earlier).exists()
    assert not spent_marker(later).exists()


def test_a_different_schema_ahead_of_the_match_is_skipped(tmp_path: Path) -> None:
    journal = tmp_path / "journal"
    model = JournalingModel(
        _StubModel([_success(CriticalReviewProposal(critiques=[])), _success(_sections())]),
        journal,
    )
    model.generate(prompt="critique", schema=CriticalReviewProposal)
    model.generate(prompt="report", schema=ReportSections)
    critique_path, report_path = sorted(journal.glob("[0-9]*.json"))

    live = _StubModel([])
    replay = JournalReplayModel(
        [read_journal_entry(critique_path), read_journal_entry(report_path)], live
    )
    outcome = replay.generate(prompt="report", schema=ReportSections)

    assert isinstance(outcome, ModelSuccess)
    assert isinstance(outcome.value, ReportSections)
    assert not spent_marker(critique_path).exists()
    assert spent_marker(report_path).exists()
    assert live.calls == []


def test_a_same_schema_request_mismatch_sets_the_journal_aside(tmp_path: Path) -> None:
    """This call is not the one the entry recorded: the run continues live, nothing is served."""
    stale = _journaled(tmp_path, prompt="the old prompt")
    live = _StubModel([_success(_sections()), _success(_sections())])
    replay = JournalReplayModel([read_journal_entry(stale)], live)

    outcome = replay.generate(prompt="an edited prompt", schema=ReportSections)

    assert isinstance(outcome, ModelSuccess)
    assert live.calls == ["an edited prompt"]
    assert not spent_marker(stale).exists()

    # The journal stays set aside for the rest of the process: a later matching call goes live.
    replay.generate(prompt="the old prompt", schema=ReportSections)
    assert live.calls == ["an edited prompt", "the old prompt"]


def test_an_exhausted_journal_delegates_live(tmp_path: Path) -> None:
    path = _journaled(tmp_path, prompt="p")
    live = _StubModel([_success(_sections()), _success(_sections())])
    replay = JournalReplayModel([read_journal_entry(path)], live)

    replay.generate(prompt="p", schema=ReportSections)
    outcome = replay.generate(prompt="the next call", schema=ReportSections)

    assert isinstance(outcome, ModelSuccess)
    assert live.calls == ["the next call"]


def test_a_spent_entry_is_refused_at_read(tmp_path: Path) -> None:
    path = _journaled(tmp_path, prompt="p")
    replay = JournalReplayModel([read_journal_entry(path)], _StubModel([]))
    replay.generate(prompt="p", schema=ReportSections)

    with pytest.raises(SpentJournalEntryError, match="spent"):
        read_journal_entry(path)


def test_an_entry_without_a_hash_matches_on_schema_alone(tmp_path: Path) -> None:
    """A hand-assembled envelope carries no hash; the operator asserted the looser contract."""
    path = tmp_path / "01-report-generation.json"
    path.write_text(
        json.dumps({"schema": "ReportSections", "response": _sections().model_dump(mode="json")}),
        encoding="utf-8",
    )
    replay = JournalReplayModel([read_journal_entry(path)], _StubModel([]))

    outcome = replay.generate(prompt="any prompt at all", schema=ReportSections)

    assert isinstance(outcome, ModelSuccess)
    assert spent_marker(path).exists()


def test_a_rehearsal_envelope_is_refused(tmp_path: Path) -> None:
    """The journal reads the recording envelope, rehearsal refusal included (#534)."""
    path = tmp_path / "01-report-generation.json"
    path.write_text(
        json.dumps(
            {
                "schema": "ReportSections",
                "response": _sections().model_dump(mode="json"),
                "rehearsal": True,
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="rehearsal"):
        read_journal_entry(path)


def test_a_replayed_entry_is_not_re_journaled(tmp_path: Path) -> None:
    """Composed as the CLI composes them: replay outside, journaling inside, live at the core."""
    path = _journaled(tmp_path, prompt="p", system="s")
    journal = path.parent
    before = len(list(journal.glob("[0-9]*.json")))

    live = _StubModel([_success(CriticalReviewProposal(critiques=[]))])
    journaling = JournalingModel(live, journal)
    replay = JournalReplayModel([read_journal_entry(path)], journaling)

    replay.generate(prompt="p", schema=ReportSections, system="s")
    assert len(list(journal.glob("[0-9]*.json"))) == before

    replay.generate(prompt="fresh call", schema=CriticalReviewProposal)
    assert len(list(journal.glob("[0-9]*.json"))) == before + 1
