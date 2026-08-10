"""The permanent regression suite: the false positives that must not come back.

`docs/architecture/evaluation-plan.md` section 11 requires every important bug to become a
permanent regression test and names three by name — password-policy findings generated for OIDC,
ignored inherited encryption, and hallucinated missing MFA. The unusual property of this project is
that its known false positives are known *in advance*:
`demo/forgeflow/forgeflow-scenario.md` section 14 lists five intentional non-findings, section 22
lists eleven claims Trace should not make, and DEC-011 records `common_false_positives` entries
written specifically to suppress them.

Run it deliberately:

    uv run pytest -m evaluation

**Almost all of it runs without a provider key, and that is the design rather than a compromise.**
The suite asserts the *mechanism*, not the outcome of a model call: that the catalog entry which
suppresses a wrong conclusion exists, and that the deterministic rules downgrade or refuse the
wrong conclusion when it is constructed directly. A test that waited for a model to decline to say
something would be measuring the model; these measure whether anything would stop it. The marker
is still `evaluation` because these are benchmark regressions rather than unit tests, and because
`tests/evaluation/test_context_extraction_live.py` sits beside them asking the other question.

**The positives are what stop this suite passing on a broken system.** A suite of negatives passes
perfectly on an assessment that finds nothing at all, which is DEC-011's named risk — over-
suppression — read as a test-design flaw. So every one of scenario section 13's five genuine
weaknesses gets a case asserting it stays *reachable*: given the evidence its condition names, the
deterministic rules do not downgrade it. If a catalog edit made a weakness unreachable, those cases
fail and the negatives would not notice.

**No case asserts a minimum number of anything.** `evaluation-plan.md` section 20 says the goal is
the smallest set of defensible conclusions, and a floor on output count would contradict it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from trace_ai.config import PROJECT_ROOT
from trace_ai.domain.base import now
from trace_ai.domain.control_mapping import (
    ApplicabilityStatus,
    ControlMapping,
    SatisfactionStatus,
)
from trace_ai.domain.enums import ConfidenceLevel, ObjectStatus
from trace_ai.domain.proposals.mapping import MAPPING_AGENT
from trace_ai.domain.requirement import Requirement
from trace_ai.domain.threat import Threat
from trace_ai.services.requirements.loader import load_catalog
from trace_ai.workflow.mapping_validation import (
    UNMET_WITHOUT_ADDRESSING_FALSE_POSITIVES,
    apply_downgrades,
    validate_mappings,
)

pytestmark = pytest.mark.evaluation

EXPECTED = PROJECT_ROOT / "demo" / "forgeflow" / "expected"
CATALOG_VERSION = "0.1"


def load(name: str) -> dict[str, Any]:
    parsed = yaml.safe_load((EXPECTED / name).read_text(encoding="utf-8"))
    assert isinstance(parsed, dict)
    return parsed


MAPPINGS = load("expected-control-mappings.yaml")
REJECTIONS = load("expected-rejections.yaml")

NON_FINDINGS = MAPPINGS["must_not_conclude"]
GENUINE_WEAKNESSES = MAPPINGS["genuine_weaknesses"]
REJECTED_CLAIMS = REJECTIONS["rejections"]


@pytest.fixture(scope="module")
def catalog() -> dict[str, Requirement]:
    return load_catalog(CATALOG_VERSION).by_id()


@pytest.fixture(scope="module")
def requirements() -> list[Requirement]:
    return list(load_catalog(CATALOG_VERSION).requirements)


def a_threat() -> Threat:
    return Threat.model_validate(
        {
            "id": "thr-001",
            "assessment_id": "asm-001",
            "title": "Forged webhooks trigger unauthorized analysis jobs",
            "description": "An attacker submits webhook requests the receiver acts on.",
            "methodology": "stride-scenario-based",
            "affected_component_ids": ["cmp-001"],
            "affected_asset_ids": ["ast-001"],
            "impact": "Unauthorized jobs",
            "confidence": ConfidenceLevel.MEDIUM,
            "status": ObjectStatus.APPROVED,
            "generated_by": "threat-analysis-v1",
            "created_at": now(),
        }
    )


def a_mapping(**changes: Any) -> ControlMapping:
    payload: dict[str, Any] = {
        "id": "map-001",
        "assessment_id": "asm-001",
        "threat_id": "thr-001",
        "requirement_id": "req-WEBHOOK-001",
        "applicability_status": ApplicabilityStatus.APPLICABLE,
        "applicability_reason": "The requirement's first applicable condition holds.",
        "satisfaction_status": SatisfactionStatus.UNVERIFIED,
        "confidence": ConfidenceLevel.MEDIUM,
        "generated_by": MAPPING_AGENT,
        "reviewer_status": ObjectStatus.CANDIDATE,
    }
    payload.update(changes)
    return ControlMapping.model_validate(payload)


def validate(mapping: ControlMapping, requirements: list[Requirement]) -> Any:
    return validate_mappings(
        [mapping],
        catalog_version=CATALOG_VERSION,
        requirements=requirements,
        threats=[a_threat()],
    )


# ------------------------------------------------------------------------------------------
# The five intentional non-findings (scenario section 14)
# ------------------------------------------------------------------------------------------


@pytest.mark.parametrize("case", NON_FINDINGS, ids=lambda c: c["key"])
def test_the_suppressing_mechanism_exists(case: dict[str, Any], catalog: Any) -> None:
    """The mechanism, not the absence. A conclusion missing for no reason is not a pass."""
    requirement = catalog[case["requirement_id"]]

    if case["mechanism"] == "common_false_positives":
        entries = requirement.common_false_positives
    elif case["mechanism"] == "non_applicable_conditions":
        entries = requirement.non_applicable_conditions
    else:
        # `no_evidence` has no catalog entry by construction: nothing supports the claim, and
        # that is the mechanism. The requirement still has to exist for the case to mean
        # anything.
        assert requirement.id == case["requirement_id"]
        return

    normalized = {" ".join(value.split()) for value in entries}
    assert " ".join(case["entry"].split()) in normalized


@pytest.mark.parametrize("case", NON_FINDINGS, ids=lambda c: c["key"])
def test_the_wrong_conclusion_is_stopped_by_that_mechanism(
    case: dict[str, Any], catalog: Any, requirements: list[Requirement]
) -> None:
    """Construct the wrong conclusion directly and assert the rules refuse it.

    This is the assertion a model cannot fake and a prompt edit cannot quietly remove: an
    `unmet` mapping that does not address the requirement's `common_false_positives` entries is
    downgraded to `unverified` and the downgrade is recorded with its reason (DEC-013, DEC-046).
    """
    requirement = catalog[case["requirement_id"]]
    if not requirement.common_false_positives:
        pytest.skip(f"{requirement.id} carries no common_false_positives entries")

    wrong = a_mapping(
        requirement_id=requirement.id,
        satisfaction_status=SatisfactionStatus.UNMET,
        evidence_ids=["evd-001"],
        applicability_reason=case["claim"],
    )

    outcome = validate(wrong, requirements)

    (downgrade,) = outcome.downgrades
    assert downgrade.to_status is SatisfactionStatus.UNVERIFIED
    assert downgrade.reason == UNMET_WITHOUT_ADDRESSING_FALSE_POSITIVES

    (applied,) = apply_downgrades([wrong], outcome)
    assert applied.satisfaction_status is SatisfactionStatus.UNVERIFIED
    assert applied.downgraded_from is SatisfactionStatus.UNMET


@pytest.mark.parametrize("case", NON_FINDINGS, ids=lambda c: c["key"])
def test_every_non_finding_states_what_the_right_answer_is(case: dict[str, Any]) -> None:
    """A case that only says what not to conclude leaves the correct output undefined."""
    assert case["expected_instead"].strip()


def test_all_five_intentional_non_findings_have_a_case() -> None:
    assert len(NON_FINDINGS) == 5


# ------------------------------------------------------------------------------------------
# The eleven rejected claims (scenario section 22)
# ------------------------------------------------------------------------------------------


@pytest.mark.parametrize("case", REJECTED_CLAIMS, ids=lambda c: c["key"])
def test_every_rejected_claim_names_its_mechanism(case: dict[str, Any], catalog: Any) -> None:
    requirement = catalog[case["requirement_id"]]

    if case["mechanism"] == "common_false_positives":
        entries = requirement.common_false_positives
    elif case["mechanism"] == "non_applicable_conditions":
        entries = requirement.non_applicable_conditions
    else:
        assert case["entry"].strip(), case["key"]
        return

    normalized = {" ".join(value.split()) for value in entries}
    assert " ".join(case["entry"].split()) in normalized


def test_all_eleven_rejected_claims_have_a_case() -> None:
    assert len(REJECTED_CLAIMS) == 11


@pytest.mark.parametrize(
    "key, fragment",
    [
        ("REJ-01", "password-complexity"),
        ("REJ-03", "unencrypted"),
        ("REJ-06", "Multi-factor authentication is completely absent"),
    ],
)
def test_the_three_regressions_evaluation_plan_section_11_names(key: str, fragment: str) -> None:
    """OIDC password policy, inherited encryption, hallucinated MFA. Named, so they stay named."""
    case = next(entry for entry in REJECTED_CLAIMS if entry["key"] == key)

    assert fragment in case["claim"]
    assert case["why"].strip()


def test_the_replay_claim_is_rejected_as_a_documentation_gap() -> None:
    """Section 22's own note: the claim a generic review most expects to get wrong (DEC-029)."""
    case = next(entry for entry in REJECTED_CLAIMS if entry["key"] == "REJ-11")

    assert case["mechanism"] == "documentation_gap"
    assert "undocumented" in case["entry"]


# ------------------------------------------------------------------------------------------
# The five genuine weaknesses (scenario section 13) — the half that stops this suite
# passing on a system that finds nothing
# ------------------------------------------------------------------------------------------


def test_all_five_genuine_weaknesses_have_a_case() -> None:
    assert len(GENUINE_WEAKNESSES) == 5


@pytest.mark.parametrize("case", GENUINE_WEAKNESSES, ids=lambda c: c["key"])
def test_the_weakness_requirement_still_exists(case: dict[str, Any], catalog: Any) -> None:
    """A weakness whose requirement was retired stops being reachable silently."""
    assert case["requirement_id"] in catalog


@pytest.mark.parametrize("case", GENUINE_WEAKNESSES, ids=lambda c: c["key"])
def test_the_weakness_remains_reachable(
    case: dict[str, Any], catalog: Any, requirements: list[Requirement]
) -> None:
    """Given evidence that addresses the false positives, `unmet` survives validation.

    DEC-011's tradeoffs name over-suppression as `common_false_positives`'s principal risk, and
    this is where it would show: if a catalog edit made a genuine weakness impossible to
    conclude even with qualifying evidence, this case fails and no negative case would notice.
    """
    requirement = catalog[case["requirement_id"]]
    entry = (
        requirement.common_false_positives[0]
        if requirement.common_false_positives
        else "no false-positive entry applies"
    )

    supported = a_mapping(
        requirement_id=requirement.id,
        satisfaction_status=SatisfactionStatus.UNMET,
        evidence_ids=["evd-001"],
        applicability_reason=(
            f"The requirement applies. The cited passage describes the shortfall directly "
            f"rather than being silent, so the common_false_positives entry '{entry}' does not "
            f"cover this case."
        ),
    )

    outcome = validate(supported, requirements)

    assert not outcome.downgrades, (
        f"{case['key']} is no longer reachable: {[d.reason for d in outcome.downgrades]}"
    )
    assert outcome.valid


@pytest.mark.parametrize("case", GENUINE_WEAKNESSES, ids=lambda c: c["key"])
def test_the_weakness_is_not_reachable_from_silence(
    case: dict[str, Any], catalog: Any, requirements: list[Requirement]
) -> None:
    """The other side of the same rule: the documents as supplied do not carry it there.

    Every genuine weakness in scenario section 13 is recorded as `reachable_at: unverified`,
    because the *supplied* documents establish none of them. That is the correct answer, and it
    is not the same statement as the weakness being unreachable in principle.
    """
    assert case["reachable_at"] == SatisfactionStatus.UNVERIFIED.value
    assert case["evidence_condition"].strip()


# ------------------------------------------------------------------------------------------
# The DEC-025 suppression trail
# ------------------------------------------------------------------------------------------


def test_a_suppression_is_visible_as_suppressed_rather_than_absent(
    catalog: Any, requirements: list[Requirement]
) -> None:
    """DEC-025: a suppression that leaves no trace is invisible to the false-negative rate.

    `evaluation-plan.md` section 8 makes false-negative rate a primary metric, and a catalog
    entry that is too aggressive produces a false negative no metric could attribute if the
    suppression were discarded rather than recorded.
    """
    expected = next(
        applicable
        for entry in MAPPINGS["mappings"]
        for applicable in entry["applicable"]
        if "expected_suppression" in applicable
    )
    requirement = catalog[expected["requirement_id"]]
    trail = expected["expected_suppression"]

    normalized = {" ".join(value.split()) for value in requirement.common_false_positives}
    assert " ".join(trail["suppressed_by"].split()) in normalized

    suppressed = a_mapping(
        requirement_id=requirement.id,
        suppressed_conclusion=trail["suppressed_conclusion"],
        suppressed_by=trail["suppressed_by"],
    )

    outcome = validate(suppressed, requirements)

    (recorded,) = outcome.suppressions
    assert recorded.requirement_id == requirement.id
    assert recorded.conclusion == trail["suppressed_conclusion"]
    # Whitespace-normalized: a YAML folded scalar carries a trailing newline the mapping does
    # not, and the comparison is about the words.
    assert " ".join(recorded.entry.split()) == " ".join(trail["suppressed_by"].split())


def test_the_expected_suppression_is_the_webhook_authenticity_case() -> None:
    """Scenario 15.1: "validated" is not "authenticated", and the catalog says so verbatim."""
    expected = next(
        applicable
        for entry in MAPPINGS["mappings"]
        for applicable in entry["applicable"]
        if "expected_suppression" in applicable
    )

    assert expected["requirement_id"] == "req-WEBHOOK-001"


# ------------------------------------------------------------------------------------------
# What this suite must never become
# ------------------------------------------------------------------------------------------


def test_no_case_asserts_a_minimum_output_count() -> None:
    """`evaluation-plan.md` section 20: the goal is the smallest defensible set, not a floor.

    The forbidden names are assembled rather than written out, because a test scanning its own
    source for a literal finds the literal in its own assertion and fails for the wrong reason.
    """
    text = Path(__file__).read_text(encoding="utf-8")

    for prefix, suffix in (
        ("minimum", "findings"),
        ("at_least_one", "finding"),
        ("minimum", "threats"),
    ):
        assert f"{prefix}_{suffix}" not in text


def test_the_suite_carries_the_evaluation_marker() -> None:
    """`pyproject.toml` deselects it in `addopts`, so a bare `uv run pytest` never runs it."""
    assert pytestmark.name == "evaluation"
