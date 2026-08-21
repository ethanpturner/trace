"""The live-run response journal (#623, DEC-139; carry-forward and hash keying, DEC-144).

Every live response an ordinary run consumes is journaled in the recording-envelope shape, and a
resume replays the journal only when the operator names it — an entry answers exactly the call
that recorded it, exactly once. Divergence goes live: the journal may cost money it could have
saved, and may never serve a stale conclusion. A served entry is carried into the active run's
journal, so a second re-drive reads one complete consumption order instead of a spent prefix and
a positioned remainder (#645).
"""

from __future__ import annotations

import json
from decimal import Decimal
from typing import TYPE_CHECKING

import pytest

from trace_ai.domain.proposals.critical_review import CriticalReviewProposal
from trace_ai.domain.proposals.report_sections import ReportSections
from trace_ai.infrastructure.model.journal import (
    JournalEntry,
    JournalingModel,
    JournalReplayModel,
    SpentJournalEntryError,
    append_journal_entry,
    call_hash,
    journal_entry_paths,
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


def _unspent(journal: Path) -> list[JournalEntry]:
    """The CLI's directory rule, locally: unspent numbered entries, in consumption order."""
    return [
        read_journal_entry(path)
        for path in journal_entry_paths(journal)
        if not spent_marker(path).exists()
    ]


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


def test_a_same_schema_request_mismatch_is_never_served(tmp_path: Path) -> None:
    """This call is not the one the entry recorded: the run continues live, nothing is served."""
    stale = _journaled(tmp_path, prompt="the old prompt")
    live = _StubModel([_success(_sections()), _success(_sections())])
    replay = JournalReplayModel([read_journal_entry(stale)], live)

    outcome = replay.generate(prompt="an edited prompt", schema=ReportSections)

    assert isinstance(outcome, ModelSuccess)
    assert live.calls == ["an edited prompt"]
    assert not spent_marker(stale).exists()


def test_an_entry_passed_over_stays_for_the_call_it_answers(tmp_path: Path) -> None:
    """DEC-144: the request hash proves the match, so position never disqualifies an entry.

    Before it, a same-schema mismatch set the whole remaining journal aside and every later
    call went live — the loss #332 measured, where a re-drive re-bought a run whose answers
    were sitting unspent on disk.
    """
    entry = _journaled(tmp_path, prompt="the recorded prompt")
    live = _StubModel([_success(_sections())])
    replay = JournalReplayModel([read_journal_entry(entry)], live)

    replay.generate(prompt="a call the journal never answered", schema=ReportSections)
    assert live.calls == ["a call the journal never answered"]
    assert not spent_marker(entry).exists()

    outcome = replay.generate(prompt="the recorded prompt", schema=ReportSections)

    assert isinstance(outcome, ModelSuccess)
    assert outcome.metadata["replayed_from_journal"] == entry.name
    assert live.calls == ["a call the journal never answered"], "the second call was not bought"
    assert spent_marker(entry).exists()


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


def test_a_replayed_entry_is_carried_into_the_active_journal(tmp_path: Path) -> None:
    """Composed as the CLI composes them: replay outside, journaling inside, live at the core.

    DEC-144: a served entry is copied forward, so this run's journal records every call it
    consumed rather than only the ones it bought.
    """
    path = _journaled(tmp_path, prompt="p", system="s")
    journal = path.parent

    live = _StubModel([_success(CriticalReviewProposal(critiques=[]))])
    journaling = JournalingModel(live, journal)
    replay = JournalReplayModel([read_journal_entry(path)], journaling, carry_forward=journal)

    replay.generate(prompt="p", schema=ReportSections, system="s")
    replay.generate(prompt="fresh call", schema=CriticalReviewProposal)

    names = [entry.name for entry in journal_entry_paths(journal)]
    assert names == [
        "01-report-generation.json",
        "02-report-generation.json",
        "03-critical-review.json",
    ], "the carried copy and the fresh purchase land in consumption order"
    carried = json.loads((journal / "02-report-generation.json").read_text(encoding="utf-8"))
    assert carried["replayed_from"] == path.name
    assert carried["call_sha256"] == call_hash(prompt="p", system="s")


def test_a_carried_copy_states_the_cost_of_the_purchase_it_records(tmp_path: Path) -> None:
    """The copy keeps the usage the call was bought at; the run that carried it spends nothing.

    Cost is not double-counted because the two records answer different questions: the ledger
    reads the outcome, which is zero, and the journal reads the envelope, which is what that
    response cost the run that paid for it.
    """
    path = _journaled(tmp_path, prompt="p")
    journal = path.parent
    replay = JournalReplayModel([read_journal_entry(path)], _StubModel([]), carry_forward=journal)

    outcome = replay.generate(prompt="p", schema=ReportSections)

    assert isinstance(outcome, ModelSuccess)
    assert outcome.usage.estimated_cost == Decimal(0), "this run bought nothing"
    carried = json.loads((journal / "02-report-generation.json").read_text(encoding="utf-8"))
    assert carried["usage"]["estimated_cost"] == "0.25"
    assert carried["usage"]["model"] == "live-model"
    assert carried["replayed_from"] == path.name


def test_a_second_generation_re_drive_needs_no_hand_assembled_journal(tmp_path: Path) -> None:
    """Run, kill, re-drive, kill, re-drive — the #332 loss, reproduced and closed (DEC-144).

    The third generation's fallback model is empty: every call it makes must be answered by the
    journal the second generation left behind, or the run raises rather than quietly buying.
    """
    journal = tmp_path / "journal"

    # Generation one buys two calls and is killed before the third.
    first = JournalingModel(_StubModel([_success(_sections()), _success(_sections())]), journal)
    first.generate(prompt="call one", schema=ReportSections)
    first.generate(prompt="call two", schema=ReportSections)

    # Generation two replays both, buys the third, and is killed.
    second_live = _StubModel([_success(CriticalReviewProposal(critiques=[]))])
    second = JournalReplayModel(
        _unspent(journal), JournalingModel(second_live, journal), carry_forward=journal
    )
    second.generate(prompt="call one", schema=ReportSections)
    second.generate(prompt="call two", schema=ReportSections)
    second.generate(prompt="call three", schema=CriticalReviewProposal)
    assert second_live.calls == ["call three"], "generation two bought only what it had to"

    # Generation three replays all three from what generation two left, buying nothing.
    third_live = _StubModel([])
    third = JournalReplayModel(
        _unspent(journal), JournalingModel(third_live, journal), carry_forward=journal
    )
    third.generate(prompt="call one", schema=ReportSections)
    third.generate(prompt="call two", schema=ReportSections)
    outcome = third.generate(prompt="call three", schema=CriticalReviewProposal)

    assert isinstance(outcome, ModelSuccess)
    assert third_live.calls == [], "the whole consumption order replayed with no spend"


def test_entries_past_ninety_nine_keep_their_number_order(tmp_path: Path) -> None:
    """Three generations of a large scenario pass a hundred entries, and `10-` precedes `100-`."""
    journal = tmp_path / "journal"
    journal.mkdir()
    for index in (9, 10, 100, 11):
        (journal / f"{index:02d}-report-generation.json").write_text("{}", encoding="utf-8")

    assert [path.name for path in journal_entry_paths(journal)] == [
        "09-report-generation.json",
        "10-report-generation.json",
        "11-report-generation.json",
        "100-report-generation.json",
    ]


def test_the_next_index_clears_the_highest_rather_than_the_count(tmp_path: Path) -> None:
    """A gap left by a removed entry must not send the next write onto a name that exists."""
    journal = tmp_path / "journal"
    journal.mkdir()
    for index in (1, 3):
        (journal / f"{index:02d}-report-generation.json").write_text("{}", encoding="utf-8")

    path = append_journal_entry(journal, response=_sections(), usage=None, call_sha256="abc")

    assert path.name == "04-report-generation.json"
