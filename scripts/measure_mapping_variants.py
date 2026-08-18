"""Measure the mapping step's input under catalog-partition variants, offline (#532, DEC-024).

DEC-024 sends the whole catalog on every mapping call and names its own open question: whether
to partition and fan out, "to be taken on cost evidence" that never existed. The live half of
that evidence waits on the keyed sweep (#484); the input half does not. The offline replay
drives the real pipeline over every registered scenario, and the mapping packages it built can
be rebuilt exactly — same context, same threats, same catalog pin, same assembler — then
re-composed under partition schemes and sized.

Three variants are sized per scenario:

- `whole` — today's shape: one call per threat, the whole catalog leading the trusted region.
- `by-category` — one call per threat per primary category (the `req-<CATEGORY>-` prefix, which
  is also how the catalog files partition), each call carrying only that category's slice.
- `halves` — one call per threat per half of the catalog, in catalog order: the coarsest
  partition, a lower bound on fan-out overhead.

Every figure is **estimated**: characters over the corpus heuristic (3.8 chars/token, the
`estimate_cost.py` midpoint), never a provider count — the DEC-092 discipline, stated in the
artifact. The cache-adjusted column prices each call's stable span (DEC-105's
`trusted_cache_prefix`) at the Anthropic write premium the first time that span occurs in the
run and at the cached-read discount after, with everything else at full rate — the shape a live
run would actually be billed, estimated.

The table is written to `docs/eval/mapping-variants.md`, committed, and `--check` regenerates
without writing and fails on drift. Nothing here spends a call.
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from dataclasses import dataclass, replace
from decimal import Decimal
from pathlib import Path

from trace_ai.config import PROJECT_ROOT
from trace_ai.domain.assessment import Assessment
from trace_ai.domain.evidence import EvidenceReference
from trace_ai.domain.threat import Threat
from trace_ai.infrastructure.database.store import AssessmentStore
from trace_ai.infrastructure.model.profiles import resolve_profile
from trace_ai.services.assessment import AssessmentService
from trace_ai.services.evaluation.harness import run_scenario
from trace_ai.services.evaluation.registry import load_registry
from trace_ai.services.evidence.index import EvidenceIndex
from trace_ai.services.mapping.input_package import assemble_mapping_input
from trace_ai.services.prompts import PromptRegistry
from trace_ai.services.requirements.loader import LoadedCatalog, current_version, load_catalog
from trace_ai.workflow import requirement_control_mapping as mapping_node
from trace_ai.workflow.context_review import current_system_context

OUTPUT = PROJECT_ROOT / "docs" / "eval" / "mapping-variants.md"

CHARS_PER_TOKEN = Decimal("3.8")
"""The `estimate_cost.py` midpoint. An estimate's heuristic, named where it is used."""

CACHE_WRITE_PREMIUM = Decimal("1.25")
CACHE_READ_DISCOUNT = Decimal("0.1")
"""The Anthropic cache multipliers, used to model what a live run's stable spans would bill."""


@dataclass(slots=True)
class VariantTotals:
    """One variant's pooled figures for one scenario."""

    calls: int = 0
    input_chars: int = 0
    cache_adjusted_tokens: Decimal = Decimal(0)

    @property
    def input_ktokens(self) -> Decimal:
        return (Decimal(self.input_chars) / CHARS_PER_TOKEN / 1000).quantize(Decimal("0.1"))

    @property
    def cache_adjusted_ktokens(self) -> Decimal:
        return (self.cache_adjusted_tokens / 1000).quantize(Decimal("0.1"))


def _category_of(requirement_id: str) -> str:
    """`req-AUTH-001` -> `AUTH`: the authored primary-category token (requirements/README.md)."""
    return requirement_id.split("-")[1]


def _partitions(catalog: LoadedCatalog, variant: str) -> list[LoadedCatalog]:
    if variant == "whole":
        return [catalog]
    if variant == "by-category":
        order: list[str] = []
        buckets: dict[str, list[int]] = {}
        for index, requirement in enumerate(catalog.requirements):
            category = _category_of(requirement.id)
            if category not in buckets:
                buckets[category] = []
                order.append(category)
            buckets[category].append(index)
        return [
            replace(catalog, requirements=tuple(catalog.requirements[i] for i in buckets[name]))
            for name in order
        ]
    if variant == "halves":
        middle = (len(catalog.requirements) + 1) // 2
        return [
            replace(catalog, requirements=catalog.requirements[:middle]),
            replace(catalog, requirements=catalog.requirements[middle:]),
        ]
    raise ValueError(f"unknown variant {variant!r}")


VARIANTS = ("whole", "by-category", "halves")


def _measure_scenario(slug: str, tmp: Path) -> dict[str, VariantTotals]:
    """Replay one scenario, then rebuild and size every mapping call per variant."""
    outcome = run_scenario(
        slug, data_root=tmp / slug, label="mapping-measurement", stop_after_findings=True
    )
    profile = resolve_profile("primary-development")
    registry = PromptRegistry()
    totals = {variant: VariantTotals() for variant in VARIANTS}

    with AssessmentStore.at_root(tmp / slug) as store:
        service = AssessmentService(store, artifact_root=tmp / slug)
        handle = service.handle(outcome.assessment_id)
        assessment = handle.objects.get(Assessment, outcome.assessment_id)
        catalog = load_catalog(assessment.requirements_catalog_version or current_version())
        system_context = current_system_context(handle)
        evidence_ids = handle.objects.ids(EvidenceReference)
        index = EvidenceIndex(handle)
        threats = sorted(handle.objects.list(Threat), key=lambda threat: threat.id)

        for variant in VARIANTS:
            seen_spans: set[str] = set()
            for part in _partitions(catalog, variant):
                for threat in threats:
                    package = assemble_mapping_input(
                        handle,
                        context=system_context,
                        threat=threat,
                        catalog=part,
                        index=index,
                        evidence_ids=evidence_ids,
                        profile=profile,
                    )
                    composed = registry.compose(
                        mapping_node.PROMPT_ID,
                        mapping_node.PROMPT_VERSION,
                        {
                            mapping_node._SCHEMA_MARKER: mapping_node._schema_text(),
                            **package.substitutions(),
                        },
                    )
                    stable = package.trusted_cache_prefix
                    variable_chars = len(composed.text) + len(package.trusted) - len(stable)
                    stable_tokens = Decimal(len(stable)) / CHARS_PER_TOKEN
                    rate = CACHE_READ_DISCOUNT if stable in seen_spans else CACHE_WRITE_PREMIUM
                    seen_spans.add(stable)
                    entry = totals[variant]
                    entry.calls += 1
                    entry.input_chars += len(composed.text) + len(package.trusted)
                    entry.cache_adjusted_tokens += (
                        Decimal(variable_chars) / CHARS_PER_TOKEN + stable_tokens * rate
                    )
    return totals


def _render(measured: dict[str, dict[str, VariantTotals]]) -> str:
    lines = [
        "# Mapping input under catalog-partition variants",
        "",
        "The DEC-024 cost evidence, offline half (#532): every registered scenario replayed,",
        "every mapping call rebuilt exactly as the pipeline built it, then re-composed under",
        "partition schemes and sized. **All figures are estimated** — characters over the",
        "3.8 chars/token heuristic, never a provider count (DEC-092: an estimate says so).",
        "The cache-adjusted column prices each call's stable span (DEC-105) at the write",
        "premium on first occurrence and the read discount after, everything else at full",
        "rate — the billing shape of a live run, estimated. Regenerated by",
        "`uv run python scripts/measure_mapping_variants.py`; `--check` fails on drift.",
        "",
        "| Scenario | Variant | Calls | Est. input kTok | Cache-adjusted kTok |",
        "|----------|---------|------:|----------------:|--------------------:|",
    ]
    pooled = {variant: VariantTotals() for variant in VARIANTS}
    for slug in sorted(measured):
        for variant in VARIANTS:
            entry = measured[slug][variant]
            lines.append(
                f"| {slug} | {variant} | {entry.calls} | {entry.input_ktokens} "
                f"| {entry.cache_adjusted_ktokens} |"
            )
            pooled[variant].calls += entry.calls
            pooled[variant].input_chars += entry.input_chars
            pooled[variant].cache_adjusted_tokens += entry.cache_adjusted_tokens
    for variant in VARIANTS:
        entry = pooled[variant]
        lines.append(
            f"| **all** | **{variant}** | **{entry.calls}** | **{entry.input_ktokens}** "
            f"| **{entry.cache_adjusted_ktokens}** |"
        )
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--check",
        action="store_true",
        help="regenerate and fail if it differs from the committed table, without writing",
    )
    args = parser.parse_args(argv)

    measured: dict[str, dict[str, VariantTotals]] = {}
    with tempfile.TemporaryDirectory(prefix="trace-mapping-variants-") as tmp:
        for entry in load_registry():
            measured[entry.slug] = _measure_scenario(entry.slug, Path(tmp))

    rendered = _render(measured)
    if args.check:
        current = OUTPUT.read_text(encoding="utf-8") if OUTPUT.is_file() else ""
        if rendered != current:
            print(
                "the committed mapping-variants table is stale; run "
                "`uv run python scripts/measure_mapping_variants.py`",
                file=sys.stderr,
            )
            return 1
        print("the committed mapping-variants table is current")
        return 0

    OUTPUT.write_text(rendered, encoding="utf-8")
    print(f"wrote {OUTPUT.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
