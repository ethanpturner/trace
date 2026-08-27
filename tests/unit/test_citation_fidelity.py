"""Citation fidelity: what resolves, what does not, and what never reaches the page.

The measurement exists because the comparison table asserted something false about this
repository's own schema — that a baseline "cannot cite a document even in principle" — when
`BaselineFinding.evidence_quote` is required and non-empty. Replacing an assertion with a
measurement is only an improvement if the measurement is the one it claims to be, so these tests
pin the two things that could quietly make it something else: a normalization loose enough to
accept a paraphrase, and a match that lets a citation resolve against text no single document
holds.
"""

from __future__ import annotations

from datetime import UTC, datetime

from trace_ai.services.evaluation.citations import (
    BASELINE_ORDER,
    CitationOutcome,
    CorpusOutcome,
    measure_corpus,
    normalize,
    render_citation_fidelity,
)

STAMP = datetime(2026, 8, 14, tzinfo=UTC)


# ------------------------------------------------------------------------------------------
# Normalization: every step is here because the corpus contains it
# ------------------------------------------------------------------------------------------


def test_wrapping_quote_characters_are_stripped() -> None:
    """Models return the passage already wrapped in literal quote marks; the document has none."""
    assert normalize('"the receiver does not check a signature"') == (
        "the receiver does not check a signature"
    )


def test_smart_punctuation_folds_to_ascii() -> None:
    # Escapes rather than literals for the same reason the module uses them: a linter that
    # cannot distinguish these from their ASCII lookalikes is making the point under test.
    assert normalize("\u201cthe caller\u2019s token\u201d") == "the caller's token"
    assert normalize("a \u2013 b") == normalize("a - b")


def test_a_quote_spanning_a_line_break_still_resolves() -> None:
    """Markdown wraps lines; a passage broken across two of them is the same passage."""
    assert normalize("the receiver accepts\nany well-formed delivery") == (
        "the receiver accepts any well-formed delivery"
    )


def test_normalization_does_not_accept_a_paraphrase() -> None:
    """The tolerance stops at presentation. A reworded claim is a different string, and a
    measurement that accepted it would stop being about resolvability."""
    assert normalize("the receiver does not verify signatures") != normalize(
        "the receiver does not check a signature"
    )


# ------------------------------------------------------------------------------------------
# The match itself
# ------------------------------------------------------------------------------------------


def test_a_citation_cannot_resolve_across_two_documents(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Concatenating the tail of one document to the head of another is the corpus's commonest
    unresolvable shape. Joining the documents with a separator no quote can contain is what stops
    it counting as a hit — without that, the measurement would flatter every baseline that
    stitched two real passages together.
    """
    from trace_ai.services.evaluation.citations import _corpus_text

    scenario_dir = tmp_path / "input"
    scenario_dir.mkdir(parents=True)
    (scenario_dir / "a.md").write_text("the queue is private", encoding="utf-8")
    (scenario_dir / "b.md").write_text("and the endpoint is public", encoding="utf-8")

    class _Entry:
        def input_documents(self, _condition: str) -> list:  # type: ignore[type-arg]
            return sorted(scenario_dir.iterdir())

    corpus = _corpus_text(_Entry())  # type: ignore[arg-type]
    assert normalize("the queue is private") in corpus
    assert normalize("and the endpoint is public") in corpus
    assert normalize("the queue is private and the endpoint is public") not in corpus


# ------------------------------------------------------------------------------------------
# The corpus measurement and its page
# ------------------------------------------------------------------------------------------


def test_the_committed_corpus_measures_every_baseline() -> None:
    outcome = measure_corpus()
    assert outcome.scenarios > 0
    measured = {row.baseline for row in outcome.outcomes}
    assert measured == set(BASELINE_ORDER)
    for row in outcome.outcomes:
        assert 0 <= row.resolved <= row.quoted


def test_the_measurement_is_deterministic() -> None:
    """It reads committed files and compares strings, so two runs cannot disagree. A page CI
    checks for drift has to be stable for reasons unrelated to what it says."""
    first = render_citation_fidelity(measure_corpus(), generated_at=STAMP)
    second = render_citation_fidelity(measure_corpus(), generated_at=STAMP)
    assert first == second


def test_the_page_carries_no_quoted_text() -> None:
    """DEC-076: metrics and identifiers only. A quote is assessment content whether or not it
    resolved, and a page listing the unresolved ones would publish source material through the
    back door of a quality report.
    """
    page = render_citation_fidelity(measure_corpus(), generated_at=STAMP)
    for row in measure_corpus().outcomes:
        assert row.scenario in page  # identifiers are fine
    # The corpus's own documents supply the phrases a leak would carry.
    assert "does not check a signature" not in page
    assert 'evidence_quote": "' not in page


def test_a_baseline_that_cited_nothing_renders_a_dash_not_a_zero() -> None:
    """`0/0` reads as a resolution rate of zero. Nothing was cited, so nothing resolved or
    failed to — the same rule DEC-150 applies to the scorecard's rates."""
    outcome = CorpusOutcome(
        outcomes=[
            CitationOutcome(scenario="quiet", baseline=name, quoted=0, resolved=0)
            for name in BASELINE_ORDER
        ]
    )
    page = render_citation_fidelity(outcome, generated_at=STAMP)
    assert "0/0" not in page
    assert "| quiet | — | — | — |" in page
