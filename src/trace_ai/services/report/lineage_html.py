"""The lineage appendix for the derived HTML report: the nine-hop walk, portable (#600).

Future-features 13.1's localhost form exists three times over — DEC-078's read-only view, #533's
navigable walk, #572's click-through to the source span — and all three die when `http.server`
stops. The artifact a reviewer hands to someone is the report, so the walk travels in it: one
expandable section per approved finding, appended to the DEC-108 HTML view, carrying the chain
`data-model.md` section 32 draws — source document, evidence, context claim, threat, requirement,
control, evidence assessment, critique, reviewer decision, finding.

**Derived from persisted approved objects only.** The walk is `services/findings/lineage.py`'s
resolution over what the store holds, plus the reviewer decisions and controls those objects name.
Nothing here re-renders a report section, so DEC-035's one-owner rule is untouched: the sixteen
sections are the body, and this is an appendix the Markdown deliverable does not carry — a view
affordance, not report content, which is why its absence from the deliverable is not drift.

**The evidence leaf shows the same verification the CLI offers.** Each excerpt is re-checked
against its stored source as the page renders (`EvidenceIndex.verify`), and the verdict rendered
is that check's outcome — state, not time: the page still carries no clock, and two renders over
the same store are byte-identical. A static page cannot re-verify after it is written, and the
wording says so rather than implying a live property.

**Everything is escaped.** Finding titles, quoted excerpts, claim values, and rationales are
source-derived or reviewer-authored text; every text node passes through `html.escape`. Anchors
are namespaced `lin-` so they cannot collide with the report body's own object anchors, which are
bare lowercased identifiers by the template's rule.
"""

from __future__ import annotations

import html
from typing import TYPE_CHECKING

from trace_ai.domain.context_claim import ContextClaim
from trace_ai.domain.control import Control
from trace_ai.domain.control_mapping import ControlMapping
from trace_ai.domain.critique import Critique
from trace_ai.domain.evidence import EvidenceReference
from trace_ai.domain.evidence_assessment import EvidenceAssessment
from trace_ai.domain.reviewer_decision import ReviewerDecision
from trace_ai.domain.source_document import SourceDocument
from trace_ai.domain.threat import Threat
from trace_ai.services.evidence.index import EvidenceIndex
from trace_ai.services.findings.approved import approved_findings
from trace_ai.services.findings.lineage import finding_lineage

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

    from trace_ai.domain.finding import Finding
    from trace_ai.services.assessment import AssessmentHandle
    from trace_ai.services.evidence.index import VerificationResult
    from trace_ai.services.findings.lineage import FindingLineage

__all__ = ["UNTRUSTED_LABEL", "finding_walk_html", "lineage_appendix"]

# The same literal the read-only view and the CLI print; a test holds the three in agreement.
UNTRUSTED_LABEL = "quoted untrusted source content"


def _e(value: object) -> str:
    return html.escape(str(value), quote=False)


def _item(anchor: str, text: str) -> str:
    return f'<li><a id="lin-{_e(anchor.lower())}"></a>{text}</li>'


def _hop(label: str, items: list[str]) -> str:
    body = "".join(items) if items else "<li><em>none</em></li>"
    return f"<h4>{_e(label)}</h4><ul>{body}</ul>"


def finding_walk_html(
    finding: Finding,
    lineage: FindingLineage,
    *,
    controls_by_id: Mapping[str, Control],
    decisions: Sequence[ReviewerDecision],
    verify: Callable[[str], VerificationResult],
) -> str:
    """One finding's expandable walk, rendered from already-resolved objects.

    Pure over its inputs so the escaping discipline is testable without a store; `verify` is
    `EvidenceIndex.verify` in production and whatever a test needs it to be.
    """
    names = {doc.id: doc.filename for doc in lineage.source_documents}
    evidence_items: list[str] = []
    for reference in lineage.evidence_references:
        checked = verify(reference.id)
        verdict = "verifies" if checked.ok else checked.outcome.value
        where = (
            f", lines {reference.start_line}-{reference.end_line}"
            if reference.start_line is not None and reference.end_line is not None
            else ""
        )
        evidence_items.append(
            _item(
                reference.id,
                f"<div><code>{_e(reference.id)}</code> · "
                f"{_e(names.get(reference.source_document_id, '?'))}{_e(where)} · "
                f"checked against the stored source as this page rendered: "
                f"<strong>{_e(verdict)}</strong>"
                f"<div><em>[{_e(UNTRUSTED_LABEL)} — {_e(reference.id)}]</em></div>"
                f"<pre>{html.escape(reference.quoted_text)}</pre>"
                f"<code>{_e(reference.content_hash)}</code></div>",
            )
        )

    seen_controls: list[Control] = []
    for mapping in lineage.control_mappings:
        for control_id in mapping.control_ids:
            control = controls_by_id.get(control_id)
            if control is not None and all(c.id != control.id for c in seen_controls):
                seen_controls.append(control)

    requirement_items = [
        _item(
            mapping.id,
            f"<code>{_e(mapping.requirement_id)}</code> — "
            f"{_e(mapping.applicability_status.value)}, "
            f"{_e(mapping.satisfaction_status.value)} "
            f"(mapping <code>{_e(mapping.id)}</code>, threat "
            f'<a href="#lin-{_e(mapping.threat_id.lower())}">'
            f"<code>{_e(mapping.threat_id)}</code></a>)",
        )
        for mapping in lineage.control_mappings
    ]

    hops = [
        _hop(
            "Source documents",
            [
                _item(doc.id, f"{_e(doc.filename)} · <code>{_e(doc.content_hash)}</code>")
                for doc in lineage.source_documents
            ],
        ),
        _hop("Evidence, quoted and checked", evidence_items),
        _hop(
            "Context claims",
            [
                _item(
                    claim.id,
                    f"<code>{_e(claim.id)}</code>: {_e(claim.predicate)} = "
                    f"{_e(claim.value)} ({_e(claim.status.value)})",
                )
                for claim in lineage.context_claims
            ],
        ),
        _hop(
            "Threats",
            [
                _item(threat.id, f"<code>{_e(threat.id)}</code>: {_e(threat.title)}")
                for threat in lineage.threats
            ],
        ),
        _hop("Requirements and their mappings", requirement_items),
        _hop(
            "Controls",
            [
                _item(
                    control.id,
                    f"<code>{_e(control.id)}</code>: {_e(control.name)} "
                    f"({_e(control.control_type.value)}, "
                    f"{_e(control.implementation_status.value)}, "
                    f"{_e(control.validation_status.value)})",
                )
                for control in seen_controls
            ],
        ),
        _hop(
            "Evidence assessments",
            [
                _item(
                    assessed.id,
                    f"<code>{_e(assessed.id)}</code>: {_e(assessed.subject_type.value)} "
                    f"<code>{_e(assessed.subject_id)}</code> — "
                    f"{_e(assessed.validation_status.value)}, "
                    f"recommends {_e(assessed.recommendation.value)}",
                )
                for assessed in lineage.evidence_assessments
            ],
        ),
        _hop(
            "Critiques",
            [
                _item(
                    critique.id,
                    f"<code>{_e(critique.id)}</code>: {_e(critique.critique_type.value)} "
                    f"on <code>{_e(critique.subject_id)}</code>",
                )
                for critique in lineage.critiques
            ],
        ),
        _hop(
            "Reviewer decisions",
            [
                _item(
                    decision.id,
                    f"<code>{_e(decision.id)}</code>: {_e(decision.disposition.value)}"
                    + (f" — {_e(decision.rationale)}" if decision.rationale else ""),
                )
                for decision in decisions
            ],
        ),
        _hop(
            "Finding",
            [
                _item(
                    finding.id,
                    f"<code>{_e(finding.id)}</code>: severity {_e(finding.severity.value)}, "
                    f"{_e(finding.status.value)}, confidence {_e(finding.confidence.value)}",
                )
            ],
        ),
    ]
    summary = f"<code>{_e(finding.id)}</code> — {_e(finding.title)}"
    return f'<details class="lineage"><summary>{summary}</summary>' + "".join(hops) + "</details>"


def lineage_appendix(handle: AssessmentHandle) -> str:
    """The appendix fragment: one expandable walk per approved finding, or nothing.

    An assessment with no approved findings gets no appendix at all — an empty heading would
    imply a section the report does not have. A finding whose chain has a missing link raises
    `LineageError` out of this function, because a walk that cannot be read is a defect, not a
    sparse rendering (`services/findings/lineage.py`).
    """
    findings = approved_findings(handle)
    if not findings:
        return ""
    index = EvidenceIndex(handle)
    threats = handle.objects.list(Threat)
    mappings = handle.objects.list(ControlMapping)
    assessments = handle.objects.list(EvidenceAssessment)
    critiques = handle.objects.list(Critique)
    claims = handle.objects.list(ContextClaim)
    references = handle.objects.list(EvidenceReference)
    documents = handle.objects.list(SourceDocument)
    controls_by_id = {control.id: control for control in handle.objects.list(Control)}
    all_decisions = handle.objects.list(ReviewerDecision)
    walks = "".join(
        finding_walk_html(
            finding,
            finding_lineage(
                finding,
                threats=threats,
                control_mappings=mappings,
                evidence_assessments=assessments,
                critiques=critiques,
                context_claims=claims,
                evidence_references=references,
                source_documents=documents,
            ),
            controls_by_id=controls_by_id,
            decisions=[
                decision
                for decision in all_decisions
                if decision.subject_type == "finding" and decision.subject_id == finding.id
            ],
            verify=index.verify,
        )
        for finding in findings
    )
    return (
        '<hr><a id="lineage-appendix"></a><h2>Appendix: finding lineage</h2>'
        "<p><em>The chain below is what the store held when this page was rendered, walked "
        "from each approved finding to its hashed evidence. A static page cannot re-verify "
        "after it is written; the live view (<code>trace view</code>) re-checks on every "
        "render.</em></p>" + walks
    )
