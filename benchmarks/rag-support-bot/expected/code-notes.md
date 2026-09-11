# Relay Answers: notes on the code layer

`../code/` is a running implementation of the system `../input/` describes, authored from this
truth set (DEC-156). It exists so a code reviewer and a documentation reviewer can be measured on
the same system. Nothing here or under `../code/` is supplied to Trace, and nothing in this file or
in `code-ground-truth.yaml` is supplied to a code reviewer: the reviewer receives `../code/` alone.

This note was written before the code. It records what each module is for, which truth-set item
it realises, and which items are reachable from only one side, so the experiment measures the
reviewers rather than the author's memory of what was intended.

## Module intent

| Module | Realises | Intent |
|---|---|---|
| `relay_answers/index.py` | FND-RSB-01 | One shared in-memory vector index for every workspace. `search` ranks every chunk by similarity and returns the top eight. It takes no workspace argument and applies no filter, although every chunk carries the workspace it came from. This is the documented negative, made literal: relevance alone selects the passages that reach the prompt. |
| `relay_answers/main.py` | FND-RSB-01, trap | `POST /v1/answers` resolves the caller's workspace from the bearer token, charges the quota, and calls `search` without passing the workspace on. `GET /v1/health` is unauthenticated, as the OpenAPI document declares with `security: []`. |
| `relay_answers/retention.py` | GAP-RSB-01, non-scoring | The deletion-propagation job the documentation never names. It removes every chunk whose source ticket appears in the export with a `deleted_at` tombstone. Whether a ticket deleted under the two-year retention schedule arrives as a tombstone or simply vanishes from the export is a property of the support platform, not of this code. The documentation layer records a gap for the same reason; the code layer records a non-scoring entry. |
| `relay_answers/ingestion.py` | trap | The only writer to the index. Reads the two named sources, masks email addresses, chunks, embeds, records source reference and timestamp on every chunk, and replaces changed chunks by source reference. A reviewer flagging "only emails are masked" restates a documented known item that is evidence for FND-RSB-01, not a second weakness. |
| `relay_answers/prompt.py` | trap | Places retrieved passages inside a delimited context block under a system instruction that names them reference material. Documented handling for the prompt-injection class; a finding here is REJ-RSB-01 in code form. |
| `relay_answers/provider.py` | trap | Strips workspace and user identifiers from the request before it leaves, and sends over TLS. Without a key it answers from a stub so the service runs in tests. |
| `relay_answers/quota.py` | trap | The per-workspace daily answer quota and the per-workspace feature flag. |
| `relay_answers/auth.py` | trap | Bearer token to workspace. Tokens are opaque and looked up, never parsed. |
| `relay_answers/embeddings.py` | none | A deterministic hashed bag-of-words embedding so the index runs with no model and the tests are exact. |

## Reachable only from code

- That the deletion-propagation job exists at all, and that it keys on tombstones. The
  documentation says nothing about deletion reaching the index.
- That the retrieval call site has a workspace in hand and does not pass it. The documentation
  states the outcome; the code shows the missed opportunity.

## Reachable only from documentation

- The organizational facts around the finding: that the help panel ships to every plan including
  trials, that the vector database is the managed offering's standard tier reachable only from
  the answer service's network segment, and that answer quality is a weekly manual sample. A
  code reviewer cannot see any of these, and a code-only threat model that assumes an internal
  user base will under-rate FND-RSB-01.
- The model provider's terms excluding training on submitted content, which resolves a class of
  finding a code reviewer would otherwise have to raise.

## How the truth was derived

FND-RSB-01 maps to `search`, the sink where the filter is absent, with the answer endpoint as its
call site. Its CWE is 285 (improper authorization), with 284, 639, 862, and 200 acceptable because
tools name a cross-tenant read under different headings. Every trap names a location a scanner is
likely to flag on pattern alone. Nothing under `../code/` was changed after this note and the truth
file were written except to make the tests pass.
