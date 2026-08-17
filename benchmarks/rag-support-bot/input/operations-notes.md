# Relay Answers: operations notes

Working notes from the support-platform team. Current as of this quarter.

## Running the assistant

The answer service runs as a single deployment beside the main Relay API. Each answer makes one
model call; there is no multi-step agent loop, and the assistant takes no actions beyond
returning text. A per-workspace daily answer quota bounds spend, and the service can be disabled
per workspace with a feature flag.

## The index

The nightly ingestion run replaces changed chunks by source reference. Tickets arrive in the
resolved-tickets export with customer email addresses masked by the support platform before
export. The index is the only copy of the embeddings; the vector database is the managed
offering's standard tier, reachable only from the answer service's network segment.

## Known items

- Ticket text sometimes quotes configuration snippets customers pasted into support
  conversations. The masking step covers email addresses only.
- The help panel ships to every plan, including trials.
- Answer quality review is a weekly manual sample of twenty answers by the support team.
