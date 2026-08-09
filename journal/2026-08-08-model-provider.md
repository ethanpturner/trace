# 2026-08-08 — Separating the provider from the architecture

Closes #24 as DEC-014. The third M0 decision, and the one where the framing I brought to it was
wrong.

## What I got wrong first

I set the question up as a choice between providers: Anthropic, OpenAI, or defer. Each option
carried a consequence for `agent-design.md` section 29, whose per-agent "creativity need" table I
had read as specifying `temperature`.

The reply reframed it: **model-agnostic, defaulting to Anthropic.**

That is not a fourth option on the same axis. It separates two questions I had bundled together.
*Which provider* is a default that should be changeable. *Where provider-specific code lives* is an
architecture decision that holds regardless of the answer. Conflating them is what made the
decision feel larger than it is, and `current-architecture.md` section 9 had already answered the
architectural half — it asked for a model abstraction rather than provider calls scattered through
the codebase. What was actually open was only the default.

## The section 29 problem, and why the reframing dissolved it

Section 29 assigns each agent a creativity need: low for context extraction and mapping, moderate
for threat analysis. On Anthropic's current models, `temperature`, `top_p`, and `top_k` are removed
and return a 400 — so read as naming a sampling parameter, the table is not implementable.

Under a seam, it does not name one. The creativity column is **provider-neutral intent**: how much
latitude an agent should have. Each adapter maps intent to whatever its provider exposes — the
Anthropic adapter to effort and adaptive thinking, a hypothetical OpenAI adapter to `temperature`.
The table survives intact, which is the better outcome; that it happened to be implementable as
`temperature` on the models available when it was written is incidental. Rewriting it to name one
provider's control would have made the corpus *less* portable while appearing to fix it.

I added a note to section 29 saying the column is intent rather than a knob, because the reading
that produced my original framing is the obvious one and someone else will arrive at it.

## The decision that actually mattered

Not the provider. **Whether the seam is capability-aware or lowest-common-denominator.**

The tempting reading of "model-agnostic" is that every adapter should be interchangeable by
construction, which means the seam exposes only what all providers offer. That would have silently
discarded prompt caching — and Trace's shape fits prompt caching unusually well. Caching is a
prefix match served at a fraction of input cost, and the requirements catalog plus the approved
context is a large stable prefix reused across every mapping call, in a project whose evaluation
plan re-runs the whole benchmark suite on every prompt change. Losing that in the name of a
portability no second adapter yet exercises would have been a bad trade made invisibly.

So the seam is capability-aware: an adapter declares what it supports, the application uses a
capability where present and proceeds without it where absent, and which capabilities were used is
recorded on the `ExecutionRecord`. That last part is the price of the choice — behaviour now
differs by adapter, so an evaluation result is comparable only against runs with the same
capabilities. Recording them makes that visible; it does not make the results comparable.

## Dependencies

Removed `instructor`, `openai`, and `langchain-openai`.

`instructor` is redundant: the Anthropic SDK validates against a Pydantic model natively, and a
third layer between application and provider would own a retry loop this decision explicitly
assigns to the orchestrator. A hidden retry loop breaks both the `ExecutionRecord` retry count and
the cost ceiling.

The other two took a moment's thought, because "model-agnostic" reads as an argument for keeping
them. It is not: being agnostic is a property of the seam, not of the dependency list. A declared,
unused provider SDK is the same "presence is not a choice" problem the corpus already called out
about this exact set of packages. They come back when an adapter is written.

`langchain`, `langchain-anthropic`, and `langgraph` stay, unused, pending DEC-007 — still the only
non-Accepted entry in the log.

## What I am least sure about

The entry says so, but it belongs here too: **a seam with one implementation is not proven
agnostic.** Every abstraction written against a single provider encodes that provider's
assumptions, and the shape of this one will not be tested until a second adapter exists. Structured
output, generation intent, and capability declaration are all modelled on how one SDK happens to
work. The claim is an intention, and nobody should later read DEC-014 as evidence that portability
was demonstrated.

The cost question is also unanswered. `claude-opus-5` is the most capable tier and the most
expensive reasonable option, the benchmark suite re-runs on every prompt change, and I have not
estimated what one ForgeFlow assessment or one full sweep actually costs. Prompt caching is the
offset and is the reason capability-awareness matters, but the offset is unmeasured. That is the
first open question on the entry, and it could still change the model tier.

## Open next

- #22, evidence location, is now the sharpest remaining foundational decision: nothing states
  whether `start_line` indexes the original or the normalized document, and every evidence
  reference depends on the answer.
- #25, DEC-007, is unblocked by nothing this decision did but is adjacent — the orchestrator
  question is the last of the four that gate M1 and M2.
- Cost estimation against the real fixture, which would settle DEC-014's first open question.
