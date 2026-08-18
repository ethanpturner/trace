"""The CloudFormation parser: deterministic proposals from declared AWS templates (#593).

The IaC family's CloudFormation member, under the shape DEC-113 and DEC-121 settled: one
component per declared resource, one documented claim per security-relevant attribute the
declaration states as a literal boolean, and silence for everything else. An intrinsic —
``{"Ref": ...}``, ``{"Fn::GetAtt": ...}``, ``Fn::Sub`` — states no boolean and yields nothing,
which is DEC-009's line held by a parser: an expression is *not stated*.

**The syntax scope is what already parses at the loader's boundary.** JSON templates
(``*.cfn.json``) and tag-free YAML templates (``*.cfn.yaml``, ``*.cfn.yml``) are in scope.
CloudFormation's short-form intrinsic tags (``!Ref``, ``!Sub``) fail ``yaml.safe_load``, and the
document loader already refuses a YAML document that does not safe-parse — so a short-form
template is refused at ingestion by the existing untrusted-input rule, and this parser adds no
tag handling to admit it. Long-form intrinsics parse as mappings and are not literal booleans,
so they yield nothing without special casing. The suffix names the format; content is never
sniffed.

**Attribute admission is DEC-121's rule, in CloudFormation's spelling.** The template states
``StorageEncrypted``; the claim carries the family predicate ``storage_encrypted``, so a
CloudFormation-declared database and a Terraform-declared one make the same documented claim
downstream. The table grows only by the rule — literal boolean, self-contained meaning, both
directions meaningful.

**Parser output enters the pipeline as proposals, not as authority** — converted through
``convert_proposal``, validated by Context Validation, decided at checkpoint 1, with
``source_origin: structured_input`` and ``generated_by: cloudformation-parser-v1``. A template
is attacker-authorable text; its excerpts render inside the fence like any other evidence.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Final

import yaml

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

__all__ = [
    "CLOUDFORMATION_PARSER",
    "looks_like_cloudformation",
    "parse_cloudformation",
    "seed_cloudformation_context",
]

CLOUDFORMATION_PARSER: Final = "cloudformation-parser-v1"

# CloudFormation property spellings admitted under DEC-121's rule, each mapped to the family
# predicate its Terraform twin uses, so the same stated fact makes the same claim whichever
# dialect declared it. Growth is by the rule, never ad hoc.
_STATED_PROPERTIES: Final[dict[str, str]] = {
    "StorageEncrypted": "storage_encrypted",
    "PubliclyAccessible": "publicly_accessible",
    "Encrypted": "encrypted",
    "DeletionProtection": "deletion_protection",
}

# Closed-vocabulary string properties, admitted by the widened rule (DEC-121 as amended): the
# platform defines a finite enumerated value set — a listener's `SslPolicy` is one of AWS's
# published policy names — and a stated member is as literal as a stated boolean. The claim
# carries the stated string verbatim; an intrinsic is a mapping and yields nothing. Reading
# stays at `Properties`' top level, the family discipline: a vocabulary nested deeper (say
# CloudFront's `MinimumProtocolVersion` under `ViewerCertificate`) is not admitted by this
# table existing — nesting is its own decision, unmade.
_STATED_STRING_PROPERTIES: Final[dict[str, str]] = {
    "SslPolicy": "ssl_policy",
}

# CloudFormation type strings (`AWS::Service::Kind`) mapped to the family's open-vocabulary
# component spellings (DEC-036). Matching is by substring of the casefolded type, first hit
# wins; an unmatched type stays a generic `infrastructure_resource`.
_TYPE_FAMILIES: Final[tuple[tuple[str, str], ...]] = (
    ("dbinstance", "managed_database"),
    ("dbcluster", "managed_database"),
    ("rds", "managed_database"),
    ("s3::bucket", "object_storage"),
    ("efs", "object_storage"),
    ("lambda::function", "function"),
    ("sqs::queue", "message_queue"),
    ("ec2::instance", "virtual_machine"),
)


@dataclass(frozen=True, slots=True)
class ParsedCloudFormationResource:
    logical_id: str
    resource_type: str
    stated: tuple[tuple[str, bool | str], ...]
    """The admitted properties this declaration states, as (family predicate, stated value)."""


@dataclass(frozen=True, slots=True)
class ParsedCloudFormation:
    resources: tuple[ParsedCloudFormationResource, ...]


def looks_like_cloudformation(document: SourceDocument) -> bool:
    """Whether this registered document is a CloudFormation template, by name and type.

    ``*.cfn.json`` under the JSON media type, ``*.cfn.yaml`` or ``*.cfn.yml`` under YAML — the
    suffix names the format, the loader admitted the media type, and content is never sniffed.
    """
    basename = document.filename.rpartition("/")[2].casefold()
    if document.media_type is MediaType.JSON:
        return basename.endswith(".cfn.json")
    if document.media_type is MediaType.YAML:
        return basename.endswith((".cfn.yaml", ".cfn.yml"))
    return False


def _family_of(resource_type: str) -> str:
    lowered = resource_type.casefold()
    for token, family in _TYPE_FAMILIES:
        if token in lowered:
            return family
    return "infrastructure_resource"


def parse_cloudformation(text: str, *, media_type: MediaType) -> ParsedCloudFormation:
    """The template's resources. Raises ``ValueError`` when it is not a CloudFormation template.

    The reader is ``json.loads`` or ``yaml.safe_load`` — the same parsers the loader validated
    the document against — so nothing parses here that the ingestion boundary did not already
    admit. Only literal booleans at a resource's ``Properties`` top level are read; an intrinsic
    parses as a mapping and is not a boolean, so it yields nothing.
    """
    data: Any = json.loads(text) if media_type is MediaType.JSON else yaml.safe_load(text)
    if not isinstance(data, dict) or not isinstance(data.get("Resources"), dict):
        raise ValueError("not a CloudFormation template: no top-level `Resources` block")

    resources: list[ParsedCloudFormationResource] = []
    for logical_id, declared in data["Resources"].items():
        if not isinstance(declared, dict):
            continue
        properties = declared.get("Properties")
        attributes: dict[str, Any] = properties if isinstance(properties, dict) else {}
        stated: tuple[tuple[str, bool | str], ...] = tuple(
            [
                (predicate, bool(attributes[spelling]))
                for spelling, predicate in _STATED_PROPERTIES.items()
                if isinstance(attributes.get(spelling), bool)
            ]
            + [
                (predicate, str(attributes[spelling]))
                for spelling, predicate in _STATED_STRING_PROPERTIES.items()
                if isinstance(attributes.get(spelling), str)
            ]
        )
        resources.append(
            ParsedCloudFormationResource(
                logical_id=str(logical_id),
                resource_type=str(declared.get("Type", "")),
                stated=stated,
            )
        )
    return ParsedCloudFormation(resources=tuple(resources))


# A YAML logical id line: the resource's own key at its indent, nothing else on the line.
_YAML_KEY: Final = re.compile(r"^(\s*)([A-Za-z0-9]+):\s*(?:#.*)?$")


def _yaml_resource_spans(text: str) -> dict[str, tuple[int, int]]:
    """Each logical id's 1-based line span in a YAML template, from the document's own layout.

    Line-based and tolerant on purpose, like the JSON span scanner: the span exists so an
    excerpt quotes the document's own lines with a hash, and a resource whose span cannot be
    found contributes document-level evidence instead of a narrower quote.
    """
    lines = text.splitlines()
    spans: dict[str, tuple[int, int]] = {}
    resources_indent: int | None = None
    child_indent: int | None = None
    current: tuple[str, int] | None = None

    def close(end: int) -> None:
        nonlocal current
        if current is not None:
            spans[current[0]] = (current[1], end)
            current = None

    for number, line in enumerate(lines, start=1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        match = _YAML_KEY.match(line)
        indent = len(line) - len(line.lstrip())
        if resources_indent is None:
            if match and match.group(2) == "Resources":
                resources_indent = indent
            continue
        if indent <= resources_indent:
            close(number - 1)
            resources_indent = None
            continue
        if child_indent is None:
            child_indent = indent
        if match and indent == child_indent:
            close(number - 1)
            current = (match.group(2), number)
    close(len(lines))
    return spans


def _json_resource_spans(text: str) -> dict[str, tuple[int, int]]:
    """Each logical id's line span in a JSON template, by the family's brace-tracking scan."""
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


def seed_cloudformation_context(
    handle: AssessmentHandle, document: SourceDocument
) -> ConvertedContext:
    """Parse one template and persist what it states, through the proposal path.

    Evidence per declared resource (the resource's own line span, hashed) with a whole-document
    fallback; one component per resource under its open-vocabulary family; one documented claim
    per stated admitted property — converted with ``structured_input`` provenance for
    checkpoint 1 to decide.
    """
    text = handle.artifacts.read("sources", document.filename).decode("utf-8")
    parsed = parse_cloudformation(text, media_type=document.media_type)
    spans = (
        _json_resource_spans(text)
        if document.media_type is MediaType.JSON
        else _yaml_resource_spans(text)
    )
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
            span = spans.get(resource.logical_id) or (1, len(lines))
            label = (
                f"{resource.resource_type}.{resource.logical_id}"
                if resource.resource_type
                else resource.logical_id
            )
            evidence_id = evidence_for(span, label)
            key = f"cmp_cfn_{index}"
            components.append(
                {
                    "key": key,
                    "name": _spaced(resource.logical_id),
                    "component_type": _family_of(resource.resource_type),
                    "description": (
                        f"Declared in {document.filename} as {resource.resource_type or 'a resource'}."
                    ),
                    "evidence_ids": [evidence_id],
                }
            )
            for predicate, value in resource.stated:
                claims.append(
                    {
                        "key": f"clm_cfn_{index}_{predicate}",
                        "subject_type": "component",
                        "subject_key": key,
                        "predicate": predicate,
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
            generated_by=CLOUDFORMATION_PARSER,
            source_origin=SourceOrigin.STRUCTURED_INPUT,
        )
        for obj in converted.all_objects():
            repository.save(obj)
    return converted


def _spaced(logical_id: str) -> str:
    """A logical id as a readable name: CamelCase and underscores become spaces."""
    withspaces = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", logical_id).replace("_", " ")
    return " ".join(withspaces.split()).lower()
