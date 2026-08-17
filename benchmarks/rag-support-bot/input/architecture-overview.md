# Relay Answers: architecture overview

Relay Answers is the in-product support assistant for the Relay project-management platform.
A signed-in user asks a question in the help panel; the assistant answers from Relay's own
documentation and from the workspace's support history, citing the passages it used.

## Components

- **Help panel** — the in-product chat surface. Available to every signed-in user of any
  workspace on any plan.
- **Answer service** — receives the question, runs retrieval, assembles the prompt, calls the
  model provider, and returns the answer with its citations.
- **Retrieval index** — a managed vector database holding embeddings of the help-center
  articles and of resolved support tickets. All workspaces are served from one shared index;
  a query returns the top eight passages ranked by embedding similarity, and relevance alone
  selects the passages that reach the prompt.
- **Ingestion pipeline** — the only writer to the retrieval index. It runs nightly, reads two
  named sources — the published help-center repository and the support platform's resolved
  tickets export — chunks and embeds them, and records the source and timestamp on every
  indexed item. Help-center content is published through the documentation team's review
  process before the pipeline ever sees it.
- **Model provider** — a hosted large-language-model API. The answer service sends the user's
  question and the retrieved passages; workspace identifiers and user identifiers are stripped
  from the request first.

## Prompt assembly

The prompt places retrieved passages inside a delimited context block, and the system
instructions state that content inside the block is reference material, not instructions. The
answer is returned with the source reference of each cited passage. Answers are rendered in the
help panel as plain text; the panel does not execute or interpret model output.

## Data handling

Resolved support tickets are retained on the support platform for two years and then deleted
under the retention schedule agreed with customers. The help-center repository is public
documentation. The model provider's terms for the assistant's traffic exclude training on
submitted content, and requests are sent over TLS.
