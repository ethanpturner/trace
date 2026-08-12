"""The compose-manifest parser: deterministic proposals from machine-readable topology (DEC-070).

A compose manifest states its services and their dependencies outright, and a claim derived
mechanically from it is *documented* evidence — the artifact states the service, and the excerpt
proves it, verifiable forever at zero model cost. Compose comes first in DEC-070's sequence
because it yields the topology objects (components, flows) with the least ambiguity.

**Parser output enters the pipeline as proposals, not as authority.** What this module builds is
a `ContextExtractionProposal`, converted through the same `convert_proposal`, validated by the
same Context Validation, and decided at the same checkpoint 1 as agent output — determinism
earns no bypass, because a parser can be wrong about meaning while right about syntax. The one
semantic call the DEC names is honoured here: a compose port exposed to a host network is not
thereby internet-accessible, so `internet_accessible` stays `None` whatever the manifest maps.

**Provenance rides the existing vocabulary.** Converted objects carry
`source_origin: structured_input` and `generated_by: compose-parser-v1`; no new `SourceOrigin`
value exists, because mechanical-versus-model-extracted is exactly the distinction
`structured_input` already draws.

**The untrusted-source rules apply unchanged.** A compose file is attacker-authorable text. Its
excerpts are `EvidenceReference` rows like any other, they render inside the fence, and nothing
this parser reads becomes an instruction — parsers are the one place that is easy to forget,
because their input looks like configuration rather than prose.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Final

import yaml

from trace_ai.domain.base import now
from trace_ai.domain.enums import SourceOrigin
from trace_ai.domain.evidence import EvidenceReference
from trace_ai.domain.hashing import content_hash
from trace_ai.domain.proposals import ContextExtractionProposal, convert_proposal
from trace_ai.domain.source_document import MediaType
from trace_ai.domain.vocabulary import normalize_term

if TYPE_CHECKING:
    from trace_ai.domain.proposals.conversion import ConvertedContext
    from trace_ai.domain.source_document import SourceDocument
    from trace_ai.services.assessment import AssessmentHandle

__all__ = [
    "COMPOSE_PARSER",
    "looks_like_compose",
    "parse_compose",
    "seed_compose_context",
    "seed_compose_documents",
]

COMPOSE_PARSER: Final = "compose-parser-v1"

# Filenames the compose ecosystem actually uses. Matched on the basename, case-insensitively;
# an arbitrary YAML file is not assumed to be a manifest just for parsing as one.
_COMPOSE_NAMES: Final = ("compose.yaml", "compose.yml", "docker-compose.yaml", "docker-compose.yml")


@dataclass(frozen=True, slots=True)
class ParsedService:
    """One service block, with the excerpt that proves it exists."""

    key: str
    name: str
    image: str | None
    depends_on: tuple[str, ...]
    start_line: int
    end_line: int
    excerpt: str


@dataclass(frozen=True, slots=True)
class ParsedCompose:
    """What the manifest states: services and the dependencies between them."""

    services: tuple[ParsedService, ...]


def looks_like_compose(document: SourceDocument) -> bool:
    """Whether this registered document is a compose manifest, by name and type."""
    if document.media_type is not MediaType.YAML:
        return False
    basename = document.filename.rpartition("/")[2].casefold()
    return basename in _COMPOSE_NAMES


def _service_lines(text: str) -> dict[str, tuple[int, int]]:
    """Each service block's 1-based line span, from the manifest's own layout.

    Line-based rather than re-serialized, because the excerpt must be the artifact's own text —
    a re-serialization would hash differently from what the author wrote and the reader opens.
    """
    lines = text.splitlines()
    spans: dict[str, tuple[int, int]] = {}
    in_services = False
    current: str | None = None
    start = 0

    def close(end: int) -> None:
        if current is not None:
            spans[current] = (start, end)

    for number, line in enumerate(lines, start=1):
        stripped = line.rstrip()
        if not stripped or stripped.lstrip().startswith("#"):
            continue
        indent = len(stripped) - len(stripped.lstrip())
        if indent == 0:
            close(number - 1)
            current = None
            in_services = stripped.rstrip(":") == "services" and stripped.endswith(":")
            continue
        if in_services and indent == 2 and stripped.lstrip().endswith(":"):
            close(number - 1)
            current = stripped.strip().rstrip(":")
            start = number
    close(len(lines))
    return spans


def parse_compose(text: str) -> ParsedCompose:
    """The manifest's stated topology. Raises `ValueError` on YAML that is not a manifest."""
    data = yaml.safe_load(text)
    if not isinstance(data, dict) or not isinstance(data.get("services"), dict):
        raise ValueError("not a compose manifest: no `services` mapping")

    spans = _service_lines(text)
    lines = text.splitlines()
    services: list[ParsedService] = []
    for raw_name, definition in data["services"].items():
        name = str(raw_name)
        body: dict[str, Any] = definition if isinstance(definition, dict) else {}
        raw_depends = body.get("depends_on")
        if isinstance(raw_depends, dict | list):
            depends = tuple(str(item) for item in raw_depends)
        else:
            depends = ()
        start, end = spans.get(name, (1, len(lines)))
        services.append(
            ParsedService(
                key=normalize_term(name).replace("_", "-"),
                name=name,
                image=str(body["image"]) if body.get("image") else None,
                depends_on=depends,
                start_line=start,
                end_line=end,
                excerpt="\n".join(lines[start - 1 : end]),
            )
        )
    return ParsedCompose(services=tuple(services))


def seed_compose_context(handle: AssessmentHandle, document: SourceDocument) -> ConvertedContext:
    """Parse one manifest and persist what it states, through the ordinary proposal path.

    Evidence first: one `EvidenceReference` per service block, quoting the artifact's own lines
    with their hash, so every derived object cites an excerpt that re-verifies forever. Then the
    proposal — components for services, one-way flows for `depends_on` — converted with
    `structured_input` provenance and persisted as `candidate` objects for checkpoint 1 to
    decide, exactly like agent output.
    """
    text = handle.artifacts.read("sources", document.filename).decode("utf-8")
    parsed = parse_compose(text)
    stamped = now()

    repository = handle.objects
    with repository.transaction():
        evidence_by_service: dict[str, str] = {}
        for service in parsed.services:
            reference = EvidenceReference.model_validate(
                {
                    "id": repository.allocate("evd"),
                    "assessment_id": handle.assessment_id,
                    "source_document_id": document.id,
                    "section_title": f"services.{service.name}",
                    "start_line": service.start_line,
                    "end_line": service.end_line,
                    "quoted_text": service.excerpt,
                    "content_hash": content_hash(service.excerpt.encode("utf-8")),
                    "source_origin": SourceOrigin.STRUCTURED_INPUT,
                    "created_at": stamped,
                }
            )
            repository.save(reference)
            evidence_by_service[service.key] = reference.id

        known = {service.key for service in parsed.services}
        proposal = ContextExtractionProposal.model_validate(
            {
                "system": {"system_name": document.filename},
                "claims": [],
                "components": [
                    {
                        "key": service.key,
                        "name": service.name,
                        "component_type": "service",
                        "description": (
                            f"Defined as service {service.name!r} in {document.filename}."
                        ),
                        "technology": [service.image] if service.image else [],
                        # A compose port exposed to a host network is not thereby
                        # internet-accessible (DEC-070); the parser does not guess meaning.
                        "internet_accessible": None,
                        "evidence_ids": [evidence_by_service[service.key]],
                    }
                    for service in parsed.services
                ],
                "actors": [],
                "assets": [],
                "data_flows": [
                    {
                        "key": f"{service.key}-uses-{normalize_term(target).replace('_', '-')}",
                        "name": f"{service.name} depends on {target}",
                        "source_component_key": service.key,
                        "destination_component_key": normalize_term(target).replace("_", "-"),
                        "direction": "one_way",
                        "evidence_ids": [evidence_by_service[service.key]],
                    }
                    for service in parsed.services
                    for target in service.depends_on
                    if normalize_term(target).replace("_", "-") in known
                ],
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
            generated_by=COMPOSE_PARSER,
            source_origin=SourceOrigin.STRUCTURED_INPUT,
        )
        for obj in converted.all_objects():
            repository.save(obj)
    return converted


def seed_compose_documents(handle: AssessmentHandle) -> ConvertedContext | None:
    """Seed every registered compose manifest, once per assessment.

    Idempotent by provenance: components carry no `generated_by`, so `source_origin ==
    structured_input` is the marker — only a DEC-070 parser converts with it — and a
    re-extraction run (DEC-038) reuses what the first run seeded instead of minting duplicates.
    Returns what was (or already had been) seeded, or `None` when no manifest is registered.
    """
    from trace_ai.domain.component import Component
    from trace_ai.domain.data_flow import DataFlow
    from trace_ai.domain.proposals.conversion import ConvertedContext

    already = [
        component
        for component in handle.objects.list(Component)
        if component.source_origin is SourceOrigin.STRUCTURED_INPUT
    ]
    if already:
        flows = [
            flow
            for flow in handle.objects.list(DataFlow)
            if flow.source_origin is SourceOrigin.STRUCTURED_INPUT
        ]
        return ConvertedContext(components=tuple(already), data_flows=tuple(flows))

    from trace_ai.domain.source_document import SourceDocument

    manifests = [
        document for document in handle.objects.list(SourceDocument) if looks_like_compose(document)
    ]
    if not manifests:
        return None

    components: list[Any] = []
    flows_out: list[Any] = []
    for document in sorted(manifests, key=lambda item: item.id):
        converted = seed_compose_context(handle, document)
        components.extend(converted.components)
        flows_out.extend(converted.data_flows)
    return ConvertedContext(components=tuple(components), data_flows=tuple(flows_out))
