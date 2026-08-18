"""The org-controls parser: documented claims with catalog provenance (#528, DEC-115).

The DEC-070 family's fourth member, and the one whose input is not the system's own material:
an assessment opts in by registering an `org-controls.yaml` document naming the catalog version
and the controls asserted to bear on this system. The parser verifies the assertion against the
central catalog — the named version loads through the one reader, hash-verified, and every
asserted name must exist in it — and seeds one *documented claim* per asserted control, its
value carrying the control's own statement and its provenance (`name`, catalog version).

**An org control is never authority.** The claim says a mechanism exists organizationally,
sourced; whether this system inherits it stays the pipeline's ordinary work — the claim is
decided at checkpoint 1 like every parser product, and evidence validation still judges what
any mapping concludes from it (DEC-009 in the other direction: a documented organizational
mechanism is evidence a conclusion can rest on, not a conclusion).

**A registered document that fails verification seeds nothing.** An `org-controls.yaml` naming
an unknown version or an unknown control name is an untrusted document making an unverifiable
claim about the organization; the parser raises with the reason, the run stops with it, and the
operator fixes the document or the catalog. Silent partial seeding would let a typo drop a
control without anyone deciding to.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Final

import yaml

from trace_ai.domain.base import now
from trace_ai.domain.enums import SourceOrigin
from trace_ai.domain.evidence import EvidenceReference
from trace_ai.domain.hashing import content_hash
from trace_ai.domain.proposals import ContextExtractionProposal, convert_proposal
from trace_ai.domain.source_document import MediaType
from trace_ai.services.org_controls import load_org_controls

if TYPE_CHECKING:
    from trace_ai.domain.proposals.conversion import ConvertedContext
    from trace_ai.domain.source_document import SourceDocument
    from trace_ai.services.assessment import AssessmentHandle

__all__ = ["ORG_CONTROLS_PARSER", "looks_like_org_controls", "seed_org_controls_context"]

ORG_CONTROLS_PARSER: Final = "org-controls-parser-v1"

_BASENAME: Final = "org-controls.yaml"


def looks_like_org_controls(document: SourceDocument) -> bool:
    """Whether this registered document asserts organizational controls, by name and type.

    Suffix-matched so a corpus can prefix the name for ordering ("workspace-org-controls.yaml")
    without the parser losing it."""
    if document.media_type is not MediaType.YAML:
        return False
    return document.filename.rpartition("/")[2].casefold().endswith(_BASENAME)


def seed_org_controls_context(
    handle: AssessmentHandle, document: SourceDocument
) -> ConvertedContext:
    """Verify the assertion against the central catalog and seed its documented claims.

    Evidence quotes the registered document itself — the assertion this assessment made — and
    each claim's value carries the central catalog's statement with `(name, catalog version)`
    provenance, so the claim is traceable to both the assertion and its source.
    """
    text = handle.artifacts.read("sources", document.filename).decode("utf-8")
    parsed: Any = yaml.safe_load(text)
    body = (parsed or {}).get("org_controls_catalog")
    if not isinstance(body, dict):
        raise ValueError(f"{document.filename} has no `org_controls_catalog` mapping")
    version = str(body.get("version", ""))
    asserted_raw = body.get("asserted")
    if not version or not isinstance(asserted_raw, list) or not asserted_raw:
        raise ValueError(
            f"{document.filename} must name a catalog `version` and a non-empty `asserted` "
            f"list of control names"
        )
    catalog = load_org_controls(version)
    by_name = catalog.by_name()
    unknown = sorted(str(name) for name in asserted_raw if str(name) not in by_name)
    if unknown:
        raise ValueError(
            f"{document.filename} asserts controls the org-controls catalog {version} does "
            f"not define: {', '.join(unknown)}"
        )

    lines = text.splitlines()
    stamped = now()
    repository = handle.objects
    with repository.transaction():
        excerpt = text.strip()
        reference = EvidenceReference.model_validate(
            {
                "id": repository.allocate("evd"),
                "assessment_id": handle.assessment_id,
                "source_document_id": document.id,
                "section_title": "org_controls_catalog",
                "start_line": 1,
                "end_line": len(lines),
                "quoted_text": excerpt,
                "content_hash": content_hash(excerpt.encode("utf-8")),
                "source_origin": SourceOrigin.STRUCTURED_INPUT,
                "created_at": stamped,
            }
        )
        repository.save(reference)

        claims = [
            {
                "key": f"clm_org_{index}",
                "subject_type": "system",
                "predicate": "organizational_control",
                "value": (
                    f"{control.name} (org-controls catalog {catalog.version}): "
                    f"{control.title}. {' '.join(control.statement.split())} "
                    f"Mechanism: {control.mechanism}."
                ),
                "status": "documented",
                "confidence": "high",
                "evidence_ids": [reference.id],
            }
            for index, control in enumerate(by_name[str(name)] for name in asserted_raw)
        ]

        proposal = ContextExtractionProposal.model_validate(
            {
                "system": {"system_name": "Organizational controls"},
                "claims": claims,
                "components": [],
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
            generated_by=ORG_CONTROLS_PARSER,
            source_origin=SourceOrigin.STRUCTURED_INPUT,
        )
        for obj in converted.all_objects():
            repository.save(obj)
    return converted
