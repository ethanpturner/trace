"""The derived HTML report view (#527, DEC-108): a transform, escaped, deterministic.

The properties that matter: the transform preserves the render's structure (headings, anchors,
tables, fences, lists); it escapes everything else, so source-derived text cannot become
markup; and it is byte-deterministic. There is no second section inventory to test against the
template, because there is no second renderer — a section is in the HTML because it is in the
Markdown render.
"""

from __future__ import annotations

from trace_ai.services.report.html import render_report_html


def test_headings_anchors_tables_and_fences_convert() -> None:
    markdown = "\n".join(
        [
            "# Security Architecture Assessment: ForgeFlow",
            "",
            "## 8. Approved findings",
            "",
            '<a id="fnd-001"></a>',
            "",
            "### fnd-001 — Webhook authenticity",
            "",
            "| Field | Value |",
            "| --- | --- |",
            "| Severity | high |",
            "| Impact | jobs \\| disclosure |",
            "",
            "- qst-001 (blocking): Is authenticity verified? *(also asked as qst-002)*",
            "",
            "```",
            "raw <quoted> text",
            "```",
        ]
    )
    page = render_report_html(markdown, title="ForgeFlow")

    assert "<h1>Security Architecture Assessment: ForgeFlow</h1>" in page
    assert "<h2>8. Approved findings</h2>" in page
    assert '<a id="fnd-001"></a>' in page
    assert "<h3>fnd-001 — Webhook authenticity</h3>" in page
    assert "<th>Field</th><th>Value</th>" in page
    assert "<td>jobs | disclosure</td>" in page
    assert (
        "<li>qst-001 (blocking): Is authenticity verified? <em>(also asked as qst-002)</em></li>"
        in page
    )
    assert "<pre><code>raw &lt;quoted&gt; text</code></pre>" in page


def test_source_derived_text_cannot_become_markup() -> None:
    """The load-bearing property: a description carrying markup renders as text."""
    markdown = "\n".join(
        [
            "## 8. Approved findings",
            "",
            'The description says <script>alert("x")</script> and <img src=x onerror=y>.',
            "",
            "| Field | Value |",
            "| --- | --- |",
            "| Impact | <b>bold-looking</b> |",
        ]
    )
    page = render_report_html(markdown, title="t")

    assert "<script>" not in page
    assert "&lt;script&gt;" in page
    assert "<img" not in page
    assert "<b>" not in page


def test_only_the_exact_anchor_form_passes_through() -> None:
    page = render_report_html('<a id="fnd-001" onclick="x()"></a>', title="t")
    assert "onclick" not in page or "&lt;a" in page
    assert '<a id="fnd-001" onclick' not in page


def test_ownership_comments_are_dropped() -> None:
    page = render_report_html("<!-- OWNER: render.findings -->\n\nBody text.", title="t")
    assert "OWNER" not in page
    assert "<p>Body text.</p>" in page


def test_bold_and_fragment_links_convert_and_nothing_else_does() -> None:
    page = render_report_html(
        "See **fnd-001** at [the finding](#fnd-001), not [a site](https://example.test).",
        title="t",
    )
    assert "<strong>fnd-001</strong>" in page
    assert '<a href="#fnd-001">the finding</a>' in page
    assert '<a href="https://example.test"' not in page
    assert "[a site](https://example.test)" in page


def test_the_transform_is_deterministic() -> None:
    markdown = "## 2. Scope\n\nOne paragraph.\n"
    assert render_report_html(markdown, title="t") == render_report_html(markdown, title="t")
