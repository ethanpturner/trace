"""Documentation gaps are checkpoint-2 subjects, and section 9 says which empty state it is.

DEC-159. Before it a gap was proposed and decided nowhere: `DocumentationGap.status` never left
`candidate`, the report's section 9 filtered on `approved` and was therefore structurally empty,
and the deliverable's authored wording stated that the assessment recorded no documentation gaps
while the package held twenty-five. The failure was measured in `docs/eval/exchange.md`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from trace_ai.domain.enums import ObjectStatus, ReviewDisposition, Severity
from trace_ai.infrastructure.database.store import AssessmentStore
from trace_ai.services.assessment import AssessmentHandle, AssessmentService
from trace_ai.workflow.context_review import ReviewerActionError
from trace_ai.workflow.finding_review import (
    approve_documentation_gap,
    edit_documentation_gap,
    reject_documentation_gap,
)

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

    from trace_ai.domain.documentation_gap import DocumentationGap


def _gap(
    handle: AssessmentHandle, *, title: str = "Retention of embeddings is undocumented"
) -> DocumentationGap:
    from trace_ai.domain.documentation_gap import DocumentationGap as Gap

    with handle.objects.transaction() as tx:
        identifier = tx.allocate("gap")
        gap = Gap.model_validate(
            {
                "id": identifier,
                "assessment_id": handle.assessment_id,
                "title": title,
                "description": "The documents do not state how long embeddings are retained.",
                "importance": "Retention bounds the exposure of a compromised index.",
                "severity": Severity.MEDIUM,
                "status": ObjectStatus.CANDIDATE,
                "generated_by": "test",
            }
        )
        tx.save(gap)
    return gap


@pytest.fixture
def handle(tmp_path: Path) -> Iterator[AssessmentHandle]:
    from trace_ai.domain.assessment import default_configuration

    with AssessmentStore.at_root(tmp_path) as store:
        service = AssessmentService(store, artifact_root=tmp_path)
        created = service.create(
            "Gap decisions",
            default_configuration("primary-development", "stride-scenario-based"),
        )
        yield service.handle(created.id)


def test_approving_a_gap_is_the_only_path_to_approved(handle: AssessmentHandle) -> None:
    """The status a report section 9 filters on is reachable, which before DEC-159 it was not."""
    gap = _gap(handle)
    assert gap.status is ObjectStatus.CANDIDATE

    decided, decision = approve_documentation_gap(
        handle, gap, reviewer_id="reviewer-local", rationale="The silence is real."
    )
    assert decided.status is ObjectStatus.APPROVED
    assert decision.subject_type == "documentation_gap"
    assert decision.subject_id == gap.id
    assert decision.disposition is ReviewDisposition.APPROVE


def test_rejecting_a_gap_retains_it(handle: AssessmentHandle) -> None:
    """A rejected gap is kept, not deleted — the disposition is the record (section 18)."""
    gap = _gap(handle)
    decided, decision = reject_documentation_gap(
        handle, gap, reviewer_id="reviewer-local", rationale="The overview does state it."
    )
    assert decided.status is ObjectStatus.REJECTED
    assert decision.disposition is ReviewDisposition.REJECT
    from trace_ai.domain.documentation_gap import DocumentationGap

    assert [item.id for item in handle.objects.list(DocumentationGap)] == [gap.id]


def test_a_decided_gap_refuses_a_second_decision(handle: AssessmentHandle) -> None:
    """The structural mirror of the merged-finding refusal in `approve_finding`."""
    gap = _gap(handle)
    decided, _ = reject_documentation_gap(handle, gap, reviewer_id="reviewer-local")
    with pytest.raises(ReviewerActionError, match="not a candidate"):
        approve_documentation_gap(handle, decided, reviewer_id="reviewer-local")


def test_an_edit_records_the_delta_and_does_not_decide(handle: AssessmentHandle) -> None:
    """DEC-023's shape: the new object is built through the schema and the decision carries both
    sides. An edit is not a decision, so the gap stays a candidate and the checkpoint still waits."""
    gap = _gap(handle)
    updated, decision = edit_documentation_gap(
        handle,
        gap,
        {"importance": "Retention bounds exposure, and the index is customer-visible."},
        reviewer_id="reviewer-local",
    )
    assert updated.status is ObjectStatus.CANDIDATE
    assert decision.disposition is ReviewDisposition.EDIT
    assert decision.prior_value == {"importance": gap.importance}
    assert decision.updated_value == {"importance": updated.importance}


def test_an_uneditable_field_is_refused(handle: AssessmentHandle) -> None:
    """Status, provenance, and the identifier are the application's, not the reviewer's."""
    gap = _gap(handle)
    with pytest.raises(ReviewerActionError, match="not editable"):
        edit_documentation_gap(handle, gap, {"severity": "high"}, reviewer_id="reviewer-local")


def test_the_template_carries_both_empty_states() -> None:
    """Section 9 has two empty states and they say different things (DEC-159).

    "Nothing was proposed" and "everything proposed was rejected" are both empty tables. Reporting
    the first while the second is true states an absence nobody established, which is what the
    exchange runs measured.
    """
    from trace_ai.config import PROJECT_ROOT

    text = (PROJECT_ROOT / "templates" / "report-v1.md").read_text(encoding="utf-8")
    assert "<!-- empty.documentation_gaps -->" in text
    assert "<!-- empty.documentation_gaps_none_approved -->" in text
    none_approved = text.split("<!-- empty.documentation_gaps_none_approved -->", 1)[1].split(
        "<!--", 1
    )[0]
    assert "approved none of them" in none_approved
    assert "not because nothing was proposed" in none_approved


def test_the_renderer_picks_the_none_approved_wording() -> None:
    """The selection is the renderer's, from the count the assembler carries."""
    import inspect

    from trace_ai.workflow import report_rendering

    source = inspect.getsource(report_rendering)
    assert "proposed_documentation_gap_count" in source
    assert "documentation_gaps_none_approved" in source
