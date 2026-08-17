"""The assessment comparison report: the diff, in prose a reviewer reads (DEC-103, #509).

`trace diff` produces the structural diff — families, fingerprints, changed field names. This
renders it as the narrative layer future-features 13.3 asked for: the artifact a reviewer opens
to answer "what changed between these two approved models, and does it matter", ordered so the
things that change a conclusion come first.

**It is an output artifact, not a report.** DEC-035's sixteen-section report contract and
`templates/report-v1.md` are untouched; this is Markdown written to the newer assessment's
`outputs/`, content-addressed, exactly as the exports are. It carries no prose of its own beyond
the diff — every line is derived from the two approved models — and adds no conclusion the diff
did not already draw.

**Findings and questions lead; context follows.** A changed or removed finding is what a
reviewer re-reviews first; a new open question is what they answer next; context movement is the
supporting detail. The order is fixed here so two comparisons of the same pair read the same.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from trace_ai.services.diff.assessments import diff_assessments

if TYPE_CHECKING:
    from pathlib import Path

    from trace_ai.services.assessment import AssessmentHandle
    from trace_ai.services.diff.assessments import AssessmentDiff, FamilyDiff

__all__ = ["render_comparison_report", "write_comparison_report"]

# Families in the order a reviewer acts on them: what changes a conclusion first, context last.
_ORDER: tuple[tuple[str, str], ...] = (
    ("findings", "Findings"),
    ("open_questions", "Open questions"),
    ("documentation_gaps", "Documentation gaps"),
    ("threats", "Threats"),
    ("components", "Components"),
    ("actors", "Actors"),
    ("assets", "Assets"),
    ("data_flows", "Data flows"),
    ("trust_boundaries", "Trust boundaries"),
    ("claims", "Context claims"),
)


def _family_section(title: str, family: FamilyDiff) -> list[str]:
    if not family.moved:
        return [f"- **{title}:** unchanged ({family.unchanged})."]
    lines = [f"### {title}", ""]
    if family.changed:
        lines.append(f"Changed ({len(family.changed)}):")
        lines.extend(
            f"- {entry.identity}"
            + (f" — {', '.join(entry.changed_fields)}" if entry.changed_fields else "")
            for entry in family.changed
        )
        lines.append("")
    if family.added:
        lines.append(f"Added ({len(family.added)}):")
        lines.extend(f"- {entry.identity}" for entry in family.added)
        lines.append("")
    if family.removed:
        lines.append(f"Removed ({len(family.removed)}):")
        lines.extend(f"- {entry.identity}" for entry in family.removed)
        lines.append("")
    lines.append(f"Unchanged: {family.unchanged}.")
    lines.append("")
    return lines


def render_comparison_report(diff: AssessmentDiff, *, before_name: str, after_name: str) -> str:
    """Render one assessment diff as a Markdown comparison report (DEC-103).

    Deterministic: the same diff renders byte-identically, so the artifact is content-addressed
    like the exports and two runs over the same pair agree.
    """
    lines = [
        "# Assessment comparison",
        "",
        f"Comparing **{before_name}** (`{diff.before}`) with **{after_name}** (`{diff.after}`), "
        "over the reviewer-approved models of each (DEC-097).",
        "",
    ]
    if not diff.moved:
        lines.append("The two approved models do not differ.")
        lines.append("")
        return "\n".join(lines)

    moved = [title for key, title in _ORDER if diff.families.get(key) and diff.families[key].moved]
    lines.append("What moved: " + ", ".join(moved) + ". Everything else is unchanged.")
    lines.append("")

    detail: list[str] = []
    summary: list[str] = []
    for key, title in _ORDER:
        family = diff.families.get(key)
        if family is None:
            continue
        if family.moved:
            detail.extend(_family_section(title, family))
        else:
            summary.append(f"- **{title}:** unchanged ({family.unchanged}).")

    lines.extend(detail)
    if summary:
        lines.append("## Unchanged")
        lines.append("")
        lines.extend(summary)
        lines.append("")
    return "\n".join(lines)


def write_comparison_report(before: AssessmentHandle, after: AssessmentHandle) -> Path:
    """Diff two assessments and write the comparison report to the newer one's outputs area.

    The report lands under the `after` assessment — it is that assessment's account of what
    changed since `before` — content-addressed like the exports so re-running writes a new
    artifact beside the old rather than tripping the store's no-overwrite rule.
    """
    from trace_ai.domain.assessment import Assessment
    from trace_ai.domain.hashing import content_hash

    diff = diff_assessments(before, after)
    before_name = before.objects.get(Assessment, before.assessment_id).name
    after_name = after.objects.get(Assessment, after.assessment_id).name
    markdown = render_comparison_report(diff, before_name=before_name, after_name=after_name)
    digest = content_hash(markdown.encode("utf-8")).removeprefix("sha256:")[:12]
    return after.artifacts.store_output(f"comparison-{digest}.md", markdown.encode("utf-8"))
