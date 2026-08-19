# 2026-08-19 — OpenRouter behind the OpenAI adapter (DEC-135)

## What changed

The queue's remaining live work — the eleven-scenario sweep (#484), the model comparison
(#332), the prompt-version comparison (#331), live-coverage enforcement (#588) — is parked on
one fact: DEC-092 priced a single pipeline run at $6.92 ± $3.28 on `claude-opus-5`, and every
open measurement multiplies that number. Today's session attacked the rate rather than the
work. OpenRouter serves an OpenAI-compatible Responses API, so `provider="openrouter"` became
a name the existing OpenAI adapter serves — a provider table pairing each name with its base
URL and its `Settings` key field — rather than a third adapter. `build_model` widened one
branch condition; the seam, the nodes, and the driver are untouched. The shipped
`openrouter-economy` profile prices both token spans at 7.5% of the primary rates, so the
measured run projects to roughly fifty cents and the sweep to single-digit dollars.

## Decisions and reasoning

- **DEC-135, Accepted.** The interesting boundary call was where the base URL lives. On the
  profile it would be one more field; in the adapter's provider table it is identity rather
  than configuration, and a profile cannot point one provider's name at another host and make
  the `ExecutionRecord`'s provenance lie. The gateway also got no adapter of its own for the
  same reason inverted: OpenRouter's documented client *is* the `openai` package, so a third
  module would duplicate the Responses handling and hand `test_model_boundary.py` a second
  sanctioned `openai` importer, weakening the boundary to prove nothing new.
- **The model was chosen by probe, not by price list.** The plan was the cost floor,
  `deepseek/deepseek-v4-flash` ($0.0679/$0.168 per million). A live five-line copy task —
  'the colour is "blue"; fill the one-field schema' — refused it: three samples of four came
  back as key-name junk (`sky_color`, `colour_schema`) or invalid JSON, with the `json_schema`
  format *honored* each time. `qwen/qwen3.6-flash` failed three of three.
  `google/gemini-3.7-flash` went three for three, so it ships. The probe cost under a cent and
  is the difference between a profile that runs the pipeline and a profile that fabricates it;
  it also produced the entry's sharpest sentence — a capture model that cannot copy a quoted
  word into a one-field schema has no business proposing threat analyses.
- **Effort normalization accepted as the gateway's job.** The creativity mapping is unchanged;
  OpenRouter maps a requested effort to the nearest level the routed model supports, and the
  recorded `effort` metadata keeps meaning what the application asked for. The alternative —
  per-model effort tables in the adapter — re-creates the knob DEC-014 keeps out of the seam.

## Discovered along the way

- The new `Settings.openrouter_api_key` field made `test_context_injection`'s fake-settings
  fixture fail on this machine — the ambient exported `OPENROUTER_API_KEY` flowed into a
  `Settings(_env_file=None, ...)` that only overrode the two keys it knew about. The fixture
  now plants a fake OpenRouter key too, which also puts the new field under the
  no-secret-reaches-the-prompt assertion. A useful reminder that `_env_file=None` silences the
  file, not the environment.
- The gateway's Responses endpoint is beta but behaved: `json_schema` accepted without the
  `json_object` fallback, usage echoing the routed model, cached spans reported in
  `input_tokens_details`. The key-gated round trip (`tests/integration/test_openrouter_adapter.py`)
  passed live, repeatedly, in ~3 seconds per call.

## Open next

- The cheap live track is now schedulable: #484's sweep on `openrouter-economy` with
  `primary-development` held to one or two confirmation scenarios, and #332's comparison gains
  a third provider's bundle. Sweep results on this profile characterize Gemini Flash, not
  Opus — the scorecard's profile attribution is what keeps that honest.
- The DEC-134 batching shape (#585) should land before any sweep capture, since it changes the
  call shape every recording would pin.
