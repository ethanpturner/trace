"""The Kubernetes parser: deterministic proposals from declared manifests (#594).

The IaC family's Kubernetes member, closing future-features 7.2's parser list. The shape is
DEC-113's and DEC-121's, held again: one component per declared object on a small kind
allowlist, one documented claim per admitted attribute the manifest states as a literal
boolean, both directions, and silence for everything else. Anything templated — a Helm
expression is not YAML and fails the loader's safe-parse rule — or indirect — a value reached
through a ConfigMap reference is not a literal — yields nothing.

**The kind allowlist is deliberate and small**: Deployment, Service, Ingress, NetworkPolicy.
A Deployment is the workload whose pod spec states the admitted booleans; the other three are
architecture surface a reviewer needs on the component list. Kinds outside the allowlist yield
nothing — a CRD's semantics are its own, and reading one would be interpretation.

**Multi-document streams are the convention and are in scope** (DEC-125): the ingestion loader
validates a YAML stream with the same safe loader it validates a single document with, and this
parser reads every document on the allowlist. Recognition is by suffix — ``*.k8s.yaml``,
``*.k8s.yml``, ``*.k8s.json`` — and content is never sniffed.

**Container-level attributes are read uniformly or not at all.** ``hostNetwork`` and
``automountServiceAccountToken`` are pod-level statements. ``allowPrivilegeEscalation`` and
``readOnlyRootFilesystem`` are per-container: when every container that states the attribute
states the same value, the manifest has stated one thing and the claim carries it; when
containers disagree, the manifest has not stated one self-contained fact about the workload,
and the split yields nothing — DEC-121's self-contained-meaning bar, applied to aggregation.

**Parser output enters the pipeline as proposals, not as authority** — converted through
``convert_proposal``, decided at checkpoint 1, with ``source_origin: structured_input`` and
``generated_by: kubernetes-parser-v1``. A manifest is attacker-authorable text; its excerpts
render inside the fence like any other evidence.
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
    "KUBERNETES_PARSER",
    "looks_like_kubernetes",
    "parse_kubernetes",
    "seed_kubernetes_context",
]

KUBERNETES_PARSER: Final = "kubernetes-parser-v1"

# The kind allowlist (DEC-125), each mapped to the family's open-vocabulary component spelling
# (DEC-036). Kinds outside the allowlist yield nothing.
_KINDS: Final[dict[str, str]] = {
    "Deployment": "workload",
    "Service": "service",
    "Ingress": "gateway",
    "NetworkPolicy": "network_policy",
}

# Pod-level attributes admitted under DEC-121's rule, read at `spec.template.spec`.
_POD_ATTRIBUTES: Final[tuple[str, ...]] = ("hostNetwork", "automountServiceAccountToken")

# Container-level attributes, read from each container's `securityContext` and admitted only
# when every container that states the attribute states the same value.
_CONTAINER_ATTRIBUTES: Final[tuple[str, ...]] = (
    "allowPrivilegeEscalation",
    "readOnlyRootFilesystem",
)


@dataclass(frozen=True, slots=True)
class ParsedManifestObject:
    kind: str
    name: str
    stated: tuple[tuple[str, bool], ...]
    """The admitted attributes this manifest states, as (attribute, stated value)."""


@dataclass(frozen=True, slots=True)
class ParsedKubernetes:
    objects: tuple[ParsedManifestObject, ...]


def looks_like_kubernetes(document: SourceDocument) -> bool:
    """Whether this registered document is a Kubernetes manifest, by name and type."""
    basename = document.filename.rpartition("/")[2].casefold()
    if document.media_type is MediaType.YAML:
        return basename.endswith((".k8s.yaml", ".k8s.yml"))
    if document.media_type is MediaType.JSON:
        return basename.endswith(".k8s.json")
    return False


def _pod_spec(declared: dict[str, Any]) -> dict[str, Any]:
    spec = declared.get("spec")
    template = spec.get("template") if isinstance(spec, dict) else None
    pod = template.get("spec") if isinstance(template, dict) else None
    return pod if isinstance(pod, dict) else {}


def _stated_of(declared: dict[str, Any]) -> tuple[tuple[str, bool], ...]:
    """The admitted booleans one Deployment states, pod-level and uniform container-level."""
    pod = _pod_spec(declared)
    stated: list[tuple[str, bool]] = [
        (attribute, bool(pod[attribute]))
        for attribute in _POD_ATTRIBUTES
        if isinstance(pod.get(attribute), bool)
    ]
    containers = pod.get("containers")
    listed = containers if isinstance(containers, list) else []
    for attribute in _CONTAINER_ATTRIBUTES:
        values = {
            context[attribute]
            for container in listed
            if isinstance(container, dict)
            and isinstance(context := container.get("securityContext", {}), dict)
            and isinstance(context.get(attribute), bool)
        }
        if len(values) == 1:
            stated.append((attribute, values.pop()))
        # Zero statements is silence; a split statement is not one self-contained fact about
        # the workload, and yields nothing either (DEC-125).
    return tuple(stated)


def parse_kubernetes(text: str, *, media_type: MediaType) -> ParsedKubernetes:
    """The manifest stream's allowlisted objects. Raises ``ValueError`` when none is one.

    The readers are the loader's own — ``yaml.safe_load_all`` or ``json.loads`` — so nothing
    parses here that the ingestion boundary did not already admit.
    """
    if media_type is MediaType.JSON:
        documents: list[Any] = [json.loads(text)]
    else:
        documents = [parsed for parsed in yaml.safe_load_all(text) if parsed is not None]

    objects: list[ParsedManifestObject] = []
    saw_kind = False
    for declared in documents:
        if not isinstance(declared, dict):
            continue
        kind = declared.get("kind")
        if isinstance(kind, str):
            saw_kind = True
        if kind not in _KINDS:
            continue
        metadata = declared.get("metadata")
        name = metadata.get("name") if isinstance(metadata, dict) else None
        objects.append(
            ParsedManifestObject(
                kind=str(kind),
                name=str(name) if isinstance(name, str) else str(kind).casefold(),
                stated=_stated_of(declared) if kind == "Deployment" else (),
            )
        )
    if not saw_kind:
        raise ValueError("not a Kubernetes manifest: no document with a `kind`")
    return ParsedKubernetes(objects=tuple(objects))


_SEPARATOR: Final = re.compile(r"^---\s*(?:#.*)?$")


def _document_spans(text: str) -> list[tuple[int, int]]:
    """Each YAML document's 1-based line span, split on the stream's own `---` separators."""
    lines = text.splitlines()
    spans: list[tuple[int, int]] = []
    start = 1
    for number, line in enumerate(lines, start=1):
        if _SEPARATOR.match(line.strip()):
            if number > start:
                spans.append((start, number - 1))
            start = number + 1
    if start <= len(lines):
        spans.append((start, len(lines)))
    return spans


def _span_for(
    name: str, kind: str, spans: list[tuple[int, int]], lines: list[str]
) -> tuple[int, int]:
    """The document span naming this object, by its own `name:` line, with the honest fallback."""
    needle = re.compile(rf"^\s*name:\s*[\"']?{re.escape(name)}[\"']?\s*$")
    kindline = re.compile(rf"^\s*kind:\s*[\"']?{re.escape(kind)}[\"']?\s*$")
    for start, end in spans:
        block = lines[start - 1 : end]
        if any(needle.match(line) for line in block) and any(
            kindline.match(line) for line in block
        ):
            return (start, end)
    return (1, len(lines))


def seed_kubernetes_context(handle: AssessmentHandle, document: SourceDocument) -> ConvertedContext:
    """Parse one manifest stream and persist what it states, through the proposal path."""
    text = handle.artifacts.read("sources", document.filename).decode("utf-8")
    parsed = parse_kubernetes(text, media_type=document.media_type)
    lines = text.splitlines()
    spans = _document_spans(text) if document.media_type is MediaType.YAML else [(1, len(lines))]
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
        for index, declared in enumerate(parsed.objects):
            span = _span_for(declared.name, declared.kind, spans, lines)
            evidence_id = evidence_for(span, f"{declared.kind}.{declared.name}")
            key = f"cmp_k8s_{index}"
            components.append(
                {
                    "key": key,
                    "name": declared.name.replace("-", " ").replace("_", " "),
                    "component_type": _KINDS[declared.kind],
                    "description": f"Declared in {document.filename} as a {declared.kind}.",
                    "evidence_ids": [evidence_id],
                }
            )
            for attribute, value in declared.stated:
                claims.append(
                    {
                        "key": f"clm_k8s_{index}_{attribute.casefold()}",
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
            generated_by=KUBERNETES_PARSER,
            source_origin=SourceOrigin.STRUCTURED_INPUT,
        )
        for obj in converted.all_objects():
            repository.save(obj)
    return converted
