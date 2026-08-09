"""The ForgeFlow context fixture: the expected file, and the five cases it exists to pin.

Two halves.

**The expected file.** `demo/forgeflow/expected/expected-context.yaml` is benchmark truth for
context extraction. It is data, not code, and the failure it is prone to is drift — a field renamed
in `data-model.md`, a section retitled in an input document, a citation that stops resolving. None
of that would break anything until the evaluation harness ran, which is Stage 5. The tests below
check it now: every key is a real field of the corresponding domain model, every citation names a
passage that exists, and every reference resolves.

They also check the property the file is most at risk of losing. `forgeflow-scenario.md` sections
5, 7, 8, 10, and 11 enumerate the system as its author knows it, and the input documents describe
it as its documentation records it. Grading against the former rewards invention, which is DEC-009
with its sign flipped — so the expected file must contain nothing the inputs do not support, and
must itself obey the evidence rules it grades against.

**The five cases.** `agent-design.md` section 31 requires each agent be tested independently before
it is connected to the full workflow, and names the cases. These are the five that belong to
context: two intentional non-findings, one intentional ambiguity, one intentional contradiction,
and one three-valued field that must not be collapsed. Each runs the real node against
`DeterministicModel` with a recorded response — no API key, no network, no cost.

A recorded response only proves what the application does with it, which is the point: the cases
assert the *handling*, not the model. Where the machinery can catch the wrong answer, the case
asserts that too, so the pin is on something stronger than a fixture agreeing with itself.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
import yaml

from trace_ai.config import PROJECT_ROOT
from trace_ai.domain.actor import Actor
from trace_ai.domain.assessment import default_configuration
from trace_ai.domain.asset import Asset
from trace_ai.domain.base import DomainModel
from trace_ai.domain.component import Component
from trace_ai.domain.context_claim import ClaimStatus, ContextClaim
from trace_ai.domain.data_flow import DataFlow, FlowDirection
from trace_ai.domain.enums import ConfidenceLevel, SourceOrigin
from trace_ai.domain.evidence import EvidenceReference
from trace_ai.domain.proposals import ContextExtractionProposal
from trace_ai.domain.question import Question, QuestionPriority
from trace_ai.domain.source_document import SourceDocument, TrustLevel
from trace_ai.domain.source_observation import (
    ObservationKind,
    SourceObservation,
    unsupported_contradictions,
)
from trace_ai.domain.system_context import SystemContext
from trace_ai.domain.trust_boundary import TrustBoundary
from trace_ai.infrastructure.database.store import AssessmentStore
from trace_ai.infrastructure.model import DeterministicModel, ModelUsage
from trace_ai.infrastructure.model.profiles import resolve_profile
from trace_ai.services.assessment import AssessmentHandle, AssessmentService
from trace_ai.services.evidence.index import EvidenceIndex
from trace_ai.services.evidence.indexing import index_document
from trace_ai.services.execution_ledger import ExecutionLedger, start_run
from trace_ai.services.ingestion.loader import DocumentLoader
from trace_ai.services.prompts import PromptRegistry
from trace_ai.workflow.context_extraction import ContextExtractionNode
from trace_ai.workflow.context_validation import validate_context
from trace_ai.workflow.nodes import NodeContext
from trace_ai.workflow.state import AssessmentState

FORGEFLOW = PROJECT_ROOT / "demo" / "forgeflow"
INPUT_DIR = FORGEFLOW / "input"
EXPECTED = FORGEFLOW / "expected" / "expected-context.yaml"
PROFILE = resolve_profile("primary-development")

# Which section of the expected file holds which domain object type. `data-model.md` sections 9 to
# 15 are authoritative for the fields; this maps the file's plural section names onto them.
SECTION_MODELS: dict[str, type[DomainModel]] = {
    "components": Component,
    "actors": Actor,
    "assets": Asset,
    "data_flows": DataFlow,
    "trust_boundaries": TrustBoundary,
    "context_claims": ContextClaim,
}

# Fields the expected file renames because it cannot carry an identifier: DEC-018 allocates them
# at insert, so a generated identifier means nothing across runs. Each maps a key the file uses to
# the domain field it stands in for, and the file's header states the same table.
SUBSTITUTIONS: dict[str, str] = {
    "evidence": "evidence_ids",
    "components": "component_ids",
    "source_component": "source_component_id",
    "destination_component": "destination_component_id",
    "crosses_trust_boundaries": "crosses_trust_boundary_ids",
    "inside_components": "inside_component_ids",
    "outside_components": "outside_component_ids",
    "subject": "subject_id",
}

# Fields the application owns and no expected file may state: identifiers, statuses that record
# where an object is in the workflow, provenance, and timestamps.
APPLICATION_OWNED = frozenset(
    {"id", "assessment_id", "created_at", "updated_at", "generated_by", "supersedes_id", "version"}
)

USAGE = ModelUsage(
    model="claude-opus-5",
    input_tokens=12_000,
    output_tokens=1_500,
    estimated_cost=Decimal("0.0975"),
)


def expected() -> dict[str, Any]:
    loaded: Any = yaml.safe_load(EXPECTED.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def entries(section: str) -> list[dict[str, Any]]:
    found: Any = expected()[section]
    assert isinstance(found, list)
    return found


def headings(document: Path) -> set[str]:
    """Every Markdown heading title in a document, or every top-level key in a YAML one."""
    if document.suffix == ".yaml":
        loaded: Any = yaml.safe_load(document.read_text(encoding="utf-8"))
        return set(loaded) if isinstance(loaded, dict) else set()
    return {
        line.lstrip("#").strip()
        for line in document.read_text(encoding="utf-8").splitlines()
        if line.startswith("#")
    }


def citations() -> list[tuple[str, str, dict[str, Any]]]:
    """Every `evidence` entry in the file, with the section it came from."""
    found: list[tuple[str, str, dict[str, Any]]] = []
    document = expected()
    for section in ("system_context", *SECTION_MODELS):
        block = document[section]
        items = [block] if isinstance(block, dict) else block
        for item in items:
            label = str(item.get("name") or item.get("subject") or item.get("predicate") or section)
            for citation in item.get("evidence", []):
                found.append((section, label, citation))
    return found


# ------------------------------------------------------------------------------------------
# The expected file
# ------------------------------------------------------------------------------------------


def test_the_expected_file_exists_and_parses() -> None:
    assert EXPECTED.is_file()
    document = expected()
    assert document["benchmark_version"] == "1.0"
    assert document["scenario"] == "forgeflow"
    assert document["catalog_version"] == "0.1", (
        "the expected file pins the catalog version it was authored against, as the evaluation "
        "contract does (DEC-027)"
    )


def test_the_expected_file_holds_only_context_sections() -> None:
    """Questions, observations, threats, findings, and control mappings have their own files under
    DEC-027's derived list. Recording the same fact in two files makes one of them wrong the first
    time either changes."""
    assert set(expected()) == {
        "benchmark_version",
        "scenario",
        "catalog_version",
        "matching",
        "system_context",
        *SECTION_MODELS,
    }


@pytest.mark.parametrize("section", sorted(SECTION_MODELS))
def test_every_key_in_every_entry_is_a_real_domain_field(section: str) -> None:
    """`data-model.md` is authoritative and `test_data_model_conformance.py` enforces it against
    the code. This enforces it against the benchmark truth, in the same direction: a field the
    expected file invents would sit here looking authoritative and grade nothing."""
    model = SECTION_MODELS[section]
    fields = set(model.model_fields)
    offenders: list[str] = []
    for entry in entries(section):
        for key in entry:
            resolved = SUBSTITUTIONS.get(key, key)
            if resolved not in fields:
                offenders.append(f"{section}[{entry.get('name', entry.get('predicate'))}].{key}")
    assert not offenders, f"{offenders} are not fields of {model.__name__}"


def test_the_system_context_entry_matches_its_model() -> None:
    """One exception, and it is the only one in the file.

    `SystemContext` holds identifier lists and carries no `evidence_ids` of its own — the claims
    do. The entry cites its sources anyway, because `system_purpose` and `business_criticality` are
    authored prose and the file's whole discipline is that every line of it can be traced to an
    input document. The citation is checked like every other one; it simply grades nothing.
    """
    fields = set(SystemContext.model_fields) | {"evidence_ids"}
    keys = {SUBSTITUTIONS.get(key, key) for key in expected()["system_context"]}
    assert keys <= fields


@pytest.mark.parametrize("section", sorted(SECTION_MODELS))
def test_no_entry_states_a_field_the_application_owns(section: str) -> None:
    """An expected file that carried `id` would be asserting a number DEC-018 mints at insert, and
    `status` on a produced object records where it is in the workflow rather than what it is.
    `ContextClaim.status` is the exception and is genuinely part of the truth: whether a claim is
    documented, unknown, or contradicted is the thing being graded."""
    owned = APPLICATION_OWNED if section == "context_claims" else APPLICATION_OWNED | {"status"}
    offenders = sorted({key for entry in entries(section) for key in entry if key in owned})
    assert not offenders, f"{section} states application-owned field(s) {offenders}"


def test_the_file_carries_no_generated_identifiers() -> None:
    """DEC-018 identifiers are scoped to a run and carry no meaning across them. One appearing here
    would be matched against and would never match."""
    text = EXPECTED.read_text(encoding="utf-8")
    found = sorted(set(re.findall(r"\b(?:cmp|act|ast|dfl|tbd|ctx|qst|obs|evd)-\d{3,}\b", text)))
    assert not found, f"{found} are generated identifiers; the file matches on names instead"


def test_every_claim_status_and_confidence_is_a_real_enum_member() -> None:
    for entry in entries("context_claims"):
        assert entry["status"] in set(ClaimStatus), entry["predicate"]
        assert entry["confidence"] in set(ConfidenceLevel), entry["predicate"]


def test_every_data_flow_direction_is_a_real_enum_member() -> None:
    for entry in entries("data_flows"):
        assert entry["direction"] in set(FlowDirection), entry["name"]


def test_the_expected_file_obeys_the_evidence_rule_it_grades_against() -> None:
    """A `documented` or `inferred` claim cites evidence; an `unknown` or `assumed` one carries a
    rationale instead. The file is graded against these rules and would be incoherent breaking
    them — an expected `documented` claim with nothing behind it is the DEC-009 failure written
    into the answer key."""
    for entry in entries("context_claims"):
        status, label = entry["status"], entry["predicate"]
        if status in {ClaimStatus.DOCUMENTED, ClaimStatus.INFERRED}:
            assert entry.get("evidence"), f"{label} is {status} and cites nothing"
        if status in {ClaimStatus.UNKNOWN, ClaimStatus.ASSUMED}:
            assert entry.get("rationale"), f"{label} is {status} and carries no rationale"
            assert entry.get("value") is None, (
                f"{label} is {status} and states a value; a claim the documentation does not "
                f"settle has no value to state"
            )


def test_no_expected_claim_asserts_absence_from_silence() -> None:
    """DEC-009 at the level of the answer key. A `false` value is allowed only where a document
    states it — every one below cites the sentence that does."""
    for entry in entries("context_claims"):
        if entry.get("value") is False:
            assert entry["status"] == ClaimStatus.DOCUMENTED
            assert entry.get("evidence"), f"{entry['predicate']} asserts false and cites nothing"


@pytest.mark.parametrize(
    ("section", "label", "citation"),
    [(section, label, citation) for section, label, citation in citations()],
    ids=[f"{section}:{label}" for section, label, _ in citations()],
)
def test_every_citation_resolves_to_a_passage_that_exists(
    section: str, label: str, citation: dict[str, Any]
) -> None:
    """A citation naming a section that was retitled resolves to nothing and grades nothing, and
    nobody would notice until Stage 5."""
    document = INPUT_DIR / str(citation["document"])
    assert document.is_file(), f"{section}:{label} cites {citation['document']}, which is not input"
    assert str(citation["section"]) in headings(document), (
        f"{section}:{label} cites {citation['document']} section {citation['section']!r}, which "
        f"that document does not contain"
    )


def test_every_referenced_component_name_is_a_component_the_file_lists() -> None:
    names = {entry["name"] for entry in entries("components")}
    dangling: list[str] = []
    for section, keys in (
        ("assets", ("components",)),
        ("data_flows", ("source_component", "destination_component")),
        ("trust_boundaries", ("inside_components", "outside_components")),
    ):
        for entry in entries(section):
            for key in keys:
                value = entry.get(key)
                referenced = [value] if isinstance(value, str) else list(value or [])
                dangling += [
                    f"{section}[{entry['name']}].{key}={name}"
                    for name in referenced
                    if name not in names
                ]
    assert not dangling, f"{dangling} name components the file does not list"


def test_every_crossed_boundary_is_a_boundary_the_file_lists() -> None:
    names = {entry["name"] for entry in entries("trust_boundaries")}
    dangling = [
        f"{entry['name']} crosses {crossed}"
        for entry in entries("data_flows")
        for crossed in entry.get("crosses_trust_boundaries", [])
        if crossed not in names
    ]
    assert not dangling, f"{dangling} name trust boundaries the file does not list"


def test_every_claim_subject_resolves() -> None:
    """A claim's subject is a component, an actor, an asset, or the system itself."""
    subjects = {"system"} | {
        entry["name"]
        for section in ("components", "actors", "assets")
        for entry in entries(section)
    }
    dangling = [
        f"{entry['predicate']} is about {entry['subject']}"
        for entry in entries("context_claims")
        if entry["subject"] not in subjects
    ]
    assert not dangling, f"{dangling} name objects the file does not list"


def test_no_data_flow_reads_an_undocumented_value_as_false() -> None:
    """`data-model.md` section 14: unknown transport security is `unknown`, never `false`. The
    expected file says `unknown` eleven times, and every one of them is a place a generic reviewer
    would have written "not encrypted"."""
    for entry in entries("data_flows"):
        for field in ("authentication", "encryption_in_transit"):
            assert entry.get(field) not in {False, "false", "none", "no", "absent"}, entry["name"]


# ------------------------------------------------------------------------------------------
# The node harness for the five cases
# ------------------------------------------------------------------------------------------


@pytest.fixture
def prepared(tmp_path: Path) -> Iterator[tuple[AssessmentHandle, ExecutionLedger]]:
    """An assessment with the ForgeFlow documents the five cases quote, indexed, and a run open."""
    with AssessmentStore.at_root(tmp_path) as store:
        service = AssessmentService(store, artifact_root=tmp_path)
        created = service.create(
            "ForgeFlow", default_configuration("primary-development", "stride-scenario-based")
        )
        handle = service.handle(created.id)
        loader = DocumentLoader(handle)
        for name in (
            "architecture-overview.md",
            "security-overview.md",
            "operations-guide.md",
            "product-overview.md",
            "github-integration.md",
        ):
            index_document(
                handle,
                loader.load_document(
                    INPUT_DIR / name,
                    origin=SourceOrigin.UPLOADED_DOCUMENT,
                    trust_level=TrustLevel.UNTRUSTED,
                ),
            )
        run = start_run(handle, workflow_version="0.1", model_profile="primary-development")
        yield handle, ExecutionLedger(handle, run)


class Usable(DeterministicModel):
    """The fake, with usage attached so the ledger has something to record."""

    def generate(self, **kwargs: Any) -> Any:
        outcome = super().generate(**kwargs)
        if hasattr(outcome, "usage") and outcome.usage.input_tokens == 0:
            return type(outcome)(
                **{**{f: getattr(outcome, f) for f in outcome.__slots__}, "usage": USAGE}
            )
        return outcome


def evidence_ids(handle: AssessmentHandle) -> list[str]:
    return sorted(reference.id for reference in handle.objects.list(EvidenceReference))


def cite(handle: AssessmentHandle, document: str, section: str) -> str:
    """The evidence identifier for one passage, looked up the way a grader would."""
    documents = {source.id: source.filename for source in handle.objects.list(SourceDocument)}
    matches = [
        reference.id
        for reference in handle.objects.list(EvidenceReference)
        if documents.get(reference.source_document_id) == document
        and (reference.section_title or "") == section
    ]
    assert matches, f"{document} has no indexed passage titled {section!r}"
    return matches[0]


def node(
    handle: AssessmentHandle, ledger: ExecutionLedger, **changes: Any
) -> ContextExtractionNode:
    options: dict[str, Any] = {
        "ledger": ledger,
        "index": EvidenceIndex(handle),
        "profile": PROFILE,
        "registry": PromptRegistry(),
        "evidence_ids": evidence_ids(handle),
        "assessment_name": "ForgeFlow",
        **changes,
    }
    return ContextExtractionNode(**options)


def context_for(handle: AssessmentHandle, ledger: ExecutionLedger, model: Any) -> NodeContext:
    return NodeContext(
        handle=handle,
        state=AssessmentState.begin(
            assessment_id=handle.assessment_id, workflow_run_id=ledger.run.id
        ),
        model=model,
    )


def run_with(handle: AssessmentHandle, ledger: ExecutionLedger, payload: dict[str, Any]) -> Usable:
    """Record one response, run the real node against it, and hand back the fake for inspection."""
    model = Usable([ContextExtractionProposal.model_validate(payload)])
    node(handle, ledger).run(context_for(handle, ledger, model))
    return model


def validate_persisted(handle: AssessmentHandle) -> Any:
    """Run the validation node over everything the extraction persisted."""
    (context,) = handle.objects.list(SystemContext)
    objects: list[DomainModel] = [
        obj
        for model in (
            Component,
            Actor,
            Asset,
            DataFlow,
            TrustBoundary,
            ContextClaim,
            SourceObservation,
        )
        for obj in handle.objects.list(model)
    ]
    return validate_context(context, objects, available_evidence=set(evidence_ids(handle)))


def claims_by_predicate(handle: AssessmentHandle) -> dict[str, ContextClaim]:
    return {claim.predicate: claim for claim in handle.objects.list(ContextClaim)}


# ------------------------------------------------------------------------------------------
# Case 1 -- forgeflow-scenario.md section 14.1: delegated authentication
# ------------------------------------------------------------------------------------------


def test_delegated_authentication_produces_no_local_password_policy_claim(prepared: Any) -> None:
    """ForgeFlow uses GitHub OAuth and stores no local passwords. The expected treatment is to
    recognise the delegation and identify GitHub as the control provider — **not** to record a
    missing ForgeFlow password policy.

    This is the most common way a generic security review goes wrong on this scenario: it has a
    password-policy checklist item, finds nothing, and reports the nothing. The absent control is
    absent because another party provides it.
    """
    handle, ledger = prepared
    cited = cite(handle, "security-overview.md", "3. Authentication")

    model = run_with(
        handle,
        ledger,
        {
            "system": {"system_name": "ForgeFlow", "system_purpose": "AI-assisted PR review"},
            "claims": [
                {
                    "key": "auth-provider",
                    "subject_type": "system",
                    "predicate": "customer_authentication_provider",
                    "value": "GitHub OAuth",
                    "status": ClaimStatus.DOCUMENTED,
                    "confidence": ConfidenceLevel.HIGH,
                    "evidence_ids": [cited],
                },
                {
                    "key": "local-passwords",
                    "subject_type": "system",
                    "predicate": "local_password_storage",
                    "value": False,
                    "status": ClaimStatus.DOCUMENTED,
                    "confidence": ConfidenceLevel.HIGH,
                    "evidence_ids": [cited],
                },
                {
                    "key": "mfa",
                    "subject_type": "system",
                    "predicate": "customer_multi_factor_authentication",
                    "value": None,
                    "status": ClaimStatus.UNKNOWN,
                    "confidence": ConfidenceLevel.HIGH,
                    "rationale": (
                        "Customer authentication is delegated to GitHub and no document states "
                        "whether multi-factor authentication is enforced."
                    ),
                },
            ],
        },
    )

    claims = claims_by_predicate(handle)
    assert claims["customer_authentication_provider"].value == "GitHub OAuth"
    assert claims["local_password_storage"].value is False
    assert claims["local_password_storage"].evidence_ids, (
        "the absence of local passwords is documented, not inferred from silence"
    )

    # The delegated control's own state is unknown, and unknown is where it stops.
    mfa = claims["customer_multi_factor_authentication"]
    assert mfa.status is ClaimStatus.UNKNOWN
    assert mfa.evidence_ids == []
    assert mfa.rationale

    # Nothing asserts a ForgeFlow password-policy weakness.
    assert not [claim for claim in claims if "password_policy" in claim]
    assert len(model.calls) == 1, "incomplete material was retried"

    outcome = validate_persisted(handle)
    assert not [error for error in outcome.errors if error.object_id == mfa.id], (
        "the DEC-009 outlet was penalised: an unknown claim citing nothing is the correct answer"
    )


def test_the_expected_file_records_the_delegation_and_not_a_missing_control() -> None:
    """The answer key half of the same case."""
    claims = {entry["predicate"]: entry for entry in entries("context_claims")}
    assert claims["customer_authentication_provider"]["value"] == "GitHub OAuth"
    assert claims["local_password_storage"]["status"] == ClaimStatus.DOCUMENTED
    assert claims["customer_multi_factor_authentication"]["status"] == ClaimStatus.UNKNOWN
    assert not [predicate for predicate in claims if "password_policy" in predicate]


# ------------------------------------------------------------------------------------------
# Case 2 -- forgeflow-scenario.md section 14.2: managed-database encryption
# ------------------------------------------------------------------------------------------


def storage_proposal(cited: str, encryption: str) -> dict[str, Any]:
    return {
        "system": {"system_name": "ForgeFlow", "system_purpose": "AI-assisted PR review"},
        "components": [
            {
                "key": "worker",
                "name": "Analysis Worker",
                "component_type": "background_worker",
                "evidence_ids": [cited],
            },
            {
                "key": "postgres",
                "name": "Managed PostgreSQL",
                "component_type": "managed_database",
                "externally_managed": True,
                "evidence_ids": [cited],
            },
        ],
        "data_flows": [
            {
                "key": "result-storage",
                "name": "Structured result storage",
                "source_component_key": "worker",
                "destination_component_key": "postgres",
                "direction": FlowDirection.ONE_WAY,
                "encryption_in_transit": encryption,
                "evidence_ids": [cited],
            }
        ],
        "claims": [
            {
                "key": "at-rest",
                "subject_type": "system",
                "predicate": "storage_encryption_at_rest",
                "value": "Provided by the managed cloud storage services",
                "status": ClaimStatus.DOCUMENTED,
                "confidence": ConfidenceLevel.MEDIUM,
                "evidence_ids": [cited],
            }
        ],
    }


def test_managed_database_encryption_is_recorded_as_inherited_not_asserted_absent(
    prepared: Any,
) -> None:
    """The managed PostgreSQL platform provides encryption at rest, and the application documents
    do not repeat the detail. The expected treatment is to recognise the inherited control — not to
    conclude unencrypted storage from an application document that does not discuss disks.

    The transport half of the same flow is genuinely undocumented, and `unknown` is the required
    value. `false` there would be an asserted weakness nobody evidenced.
    """
    handle, ledger = prepared
    cited = cite(handle, "security-overview.md", "6. Encryption")

    run_with(handle, ledger, storage_proposal(cited, "unknown"))

    claim = claims_by_predicate(handle)["storage_encryption_at_rest"]
    assert claim.status is ClaimStatus.DOCUMENTED
    assert "managed" in str(claim.value).lower()

    (flow,) = handle.objects.list(DataFlow)
    assert flow.encryption_in_transit == "unknown"
    assert validate_persisted(handle).blocking_errors == ()


def test_reading_undocumented_transport_encryption_as_absent_is_reported(prepared: Any) -> None:
    """The half that does not rest on the model behaving. `data-model.md` section 14 requires
    `unknown`, and the validation node reports anything false-shaped rather than accepting it."""
    handle, ledger = prepared
    cited = cite(handle, "security-overview.md", "6. Encryption")

    run_with(handle, ledger, storage_proposal(cited, "none"))

    outcome = validate_persisted(handle)
    reported = [error for error in outcome.errors if error.field == "encryption_in_transit"]
    assert reported, "an undocumented transport read as absent passed validation"
    assert "not a statement of absence" in reported[0].message
    assert not outcome.ready_for_review


# ------------------------------------------------------------------------------------------
# Case 3 -- forgeflow-scenario.md section 15.1: ambiguous webhook validation
# ------------------------------------------------------------------------------------------


def test_ambiguous_webhook_validation_becomes_a_question_not_a_claim(prepared: Any) -> None:
    """Two documents say incoming webhook requests are validated. Neither says whether validation
    covers the GitHub HMAC signature, and the difference decides whether forged deliveries are
    accepted.

    `agent-design.md` section 7's retry rule is the other half of this case: incomplete material
    produces a question, never another model call. A node that retried here would be asking the
    same model the same question until it stopped saying "I don't know".
    """
    handle, ledger = prepared
    cited = cite(handle, "github-integration.md", "6. Webhook Processing")

    model = run_with(
        handle,
        ledger,
        {
            "system": {"system_name": "ForgeFlow", "system_purpose": "AI-assisted PR review"},
            "components": [
                {
                    "key": "webhook",
                    "name": "Webhook Receiver",
                    "component_type": "service",
                    "internet_accessible": True,
                    "evidence_ids": [cited],
                }
            ],
            "claims": [
                {
                    "key": "validation",
                    "subject_type": "component",
                    "subject_key": "webhook",
                    "predicate": "webhook_request_validation",
                    "value": None,
                    "status": ClaimStatus.UNKNOWN,
                    "confidence": ConfidenceLevel.HIGH,
                    "rationale": (
                        "The documents state that incoming requests are validated without stating "
                        "what validation covers."
                    ),
                }
            ],
            "questions": [
                {
                    "key": "hmac",
                    "question": (
                        "Does webhook validation include cryptographic verification of the GitHub "
                        "signature, or only payload and schema validation?"
                    ),
                    "rationale": (
                        "Without signature verification the receiver accepts forged deliveries "
                        "from anyone who knows the endpoint."
                    ),
                    "related_object_key": "webhook",
                    "priority": QuestionPriority.HIGH,
                    "blocking": False,
                }
            ],
        },
    )

    (question,) = handle.objects.list(Question)
    assert question.priority is QuestionPriority.HIGH
    assert "signature" in question.question.lower()
    assert question.rationale

    claim = claims_by_predicate(handle)["webhook_request_validation"]
    assert claim.status is ClaimStatus.UNKNOWN
    assert claim.value is None
    assert not [
        other
        for other in handle.objects.list(ContextClaim)
        if other.status is ClaimStatus.DOCUMENTED and "signature" in str(other.value).lower()
    ], "signature verification was asserted from documents that do not mention it"

    assert len(model.calls) == 1, "incomplete material was retried"


# ------------------------------------------------------------------------------------------
# Case 4 -- forgeflow-scenario.md section 16.1: the source-retention contradiction
# ------------------------------------------------------------------------------------------


def retention_proposal(product: str, operations: str, *, with_observation: bool) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "system": {"system_name": "ForgeFlow", "system_purpose": "AI-assisted PR review"},
        "components": [
            {
                "key": "storage",
                "name": "Managed Object Storage",
                "component_type": "managed_storage",
                "evidence_ids": [operations],
            }
        ],
        "assets": [
            {
                "key": "source-code",
                "name": "Customer Source Code",
                "asset_type": "source_code",
                "data_classification": "Restricted",
                "component_keys": ["storage"],
                "evidence_ids": [product],
            }
        ],
        "claims": [
            {
                "key": "retention",
                "subject_type": "asset",
                "subject_key": "source-code",
                "predicate": "retention_period",
                "value": None,
                "status": ClaimStatus.CONTRADICTED,
                "confidence": ConfidenceLevel.HIGH,
                "rationale": "The product overview and the operations guide disagree.",
                "evidence_ids": [product, operations],
            }
        ],
    }
    if with_observation:
        payload["observations"] = [
            {
                "key": "retention-conflict",
                "kind": ObservationKind.CONTRADICTION,
                "summary": (
                    "product-overview.md states that source files are deleted after analysis "
                    "completes; operations-guide.md states a 30-day artifact retention target."
                ),
                "evidence_ids": [product, operations],
                "subject_claim_keys": ["retention"],
            }
        ]
    return payload


def test_the_source_retention_contradiction_is_surfaced_and_not_resolved(prepared: Any) -> None:
    """The product overview says source files are deleted after analysis; the operations guide
    says artifacts are retained for 30 days. The expected treatment is to flag it, prevent a
    confirmed retention claim, and ask which statement is authoritative.

    **Avoid silently choosing the safer statement** is the part that has to be pinned. Preferring
    the 30-day reading because it is more conservative would produce a claim nobody made and a
    record showing a clean extraction.
    """
    handle, ledger = prepared
    product = cite(handle, "product-overview.md", "7. Source-Content Processing")
    operations = cite(handle, "operations-guide.md", "6. Artifact Retention")

    run_with(handle, ledger, retention_proposal(product, operations, with_observation=True))

    claim = claims_by_predicate(handle)["retention_period"]
    assert claim.status is ClaimStatus.CONTRADICTED
    assert claim.value is None, "a contradicted claim that states a value has picked a side"

    (observation,) = handle.objects.list(SourceObservation)
    assert observation.kind is ObservationKind.CONTRADICTION
    assert len(observation.evidence_ids) == 2, (
        "one passage cannot establish that two disagree (data-model.md section 10a)"
    )
    assert observation.subject_claim_ids == [claim.id]

    outcome = validate_persisted(handle)
    assert "contradictory_high_impact_claims" in {trigger.name for trigger in outcome.triggers}
    assert unsupported_contradictions([claim], [observation]) == []


def test_a_contradicted_claim_with_no_observation_behind_it_is_detected(prepared: Any) -> None:
    """`SourceObservation` is what makes a claim contradicted, one-directionally: nothing on the
    claim can see the observations. A claim asserting the status with nothing behind it is a claim
    saying two documents disagree without naming either, and it is detected rather than made
    impossible."""
    handle, ledger = prepared
    product = cite(handle, "product-overview.md", "7. Source-Content Processing")
    operations = cite(handle, "operations-guide.md", "6. Artifact Retention")

    run_with(handle, ledger, retention_proposal(product, operations, with_observation=False))

    (claim,) = handle.objects.list(ContextClaim)
    assert handle.objects.list(SourceObservation) == []
    assert unsupported_contradictions([claim], []) == [claim.id]


# ------------------------------------------------------------------------------------------
# Case 5 -- forgeflow-scenario.md section 14.4: Redis network placement
# ------------------------------------------------------------------------------------------


def test_redis_network_placement_is_recorded_not_invented(prepared: Any) -> None:
    """The documents restrict Redis in two places — accessible only from approved application
    workloads, and not publicly accessible. The expected treatment is to record what they say and
    ask only if placement is material and unclear.

    The other component in this test is the one that matters more. The administrative interface is
    described as not exposed through the customer login flow, which is a statement about a login
    flow and not about network reachability, so its exposure is **not stated**. `None` is the
    third state, and reading it as `False` is the DEC-009 failure at field level: a component
    nobody documented as internet-facing is not thereby internal.
    """
    handle, ledger = prepared
    redis_evidence = cite(handle, "architecture-overview.md", "9. Managed Redis Queue")
    admin_evidence = cite(handle, "architecture-overview.md", "15. Administrative Interface")

    run_with(
        handle,
        ledger,
        {
            "system": {"system_name": "ForgeFlow", "system_purpose": "AI-assisted PR review"},
            "components": [
                {
                    "key": "redis",
                    "name": "Managed Redis Queue",
                    "component_type": "managed_cache",
                    "internet_accessible": False,
                    "externally_managed": True,
                    "evidence_ids": [redis_evidence],
                },
                {
                    "key": "admin",
                    "name": "Administrative Interface",
                    "component_type": "internal_application",
                    "authentication_mechanisms": ["Corporate identity provider"],
                    "evidence_ids": [admin_evidence],
                },
            ],
            "claims": [
                {
                    "key": "redis-exposure",
                    "subject_type": "component",
                    "subject_key": "redis",
                    "predicate": "network_exposure",
                    "value": "Accessible only from approved application workloads",
                    "status": ClaimStatus.DOCUMENTED,
                    "confidence": ConfidenceLevel.MEDIUM,
                    "evidence_ids": [redis_evidence],
                }
            ],
        },
    )

    components = {component.name: component for component in handle.objects.list(Component)}
    redis = components["Managed Redis Queue"]
    assert redis.internet_accessible is False, "a public Redis exposure was invented"
    assert redis.evidence_ids == [redis_evidence]

    admin = components["Administrative Interface"]
    assert admin.internet_accessible is None, (
        "an unstated exposure was collapsed to False; None is the third state"
    )


def test_the_expected_file_keeps_redis_restricted_and_the_admin_interface_unstated() -> None:
    components = {entry["name"]: entry for entry in entries("components")}
    assert components["Managed Redis Queue"]["internet_accessible"] is False
    assert "internet_accessible" not in components["Administrative Interface"], (
        "the expected file states an exposure the documents do not"
    )
