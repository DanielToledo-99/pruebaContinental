import json
import math

from openai import AsyncOpenAI, OpenAIError
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.domain.entities import Citation, GroundedAnswer, Source
from app.domain.exceptions import AIProviderError
from app.infrastructure.llm.prompts import SYSTEM_PROMPT


class CitationPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    chunk: int
    quote: str


class AnswerPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    answer: str = Field(max_length=12_000)
    supported: bool
    citations: list[CitationPayload]


class OpenAILLMProvider:
    def __init__(self, client: AsyncOpenAI | None, model: str) -> None:
        self.client = client
        self.model = model

    async def answer(self, question: str, context: list[Source]) -> GroundedAnswer:
        if self.client is None:
            raise AIProviderError(
                "Configura OPENAI_API_KEY en el backend para consultar."
            )
        try:
            response = await self.client.responses.parse(
                model=self.model,
                instructions=SYSTEM_PROMPT,
                input=json.dumps(
                    {
                        "question": question,
                        "context": [
                            {"chunk": s.chunk, "text": s.text} for s in context
                        ],
                    },
                    ensure_ascii=False,
                ),
                text_format=AnswerPayload,
                max_output_tokens=1800,
                store=False,
            )
            result = response.output_parsed
            if result is None or response.status != "completed":
                raise AIProviderError()
            return GroundedAnswer(
                result.answer,
                [Citation(c.chunk, c.quote) for c in result.citations],
                result.supported,
            )
        except (OpenAIError, ValidationError, ValueError) as exc:
            raise AIProviderError() from exc


class OpenAIEmbeddingProvider:
    def __init__(
        self, client: AsyncOpenAI | None, model: str, dimensions: int = 1536
    ) -> None:
        self.client = client
        self.model = model
        self.dimensions = dimensions

    @property
    def space(self) -> str:
        return f"openai:{self.model}:{self.dimensions}"

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if self.client is None:
            raise AIProviderError(
                "Configura OPENAI_API_KEY en el backend para procesar."
            )
        vectors: list[list[float]] = []
        try:
            for offset in range(0, len(texts), 64):
                batch = texts[offset : offset + 64]
                result = await self.client.embeddings.create(
                    model=self.model,
                    input=batch,
                    dimensions=self.dimensions,
                )
                ordered = sorted(result.data, key=lambda item: item.index)
                if [item.index for item in ordered] != list(range(len(batch))):
                    raise AIProviderError()
                for item in ordered:
                    vector = item.embedding
                    if (
                        len(vector) != self.dimensions
                        or not all(math.isfinite(value) for value in vector)
                        or not any(vector)
                    ):
                        raise AIProviderError()
                    vectors.append(vector)
        except (OpenAIError, ValueError) as exc:
            raise AIProviderError() from exc
        return vectors
