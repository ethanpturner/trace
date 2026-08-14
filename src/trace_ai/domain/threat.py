"""`Threat`: a plausible adverse security scenario, and the vocabulary it is categorised with.

`data-model.md` section 16 is authoritative for the fields. Three things decided about this object
are easier to get wrong than to get right.

**A threat is not a finding.** Section 16 says so in its purpose line and the whole pipeline shape
depends on it: a threat is a scenario worth evaluating, and it becomes a finding only through a
`ControlMapping` and the evidence behind it. Nothing here carries a severity, a verdict, or an
assertion that a control is absent.

**`category` is an open vocabulary** (DEC-041, applying DEC-036). Section 16 types it `list[string]`
and illustrates two values in its example rather than enumerating a set, which is DEC-036's stated
test. `KNOWN_THREAT_CATEGORIES` records the terms the surveyed corpus uses -- STRIDE, the OWASP
LLM lists, the ASI Agentic Top 10, Cumulus's operational suits, and NIST SP 800-30's threat-source
split; it is documentation and validates nothing. The decisive case is ForgeFlow's own THR-001,
prompt injection, which STRIDE has no category for -- a closed STRIDE enum would reject or
mis-bucket the single threat the demo scenario is built around.

**`affected_component_ids`, `affected_asset_ids`, and `impact` are non-empty, and section 16 does
not say so.** `agent-design.md` section 10 does: "Threats do not identify affected assets or
components" and "Threats lack plausible security impact" are named failure conditions for the
Threat Analysis agent. A threat naming nothing it affects cannot be mapped to a requirement, and
one with no impact is a scenario nobody can weigh. The schema refuses both rather than leaving them
for the validation node to notice.
"""

from __future__ import annotations

from datetime import datetime
from typing import Final

from pydantic import Field

from trace_ai.domain.base import DomainModel
from trace_ai.domain.enums import ConfidenceLevel, ObjectStatus
from trace_ai.domain.identifiers import (
    ActorId,
    AssessmentId,
    AssetId,
    ComponentId,
    ContextClaimId,
    DataFlowId,
    EvidenceReferenceId,
    QuestionId,
    ThreatId,
)
from trace_ai.domain.vocabulary import VocabularyTerm, normalize_term

__all__ = [
    "AGENTIC_THREAT_CATEGORIES",
    "AI_THREAT_CATEGORIES",
    "KNOWN_THREAT_CATEGORIES",
    "LLM_2026_THREAT_CATEGORIES",
    "OPERATIONAL_THREAT_CATEGORIES",
    "STRIDE_APPLICABILITY",
    "STRIDE_CATEGORIES",
    "THREAT_SOURCE_CATEGORIES",
    "UNCLASSIFIED_KIND",
    "Threat",
    "classify_element_kind",
]

# STRIDE, in the snake_case spelling section 16's own example uses (`spoofing`,
# `elevation_of_privilege`). `agent-design.md` section 10 calls STRIDE a *coverage aid* and warns
# against producing six generic threats to satisfy each category, so this is a checklist for
# noticing gaps rather than a set of buckets to fill.
STRIDE_CATEGORIES: Final[frozenset[str]] = frozenset(
    {
        "spoofing",
        "tampering",
        "repudiation",
        "information_disclosure",
        "denial_of_service",
        "elevation_of_privilege",
    }
)

# What STRIDE has no category for. `agent-design.md` section 10 requires AI-specific threats "where
# applicable", and ForgeFlow's expected threats include prompt injection, over-disclosure to a model
# provider, and unreviewed model output being published. The names follow OWASP Top 10 for LLM
# Applications 2025, which `requirements/README.md` already adopts as a provenance source:
# LLM01:2025, LLM02:2025, LLM05:2025, LLM10:2025. The year matters: the 2026 release renumbered two
# of the four -- Improper Output Handling is LLM05:2025 but LLM10:2026, and Unbounded Consumption is
# LLM10:2025 but LLM06:2026 -- so a bare "LLM05" or "LLM10" names different risks in adjacent
# releases. The snake_case terms themselves are stable across both.
AI_THREAT_CATEGORIES: Final[frozenset[str]] = frozenset(
    {
        "prompt_injection",
        "sensitive_information_disclosure",
        "improper_output_handling",
        "unbounded_consumption",
    }
)

# The GenAI LLM Top 10 2026 (issue #223, survey item A3), from the year-scoped entry titles at
# https://github.com/GenAI-Security-Project/GenAI-LLM-Top10/tree/main/2026/final. Four terms are
# shared with `AI_THREAT_CATEGORIES` because the titles are stable across the 2025 and 2026
# releases even where the LLMxx numbers moved (see the renumbering note above).
LLM_2026_THREAT_CATEGORIES: Final[frozenset[str]] = frozenset(
    {
        "prompt_injection",
        "sensitive_information_disclosure",
        "excessive_agency",
        "supply_chain",
        "data_and_model_poisoning",
        "unbounded_consumption",
        "misinformation",
        "hidden_context_exposure",
        "vector_and_embedding_weaknesses",
        "improper_output_handling",
    }
)

# The OWASP Top 10 for Agentic Applications (ASI) 2026, ASI01 through ASI10, from the published
# titles ("Agent Goal Hijack", "Memory & Context Poisoning", ...) normalised to one spelling.
# Agentic ground the LLM list treats as a single category (excessive_agency) split out here.
AGENTIC_THREAT_CATEGORIES: Final[frozenset[str]] = frozenset(
    {
        "agent_goal_hijack",
        "tool_misuse_and_exploitation",
        "identity_and_privilege_abuse",
        "agentic_supply_chain_vulnerabilities",
        "unexpected_code_execution",
        "memory_and_context_poisoning",
        "insecure_inter_agent_communication",
        "cascading_failures",
        "human_agent_trust_exploitation",
        "rogue_agents",
    }
)

# OWASP Cumulus's five suits, naming the cloud and DevOps operational ground that neither STRIDE
# nor the LLM lists cover: pipeline delivery, backup and restoration, detection, resource
# configuration, and credential handling.
OPERATIONAL_THREAT_CATEGORIES: Final[frozenset[str]] = frozenset(
    {
        "delivery",
        "recovery",
        "monitoring",
        "resources",
        "access_and_secrets",
    }
)

# NIST SP 800-30's threat-source split, so a non-adversarial threat -- an operator mistake, a
# disk failure, a regional outage -- is recorded as what it is rather than forced into
# adversarial framing. TM-BOM cites the same source for its `sources` field.
THREAT_SOURCE_CATEGORIES: Final[frozenset[str]] = frozenset(
    {
        "adversary",
        "human_error",
        "failure",
        "events_beyond_org_control",
    }
)

# Documentation, not a validation rule (DEC-036, DEC-041). The same relationship
# `acceptable_implementations` has to the requirements catalog, for the same reason: a list of
# examples treated as the set of allowed values decides cases it was never shown. The validation
# node reports a category outside this set as an observation and rejects nothing
# (`workflow/threat_validation.py`).
KNOWN_THREAT_CATEGORIES: Final[frozenset[str]] = (
    STRIDE_CATEGORIES
    | AI_THREAT_CATEGORIES
    | LLM_2026_THREAT_CATEGORIES
    | AGENTIC_THREAT_CATEGORIES
    | OPERATIONAL_THREAT_CATEGORIES
    | THREAT_SOURCE_CATEGORIES
)

# STRIDE-per-element applicability (DEC-063), the Threat Dragon / OdTM convention: a STRIDE
# category applies to an element kind or it does not. Authored data, warn-only — it feeds a
# plausibility observation and a coverage listing, and nothing rejects or retries against it. It
# covers only the STRIDE categories; the open `category` vocabulary (DEC-041) is untouched, and a
# category outside STRIDE is simply not judged here. A trust boundary is where you look rather than
# an element threats attach to, so no category applies to it directly.
STRIDE_APPLICABILITY: Final[dict[str, frozenset[str]]] = {
    "external_actor": frozenset({"spoofing", "repudiation"}),
    "process": STRIDE_CATEGORIES,
    "data_store": frozenset(
        {"tampering", "repudiation", "information_disclosure", "denial_of_service"}
    ),
    "data_flow": frozenset({"tampering", "information_disclosure", "denial_of_service"}),
    "trust_boundary": frozenset(),
}

# The kind a component whose type does not classify is presented as. Never rendered as "no gaps":
# where absence would read as an answer, say it explicitly (DEC-036).
UNCLASSIFIED_KIND: Final = "unclassified"

# A conservative classification from the open `component_type` vocabulary (DEC-041) to a STRIDE
# element kind. Deliberately incomplete: a type it does not name is `unclassified`, which is
# presented as such rather than assumed to have full or no coverage. The kind is a judgment
# compressed into a lookup, which is the stated cost of the checklist being arithmetic.
_TYPE_TO_KIND: Final[dict[str, str]] = {
    "user_interface": "process",
    "service": "process",
    "api_gateway": "process",
    "background_worker": "process",
    "ci_cd_system": "process",
    "administrative_interface": "process",
    "web_application": "process",
    "internal_application": "process",
    "data_store": "data_store",
    "message_queue": "data_store",
    "object_storage": "data_store",
    "secrets_manager": "data_store",
    "managed_database": "data_store",
    "managed_cache": "data_store",
    "managed_storage": "data_store",
    "identity_provider": "external_actor",
    "external_service": "external_actor",
    "repository_provider": "external_actor",
    "managed_security_service": "external_actor",
}


def classify_element_kind(component_type: str) -> str:
    """The STRIDE element kind a component type maps to, or `unclassified` (DEC-063).

    Normalizes the type the DEC-036 way before the lookup, so a spelling the vocabulary would
    fold reaches the same kind. An unrecognised type is `unclassified` — never silently treated as
    covered or uncovered.
    """
    try:
        normalized = normalize_term(component_type)
    except ValueError:
        return UNCLASSIFIED_KIND
    return _TYPE_TO_KIND.get(normalized, UNCLASSIFIED_KIND)


class Threat(DomainModel):
    """A plausible adverse security scenario (section 16). Not a finding."""

    id: ThreatId
    assessment_id: AssessmentId

    title: str = Field(min_length=1)
    description: str = Field(min_length=1)

    methodology: str = Field(min_length=1)
    """How the threat was arrived at, such as `stride-scenario-based`. Free text for the MVP
    (DEC-041): one methodology exists, and a registry with one entry validates nothing."""

    category: list[VocabularyTerm] = Field(default_factory=list)
    """Open vocabulary; see `KNOWN_THREAT_CATEGORIES`. Optional in section 16, and it stays
    optional: an uncategorisable threat is recorded uncategorised rather than forced into a
    category that does not fit."""

    threat_actor_ids: list[ActorId] = Field(default_factory=list)

    affected_component_ids: list[ComponentId] = Field(min_length=1)
    """Non-empty. `agent-design.md` section 10 makes a threat that identifies no affected component
    an invalid output, and an unmapped threat reaches no requirement."""

    affected_asset_ids: list[AssetId] = Field(min_length=1)
    """Non-empty, for the same reason."""

    related_data_flow_ids: list[DataFlowId] = Field(default_factory=list)
    preconditions: list[str] = Field(default_factory=list)
    attack_path: list[str] = Field(default_factory=list)

    impact: str = Field(min_length=1)
    """The security consequence. Non-empty: section 10 makes a threat lacking plausible security
    impact an invalid output. `str_strip_whitespace` on `DomainModel` means whitespace-only text
    arrives empty and is refused here."""

    likelihood: str | None = None
    """Preliminary, and free text. Not a severity: DEC-030 gives severity to the reviewer at
    checkpoint 2, and nothing on this object feeds an automatic one."""

    confidence: ConfidenceLevel
    evidence_ids: list[EvidenceReferenceId] = Field(default_factory=list)

    assumption_ids: list[ContextClaimId] = Field(default_factory=list)
    """Claims the scenario rests on. `ContextClaim` identifiers: an assumption is a claim with
    `status: assumed`, not a separate object."""

    open_question_ids: list[QuestionId] = Field(default_factory=list)

    status: ObjectStatus
    generated_by: str = Field(min_length=1)
    """The agent version or the reviewer, such as `threat-analysis-v1` (`agent-design.md`
    section 33). Not the model name."""

    created_at: datetime
