"""PDF text extraction: the deterministic function that makes a PDF addressable (DEC-123).

A PDF's stored original is binary, and every consumer of a source document — normalization,
segmentation, evidence verification, the source view — addresses text by line. DEC-123 resolves
the mismatch structurally: **the text layer extracted from the stored bytes is the addressable
text**, computed by this module wherever the document is read, never stored as a second artifact.
The original stays byte-identical and remains the only stored source; the extraction is a pure
function of those bytes and the pinned `pypdf` version, so a dependency upgrade that changes
extraction output moves quoted-text hashes and `trace verify` reports the drift instead of
absorbing it.

**One addressable unit per page.** Prose segmentation keys on ATX headings, which extracted PDF
text does not reliably carry, and a single chunk for a forty-page document is the failure
segmentation exists to prevent. A page is the unit a reviewer can find in the original — the one
address both the extraction and the PDF itself agree on — so each page with any text becomes one
segment titled `Page N`, and each evidence reference into a PDF carries its page in the
`page_number` field section 8 reserved for exactly this arrival.

**Extraction is text-layer only.** No OCR and no diagram interpretation (future-features 7.3
stays Research). A document with no extractable text anywhere is refused at registration —
DEC-009's principle applied to ingestion: unreadable content is not quietly interpreted, and an
image-only PDF ingested as an empty document would be silence presented as content. Pages
without text in an otherwise textual document are tolerated and named: the count and the page
numbers land in the document's metadata rather than being papered over.

`pypdf` is the extraction dependency: pure Python, typed (`py.typed`), actively maintained, and
the parsing surface is bounded by the loader's size cap. It is untrusted-input parsing all the
same, so the boundary here catches every exception `pypdf` raises and returns a named error —
a hostile file gets a refusal, never a traceback.
"""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

from trace_ai.domain.source_document import MediaType
from trace_ai.services.ingestion.segment import Segment

__all__ = [
    "EncryptedPdfError",
    "PageText",
    "PdfExtraction",
    "PdfExtractionError",
    "UnreadablePdfError",
    "addressable_text",
    "extract_pdf",
    "pdf_segments",
]


class PdfExtractionError(RuntimeError):
    """A PDF whose text layer cannot be produced. Subclasses say why."""


class UnreadablePdfError(PdfExtractionError):
    def __init__(self, detail: str) -> None:
        super().__init__(f"it does not parse as a PDF: {detail}")


class EncryptedPdfError(PdfExtractionError):
    def __init__(self) -> None:
        super().__init__(
            "it is encrypted. Trace does not take passwords for source documents; "
            "supply a decrypted copy"
        )


@dataclass(frozen=True, slots=True)
class PageText:
    """One page's extracted text and its 1-based line span within the joined extraction.

    A page with no extractable text is not represented here; its number appears in
    `PdfExtraction.pages_without_text` instead.
    """

    number: int
    text: str
    start_line: int
    end_line: int


@dataclass(frozen=True, slots=True)
class PdfExtraction:
    """The addressable text of a PDF: pages joined by newline, nothing synthetic inserted.

    `text` contains extracted content only — no page-marker lines, because a synthetic line
    would be quotable as evidence and nothing in the original says it. Page provenance travels
    as data: each `PageText` records the lines it occupies.
    """

    text: str
    pages: tuple[PageText, ...]
    page_count: int
    pages_without_text: tuple[int, ...]

    @property
    def has_text(self) -> bool:
        return bool(self.text.strip())


def extract_pdf(content: bytes) -> PdfExtraction:
    """Extract the text layer of a PDF, deterministically.

    Raises `UnreadablePdfError` for anything `pypdf` cannot parse and `EncryptedPdfError` for a
    document that requires a password. An empty text layer is not an error here — the loader
    decides whether to refuse, because "no text at all" and "this page has no text" are different
    answers and only the caller knows which question it is asking.
    """
    from pypdf import PdfReader

    try:
        reader = PdfReader(BytesIO(content))
        if reader.is_encrypted:
            raise EncryptedPdfError
        raw_pages = [page.extract_text() for page in reader.pages]
    except PdfExtractionError:
        raise
    except Exception as error:
        # pypdf raises its own hierarchy plus assorted built-ins on malformed input. The file is
        # untrusted, so every parse-time failure is one refusal class rather than a traceback.
        raise UnreadablePdfError(str(error).split("\n")[0] or type(error).__name__) from error

    pages: list[PageText] = []
    without_text: list[int] = []
    blocks: list[str] = []
    next_line = 1
    for index, raw in enumerate(raw_pages, start=1):
        lines = raw.splitlines()
        if not any(line.strip() for line in lines):
            without_text.append(index)
            continue
        block = "\n".join(lines)
        pages.append(
            PageText(
                number=index,
                text=block,
                start_line=next_line,
                end_line=next_line + len(lines) - 1,
            )
        )
        blocks.append(block)
        next_line += len(lines)

    return PdfExtraction(
        text="\n".join(blocks),
        pages=tuple(pages),
        page_count=len(raw_pages),
        pages_without_text=tuple(without_text),
    )


def addressable_text(content: bytes, media_type: MediaType) -> tuple[str, PdfExtraction | None]:
    """The text every consumer of a stored source addresses, plus the extraction for a PDF.

    One definition, shared by indexing, verification, and the source view, because two readers
    with two answers to "what is line n" would move citations between them. For every text
    format this is the UTF-8 decode of the stored bytes; for a PDF it is the extraction
    (DEC-123), returned alongside so callers that need page structure do not extract twice.
    Raises what the underlying reader raises — `UnicodeDecodeError` for a text format,
    `PdfExtractionError` for a PDF — and callers keep their existing failure handling.
    """
    if media_type is MediaType.PDF:
        extraction = extract_pdf(content)
        return extraction.text, extraction
    return content.decode("utf-8"), None


def pdf_segments(extraction: PdfExtraction) -> list[Segment]:
    """One addressable unit per page with text (DEC-123).

    Pages are the address a reviewer can find in the original, so each becomes one segment
    titled `Page N` carrying its page number; pages without text are absent here and named in
    the document's metadata instead.
    """
    return [
        Segment(
            text=page.text,
            start_line=page.start_line,
            end_line=page.end_line,
            section_title=f"Page {page.number}",
            page_number=page.number,
        )
        for page in extraction.pages
    ]
