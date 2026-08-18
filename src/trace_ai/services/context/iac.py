"""The IaC parser: deterministic proposals from declared infrastructure (DEC-070, #525).

Third and last in DEC-070's sequence, and the one its argument bears on hardest: infrastructure
code declares the largest surface of verifiable ground — the resources that exist, and the
security-relevant attributes their declarations state — and every claim derived from it shrinks
the DocumentationGap surface at zero model cost.

**Scope is Terraform's JSON syntax (`*.tf.json`), deliberately.** Terraform's JSON form is a
first-class, documented equivalent of HCL, and it parses with the standard library: no HCL
dependency to vet under the supply-chain posture, no grammar to maintain, and DEC-070's
determinism held trivially. HCL (`*.tf`) stays future work with this stated reason — the same
way the OpenAPI parser scoped to YAML — and the ingestion loader's accepted formats already
admit `.tf.json` through its `.json` suffix.

**What the parser reads is what the declaration states, and nothing more.** One component per
declared resource, its type mapped to an open-vocabulary family (DEC-036) from the resource
type's own naming; and one documented claim per security-relevant attribute the declaration
*states* — `storage_encrypted` and `publicly_accessible`, both directions. A stated `false` is
a documented negative, exactly the distinction DEC-009 turns on: a resource block silent about
encryption has said nothing and yields no claim, while `"storage_encrypted": false` has said
no, in writing, with a line number.

**Parser output enters the pipeline as proposals, not as authority** — the family rule,
unchanged: converted through `convert_proposal`, validated by Context Validation, decided at
checkpoint 1, with `source_origin: structured_input` and `generated_by: iac-parser-v1`. A
Terraform file is attacker-authorable text; its excerpts render inside the fence like any other
evidence.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Final

from trace_ai.domain.base import now
from trace_ai.domain.enums import SourceOrigin
from trace_ai.domain.evidence import EvidenceReference
from trace_ai.domain.hashing import content_hash
from trace_ai.domain.proposals import ContextExtractionProposal, convert_proposal
from trace_ai.domain.source_document import MediaType

if TYPE_CHECKING:
    from trace_ai.domain.proposals.conversion import ConvertedContext
    from trace_ai.domain.source_document import SourceDocument
    from trace_ai.services.assessment import AssessmentHandle

__all__ = ["IAC_PARSER", "looks_like_terraform", "parse_terraform", "seed_terraform_context"]

IAC_PARSER: Final = "iac-parser-v1"

# Resource-type naming mapped to open-vocabulary component families (DEC-036: any term is
# accepted downstream; this table only chooses a sensible spelling). Matching is by substring
# of the declared resource type, first hit wins, and an unmatched type stays a generic
# `infrastructure_resource` rather than being guessed at.
_TYPE_FAMILIES: Final[tuple[tuple[str, str], ...]] = (
    ("db_instance", "managed_database"),
    ("database", "managed_database"),
    ("sql", "managed_database"),
    ("bucket", "object_storage"),
    ("storage", "object_storage"),
    ("function", "function"),
    ("lambda", "function"),
    ("queue", "message_queue"),
    ("instance", "virtual_machine"),
)

# The security-relevant attributes a declaration can state, each read only when present: the
# claim carries the stated boolean, true or false alike (a stated false is a documented
# negative, never an inferred one).
_STATED_ATTRIBUTES: Final[tuple[str, ...]] = ("storage_encrypted", "publicly_accessible")


@dataclass(frozen=True, slots=True)
class ParsedResource:
    resource_type: str
    name: str
    stated: tuple[tuple[str, bool], ...]
    """The `_STATED_ATTRIBUTES` this declaration states, with their stated values."""


@dataclass(frozen=True, slots=True)
class ParsedTerraform:
    resources: tuple[ParsedResource, ...]


def looks_like_terraform(document: SourceDocument) -> bool:
    """Whether this registered document is Terraform JSON syntax, by name and type."""
    if document.media_type is not MediaType.JSON:
        return False
    return document.filename.rpartition("/")[2].casefold().endswith(".tf.json")


def _family_of(resource_type: str) -> str:
    lowered = resource_type.casefold()
    for token, family in _TYPE_FAMILIES:
        if token in lowered:
            return family
    return "infrastructure_resource"


def parse_terraform(text: str) -> ParsedTerraform:
    """The declaration's resources. Raises `ValueError` when it is not Terraform JSON."""
    data = json.loads(text)
    if not isinstance(data, dict) or not isinstance(data.get("resource"), dict):
        raise ValueError("not Terraform JSON syntax: no top-level `resource` block")

    resources: list[ParsedResource] = []
    for resource_type, declared in data["resource"].items():
        if not isinstance(declared, dict):
            continue
        for name, body in declared.items():
            attributes: dict[str, Any] = body if isinstance(body, dict) else {}
            stated = tuple(
                (attribute, bool(attributes[attribute]))
                for attribute in _STATED_ATTRIBUTES
                if isinstance(attributes.get(attribute), bool)
            )
            resources.append(
                ParsedResource(resource_type=str(resource_type), name=str(name), stated=stated)
            )
    return ParsedTerraform(resources=tuple(resources))


def _resource_spans(text: str) -> dict[str, tuple[int, int]]:
    """Each `"type" "name"` resource's 1-based line span, from the document's own layout.

    Line-based and format-tolerant on purpose: the span exists so an excerpt quotes the
    document's own lines with a hash, and a declaration whose span cannot be found simply
    contributes document-level evidence instead of a narrower quote.
    """
    lines = text.splitlines()
    spans: dict[str, tuple[int, int]] = {}
    for number, line in enumerate(lines, start=1):
        stripped = line.strip().strip(",")
        if not (stripped.startswith('"') and stripped.endswith("{")):
            continue
        key = stripped.strip("{").strip().strip(":").strip().strip('"')
        depth = line.count("{") - line.count("}")
        end = number
        for offset, later in enumerate(lines[number:], start=number + 1):
            depth += later.count("{") - later.count("}")
            end = offset
            if depth <= 0:
                break
        spans[key] = (number, end)
    return spans


def seed_terraform_context(handle: AssessmentHandle, document: SourceDocument) -> ConvertedContext:
    """Parse one declaration and persist what it states, through the proposal path.

    Evidence per declared resource (the resource's own line span, hashed) with a whole-document
    fallback; one component per resource under its open-vocabulary family; one documented claim
    per stated security-relevant attribute — converted with `structured_input` provenance for
    checkpoint 1 to decide.
    """
    text = handle.artifacts.read("sources", document.filename).decode("utf-8")
    parsed = parse_terraform(text)
    spans = _resource_spans(text)
    lines = text.splitlines()
    stamped = now()

    repository = handle.objects
    with repository.transaction():

        def evidence_for(span: tuple[int, int], label: str) -> str:
            start, end = span
            excerpt = "\n".join(lines[start - 1 : end])
            reference = EvidenceReference.model_validate(
                {
                    "id": repository.allocate("evd"),
                    "assessment_id": handle.assessment_id,
                    "source_document_id": document.id,
                    "section_title": label,
                    "start_line": start,
                    "end_line": end,
                    "quoted_text": excerpt,
                    "content_hash": content_hash(excerpt.encode("utf-8")),
                    "source_origin": SourceOrigin.STRUCTURED_INPUT,
                    "created_at": stamped,
                }
            )
            repository.save(reference)
            return reference.id

        components: list[dict[str, Any]] = []
        claims: list[dict[str, Any]] = []
        for index, resource in enumerate(parsed.resources):
            span = (
                spans.get(resource.name)
                or spans.get(resource.resource_type)
                or (
                    1,
                    len(lines),
                )
            )
            evidence_id = evidence_for(span, f"{resource.resource_type}.{resource.name}")
            key = f"cmp_iac_{index}"
            components.append(
                {
                    "key": key,
                    "name": resource.name.replace("_", " "),
                    "component_type": _family_of(resource.resource_type),
                    "description": (
                        f"Declared in {document.filename} as {resource.resource_type}."
                    ),
                    "evidence_ids": [evidence_id],
                }
            )
            for attribute, value in resource.stated:
                claims.append(
                    {
                        "key": f"clm_iac_{index}_{attribute}",
                        "subject_type": "component",
                        "subject_key": key,
                        "predicate": attribute,
                        "value": value,
                        "status": "documented",
                        "confidence": "high",
                        "evidence_ids": [evidence_id],
                    }
                )

        proposal = ContextExtractionProposal.model_validate(
            {
                "system": {"system_name": "Declared infrastructure"},
                "claims": claims,
                "components": components,
                "actors": [],
                "assets": [],
                "data_flows": [],
                "trust_boundaries": [],
                "questions": [],
                "observations": [],
            }
        )
        converted = convert_proposal(
            proposal,
            allocator=repository,
            assessment_id=handle.assessment_id,
            created_at=stamped,
            generated_by=IAC_PARSER,
            source_origin=SourceOrigin.STRUCTURED_INPUT,
        )
        for obj in converted.all_objects():
            repository.save(obj)
    return converted
