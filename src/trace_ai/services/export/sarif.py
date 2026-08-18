"""The SARIF export: approved findings as a static-analysis interchange log (DEC-072, #487).

SARIF 2.1.0 is the format security tooling actually ingests, and DEC-072 ordered it second in
the serializer family after TM-BOM. This module follows the family's rules exactly: a
post-approval serializer that refuses an assessment whose context no reviewer approved, reads
approved objects only, rewrites no approved text, and writes to the assessment's `outputs/`
area, content-addressed.

**The mapping keeps DEC-009's distinction structural.** A `Finding` — evidence supports a
weakness — becomes a SARIF result whose `level` follows the reviewer-assigned severity. A
`DocumentationGap` — it cannot be determined whether a control exists — becomes a result of
`kind: "review"` at `level: "none"`: SARIF's own vocabulary for "a human should look at this",
never an error or a warning, because a gap asserts nothing about the implementation. Collapsing
the two in an export would reintroduce exactly the failure the distinction exists to prevent.

**Rules are the cited requirements.** Each distinct requirement an approved finding or a gap's
mapping names becomes one `rule`, titled from the assessment's pinned catalog version where it
resolves; a requirement the catalog cannot resolve still appears as a bare rule identifier
rather than being dropped. Requirement text is originally written (the catalog's own rule), so
titles serialize verbatim.

**Locations come from the evidence chain.** Each result carries a physical location per
evidence reference — the stored filename and line span the reviewer saw — and a logical
location per affected component. `EvidenceReference.id` rides `partialFingerprints` beside the
DEC-066 finding fingerprint, so two exports of the same run identify the same result.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Final

from trace_ai.domain.component import Component
from trace_ai.domain.control_mapping import ControlMapping
from trace_ai.domain.documentation_gap import DocumentationGap
from trace_ai.domain.enums import ObjectStatus, Severity
from trace_ai.domain.evidence import EvidenceReference
from trace_ai.domain.source_document import SourceDocument
from trace_ai.services.export.tm_bom import ExportError
from trace_ai.services.findings.approved import approved_findings
from trace_ai.workflow.context_review import current_system_context

if TYPE_CHECKING:
    from pathlib import Path

    from trace_ai.domain.finding import Finding
    from trace_ai.services.assessment import AssessmentHandle

__all__ = ["SARIF_VERSION", "export_sarif", "write_sarif"]

SARIF_VERSION: Final = "2.1.0"
_SCHEMA_URI: Final = "https://json.schemastore.org/sarif-2.1.0.json"

# The reviewer's severity on SARIF's four-level vocabulary. `unassigned` cannot appear: an
# approval carrying it is refused at the checkpoint, and this exporter reads approved findings.
_LEVEL_BY_SEVERITY: Final[dict[Severity, str]] = {
    Severity.CRITICAL: "error",
    Severity.HIGH: "error",
    Severity.MEDIUM: "warning",
    Severity.LOW: "note",
    Severity.INFORMATIONAL: "note",
}


def export_sarif(handle: AssessmentHandle) -> dict[str, Any]:
    """Serialize the approved findings and documentation gaps as one SARIF log.

    Refuses an assessment with no approved context, like every export (DEC-072). An assessment
    whose review approved nothing exports a log with zero results, which is the honest document:
    a successful assessment may produce no findings.
    """
    try:
        context = current_system_context(handle)
    except ValueError as missing:
        raise ExportError(
            f"{handle.assessment_id} has no extracted context to export: {missing}"
        ) from None
    if not context.is_approved:
        raise ExportError(
            f"{handle.assessment_id} has no approved system context. Exports serialize approved "
            f"objects only (DEC-072); run the assessment through checkpoint 1 first."
        )

    repository = handle.objects
    findings = approved_findings(handle)
    gaps = [gap for gap in repository.list(DocumentationGap) if gap.status is ObjectStatus.APPROVED]
    requirement_by_mapping = {
        mapping.id: mapping.requirement_id for mapping in repository.list(ControlMapping)
    }
    component_names = {component.id: component.name for component in repository.list(Component)}
    filenames = {document.id: document.filename for document in repository.list(SourceDocument)}
    references = {reference.id: reference for reference in repository.list(EvidenceReference)}

    cited: list[str] = []
    for finding in findings:
        cited.extend(finding.requirement_ids)
    for gap in gaps:
        cited.extend(
            requirement_by_mapping[related]
            for related in gap.related_object_ids
            if related in requirement_by_mapping
        )

    results = [
        _finding_result(finding, references, filenames, component_names) for finding in findings
    ]
    results.extend(_gap_result(gap, requirement_by_mapping, references, filenames) for gap in gaps)

    return {
        "$schema": _SCHEMA_URI,
        "version": SARIF_VERSION,
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "trace",
                        "informationUri": "https://github.com/ethanpturner/trace",
                        "rules": _rules(cited, handle),
                    }
                },
                "results": results,
            }
        ],
    }


def _rules(cited: list[str], handle: AssessmentHandle) -> list[dict[str, Any]]:
    """One rule per distinct cited requirement, titled from the pinned catalog where it resolves.

    The catalog version comes from the assessment's own configuration (DEC-010's pinning rule);
    a catalog that cannot be loaded or a requirement it does not carry degrades to a bare rule
    identifier — the citation survives, untitled, rather than being dropped or guessed at.
    """
    from trace_ai.domain.assessment import Assessment
    from trace_ai.services.requirements.loader import CatalogError, load_catalog

    titles: dict[str, str] = {}
    assessment = handle.objects.get(Assessment, handle.assessment_id)
    version = assessment.requirements_catalog_version
    if version is not None:
        try:
            titles = {
                requirement.id: requirement.title
                for requirement in load_catalog(version).requirements
            }
        except CatalogError:
            titles = {}

    rules: list[dict[str, Any]] = []
    for requirement_id in sorted(set(cited)):
        rule: dict[str, Any] = {"id": requirement_id}
        title = titles.get(requirement_id)
        if title is not None:
            rule["shortDescription"] = {"text": title}
        rules.append(rule)
    return rules


def _locations(
    evidence_ids: list[str],
    references: dict[str, EvidenceReference],
    filenames: dict[str, str],
) -> list[dict[str, Any]]:
    locations: list[dict[str, Any]] = []
    for evidence_id in evidence_ids:
        reference = references.get(evidence_id)
        if reference is None:
            continue
        locations.append(
            {
                "physicalLocation": {
                    "artifactLocation": {
                        "uri": filenames.get(
                            reference.source_document_id, reference.source_document_id
                        )
                    },
                    "region": {
                        "startLine": reference.start_line,
                        "endLine": reference.end_line,
                    },
                }
            }
        )
    return locations


def _finding_result(
    finding: Finding,
    references: dict[str, EvidenceReference],
    filenames: dict[str, str],
    component_names: dict[str, str],
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "ruleId": sorted(finding.requirement_ids)[0] if finding.requirement_ids else "trace",
        "level": _LEVEL_BY_SEVERITY[finding.severity],
        "message": {"text": f"{finding.title}\n\n{finding.description}"},
        "partialFingerprints": {"traceAi/findingId": finding.id},
        "properties": {
            "traceAi": {
                "kind": "finding",
                "severity": finding.severity.value,
                "confidence": finding.confidence.value,
                "requirement_ids": sorted(finding.requirement_ids),
                "evidence_ids": list(finding.evidence_ids),
            }
        },
    }
    if finding.content_fingerprint is not None:
        result["partialFingerprints"]["traceAi/contentFingerprint"] = finding.content_fingerprint
    locations = _locations(list(finding.evidence_ids), references, filenames)
    logical = [
        {"logicalLocations": [{"name": component_names.get(component_id, component_id)}]}
        for component_id in finding.affected_component_ids
    ]
    if locations or logical:
        result["locations"] = locations + logical
    return result


def _gap_result(
    gap: DocumentationGap,
    requirement_by_mapping: dict[str, str],
    references: dict[str, EvidenceReference],
    filenames: dict[str, str],
) -> dict[str, Any]:
    """A documentation gap as `kind: "review"` at `level: "none"` — DEC-009, structurally.

    A gap asserts nothing about the implementation, so it is never an error or a warning; SARIF's
    `review` kind is precisely "a human should evaluate this", which is what a gap is.
    """
    requirement_ids = sorted(
        {
            requirement_by_mapping[related]
            for related in gap.related_object_ids
            if related in requirement_by_mapping
        }
    )
    result: dict[str, Any] = {
        "ruleId": requirement_ids[0] if requirement_ids else "trace",
        "kind": "review",
        "level": "none",
        "message": {"text": f"{gap.title}\n\n{gap.description}"},
        "partialFingerprints": {"traceAi/gapId": gap.id},
        "properties": {
            "traceAi": {
                "kind": "documentation-gap",
                "requirement_ids": requirement_ids,
            }
        },
    }
    locations = _locations(list(gap.evidence_ids), references, filenames)
    if locations:
        result["locations"] = locations
    return result


def write_sarif(handle: AssessmentHandle) -> Path:
    """Serialize and write the export to the assessment's outputs area, content-addressed."""
    from trace_ai.domain.hashing import content_hash

    document = export_sarif(handle)
    payload = json.dumps(document, indent=2, sort_keys=False) + "\n"
    digest = content_hash(payload.encode("utf-8")).removeprefix("sha256:")[:12]
    return handle.artifacts.store_output(f"findings-{digest}.sarif", payload.encode("utf-8"))
