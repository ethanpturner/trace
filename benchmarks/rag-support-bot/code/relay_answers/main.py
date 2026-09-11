"""The answer service: receives a question, retrieves, assembles the prompt, calls the provider."""

from __future__ import annotations

from typing import Annotated

from fastapi import FastAPI, Header
from pydantic import BaseModel, ConfigDict, Field

from relay_answers.auth import workspace_for
from relay_answers.config import load_settings
from relay_answers.embeddings import embed
from relay_answers.index import RetrievalIndex
from relay_answers.prompt import assemble_prompt, passages_from
from relay_answers.provider import ModelProvider, ProviderRequest
from relay_answers.quota import DailyQuota

settings = load_settings()
index = RetrievalIndex()
provider = ModelProvider(settings.provider_url, settings.provider_key)
quota = DailyQuota(settings.daily_answer_quota)

app = FastAPI(title="Relay Answers API", version="1.2")


class Question(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1, max_length=2000)


class Citation(BaseModel):
    reference: str
    source_ref: str


class Answer(BaseModel):
    answer: str
    citations: list[Citation]


@app.get("/v1/health")
def health() -> dict[str, str]:
    """Liveness probe for the deployment beside the Relay API."""
    return {"status": "ok"}


@app.post("/v1/answers", response_model=Answer)
def answer(
    body: Question,
    authorization: Annotated[str | None, Header()] = None,
) -> Answer:
    """Ask a question and receive a cited answer."""
    workspace_id = workspace_for(authorization, settings.workspace_tokens)
    quota.charge(workspace_id)

    hits = index.search(embed(body.question), k=settings.top_k)
    passages = passages_from(hits)
    prompt = assemble_prompt(body.question, passages)
    text = provider.answer(ProviderRequest(prompt=prompt), passages)

    return Answer(
        answer=text,
        citations=[
            Citation(reference=hit.chunk.chunk_id, source_ref=hit.chunk.source_ref) for hit in hits
        ],
    )
