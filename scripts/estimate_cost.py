"""Estimate the model cost of one assessment and one benchmark sweep.

**Superseded for the per-assessment figure (DEC-092).** The DEC-077 stability protocol measured
five completed live runs at $6.92 ± $3.28 each — above this script's $2.25 to $5.97 ceiling — and
the measurement, not this model, is the quotable cost. The script survives because its
per-component shape is still the only a-priori estimate for a scenario never run live, and
because the conclusion it was built to check (the cost does not change the model tier) held.

It originally answered the first open question on DEC-014: what does a ForgeFlow assessment cost
at the selected model and effort level, and does the answer change the model tier?

**This is an estimate, not a measurement.** No product code exists, so there is nothing to
instrument; and with no provider credential configured there is no `count_tokens` call available
either. Token counts are derived from character counts using a stated ratio, swept across a range
so the conclusion can be checked for robustness rather than taken on the midpoint.

Every assumption is a named constant below. The pipeline shape is taken from the corpus:
`agent-design.md` names six model-assisted agents, `forgeflow-scenario.md` section 18 lists ten
expected threats, and `data-model.md` section 6's own example sets `maximum_model_calls: 25` and
`maximum_cost: 5.00` -- which this script exists to check rather than assume.

    uv run python scripts/estimate_cost.py
    uv run python scripts/estimate_cost.py --sweep     # ratio sensitivity
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Final

PROJECT_ROOT: Final = Path(__file__).resolve().parent.parent
INPUT_DIR: Final = PROJECT_ROOT / "demo" / "forgeflow" / "input"
CATALOG_DIR: Final = PROJECT_ROOT / "requirements"

# --- assumptions ----------------------------------------------------------------------

# Characters per token. English Markdown prose sits near 4; the tokenizer introduced with
# Opus 4.7 produces 1x-1.35x the tokens of its predecessor for the same text, so the low end
# of this range is the conservative (more expensive) case.
CHARS_PER_TOKEN_LOW: Final = Decimal("3.2")
CHARS_PER_TOKEN_MID: Final = Decimal("3.8")
CHARS_PER_TOKEN_HIGH: Final = Decimal("4.4")

# Threats drive the per-threat call count. forgeflow-scenario.md section 18 lists ten.
EXPECTED_THREATS: Final = 10

# Thinking is billed as output. Adaptive thinking at effort `high` is the dominant unknown
# in this estimate; these are per-call figures, swept in --sweep.
THINKING_TOKENS_PER_CALL_LOW: Final = 800
THINKING_TOKENS_PER_CALL_MID: Final = 2500
THINKING_TOKENS_PER_CALL_HIGH: Final = 6000

# Prompt overhead per call: role, instructions, schema, the three shared blocks.
PROMPT_OVERHEAD_TOKENS: Final = 1200

# Cache economics. Reads are ~0.1x input price; writes are 1.25x at the 5-minute TTL.
CACHE_READ_MULTIPLIER: Final = Decimal("0.10")
CACHE_WRITE_MULTIPLIER: Final = Decimal("1.25")


@dataclass(frozen=True)
class Model:
    name: str
    input_per_mtok: Decimal
    output_per_mtok: Decimal


MODELS: Final = (
    Model("claude-opus-5", Decimal("5.00"), Decimal("25.00")),
    Model("claude-sonnet-5", Decimal("3.00"), Decimal("15.00")),
    Model("claude-sonnet-5 (intro)", Decimal("2.00"), Decimal("10.00")),
    Model("claude-haiku-4-5", Decimal("1.00"), Decimal("5.00")),
)


@dataclass(frozen=True)
class Stage:
    """One model-assisted step, and how its input is composed."""

    name: str
    calls: int
    # Fraction of the full source corpus this stage's input carries.
    corpus_fraction: Decimal
    # Fraction of the requirements catalog this stage's input carries.
    catalog_fraction: Decimal
    # Non-cacheable per-call input beyond prompt overhead, in tokens.
    variable_tokens: int
    # Structured output per call, excluding thinking.
    output_tokens: int


# agent-design.md sections 7, 10, 12, 14, 15, 19. Mapping runs per threat; evidence
# validation and critique run over bounded groups (section 23).
STAGES: Final = (
    Stage("Context extraction", 1, Decimal("1.00"), Decimal("0"), 0, 6000),
    Stage("Threat analysis", 1, Decimal("0"), Decimal("0"), 4000, 4000),
    Stage(
        "Requirement and control mapping",
        EXPECTED_THREATS,
        Decimal("0"),
        Decimal("1.00"),
        1500,
        1200,
    ),
    Stage("Evidence validation", EXPECTED_THREATS, Decimal("0"), Decimal("0"), 2500, 800),
    Stage("Critical review", 5, Decimal("0"), Decimal("0"), 3500, 900),
    Stage("Report generation", 1, Decimal("0"), Decimal("0"), 5000, 5000),
)


def chars(paths: list[Path]) -> int:
    return sum(len(p.read_text()) for p in paths)


def corpus_chars() -> int:
    return chars(sorted(p for p in INPUT_DIR.iterdir() if p.is_file()))


def catalog_chars() -> int:
    return chars(sorted(CATALOG_DIR.rglob("*.yaml")))


def tokens(char_count: int, ratio: Decimal) -> int:
    return int(Decimal(char_count) / ratio)


@dataclass(frozen=True)
class Usage:
    input_uncached: int
    input_cache_write: int
    input_cache_read: int
    output: int


def usage_for(ratio: Decimal, thinking: int, *, cached: bool) -> tuple[Usage, int]:
    """Total token usage across one assessment, and the model-call count."""
    corpus = tokens(corpus_chars(), ratio)
    catalog = tokens(catalog_chars(), ratio)

    uncached = write = read = out = 0
    call_count = 0

    for stage in STAGES:
        stage_stable = int(Decimal(corpus) * stage.corpus_fraction) + int(
            Decimal(catalog) * stage.catalog_fraction
        )
        stage_variable = stage.variable_tokens + PROMPT_OVERHEAD_TOKENS

        for i in range(stage.calls):
            call_count += 1
            out += stage.output_tokens + thinking
            if cached and stage_stable > 0:
                # First call in a stage writes the stable prefix; the rest read it.
                if i == 0:
                    write += stage_stable
                else:
                    read += stage_stable
                uncached += stage_variable
            else:
                uncached += stage_stable + stage_variable

    return Usage(uncached, write, read, out), call_count


def cost(usage: Usage, model: Model) -> Decimal:
    inp = model.input_per_mtok / Decimal(1_000_000)
    outp = model.output_per_mtok / Decimal(1_000_000)
    return (
        Decimal(usage.input_uncached) * inp
        + Decimal(usage.input_cache_write) * inp * CACHE_WRITE_MULTIPLIER
        + Decimal(usage.input_cache_read) * inp * CACHE_READ_MULTIPLIER
        + Decimal(usage.output) * outp
    )


def money(value: Decimal) -> str:
    return f"${value.quantize(Decimal('0.01'))}"


def report() -> None:
    ratio = CHARS_PER_TOKEN_MID
    thinking = THINKING_TOKENS_PER_CALL_MID

    corpus = tokens(corpus_chars(), ratio)
    catalog = tokens(catalog_chars(), ratio)

    print("Inputs (midpoint assumptions)")
    print(f"  chars per token           {ratio}")
    print(f"  thinking tokens per call  {thinking:,}")
    print(f"  source corpus             {corpus_chars():,} chars  ~{corpus:,} tokens")
    print(f"  requirements catalog      {catalog_chars():,} chars  ~{catalog:,} tokens")
    print()

    plain, calls = usage_for(ratio, thinking, cached=False)
    cached, _ = usage_for(ratio, thinking, cached=True)

    print(f"Pipeline: {calls} model calls per assessment")
    for stage in STAGES:
        print(f"  {stage.name:<34} {stage.calls:>3} call(s)")
    print()

    print("Token usage per assessment")
    print(f"  without caching   input {plain.input_uncached:>9,}   output {plain.output:>9,}")
    print(
        f"  with caching      input {cached.input_uncached:>9,}"
        f"   write {cached.input_cache_write:>7,}"
        f"   read {cached.input_cache_read:>7,}"
        f"   output {cached.output:>9,}"
    )
    print()

    print(f"{'Model':<26} {'1 assessment':>14} {'+ caching':>12} {'12-scenario sweep':>19}")
    print(f"{'-' * 26} {'-' * 14} {'-' * 12} {'-' * 19}")
    for model in MODELS:
        one = cost(plain, model)
        one_cached = cost(cached, model)
        sweep = one_cached * 12
        print(f"{model.name:<26} {money(one):>14} {money(one_cached):>12} {money(sweep):>19}")
    print()

    opus = MODELS[0]
    one_cached = cost(cached, opus)
    print("Against the corpus's own example limits (data-model.md section 6)")
    print(f"  maximum_model_calls: 25   -> this model predicts {calls}")
    print(f"  maximum_cost: 5.00        -> this model predicts {money(one_cached)} on {opus.name}")
    print()

    share = (
        Decimal(cached.output)
        * opus.output_per_mtok
        / (
            Decimal(cached.output) * opus.output_per_mtok
            + Decimal(cached.input_uncached) * opus.input_per_mtok
        )
    )
    print(f"  output share of cost (cached, {opus.name}): {(share * 100).quantize(Decimal('1'))}%")


def sweep() -> None:
    print(
        f"{'chars/tok':>10} {'think/call':>11} {'calls':>6} "
        f"{'opus-5':>10} {'opus-5 cached':>14} {'sonnet-5 cached':>16}"
    )
    print("-" * 72)
    opus, sonnet = MODELS[0], MODELS[1]
    for ratio in (CHARS_PER_TOKEN_LOW, CHARS_PER_TOKEN_MID, CHARS_PER_TOKEN_HIGH):
        for thinking in (
            THINKING_TOKENS_PER_CALL_LOW,
            THINKING_TOKENS_PER_CALL_MID,
            THINKING_TOKENS_PER_CALL_HIGH,
        ):
            plain, calls = usage_for(ratio, thinking, cached=False)
            cached, _ = usage_for(ratio, thinking, cached=True)
            print(
                f"{ratio:>10} {thinking:>11,} {calls:>6} "
                f"{money(cost(plain, opus)):>10} {money(cost(cached, opus)):>14} "
                f"{money(cost(cached, sonnet)):>16}"
            )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sweep", action="store_true", help="Show assumption sensitivity.")
    args = parser.parse_args()
    if args.sweep:
        sweep()
    else:
        report()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
