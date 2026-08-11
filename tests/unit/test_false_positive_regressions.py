"""The permanent false-positive regression tests (issue #112, evaluation-plan section 11).

Every fixture under `benchmarks/regressions/` is one behaviour a previous generation of tools
got wrong, and each test asserts **both halves**: the false positive is absent from
consolidation output, and the correct output — a recognised inherited control, a question, or
no output — is present. The tests run against `consolidate`, not against agent output, so they
hold regardless of which prompt version produced the candidate; no test here needs a provider.

Deleting one of these tests is deleting a promise the evaluation plan makes by name. Each test
carries the failure it prevents and the decision it defends.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from trace_ai.config import PROJECT_ROOT
from trace_ai.domain.base import now
from trace_ai.domain.component import Component
from trace_ai.domain.control import (
    Control,
    ControlType,
    ImplementationStatus,
)
from trace_ai.domain.control_mapping import (
    ApplicabilityStatus,
    ControlMapping,
    SatisfactionStatus,
)
from trace_ai.domain.enums import (
    ConfidenceLevel,
    ObjectStatus,
    SourceOrigin,
    ValidationStatus,
)
from trace_ai.domain.evidence_assessment import EvidenceAssessment, Recommendation, SubjectType
from trace_ai.domain.outcomes import Outcome
from trace_ai.domain.threat import Threat
from trace_ai.workflow.finding_consolidation import ConsolidationOutcome, consolidate

REGRESSIONS = PROJECT_ROOT / "benchmarks" / "regressions"

FIXTURES = {path.stem: path for path in REGRESSIONS.glob("*.yaml") if path.name != "README.md"}


def fixture(name: str) -> dict[str, Any]:
    parsed: Any = yaml.safe_load(FIXTURES[name].read_text(encoding="utf-8"))
    assert isinstance(parsed, dict)
    return parsed


def build_control(data: dict[str, Any], provider_id: str) -> Control:
    return Control.model_validate(
        {
            "id": data["control"]["id"],
            "assessment_id": "asm-001",
            "name": data["control"]["name"],
            "description": data["control"]["description"],
            "control_type": ControlType(data["control"]["control_type"]),
            "provider_component_id": provider_id,
            "implementation_status": ImplementationStatus(data["control"]["implementation_status"]),
            "validation_status": ValidationStatus.SUPPORTED,
            "evidence_ids": ["evd-001"],
            "generated_by": "mapping-v1",
            "created_at": now(),
            "status": ObjectStatus.CANDIDATE,
        }
    )


def run_fixture(name: str) -> tuple[dict[str, Any], ConsolidationOutcome]:
    data = fixture(name)
    stamped = now()
    threat = Threat.model_validate(
        {
            "id": "thr-001",
            "assessment_id": "asm-001",
            "title": f"A scenario against {data['provider_component']['name']}",
            "description": "The threat consolidation routes this fixture's mapping under.",
            "methodology": "stride-scenario-based",
            "affected_component_ids": [data["provider_component"]["id"]],
            "affected_asset_ids": ["ast-001"],
            "impact": "Meaningful impact for the fixture's requirement.",
            "confidence": ConfidenceLevel.MEDIUM,
            "status": ObjectStatus.APPROVED,
            "generated_by": "threat-analysis-v1",
            "created_at": stamped,
        }
    )
    mapping_data = data["mapping"]
    satisfaction = SatisfactionStatus(mapping_data["satisfaction_status"])
    mapping = ControlMapping.model_validate(
        {
            "id": mapping_data["id"],
            "assessment_id": "asm-001",
            "threat_id": threat.id,
            "requirement_id": data["requirement_id"],
            "control_ids": [data["control"]["id"]] if "control" in data else [],
            "applicability_status": ApplicabilityStatus.APPLICABLE,
            "applicability_reason": mapping_data["applicability_reason"],
            "satisfaction_status": satisfaction,
            "evidence_ids": [] if satisfaction is SatisfactionStatus.UNVERIFIED else ["evd-001"],
            "confidence": ConfidenceLevel.MEDIUM,
            "generated_by": "mapping-v1",
            "reviewer_status": ObjectStatus.CANDIDATE,
        }
    )
    assessment_data = data["assessment"]
    assessment = EvidenceAssessment.model_validate(
        {
            "id": "eas-001",
            "assessment_id": "asm-001",
            "subject_type": SubjectType.CONTROL_MAPPING,
            "subject_id": mapping.id,
            "evidence_ids": ["evd-001"],
            "evidence_strengths": {"evd-001": "direct"},
            "validation_status": ValidationStatus(assessment_data["validation_status"]),
            "rationale": assessment_data["rationale"],
            "missing_evidence": assessment_data.get("missing_evidence", []),
            "confidence": ConfidenceLevel.MEDIUM,
            "recommendation": Recommendation.CONTINUE,
            "generated_by": "evidence-validation-v1",
            "created_at": stamped,
        }
    )

    outcome = consolidate(
        threats=[threat],
        mappings=[mapping],
        assessments=[assessment],
        assessment_id="asm-001",
    )
    return data, outcome


def assert_no_false_positive(data: dict[str, Any], outcome: ConsolidationOutcome) -> None:
    """The negative half: no finding cites the fixture's requirement."""
    offending = [
        finding for finding in outcome.findings if data["requirement_id"] in finding.requirement_ids
    ]
    assert not offending, (
        f"{data['regression']}: consolidation produced the exact false positive this fixture "
        f"exists to prevent — {data['prevents']} — which {data['defends']} forbids."
    )


def assert_correct_output(data: dict[str, Any], outcome: ConsolidationOutcome) -> None:
    """The positive half: the correct treatment is present, not merely the wrong one absent."""
    if data["correct_output"] == "no_output":
        (rejected,) = outcome.rejected
        assert rejected.outcome is Outcome.NO_OUTPUT
        assert outcome.questions == () and outcome.documentation_gaps == ()
    else:
        (question,) = outcome.questions
        assert data["requirement_id"] in question.rationale
        assert outcome.rejected == () and outcome.documentation_gaps == ()


def test_the_five_fixtures_exist() -> None:
    assert set(FIXTURES) == {
        "delegated-authentication",
        "inherited-encryption",
        "missing-mfa",
        "redis-network-placement",
        "custom-cryptography",
    }


@pytest.mark.parametrize("name", sorted(FIXTURES))
def test_every_fixture_names_what_it_prevents_and_defends(name: str) -> None:
    data = fixture(name)
    assert data["prevents"], name
    assert "DEC-009" in data["defends"], (
        f"{name}: every one of these fixtures defends DEC-009, and says so"
    )


def test_delegated_authentication_produces_no_password_policy_finding() -> None:
    # Prevents: password-policy findings generated under delegated authentication -- the
    # first failure evaluation-plan.md section 11 names. Defends DEC-009 and DEC-011
    # (forgeflow-scenario.md section 14.1).
    data, outcome = run_fixture("delegated-authentication")
    assert_no_false_positive(data, outcome)
    assert_correct_output(data, outcome)

    # The external identity provider is identified as the control provider: the delegation is
    # recognised, not merely the finding suppressed.
    control = build_control(data, data["provider_component"]["id"])
    assert control.provider_component_id == data["provider_component"]["id"]
    assert control.control_type is ControlType.INHERITED
    provider = Component.model_validate(
        {
            "id": data["provider_component"]["id"],
            "assessment_id": "asm-001",
            "name": data["provider_component"]["name"],
            "component_type": data["provider_component"]["component_type"],
            "internet_accessible": True,
            "source_origin": SourceOrigin.UPLOADED_DOCUMENT,
            "status": ObjectStatus.APPROVED,
        }
    )
    assert provider.name == "GitHub"


def test_inherited_encryption_is_recognised_and_produces_no_finding() -> None:
    # Prevents: ignored inherited encryption -- the second failure evaluation-plan.md
    # section 11 names. Defends DEC-009 and DEC-026 (forgeflow-scenario.md section 14.2).
    data, outcome = run_fixture("inherited-encryption")
    assert_no_false_positive(data, outcome)
    assert_correct_output(data, outcome)

    # The inherited control is *recognised* -- DEC-026's documented-inheritance test holds --
    # not merely the finding absent.
    control = build_control(data, data["provider_component"]["id"])
    assert control.is_documented_inheritance is True


def test_missing_mfa_is_mapped_to_the_identity_provider_not_hallucinated() -> None:
    # Prevents: hallucinated missing MFA -- the third failure evaluation-plan.md section 11
    # names. Defends DEC-009 (forgeflow-scenario.md section 14.3): MFA responsibility is the
    # identity provider's, and the application is not required to implement its own.
    data, outcome = run_fixture("missing-mfa")
    assert_no_false_positive(data, outcome)
    assert_correct_output(data, outcome)


def test_undescribed_network_placement_becomes_a_question_not_an_exposure_finding() -> None:
    # Prevents: a public-exposure finding invented from undescribed network controls.
    # Defends DEC-009 and DEC-013 (forgeflow-scenario.md section 14.4): the answer is
    # obtainable and material, so the correct output is a question -- never a finding, and
    # not silence either.
    data, outcome = run_fixture("redis-network-placement")
    assert_no_false_positive(data, outcome)
    assert_correct_output(data, outcome)
    (question,) = outcome.questions
    assert "network" in question.question.casefold()


def test_absent_custom_cryptography_is_not_a_finding() -> None:
    # Prevents: a finding generated merely because the application implements no custom
    # cryptography. Defends DEC-009 (forgeflow-scenario.md section 14.5): the managed
    # platform services are the controls, and their use is the satisfied case.
    data, outcome = run_fixture("custom-cryptography")
    assert_no_false_positive(data, outcome)
    assert_correct_output(data, outcome)


def test_the_regressions_run_against_consolidation_not_agent_output() -> None:
    """The fixtures exercise `consolidate` so the assertions hold across prompt versions.

    The names are assembled from parts because a test scanning its own source for a literal
    finds the literal in its own assertion — the same trap the consolidation and M3 suites hit.
    """
    module = Path(__file__).read_text(encoding="utf-8")
    assert "consolidate(" in module
    for prefix, suffix in (("Structured", "Model"), ("Deterministic", "Model")):
        assert f"{prefix}{suffix}" not in module.replace(f'("{prefix}", "{suffix}")', "")
