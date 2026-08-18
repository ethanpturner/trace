"""The Mermaid DFD import: the export dialect's flowchart subset as documented claims (#599).

`trace export mermaid` (DEC-072, #503) emits a deterministic flowchart dialect from approved
state; this module reads that same subset back — the DEC-070 family's sixth member, and
future-features 7.3's first slice, taken without a vision model: a diagram whose grammar is known
parses deterministically, and everything diagram analysis must not do is structurally impossible
here, because the parser only proposes. Components, component-to-component flows, and
trust-boundary membership enter as candidates with `structured_input` provenance, validated and
decided at checkpoint 1 like every other structured artifact (DEC-115's rule). A diagram that
disagrees with prose surfaces through the cross-claim observations (DEC-070's #526 machinery),
never through precedence: two asserted statements about one fact disagree, and a reviewer
decides which stands.

**Only the export dialect parses.** Node declarations, stadium-shaped actor nodes, quoted edge
labels, subgraph boundaries, and the three arrow forms the exporter emits. A hand-drawn diagram
in the wild — sequence diagrams, class diagrams, styling, chained edges — stays Research
(future-features 7.3); any line outside the subset yields nothing, and a file that is not a
flowchart at all is refused by `parse_mermaid`.

**What cannot round-trip, and how that is honest.** The dialect carries names, direction, and
grouping — no protocols, no authentication, no encryption, no classifications. Everything the
diagram does not say imports as absent or `unknown`, never as a stated negative (the DEC-120
boolean rule, applied to a format that has no booleans at all). Actor nodes are recognized and
deliberately not seeded: the family's seeding contract carries components, flows, and claims,
and widening it is its own change (the TM-BOM precedent). An edge with `unknown` direction —
the exporter's dotted, undirected form — imports as a flow whose direction is `unknown`,
exactly the claim the diagram makes.
"""

from __future__ import annotations

import re
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

__all__ = ["MERMAID_PARSER", "looks_like_mermaid", "parse_mermaid", "seed_mermaid_context"]

MERMAID_PARSER: Final = "mermaid-dfd-parser-v1"

_NON_KEY: Final = re.compile(r"[^a-z0-9]+")

# The export dialect, one pattern per line form the exporter emits. Labels are quoted and the
# exporter escapes `"` as `#quot;`; the patterns require the quotes, so an unquoted or styled
# node is outside the subset and yields nothing.
_HEADER: Final = re.compile(r"^flowchart\s+\w+\s*$")
_SUBGRAPH: Final = re.compile(r'^subgraph\s+(?P<name>[\w-]+)\["(?P<label>[^"]*)"\]\s*$')
_END: Final = re.compile(r"^end\s*$")
_ACTOR: Final = re.compile(r'^(?P<name>[\w-]+)\(\["(?P<label>[^"]*)"\]\)\s*$')
_NODE: Final = re.compile(r'^(?P<name>[\w-]+)\["(?P<label>[^"]*)"\]\s*$')
_EDGE: Final = re.compile(
    r'^(?P<source>[\w-]+)\s+(?P<arrow><-->|-->|-\.-)\|"(?P<label>[^"]*)"\|\s+'
    r"(?P<destination>[\w-]+)\s*$"
)

_DIRECTIONS: Final = {"-->": "one_way", "<-->": "bidirectional", "-.-": "unknown"}


def looks_like_mermaid(document: SourceDocument) -> bool:
    """Whether this registered document is a Mermaid diagram, by extension and type.

    `.mmd` ingests as plain text (the `.tf` shape, DEC-121); the suffix is the whole test,
    matching the exporter's own content-addressed names (`architecture-<digest>.mmd`) and any
    corpus name that keeps the extension. Content is never sniffed (section 5.4).
    """
    if document.media_type is not MediaType.PLAIN_TEXT:
        return False
    return document.filename.rpartition("/")[2].casefold().endswith(".mmd")


def _unescaped(label: str) -> str:
    return label.replace("#quot;", '"').strip()


def _key_of(symbolic_name: str) -> str:
    """A local key for one diagram node name.

    The `mmd` prefix is load-bearing for the same reason `tmb` is (DEC-120): a Trace export
    uses allocated identifiers as node names (`cmp-001`), and the proposal schema refuses a
    key shaped like an identifier (DEC-018).
    """
    slug = _NON_KEY.sub("_", symbolic_name.casefold()).strip("_")
    return f"mmd_{slug}" if slug else "mmd_unnamed"


def parse_mermaid(text: str) -> dict[str, Any]:
    """The diagram as nodes, actors, edges, and boundaries, with 1-based line numbers.

    Raises `ValueError` when the file is not a flowchart at all; a flowchart whose lines fall
    outside the export subset parses to whatever subset lines it does contain.
    """
    lines = text.splitlines()
    stripped = [(number, line.strip()) for number, line in enumerate(lines, start=1)]
    meaningful = [(number, line) for number, line in stripped if line]
    if not meaningful or not _HEADER.match(meaningful[0][1]):
        raise ValueError("not the Mermaid export dialect: the first line is not `flowchart`")

    nodes: dict[str, dict[str, Any]] = {}
    actors: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, Any]] = []
    boundaries: list[dict[str, Any]] = []
    boundary: dict[str, Any] | None = None

    for number, line in meaningful[1:]:
        if matched := _SUBGRAPH.match(line):
            boundary = {
                "name": matched["name"],
                "label": _unescaped(matched["label"]),
                "members": [],
                "start_line": number,
                "end_line": number,
            }
            continue
        if _END.match(line):
            if boundary is not None:
                boundary["end_line"] = number
                boundaries.append(boundary)
                boundary = None
            continue
        if matched := _ACTOR.match(line):
            actors.setdefault(
                matched["name"], {"label": _unescaped(matched["label"]), "line": number}
            )
            continue
        if matched := _NODE.match(line):
            name = matched["name"]
            nodes.setdefault(name, {"label": _unescaped(matched["label"]), "line": number})
            if boundary is not None:
                boundary["members"].append(name)
            continue
        if matched := _EDGE.match(line):
            edges.append(
                {
                    "source": matched["source"],
                    "destination": matched["destination"],
                    "label": _unescaped(matched["label"]),
                    "direction": _DIRECTIONS[matched["arrow"]],
                    "line": number,
                }
            )
    return {"nodes": nodes, "actors": actors, "edges": edges, "boundaries": boundaries}


def seed_mermaid_context(handle: AssessmentHandle, document: SourceDocument) -> ConvertedContext:
    """Parse one diagram and persist what it states, through the proposal path.

    One component per node; one flow per component-to-component edge, its arrow form as the
    stated direction; one documented claim per subgraph recording the boundary's membership.
    Actor nodes and edges touching them seed nothing (the seeding contract carries components,
    flows, and claims), and the diagram states nothing else.
    """
    text = handle.artifacts.read("sources", document.filename).decode("utf-8")
    parsed = parse_mermaid(text)
    lines = text.splitlines()
    stamped = now()

    repository = handle.objects
    with repository.transaction():

        def evidence_for(start: int, end: int, label: str) -> str:
            excerpt = "\n".join(lines[start - 1 : end]) or text
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

        key_by_name = {name: _key_of(name) for name in parsed["nodes"]}
        components = [
            {
                "key": key_by_name[name],
                "name": node["label"] or name,
                "component_type": "component",
                "evidence_ids": [evidence_for(node["line"], node["line"], f"node.{name}")],
            }
            for name, node in parsed["nodes"].items()
        ]

        flows = []
        for edge in parsed["edges"]:
            source_key = key_by_name.get(edge["source"])
            destination_key = key_by_name.get(edge["destination"])
            if not source_key or not destination_key or source_key == destination_key:
                continue
            flows.append(
                {
                    "key": _key_of(f"{edge['source']} {edge['label']} {edge['destination']}"),
                    "name": edge["label"] or f"{edge['source']} to {edge['destination']}",
                    "source_component_key": source_key,
                    "destination_component_key": destination_key,
                    "direction": edge["direction"],
                    "evidence_ids": [evidence_for(edge["line"], edge["line"], "edge")],
                }
            )

        claims = []
        for index, entry in enumerate(parsed["boundaries"]):
            members = sorted(
                parsed["nodes"][name]["label"] or name
                for name in entry["members"]
                if name in parsed["nodes"]
            )
            if not members:
                continue
            claims.append(
                {
                    "key": f"mmd_boundary_{index}",
                    "subject_type": "system",
                    "predicate": f"trust boundary members: {entry['label'] or entry['name']}",
                    "value": ", ".join(members),
                    "status": "documented",
                    "confidence": "medium",
                    "evidence_ids": [
                        evidence_for(
                            entry["start_line"], entry["end_line"], f"subgraph.{entry['name']}"
                        )
                    ],
                }
            )

        proposal = ContextExtractionProposal.model_validate(
            {
                "system": {"system_name": document.filename.rpartition("/")[2]},
                "claims": claims,
                "components": components,
                "actors": [],
                "assets": [],
                "data_flows": flows,
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
            generated_by=MERMAID_PARSER,
            source_origin=SourceOrigin.STRUCTURED_INPUT,
        )
        for obj in converted.all_objects():
            repository.save(obj)
    return converted
