# Relay Answers

The in-product support assistant for the Relay project-management platform. A signed-in user asks
a question in the help panel; the assistant answers from Relay's documentation and from the
workspace's support history, citing the passages it used. This is the running form of the
`rag-support-bot` benchmark scenario's system description and exists as a review target.

```bash
uv sync
uv run uvicorn relay_answers.main:app --port 8081
uv run pytest
```

Configuration is read from the environment: `PROVIDER_URL` and `PROVIDER_KEY` for the model
provider (without a key, answers come from a stub), `DAILY_ANSWER_QUOTA` per workspace, and
`WORKSPACE_TOKENS` as a JSON object mapping bearer tokens to workspace identifiers (a development
mapping is used when unset).

`POST /v1/answers` takes `{"question": "..."}` with a workspace-scoped bearer token and returns the
answer with the source reference of each cited passage. `GET /v1/health` is the liveness probe.
`relay_answers.ingestion.run_nightly` is the only writer to the index.
