"""DEC-065: the catalog-gap candidate — routed to the catalog owner, never into conclusions.

Issue #340's acceptance criteria are the spine: a candidate never becomes a `Finding` or a
`DocumentationGap`, and it is persisted and listable for the catalog owner. The first is
structural — the schema carries no finding-shaped field, no report section renders it, and
finding consolidation never reads the type — so the tests assert the shape and scan the one
module where the collapse could happen. The second is the store round-trip, the checkpoint 2
informational block, and `trace assessment candidates`.

The nearest-requirements justification is DEC-065's quality gate, so an empty one is asserted to
be a schema failure rather than a style problem.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from pydantic import ValidationError

from trace_ai.config import PROJECT_ROOT
from trace_ai.domain.base import now
from trace_ai.domain.catalog_gap_candidate import CatalogGapCandidate
from trace_ai.domain.proposals.catalog_gap import (
    CatalogGapCandidateProposal,
    promote_catalog_gap_candidate,
)
from trace_ai.domain.proposals.context_extraction import ProposalError
from trace_ai.domain.proposals.mapping import MappingProposal
from trace_ai.domain.proposals.threat_analysis import ThreatAnalysisProposal
from trace_ai.infrastructure.database.store import AssessmentStore
from trace_ai.services.assessment import AssessmentHandle, AssessmentService

CONSOLIDATION = PROJECT_ROOT / "src" / "trace_ai" / "workflow" / "finding_consolidation.py"
CONVERSIONS = PROJECT_ROOT / "src" / "trace_ai" / "domain" / "conversions.py"


def a_proposal(**changes: Any) -> CatalogGapCandidateProposal:
    payload: dict[str, Any] = {
        "concern": "Webhook events are replayed to exhaust the analysis queue.",
        "suggested_category": "availability",
        "nearest_requirements": [
            {
                "requirement_id": "req-WEBHOOK-001",
                "why_not": "Covers authenticity of a single event, not replay of a valid one.",
            }
        ],
        "evidence_ids": ["evd-001"],
    }
    payload.update(changes)
    return CatalogGapCandidateProposal.model_validate(payload)


@pytest.fixture
def handle(tmp_path: Any) -> Iterator[AssessmentHandle]:
    from trace_ai.domain.assessment import default_configuration

    with AssessmentStore.at_root(tmp_path) as store:
        service = AssessmentService(store, artifact_root=tmp_path)
        created = service.create(
            "Candidates", default_configuration("primary-development", "stride-scenario-based")
        )
        yield service.handle(created.id)


# ------------------------------------------------------------------------------------------
# The shape: no finding-shaped field is representable
# ------------------------------------------------------------------------------------------


def test_an_unjustified_candidate_is_a_schema_failure() -> None:
    """DEC-065's quality gate: an empty nearest-requirements list is refused."""
    with pytest.raises(ValidationError):
        a_proposal(nearest_requirements=[])


def test_an_ungrounded_candidate_is_a_schema_failure() -> None:
    with pytest.raises(ValidationError):
        a_proposal(evidence_ids=[])


def test_a_named_requirement_with_no_reason_is_refused() -> None:
    with pytest.raises(ValidationError):
        a_proposal(nearest_requirements=[{"requirement_id": "req-WEBHOOK-001", "why_not": ""}])


def test_a_finding_shaped_field_is_unrepresentable() -> None:
    """The DEC-009 pressure point, structurally: severity and status fail `extra="forbid"`."""
    for field, value in (
        ("severity", "high"),
        ("validation_status", "supported"),
        ("status", "candidate"),
        ("recommendation", "Fix it."),
    ):
        with pytest.raises(ValidationError):
            a_proposal(**{field: value})
        with pytest.raises(ValidationError):
            CatalogGapCandidate.model_validate(
                {
                    "id": "cgc-001",
                    "assessment_id": "asm-001",
                    "concern": "A concern.",
                    "suggested_category": "availability",
                    "nearest_requirements": [
                        {"requirement_id": "req-WEBHOOK-001", "why_not": "Different ground."}
                    ],
                    "evidence_ids": ["evd-001"],
                    "generated_by": "mapping-v1",
                    "created_at": now(),
                    field: value,
                }
            )


def test_consolidation_and_conversion_never_touch_the_type() -> None:
    """A candidate never becomes a `Finding` or a `DocumentationGap` — checked at the source.

    Finding consolidation is the only module that builds findings and gaps from analysis, and the
    DEC-051 conversions are the only cross-type path. Neither may know the candidate type exists.
    """
    for module in (CONSOLIDATION, CONVERSIONS):
        text = module.read_text(encoding="utf-8")
        assert "CatalogGapCandidate" not in text, (
            f"{module.name} references CatalogGapCandidate; DEC-065 keeps candidates out of "
            f"assessment conclusions"
        )


# ------------------------------------------------------------------------------------------
# Promotion, persistence, and the listing surfaces
# ------------------------------------------------------------------------------------------


def test_a_promoted_candidate_persists_and_lists(handle: AssessmentHandle) -> None:
    proposed = a_proposal()
    with handle.objects.transaction():
        candidate = promote_catalog_gap_candidate(
            proposed,
            candidate_id=handle.objects.allocate("cgc"),
            assessment_id=handle.assessment_id,
            generated_by="mapping-v1",
        )
        handle.objects.save(candidate)

    listed = handle.objects.list(CatalogGapCandidate)
    assert [item.id for item in listed] == ["cgc-001"]
    assert listed[0].concern == proposed.concern
    assert listed[0].nearest_requirements[0].requirement_id == "req-WEBHOOK-001"


def test_the_review_package_shows_candidates_as_informational(handle: AssessmentHandle) -> None:
    from trace_ai.services.evidence.index import EvidenceIndex
    from trace_ai.services.findings.review_package import (
        build_finding_review_package,
        render_markdown,
    )

    with handle.objects.transaction():
        handle.objects.save(
            promote_catalog_gap_candidate(
                a_proposal(),
                candidate_id=handle.objects.allocate("cgc"),
                assessment_id=handle.assessment_id,
                generated_by="mapping-v1",
            )
        )

    package = build_finding_review_package(handle, index=EvidenceIndex(handle))
    assert [candidate.id for candidate in package.catalog_gap_candidates] == ["cgc-001"]
    # Informational only: the summary's counts and subjects are untouched by candidates.
    assert package.summary.finding_count == 0

    rendered = render_markdown(package)
    assert "Catalog-gap candidates (informational — no decision required)" in rendered
    assert "cgc-001" in rendered
    assert "req-WEBHOOK-001" in rendered


def test_the_cli_lists_candidates(tmp_path: Any, capsys: pytest.CaptureFixture[str]) -> None:
    from trace_ai.cli import run

    data_root = tmp_path / "data"
    assert run(["--data-root", str(data_root), "assessment", "create", "--name", "X"]) == 0
    assessment_id = capsys.readouterr().out.strip()

    assert run(["--data-root", str(data_root), "assessment", "candidates", assessment_id]) == 0
    assert "no catalog-gap candidates" in capsys.readouterr().out

    with AssessmentStore.at_root(data_root) as store:
        repository = store.repository(assessment_id)
        with repository.transaction():
            repository.save(
                promote_catalog_gap_candidate(
                    a_proposal(),
                    candidate_id=repository.allocate("cgc"),
                    assessment_id=assessment_id,
                    generated_by="threat-analysis-v1",
                )
            )

    assert run(["--data-root", str(data_root), "assessment", "candidates", assessment_id]) == 0
    output = capsys.readouterr().out
    assert "cgc-001" in output
    assert "None is a finding" in output
    assert "req-WEBHOOK-001" in output


# ------------------------------------------------------------------------------------------
# The agents' proposals carry the channel, reference-checked
# ------------------------------------------------------------------------------------------


def test_a_threat_proposal_checks_candidate_evidence() -> None:
    proposal = ThreatAnalysisProposal.model_validate(
        {"threats": [], "catalog_gap_candidates": [a_proposal().model_dump()]}
    )
    proposal.validate_references({"evd-001"})
    with pytest.raises(ProposalError, match=r"cgc|candidate"):
        proposal.validate_references({"evd-999"})


def test_a_mapping_proposal_checks_candidate_evidence_and_requirements() -> None:
    proposal = MappingProposal.model_validate(
        {"catalog_gap_candidates": [a_proposal().model_dump()]}
    )
    proposal.validate_references({"evd-001", "req-WEBHOOK-001"})
    with pytest.raises(ProposalError):
        proposal.validate_references({"evd-001"})  # the named nearest requirement is unknown
    with pytest.raises(ProposalError):
        proposal.validate_references({"req-WEBHOOK-001"})  # the evidence is unknown


def test_recorded_response_inference_stays_unambiguous() -> None:
    """A recording carrying only candidates must still resolve to exactly one schema.

    Both agents may return candidates, so a response that is *only* candidates matches both
    `ThreatAnalysisProposal` and `MappingProposal` — `parse_recorded_response` must refuse it as
    ambiguous rather than guessing, which is the documented contract for recordings this empty.
    """
    from trace_ai.infrastructure.model.recorded import parse_recorded_response

    only_candidates = '{"catalog_gap_candidates": [' + a_proposal().model_dump_json() + "]}"
    with pytest.raises(ValueError, match="more than one"):
        parse_recorded_response(only_candidates)
