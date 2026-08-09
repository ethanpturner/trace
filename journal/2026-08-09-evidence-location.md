# 2026-08-09 — The address, and a rule I got wrong

Closes #22 as DEC-015. The decision I had flagged as sharpest, and the one where writing a test
against the real corpus caught me stating a rule that fails on the exact document I cited as the
reason for it.

## The unasked question underneath

Three open questions covered evidence location — `data-model.md` questions 2 and 3, and
`current-architecture.md` question 4 — and underneath them sat one nobody had written down.
`SourceDocument` carries `original_path` and `normalized_path`. `EvidenceReference` carries
`quoted_text` and `normalized_text`. Nothing said which document `start_line` indexes.

If normalization changed line counts, every evidence reference in the system would be off by an
unknown offset, silently, in the object the traceability claim runs through. Nothing would error.
The report would cite a line number and the reviewer would open the file and find a different
sentence.

## Two rules, and why the second one matters more

The first is the obvious half: **locations address the original document.** The original is what
the reviewer opens, and "walkable back to the sentence that produced it" means a sentence in the
document they supplied, not in an artifact the pipeline derived. The original is also immutable,
whereas normalization is implementation and will change.

The second is what makes it hold: **normalization is line-count preserving by construction.** It
may convert line endings, strip trailing whitespace within a line, and normalize Unicode. It may
not remove blank lines, collapse runs of them, reflow paragraphs, or strip front matter.

The difference is between a decision and a property. A rule saying "index the original" can be
violated by an implementer who normalizes aggressively and adjusts offsets to compensate — and the
compensation is where the bug lives. A normalization that cannot change line counts leaves nothing
to adjust, and the two addressings are the same address by construction rather than by discipline.

It is also currently free. The corpus has no CRLF endings, no trailing whitespace, no front
matter, and no tabs, so a line-preserving normalizer refuses to do nothing it would otherwise have
done. The constraint costs nothing today and forecloses a class of silent error permanently.

The cost is real but deferred: front-matter stripping and paragraph reflow are now prohibited, and
if either becomes necessary this decision has to be revisited rather than worked around. That is
the intended shape of the tradeoff.

## Where I was wrong

I wrote the segmentation rule as **"the shallowest heading level present in the document."** Then I
wrote a test asserting it produces more than one chunk per document, and it failed on
`architecture-overview.md` and `product-overview.md`.

Those two use `#` once as a title and `##` for every section. The shallowest level *present* is
therefore `#`, which occurs once — so the rule I had just written into the decision log segments a
734-line document into **one chunk**. That is precisely the failure I had cited, two paragraphs
earlier in the same entry, as the reason a fixed rule was unusable.

The correction is one qualifier: **the shallowest heading level that occurs more than once.** A
heading that appears once is a title, not a partition. With it the corpus segments into 19, 35, 17,
19, 14, 13, and 20 chunks, which is right in every case.

What I want to record is not the fix but how it surfaced. I had measured the corpus before writing
the decision — the heading-depth counts are what convinced me a fixed rule was wrong — and I still
wrote a rule that failed on the data I had just looked at. Reading `h1=1, h2=35` and concluding
"shallowest present" is a small enough slip to make while looking directly at the numbers. Running
the rule is what caught it. The measurement informed the decision; only the test checked it.

## The tests

`tests/unit/test_evidence_location_corpus.py` pins both empirical claims, because both are
properties of the corpus rather than of documents in general and both could stop being true.

The precondition tests assert no input file has CRLF endings, trailing whitespace, front matter, or
non-NFC text. If one appears, line-preserving normalization stops being free, and the failure says
so — the right response is to re-read DEC-015, not to loosen the normalizer.

The segmentation tests assert the chosen rule yields multiple chunks everywhere, that a fixed h1 or
h2 rule fails somewhere, and that a document using `#` as a title alone never picks `#` as its
segmenting level. That last one is the regression test for my own mistake.

They test the corpus, not ingestion code, which does not exist. When it does, the line-count
assertion moves onto real normalized artifacts and this file keeps the precondition.

## Structured input

A line range is not an address in YAML. `- name: web` means nothing without knowing it is
`components[0]`, and two sequence elements can be textually identical. So JSON and YAML are
addressed by JSON Pointer, carried in `metadata` under a reserved key — `metadata` is already typed
`map[string, any]` and described as "additional location details", so no field is added to
`EvidenceReference` and the schema is unchanged.

Line numbers are still populated, because a reviewer still wants to open the file at the right
place. They are a convenience, not the address.

## Open next

DEC-015 leaves four questions open, all downstream of work not yet started: node granularity for
deeply nested structured input, whether oversized chunks get subdivided, what happens to evidence
references when a document is re-ingested after an edit, and whether `normalized_text` earns its
place on every reference or only where normalization changed something.

#25, DEC-007 and the orchestrator, is the last of the four decisions gating M1 and M2, and the only
non-Accepted entry in the log.
