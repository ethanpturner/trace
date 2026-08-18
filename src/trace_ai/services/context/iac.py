"""The IaC parser: deterministic proposals from declared infrastructure (DEC-070, #525).

Third and last in DEC-070's sequence, and the one its argument bears on hardest: infrastructure
code declares the largest surface of verifiable ground — the resources that exist, and the
security-relevant attributes their declarations state — and every claim derived from it shrinks
the DocumentationGap surface at zero model cost.

**Both Terraform syntaxes are in scope: JSON (`*.tf.json`) and HCL (`*.tf`), each read by the
narrowest honest reader.** The JSON form parses with the standard library, as DEC-113 scoped.
HCL (DEC-121) is read by a subset scanner in this module rather than an HCL dependency: what
the family reads — `resource "type" "name"` blocks and literal boolean attributes at the
block's top level — is a deterministic, line-oriented subset, and DEC-113's own reason for
deferring the dependency (heavyweight for a resource list and a handful of attributes) is the
reason not to add one now. Anything the subset cannot read literally — an expression, a
variable reference, an interpolation — is *not stated* and yields nothing, which is the correct
answer rather than a shortcut: `storage_encrypted = var.encrypt` states no boolean. The
ingestion loader admits `.tf` through its plain-text suffix, the way `.tf.json` arrives
through `.json`.

**What the parser reads is what the declaration states, and nothing more.** One component per
declared resource, its type mapped to an open-vocabulary family (DEC-036) from the resource
type's own naming; and one documented claim per security-relevant attribute the declaration
*states*, both directions. The attribute table is governed by DEC-121's coverage rule: an
attribute is read when it is a literal boolean in the declaration, its meaning stands alone
without cross-resource reasoning, and both stated directions are meaningful documented claims.
A stated `false` is a documented negative, exactly the distinction DEC-009 turns on: a
resource block silent about encryption has said nothing and yields no claim, while
`"storage_encrypted": false` has said no, in writing, with a line number.

**Parser output enters the pipeline as proposals, not as authority** — the family rule,
unchanged: converted through `convert_proposal`, validated by Context Validation, decided at
checkpoint 1, with `source_origin: structured_input` and `generated_by: iac-parser-v1`. A
Terraform file is attacker-authorable text; its excerpts render inside the fence like any other
evidence.
"""

from __future__ import annotations

import json
import re
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

__all__ = [
    "IAC_PARSER",
    "looks_like_terraform",
    "parse_terraform",
    "parse_terraform_hcl",
    "seed_terraform_context",
]

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
# negative, never an inferred one). Growth is by DEC-121's rule — literal boolean, meaning
# self-contained without cross-resource reasoning, both directions meaningful — so this table
# is a visible small diff, never an ad-hoc accretion. `encrypted` is `storage_encrypted`'s
# spelling on volume and disk resources; `deletion_protection` states whether the platform
# refuses destructive deletion.
_STATED_ATTRIBUTES: Final[tuple[str, ...]] = (
    "storage_encrypted",
    "publicly_accessible",
    "encrypted",
    "deletion_protection",
)


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
    """Whether this registered document is a Terraform declaration, by name and type.

    Two shapes, each recognized by its own pairing: JSON syntax arrives as `*.tf.json` under the
    JSON media type (DEC-113), and HCL arrives as `*.tf` under plain text (DEC-121) — the loader
    admits the suffix, this parser recognizes it, and content is never sniffed by either.
    """
    basename = document.filename.rpartition("/")[2].casefold()
    if document.media_type is MediaType.JSON:
        return basename.endswith(".tf.json")
    if document.media_type is MediaType.PLAIN_TEXT:
        return basename.endswith(".tf")
    return False


def _is_hcl_name(filename: str) -> bool:
    basename = filename.rpartition("/")[2].casefold()
    return basename.endswith(".tf") and not basename.endswith(".tf.json")


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


# The HCL subset this module reads (DEC-121): a `resource "type" "name" {` opener at column
# depth zero, and `attribute = true|false` at the block's own top level, an optional trailing
# line comment tolerated. Nothing else is interpreted: an expression, a variable reference, or
# an interpolation is not a stated boolean and yields nothing.
_HCL_RESOURCE: Final = re.compile(r'^resource\s+"([^"]+)"\s+"([^"]+)"\s*\{')
_HCL_ATTRIBUTE: Final = re.compile(
    r"^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(true|false)\s*(?:(?:#|//).*)?$"
)


def _hcl_scan(text: str) -> tuple[ParsedTerraform, dict[str, tuple[int, int]]]:
    """One line-oriented pass over an HCL declaration: resources, stated booleans, spans.

    Deterministic and deliberately narrow. Full-line comments (`#`, `//`, and `/* */` blocks)
    are skipped so a commented-out attribute is never read; brace depth is tracked so a nested
    block's attributes never count as the resource's own; and a `.tf` file with no resource
    block — a variables or outputs file, ordinary in a real Terraform corpus — parses to an
    empty declaration rather than refusing, because the `.tf` suffix already named the format.
    """
    lines = text.splitlines()
    resources: list[ParsedResource] = []
    spans: dict[str, tuple[int, int]] = {}

    in_block_comment = False
    current: tuple[str, str, int] | None = None  # (type, name, start line)
    stated: list[tuple[str, bool]] = []
    depth = 0

    for number, raw in enumerate(lines, start=1):
        stripped = raw.strip()
        if in_block_comment:
            if "*/" in stripped:
                in_block_comment = False
            continue
        if stripped.startswith("/*"):
            in_block_comment = "*/" not in stripped
            continue
        if stripped.startswith("#") or stripped.startswith("//"):
            continue

        if current is None:
            opener = _HCL_RESOURCE.match(stripped)
            if opener is not None:
                current = (opener.group(1), opener.group(2), number)
                stated = []
                depth = stripped.count("{") - stripped.count("}")
                if depth <= 0:  # a one-line, empty resource block
                    resource_type, name, start = current
                    resources.append(
                        ParsedResource(resource_type=resource_type, name=name, stated=())
                    )
                    spans[name] = (start, number)
                    current = None
            continue

        if depth == 1:
            attribute = _HCL_ATTRIBUTE.match(stripped)
            if attribute is not None and attribute.group(1) in _STATED_ATTRIBUTES:
                stated.append((attribute.group(1), attribute.group(2) == "true"))

        depth += stripped.count("{") - stripped.count("}")
        if depth <= 0:
            resource_type, name, start = current
            resources.append(
                ParsedResource(resource_type=resource_type, name=name, stated=tuple(stated))
            )
            spans[name] = (start, number)
            current = None

    return ParsedTerraform(resources=tuple(resources)), spans


def parse_terraform_hcl(text: str) -> ParsedTerraform:
    """The declaration's resources, from HCL syntax, by the subset scanner (DEC-121)."""
    parsed, _ = _hcl_scan(text)
    return parsed


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
    if _is_hcl_name(document.filename):
        parsed, spans = _hcl_scan(text)
        if not parsed.resources:
            # A `.tf` file with no resource block — variables, outputs — contributes nothing,
            # and nothing is not a refusal: the suffix named the format, the file states no
            # resources, and silence yields silence (DEC-121).
            from trace_ai.domain.proposals.conversion import ConvertedContext

            return ConvertedContext(components=(), data_flows=(), claims=())
    else:
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
