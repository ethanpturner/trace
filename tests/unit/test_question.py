"""Tests for `Question`, DEC-009's first-named outlet.

The field set is held to `data-model.md` section 22 by the conformance guard. What matters here is
that a question cannot half-exist: `blocking` has to be stated, and an answer is recorded completely
or not at all.

The ordering is tested as behaviour rather than as presentation. `demo/forgeflow/forgeflow-scenario.md`
section 20 says questions should be prioritized by their ability to change findings, which makes the
order a property of the assessment — and one that two independent implementations, in the review
package and on the command line, would eventually disagree about.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from trace_ai.config import PROJECT_ROOT
from trace_ai.domain.enums import SourceOrigin
from trace_ai.domain.question import (
    Question,
    QuestionPriority,
    QuestionStatus,
    order_for_review,
)

SCENARIO = PROJECT_ROOT / "demo" / "forgeflow" / "forgeflow-scenario.md"

NOW = datetime(2026, 8, 9, 12, 0, tzinfo=UTC)


def question(**changes: Any) -> Question:
    return Question.model_validate(
        {
            "id": "qst-001",
            "assessment_id": "asm-001",
            "question": "Does webhook validation include GitHub HMAC signature verification?",
            "rationale": "Without signature verification the receiver accepts forged deliveries.",
            "priority": QuestionPriority.HIGH,
            "blocking": False,
            "status": QuestionStatus.OPEN,
            "generated_by": "context-extraction-v1",
            **changes,
        }
    )


def scenario_questions() -> list[str]:
    """The ten questions `forgeflow-scenario.md` section 20 expects, parsed from the document."""
    body = SCENARIO.read_text(encoding="utf-8").split("# 20. Expected Questions", 1)[1]
    body = body.split("# 21.", 1)[0]
    return [match.group(1) for match in re.finditer(r"^\d+\.\s+(.+\?)\s*$", body, re.MULTILINE)]


# --------------------------------------------------------------------------------------------
# A question cannot half-exist
# --------------------------------------------------------------------------------------------


def test_blocking_must_be_stated() -> None:
    """Whether the workflow pauses is a property of the question. A default would decide it
    quietly, in whichever direction whoever wrote the default happened to choose."""
    payload = question().model_dump()
    del payload["blocking"]
    with pytest.raises(ValidationError, match="blocking"):
        Question.model_validate(payload)


def test_the_status_vocabulary_is_the_documented_one() -> None:
    assert [status.value for status in QuestionStatus] == ["open", "answered", "dismissed"]


def test_the_priority_vocabulary_is_closed() -> None:
    """Section 22 names the values rather than illustrating them (DEC-036)."""
    assert [priority.value for priority in QuestionPriority] == ["low", "medium", "high"]
    with pytest.raises(ValidationError):
        question(priority="urgent")


@pytest.mark.parametrize("missing", ["response", "response_origin", "answered_at"])
def test_an_answered_question_names_what_is_missing(missing: str) -> None:
    """A half-answered question reads as resolved to anything that checks `status`."""
    answer: dict[str, Any] = {
        "response": "Yes, HMAC verification is enabled.",
        "response_origin": SourceOrigin.USER_RESPONSE,
        "answered_at": NOW,
    }
    answer[missing] = None
    with pytest.raises(ValidationError, match=missing):
        question(status=QuestionStatus.ANSWERED, **answer)


def test_an_unanswered_question_carrying_an_answer_is_rejected() -> None:
    """The other direction: a response with an `open` status is an answer nobody recorded."""
    with pytest.raises(ValidationError, match="response"):
        question(status=QuestionStatus.OPEN, response="Yes")


def test_a_reviewer_answer_carries_the_user_response_origin() -> None:
    answered = question(
        status=QuestionStatus.ANSWERED,
        response="Retention is 30 days; the operations guide is authoritative.",
        response_origin=SourceOrigin.USER_RESPONSE,
        answered_at=NOW,
    )
    assert answered.response_origin is SourceOrigin.USER_RESPONSE


def test_a_dismissed_question_carries_no_answer() -> None:
    assert question(status=QuestionStatus.DISMISSED).response is None


def test_a_related_reference_must_agree_with_its_type() -> None:
    with pytest.raises(ValidationError, match="Component"):
        question(related_object_type="threat", related_object_id="cmp-002")


def test_a_related_reference_may_be_an_identifier_alone() -> None:
    """Section 22 makes both fields optional and independent."""
    assert question(related_object_id="thr-004").related_object_id == "thr-004"


# --------------------------------------------------------------------------------------------
# Ordering
# --------------------------------------------------------------------------------------------


def ordered_sample() -> list[Question]:
    return [
        question(id="qst-001", blocking=False, priority=QuestionPriority.HIGH),
        question(id="qst-002", blocking=True, priority=QuestionPriority.LOW),
        question(id="qst-003", blocking=True, priority=QuestionPriority.HIGH),
        question(id="qst-004", blocking=False, priority=QuestionPriority.LOW),
        question(id="qst-005", blocking=False, priority=QuestionPriority.MEDIUM),
    ]


def test_blocking_questions_come_first_then_priority() -> None:
    """A blocking question stops the workflow, so nothing else can be worked on until it is
    answered. Priority orders the rest."""
    assert [q.id for q in order_for_review(ordered_sample())] == [
        "qst-003",
        "qst-002",
        "qst-001",
        "qst-005",
        "qst-004",
    ]


def test_the_order_is_total_so_two_runs_agree() -> None:
    """The identifier is the final tiebreak. A review package a reviewer compares with yesterday's
    has to list the same questions in the same order."""
    same = [
        question(id="qst-009", blocking=True, priority=QuestionPriority.HIGH),
        question(id="qst-002", blocking=True, priority=QuestionPriority.HIGH),
    ]
    assert [q.id for q in order_for_review(same)] == ["qst-002", "qst-009"]
    assert order_for_review(same) == order_for_review(list(reversed(same)))


def test_answered_and_dismissed_questions_are_not_returned() -> None:
    """A review package asks for decisions, and these two are not being asked about."""
    questions = [
        question(id="qst-001", status=QuestionStatus.DISMISSED),
        question(
            id="qst-002",
            status=QuestionStatus.ANSWERED,
            response="Yes",
            response_origin=SourceOrigin.USER_RESPONSE,
            answered_at=NOW,
        ),
        question(id="qst-003"),
    ]
    assert [q.id for q in order_for_review(questions)] == ["qst-003"]


def test_ordering_an_empty_set_is_not_an_error() -> None:
    """An assessment with no open questions is a normal outcome, not an empty state to guard."""
    assert order_for_review([]) == []


# --------------------------------------------------------------------------------------------
# Against the scenario the demo expects
# --------------------------------------------------------------------------------------------


def test_the_scenario_lists_ten_expected_questions() -> None:
    """Guards the parse below, which would otherwise be vacuous if the heading shape changed."""
    assert len(scenario_questions()) == 10


@pytest.mark.parametrize("text", scenario_questions())
def test_every_expected_forgeflow_question_is_representable(text: str) -> None:
    """The model exercised against the shape the demo expects, rather than against a fixture
    written to fit the model. These ten are what section 20 says a good assessment asks."""
    built = question(question=text, rationale="Section 20 expects this question.")
    assert built.question == text
    assert built.status is QuestionStatus.OPEN
