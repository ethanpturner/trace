# Deploy Notifier

A small service that receives deployment events from a continuous-integration platform and posts
them to a chat channel. It is the running form of the `unsigned-webhooks` benchmark scenario's
system description and exists as a review target.

```bash
uv sync
uv run uvicorn deploy_notifier.main:app --port 8080
uv run pytest
```

Configuration is read from the environment: `CHAT_API_URL` and `CHAT_TOKEN` for the chat platform
(without a token, messages go to an in-memory outbox), `CHAT_CHANNEL` for the destination, and
`CI_SIGNING_SECRET` for the CI platform's shared secret.

The CI platform delivers each deployment event as a JSON body to `POST /events`. The body names the
repository, the environment, the commit, and a delivery identifier.
