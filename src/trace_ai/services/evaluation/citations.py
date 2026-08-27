"""Whether a baseline's cited passage can be found in the document it claims to quote.

The comparison table's evidence row said the baselines link no claim to evidence because their
schema carries no evidence field. That was wrong about the schema: `BaselineFinding.evidence_quote`
is required and non-empty, so every baseline finding cites a passage. The real difference is
narrower and worth measuring rather than asserting -- a baseline's citation is a string the model
produced, and Trace's is an `EvidenceReference` that resolves to a stored excerpt whose hash still
verifies. One can be checked by a machine; the other has to be believed.

**This measures resolvability, not honesty.** A quote that does not match is usually not invented:
inspection of the corpus shows most misses are two real passages concatenated into one quote, a
passage carrying its markdown emphasis, an elision written as an ellipsis, or a `From <file>:`
prefix the model added. Those are all reasonable things for a person to write and none of them is
a citation a machine can resolve, which is the property being measured. The page this renders says
so, because a reader who takes the number as a fabrication rate has been misled by it.

**Normalization is deliberately shallow**, and every step exists because the corpus contains it:
surrounding quotation marks (models wrap the quote in literal quote characters), curly quotes and
apostrophes, en and em dashes, and whitespace runs -- Markdown wraps lines, so a quote spanning a
line break is the same passage. Nothing here does fuzzy matching, and that is the point: a
tolerance wide enough to accept a paraphrase would stop measuring resolvability.

Metrics and identifiers only reach the rendered page (DEC-076). The quotes themselves are
assessment content and stay out of it, so a miss is reported as a count and a scenario name.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from trace_ai.services.evaluation.registry import CLEAN_CONDITION, load_registry

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence
    from datetime import datetime
    from pathlib import Path

    from trace_ai.services.evaluation.registry import Scenario

__all__ = [
    "BASELINE_ORDER",
    "CitationOutcome",
    "CorpusOutcome",
    "measure_corpus",
    "normalize",
    "render_citation_fidelity",
]

BASELINE_ORDER: tuple[str, ...] = (
    "baseline-generic",
    "baseline-structured",
    "baseline-single-pass",
)
"""The three DEC-074/DEC-126 baselines, in the order the comparison table lists them."""

# Written as escapes rather than literals: this module's subject is exactly these
# characters, and a linter that cannot tell them apart from their ASCII lookalikes is
# making the same point the normalization exists to handle.
_QUOTE_CHARS = "\"'\u201c\u201d\u2018\u2019\u00ab\u00bb"
_SMART = {
    "\u201c": '"',  # left double quotation mark
    "\u201d": '"',  # right double quotation mark
    "\u2018": "'",  # left single quotation mark
    "\u2019": "'",  # right single quotation mark
    "\u2013": "-",  # en dash
    "\u2014": "-",  # em dash
    "\u2212": "-",  # minus sign
    "\u00a0": " ",  # no-break space
}


def normalize(text: str) -> str:
    """The shallow normalization the match runs under.

    See the module docstring for why each step is here and why there are no others.
    """
    for source, target in _SMART.items():
        text = text.replace(source, target)
    text = text.strip().strip(_QUOTE_CHARS).strip()
    return re.sub(r"\s+", " ", text).casefold()


def _quotes(payload: Any) -> Iterator[str]:
    """Every `evidence_quote` in a recorded baseline response, whichever schema produced it."""
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key == "evidence_quote" and isinstance(value, str):
                yield value
            else:
                yield from _quotes(value)
    elif isinstance(payload, list):
        for value in payload:
            yield from _quotes(value)


@dataclass(slots=True)
class CitationOutcome:
    """One baseline's citations on one scenario, as counts."""

    scenario: str
    baseline: str
    quoted: int = 0
    resolved: int = 0

    @property
    def unresolved(self) -> int:
        return self.quoted - self.resolved


@dataclass(slots=True)
class CorpusOutcome:
    """Every scenario measured, with the per-baseline totals the page leads with."""

    outcomes: list[CitationOutcome] = field(default_factory=list)

    def totals(self, baseline: str) -> tuple[int, int]:
        rows = [row for row in self.outcomes if row.baseline == baseline]
        return sum(row.quoted for row in rows), sum(row.resolved for row in rows)

    @property
    def scenarios(self) -> int:
        return len({row.scenario for row in self.outcomes})


def _corpus_text(entry: Scenario) -> str:
    """Every document the clean run sees, normalized once and joined by a separator no quote can
    span -- so a citation cannot resolve by straddling two documents."""
    parts = [
        normalize(path.read_text(encoding="utf-8", errors="replace"))
        for path in entry.input_documents(CLEAN_CONDITION)
    ]
    return "\n \n".join(parts)


def measure_corpus(registry_path: Path | None = None) -> CorpusOutcome:
    """Measure every registered scenario that carries committed baseline recordings."""
    outcome = CorpusOutcome()
    for entry in load_registry(registry_path):
        recorded = entry.recorded_dir / "baselines"
        if not recorded.is_dir():
            continue
        corpus = _corpus_text(entry)
        for baseline in BASELINE_ORDER:
            path = recorded / f"{baseline}.json"
            if not path.is_file():
                continue
            row = CitationOutcome(scenario=entry.slug, baseline=baseline)
            for quote in _quotes(json.loads(path.read_text(encoding="utf-8"))):
                normalized = normalize(quote)
                if not normalized:
                    continue
                row.quoted += 1
                if normalized in corpus:
                    row.resolved += 1
            outcome.outcomes.append(row)
    return outcome


def _pct(numerator: int, denominator: int) -> str:
    return "—" if not denominator else f"{numerator / denominator * 100:.0f}%"


def render_citation_fidelity(
    outcome: CorpusOutcome, *, generated_at: datetime, pins: Sequence[str] = ()
) -> str:
    """Render the measurement as Markdown.

    Counts and identifiers only, never the quoted text (DEC-076): a quote is assessment content
    whether or not it resolves.
    """
    rows = []
    for baseline in BASELINE_ORDER:
        quoted, resolved = outcome.totals(baseline)
        rows.append(f"| `{baseline}` | {quoted} | {resolved} | {_pct(resolved, quoted)} |")

    per_scenario = [
        "| Scenario | " + " | ".join(f"`{name}`" for name in BASELINE_ORDER) + " |",
        "| --- | " + " | ".join("---" for _ in BASELINE_ORDER) + " |",
    ]
    for slug in sorted({row.scenario for row in outcome.outcomes}):
        cells = []
        for baseline in BASELINE_ORDER:
            match = [
                row for row in outcome.outcomes if row.scenario == slug and row.baseline == baseline
            ]
            # A dash for "produced no citations", never 0/0: the baseline found nothing to
            # cite, which is not a resolution rate of zero (DEC-150's rule, one page over).
            cells.append(
                "—"
                if not match or not match[0].quoted
                else f"{match[0].resolved}/{match[0].quoted}"
            )
        per_scenario.append(f"| {slug} | " + " | ".join(cells) + " |")

    pin_text = f" ({', '.join(pins)})" if pins else ""
    body = chr(10).join(rows)
    detail = chr(10).join(per_scenario)
    return f"""<!-- Generated by scripts/build_citation_fidelity.py -- do not edit by hand. -->
# Can a baseline's citation be resolved?

Every finding a one-call baseline produces carries a required `evidence_quote`
(`domain/proposals/baseline.py`), so the baselines do cite passages. This measures whether the
passage can be found: a citation resolves when its text appears verbatim in one of the documents
the run was given, under the shallow normalization `services/evaluation/citations.py` documents --
surrounding quotation marks, smart quotes, dashes, and whitespace runs, and nothing else.

Regenerated offline from the committed baseline recordings by
`scripts/build_citation_fidelity.py` -- no provider, no key, no network. Counts and identifiers
only, no quoted text (DEC-076). Generated {generated_at.date().isoformat()} over \
{outcome.scenarios} scenarios{pin_text}.

| Tool | Citations | Resolve verbatim | Rate |
| --- | --- | --- | --- |
{body}

**Trace's figure is 100%, and it is a different kind of number.** A `Finding` cites
`EvidenceReference` identifiers, each resolving to a stored excerpt whose content hash is
re-verified on read, and `finding_evidence_coverage` reports every approved finding in the corpus
resolving. A baseline's citation is a string with no referent -- there is nothing to resolve it
*to*, so the measurement above has to go looking for it in the documents. That asymmetry is what
the comparison's evidence row is claiming, and it is a stronger claim than the row's earlier
wording, which said a baseline could not cite a document even in principle. It can. What it cannot
do is hand a reader a citation a machine will check.

**This is not a fabrication rate.** A citation that does not resolve is usually two real passages
concatenated, a passage carrying its markdown emphasis, an elision written as an ellipsis, or a
`From <file>:` prefix the model supplied. Every one of those is a reasonable thing for a person to
write and none is a reference a program can follow. Read the number as what it is: the share of
citations that survive automated checking.

## Per scenario

Resolved over cited, per baseline.

{detail}
"""
