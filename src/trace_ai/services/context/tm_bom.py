"""The TM-BOM import: a threat-model interchange file as documented claims (DEC-120, #573).

DEC-072 exported the approved model to TM-BOM and left one question open: does the format
round-trip? This module answers yes, bounded — the DEC-070 family's fifth member, reading the
schema's *context*: components, data flows between them, assumptions, and declared controls.
A TM-BOM file from Threat Dragon, another tool, or a previous Trace assessment enters the same
way every structured artifact does: proposals with `structured_input` provenance, validated by
Context Validation, decided at checkpoint 1 (DEC-115's rule — external facts enter as documented
claims, never as pre-approved authority).

**What does not import, and why.** Threats and threat personas are analysis conclusions; seeding
them as Trace threats would carry another tool's conclusions into checkpoint-2 material without
Trace's evidence chain, so they stay text the extraction agent reads like any other document.
The `extensions` block is ignored entirely: a Trace export carries its approved findings there
verbatim, and re-importing them as claims would launder one assessment's conclusions into
another's documented ground. Actors stay out of this version because the family's seeding
contract (`parsers.py`) merges components, flows, and claims only; widening it is its own change.

**TM-BOM's booleans cannot round-trip as negatives.** The exporter writes `encrypted: false` for
a flow whose encryption is *unstated*, with an assumption row saying so — the schema has no
third value. The import therefore reads `encrypted: true` as a documented claim and
`encrypted: false` as nothing at all: the boolean cannot distinguish a stated negative from
silence, and DEC-009 forbids resolving that doubt against the system. The same asymmetry governs
controls: `active` imports as a documented claim *about the declaration*, `assumed` imports as
an `assumed` claim with the file named in the rationale (never an existence assertion — the
DEC-072 note that TM-BOM makes `assumed` first-class, honoured on the way in), and `suggested`
imports as nothing, because a recommendation asserts nothing about the system.
"""

from __future__ import annotations

import json
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

__all__ = ["TM_BOM_PARSER", "looks_like_tm_bom", "parse_tm_bom", "seed_tm_bom_context"]

TM_BOM_PARSER: Final = "tm-bom-parser-v1"

# The exporter's marker zone for "no deployment zone was stated". A zone whose name says it is
# unspecified is not a stated zone, whoever wrote the file.
_UNSPECIFIED_ZONE: Final = "zone-unspecified"

_NON_KEY: Final = re.compile(r"[^a-z0-9]+")


def looks_like_tm_bom(document: SourceDocument) -> bool:
    """Whether this registered document is a TM-BOM threat model, by name and type.

    Matches the exporter's own content-addressed names (`tm-bom-<digest>.json`), the bare name,
    and a prefixed one ("workspace-tm-bom.json") — the org-controls precedent, so a corpus can
    order its files without the parser losing them.
    """
    if document.media_type is not MediaType.JSON:
        return False
    basename = document.filename.rpartition("/")[2].casefold()
    if not basename.endswith(".json"):
        return False
    return (
        basename == "tm-bom.json"
        or basename.startswith("tm-bom-")
        or basename.endswith("-tm-bom.json")
        or basename.endswith(".tm-bom.json")
    )


def _key_of(symbolic_name: str) -> str:
    """A local key for one TM-BOM symbolic name.

    The `tmb` prefix is load-bearing: a Trace export uses allocated identifiers as symbolic
    names (`cmp-001`), and the proposal schema refuses a key shaped like an identifier
    (DEC-018). Prefixed and underscored, the name reads as what it is — a local key derived
    from an imported file.
    """
    slug = _NON_KEY.sub("_", symbolic_name.casefold()).strip("_")
    return f"tmb_{slug}" if slug else "tmb_unnamed"


def parse_tm_bom(text: str) -> dict[str, Any]:
    """The document as parsed JSON. Raises `ValueError` when it is not a TM-BOM model."""
    data = json.loads(text)
    if not isinstance(data, dict) or not isinstance(data.get("scope"), dict):
        raise ValueError("not a TM-BOM threat model: no top-level `scope` mapping")
    return data


def _rows(data: dict[str, Any], field: str) -> list[dict[str, Any]]:
    listed = data.get(field)
    if not isinstance(listed, list):
        return []
    return [row for row in listed if isinstance(row, dict)]


def _spans(text: str) -> dict[str, tuple[int, int]]:
    """Each symbolic name's enclosing JSON object as a 1-based line span.

    Line-based and tolerant, like the IaC parser's: the span exists so an excerpt quotes the
    document's own lines with a hash, and an object whose span cannot be found contributes
    document-level evidence instead of a narrower quote.
    """
    lines = text.splitlines()
    spans: dict[str, tuple[int, int]] = {}
    for number, line in enumerate(lines, start=1):
        stripped = line.strip()
        if '"symbolic_name"' not in stripped:
            continue
        _, _, value = stripped.partition(":")
        name = value.strip().strip(",").strip('"')
        if not name:
            continue
        start = number
        for earlier in range(number - 1, 0, -1):
            if lines[earlier - 1].rstrip().endswith("{"):
                start = earlier
                break
        depth = 0
        end = start
        for offset, later in enumerate(lines[start - 1 :], start=start):
            depth += later.count("{") - later.count("}")
            end = offset
            if depth <= 0:
                break
        spans.setdefault(name, (start, end))
    return spans


def seed_tm_bom_context(handle: AssessmentHandle, document: SourceDocument) -> ConvertedContext:
    """Parse one TM-BOM model and persist what it states, through the proposal path.

    One component per `components` row (its stated trust zone as `deployment_zone`); one data
    flow per component-to-component `data_flows` row, `encrypted: true` becoming the flow's
    stated transport encryption and `false` becoming nothing; one claim per assumption and per
    declared control, with the epistemic status the file can honestly support.
    """
    text = handle.artifacts.read("sources", document.filename).decode("utf-8")
    data = parse_tm_bom(text)
    spans = _spans(text)
    lines = text.splitlines()
    stamped = now()

    repository = handle.objects
    with repository.transaction():

        def evidence_for(symbolic_name: str | None, label: str) -> str:
            start, end = spans.get(symbolic_name or "", (1, len(lines) or 1))
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

        components: list[dict[str, Any]] = []
        claims: list[dict[str, Any]] = []
        flows: list[dict[str, Any]] = []
        key_by_symbol: dict[str, str] = {}

        for row in _rows(data, "components"):
            symbol = str(row.get("symbolic_name") or "")
            title = str(row.get("title") or symbol)
            if not symbol or not title or symbol in key_by_symbol:
                continue
            key = _key_of(symbol)
            if key in key_by_symbol.values():
                key = f"{key}_{len(key_by_symbol)}"
            key_by_symbol[symbol] = key
            evidence_id = evidence_for(symbol, f"components.{symbol}")
            entry: dict[str, Any] = {
                "key": key,
                "name": title,
                "component_type": "component",
                "description": str(row.get("description") or "") or None,
                "evidence_ids": [evidence_id],
            }
            zone = str(row.get("trust_zone") or "")
            if zone and zone != _UNSPECIFIED_ZONE:
                entry["deployment_zone"] = zone
            components.append(entry)

        for row in _rows(data, "data_flows"):
            symbol = str(row.get("symbolic_name") or "")
            source = row.get("source") or {}
            destination = row.get("destination") or {}
            if not (isinstance(source, dict) and isinstance(destination, dict)):
                continue
            if source.get("type") != "component" or destination.get("type") != "component":
                continue
            source_key = key_by_symbol.get(str(source.get("object") or ""))
            destination_key = key_by_symbol.get(str(destination.get("object") or ""))
            if not symbol or not source_key or not destination_key:
                continue
            if source_key == destination_key:
                continue
            flow: dict[str, Any] = {
                "key": _key_of(symbol),
                "name": str(row.get("title") or symbol),
                "source_component_key": source_key,
                "destination_component_key": destination_key,
                "direction": "one_way",
                "evidence_ids": [evidence_for(symbol, f"data_flows.{symbol}")],
            }
            # `encrypted: false` yields nothing: the schema's boolean cannot distinguish a
            # stated negative from the exporter's conservative default for silence (DEC-009).
            if row.get("encrypted") is True:
                flow["encryption_in_transit"] = "encrypted"
            flows.append(flow)

        for index, row in enumerate(_rows(data, "assumptions")):
            description = str(row.get("description") or "").strip()
            if not description:
                continue
            validity = str(row.get("validity") or "unstated")
            claims.append(
                {
                    "key": f"tmb_assumption_{index}",
                    "subject_type": "system",
                    "predicate": description,
                    "value": True,
                    "status": "assumed",
                    "confidence": "low",
                    "rationale": (
                        f"Recorded as an assumption (validity {validity!r}) in the imported "
                        f"threat model {document.filename}. A foreign file's confirmation does "
                        f"not transfer; the claim stays assumed for the reviewer to settle."
                    ),
                }
            )

        for row in _rows(data, "controls"):
            symbol = str(row.get("symbolic_name") or "")
            title = str(row.get("title") or symbol)
            status = str(row.get("status") or "")
            if not title or status not in {"active", "assumed"}:
                continue
            key = f"tmb_control_{_key_of(symbol or title).removeprefix('tmb_')}"
            if status == "active":
                claims.append(
                    {
                        "key": key,
                        "subject_type": "system",
                        "predicate": "declared_control_active",
                        "value": title,
                        "status": "documented",
                        "confidence": "medium",
                        "evidence_ids": [evidence_for(symbol, f"controls.{symbol or title}")],
                    }
                )
            else:
                claims.append(
                    {
                        "key": key,
                        "subject_type": "system",
                        "predicate": "declared_control_assumed",
                        "value": title,
                        "status": "assumed",
                        "confidence": "low",
                        "rationale": (
                            f"The imported threat model {document.filename} records this "
                            f"control as assumed, not verified; the status carries over as "
                            f"assumed rather than becoming an existence assertion."
                        ),
                    }
                )

        scope = data["scope"]
        proposal = ContextExtractionProposal.model_validate(
            {
                "system": {"system_name": str(scope.get("title") or "Imported threat model")},
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
            generated_by=TM_BOM_PARSER,
            source_origin=SourceOrigin.STRUCTURED_INPUT,
        )
        for obj in converted.all_objects():
            repository.save(obj)
    return converted
