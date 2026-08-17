"""Report section 7's threat filter, the section 11 collapse, and the question clause (#430).

DEC-101: the threats the approved findings rest on render in section 7; byte-identical asks
collapse at render with the duplicate identifier shown; missing-evidence entries interpolate
as clauses rather than sentences.
"""

from __future__ import annotations

from trace_ai.domain.question import Question, QuestionPriority, QuestionStatus
from trace_ai.workflow.finding_consolidation import _as_clause
from trace_ai.workflow.report_rendering import _question_lines


def a_question(identifier: str, text: str, priority: str = "medium") -> Question:
    return Question.model_validate(
        {
            "id": identifier,
            "assessment_id": "asm-001",
            "question": text,
            "rationale": "the documents do not settle it",
            "related_object_type": "threat",
            "related_object_id": "thr-001",
            "priority": QuestionPriority(priority),
            "blocking": False,
            "status": QuestionStatus.OPEN,
            "generated_by": "finding-consolidation-v1",
        }
    )


def test_byte_identical_questions_collapse_onto_the_survivors_line() -> None:
    lines = _question_lines(
        [
            a_question("qst-016", "Which statement is authoritative for req-AI-002?", "high"),
            a_question("qst-017", "Can you confirm the retention period?"),
            a_question("qst-019", "Which statement is authoritative for req-AI-002?", "high"),
        ]
    )
    assert len(lines) == 2
    assert "qst-016" in lines[0]
    assert "*(also asked as qst-019)*" in lines[0]
    assert "qst-017" in lines[1]


def test_distinct_questions_on_one_requirement_both_survive() -> None:
    lines = _question_lines(
        [
            a_question("qst-001", "Is the restriction enforced by network policy?"),
            a_question("qst-002", "Is the restriction enforced at the storage layer?"),
        ]
    )
    assert len(lines) == 2


def test_a_sentence_entry_interpolates_as_a_clause() -> None:
    assert (
        _as_clause(
            "The webhook validation mechanism, specifically whether signature "
            "verification is performed."
        )
        == "the webhook validation mechanism, specifically whether signature "
        "verification is performed"
    )


def test_an_acronym_led_entry_keeps_its_case() -> None:
    assert _as_clause("TLS termination for the current deployment.") == (
        "TLS termination for the current deployment"
    )
