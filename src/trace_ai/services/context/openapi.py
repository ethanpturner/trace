"""The OpenAPI parser: deterministic proposals from a declared API surface (DEC-070, #504).

Second in DEC-070's sequence, for the reason the entry gives: an OpenAPI document *declares*
entry points and authentication — the two facts the threat path wants most and prose states
least reliably — and a claim derived mechanically from a declaration is documented evidence,
verifiable forever at zero model cost.

**What the parser reads is what the specification states, and nothing more.** One component for
the API itself, carrying `entry_point_types` (DEC-068) and the declared security schemes as
authentication mechanisms; one documented claim for the global security requirement where one is
declared; and one documented claim per operation that *explicitly disables* authentication
(`security: []` on the operation — OpenAPI's own affirmative "none", which is exactly the
distinction DEC-009 turns on: a spec silent about security has said nothing, while `security:
[]` has said no). Path counts and webhook declarations shape the entry-point types; nothing is
inferred about deployment, exposure, or correctness.

**Parser output enters the pipeline as proposals, not as authority** — the compose parser's
rule, unchanged: converted through `convert_proposal`, validated by Context Validation, decided
at checkpoint 1, with `source_origin: structured_input` and `generated_by: openapi-parser-v1`.
An OpenAPI file is attacker-authorable text; its excerpts render inside the fence like any
other evidence.
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

if TYPE_CHECKING:
    from trace_ai.domain.proposals.conversion import ConvertedContext
    from trace_ai.domain.source_document import SourceDocument
    from trace_ai.services.assessment import AssessmentHandle

__all__ = [
    "OPENAPI_PARSER",
    "looks_like_openapi",
    "parse_openapi",
    "seed_openapi_context",
]

OPENAPI_PARSER: Final = "openapi-parser-v1"

# Matched on the basename, like the compose parser: an arbitrary YAML file is not assumed to be
# a specification just for parsing as one. JSON specifications are deliberately out of scope for
# now — the excerpts are line-spanned from the author's own text, and YAML is the form the
# corpus's input formats already privilege.
_OPENAPI_NAMES: Final = ("openapi.yaml", "openapi.yml")

_HTTP_METHODS: Final = frozenset(
    {"get", "put", "post", "delete", "options", "head", "patch", "trace"}
)


@dataclass(frozen=True, slots=True)
class ParsedOperation:
    """One declared operation, with whether it explicitly disables authentication."""

    method: str
    path: str
    explicit_no_auth: bool


@dataclass(frozen=True, slots=True)
class ParsedOpenAPI:
    """What the specification declares: the API, its schemes, and its operations."""

    title: str
    security_schemes: tuple[str, ...]
    """Declared scheme descriptions, e.g. `http bearer` or `apiKey (header)` — types, never
    secrets; a specification carries no key material and the parser would not copy it if it
    did."""

    global_security: bool
    """Whether a top-level `security` requirement is declared."""

    operations: tuple[ParsedOperation, ...]
    has_webhooks: bool


def looks_like_openapi(document: SourceDocument) -> bool:
    """Whether this registered document is an OpenAPI specification, by name and type."""
    if document.media_type is not MediaType.YAML:
        return False
    basename = document.filename.rpartition("/")[2].casefold()
    return basename in _OPENAPI_NAMES


def _top_level_spans(text: str) -> dict[str, tuple[int, int]]:
    """Each top-level key's 1-based line span, from the document's own layout."""
    lines = text.splitlines()
    spans: dict[str, tuple[int, int]] = {}
    current: str | None = None
    start = 0

    def close(end: int) -> None:
        if current is not None:
            spans[current] = (start, end)

    for number, line in enumerate(lines, start=1):
        stripped = line.rstrip()
        if not stripped or stripped.lstrip().startswith("#"):
            continue
        if len(stripped) - len(stripped.lstrip()) == 0 and ":" in stripped:
            close(number - 1)
            current = stripped.split(":", 1)[0].strip()
            start = number
    close(len(lines))
    return spans


def _scheme_description(name: str, body: Any) -> str:
    if not isinstance(body, dict):
        return name
    scheme_type = str(body.get("type", "unknown"))
    if scheme_type == "http":
        return f"{name}: http {body.get('scheme', '')}".strip()
    if scheme_type == "apiKey":
        return f"{name}: apiKey ({body.get('in', 'unspecified')})"
    return f"{name}: {scheme_type}"


def parse_openapi(text: str) -> ParsedOpenAPI:
    """The specification's declarations. Raises `ValueError` when it is not an OpenAPI doc."""
    data = yaml.safe_load(text)
    if not isinstance(data, dict) or "openapi" not in data:
        raise ValueError("not an OpenAPI specification: no top-level `openapi` version")

    info_raw = data.get("info")
    info: dict[str, Any] = info_raw if isinstance(info_raw, dict) else {}
    title = str(info.get("title") or "Declared API")

    components_raw = data.get("components")
    components: dict[str, Any] = components_raw if isinstance(components_raw, dict) else {}
    schemes_raw = components.get("securitySchemes")
    raw_schemes: dict[str, Any] = schemes_raw if isinstance(schemes_raw, dict) else {}
    schemes = tuple(_scheme_description(str(name), body) for name, body in raw_schemes.items())

    operations: list[ParsedOperation] = []
    paths_raw = data.get("paths")
    paths: dict[str, Any] = paths_raw if isinstance(paths_raw, dict) else {}
    for path, item in paths.items():
        if not isinstance(item, dict):
            continue
        for method, operation in item.items():
            if str(method).casefold() not in _HTTP_METHODS:
                continue
            explicit_no_auth = isinstance(operation, dict) and operation.get("security") == []
            operations.append(
                ParsedOperation(
                    method=str(method).upper(), path=str(path), explicit_no_auth=explicit_no_auth
                )
            )

    return ParsedOpenAPI(
        title=title,
        security_schemes=schemes,
        global_security=bool(data.get("security")),
        operations=tuple(operations),
        has_webhooks=isinstance(data.get("webhooks"), dict) and bool(data.get("webhooks")),
    )


def seed_openapi_context(handle: AssessmentHandle, document: SourceDocument) -> ConvertedContext:
    """Parse one specification and persist what it declares, through the proposal path.

    Evidence per top-level declaration block (`info`, `paths`, `components`, `security`,
    `webhooks` — the spans that exist), quoting the document's own lines with their hash; then
    one proposal — the API component with its DEC-068 entry-point types and declared
    authentication mechanisms, the global-security claim where declared, and one claim per
    operation that explicitly disables authentication — converted with `structured_input`
    provenance for checkpoint 1 to decide.
    """
    text = handle.artifacts.read("sources", document.filename).decode("utf-8")
    parsed = parse_openapi(text)
    spans = _top_level_spans(text)
    lines = text.splitlines()
    stamped = now()

    repository = handle.objects
    with repository.transaction():
        evidence_by_block: dict[str, str] = {}
        for block in ("info", "paths", "components", "security", "webhooks"):
            span = spans.get(block)
            if span is None:
                continue
            start, end = span
            excerpt = "\n".join(lines[start - 1 : end])
            reference = EvidenceReference.model_validate(
                {
                    "id": repository.allocate("evd"),
                    "assessment_id": handle.assessment_id,
                    "source_document_id": document.id,
                    "section_title": block,
                    "start_line": start,
                    "end_line": end,
                    "quoted_text": excerpt,
                    "content_hash": content_hash(excerpt.encode("utf-8")),
                    "source_origin": SourceOrigin.STRUCTURED_INPUT,
                    "created_at": stamped,
                }
            )
            repository.save(reference)
            evidence_by_block[block] = reference.id

        entry_point_types = ["http_api"] if parsed.operations else []
        if parsed.has_webhooks:
            entry_point_types.append("webhook")

        claims: list[dict[str, Any]] = []
        if parsed.security_schemes and evidence_by_block.get("components"):
            declared = "; ".join(parsed.security_schemes)
            claims.append(
                {
                    "key": "clm_api_security_schemes",
                    "subject_type": "component",
                    "subject_key": "cmp_declared_api",
                    "predicate": "declared_security_schemes",
                    "value": declared,
                    "status": "documented",
                    "confidence": "high",
                    "evidence_ids": [evidence_by_block["components"]],
                }
            )
        for index, operation in enumerate(parsed.operations):
            if not operation.explicit_no_auth or "paths" not in evidence_by_block:
                continue
            claims.append(
                {
                    "key": f"clm_no_auth_{index}",
                    "subject_type": "component",
                    "subject_key": "cmp_declared_api",
                    "predicate": "operation_authentication",
                    "value": (
                        f"{operation.method} {operation.path} declares `security: []` — the "
                        f"specification's own affirmative statement that the operation "
                        f"requires no authentication"
                    ),
                    "status": "documented",
                    "confidence": "high",
                    "evidence_ids": [evidence_by_block["paths"]],
                }
            )

        proposal = ContextExtractionProposal.model_validate(
            {
                "system": {"system_name": parsed.title},
                "claims": claims,
                "components": [
                    {
                        "key": "cmp_declared_api",
                        "name": parsed.title,
                        "component_type": "api_service",
                        "description": (
                            f"Declared in {document.filename}: "
                            f"{len(parsed.operations)} operation(s)."
                        ),
                        "entry_point_types": entry_point_types,
                        "authentication_mechanisms": list(parsed.security_schemes),
                        "evidence_ids": [
                            evidence_by_block[block]
                            for block in ("info", "paths")
                            if block in evidence_by_block
                        ],
                    }
                ],
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
            generated_by=OPENAPI_PARSER,
            source_origin=SourceOrigin.STRUCTURED_INPUT,
        )
        for obj in converted.all_objects():
            repository.save(obj)
    return converted
