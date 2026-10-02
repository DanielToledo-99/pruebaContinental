import json
import math

import httpx
from pydantic import ValidationError

from app.domain.entities import Citation, GroundedAnswer, Source
from app.domain.exceptions import AIProviderError
from app.infrastructure.llm.openai_provider import AnswerPayload
from app.infrastructure.llm.prompts import SYSTEM_PROMPT

_JSON_INSTRUCTIONS = (
    "Responde EXCLUSIVAMENTE con un JSON válido de forma exacta: "
    '{"answer": string, "supported": boolean, '
    '"citations": [{"chunk": integer, "quote": string}]}. '
    "No agregues texto fuera del JSON."
)
_ANSWER_SCHEMA = {
    "type": "object",
    "properties": {
        "answer": {"type": "string"},
        "supported": {"type": "boolean"},
        "citations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "chunk": {"type": "integer"},
                    "quote": {"type": "string"},
                },
                "required": ["chunk", "quote"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["answer", "supported", "citations"],
    "additionalProperties": False,
}


class OllamaLLMProvider:
    def __init__(self, client: httpx.AsyncClient, model: str) -> None:
        self.client = client
        self.model = model

    async def answer(self, question: str, context: list[Source]) -> GroundedAnswer:
        try:
            response = await self.client.post(
                "/api/chat",
                json={
                    "model": self.model,
                    "stream": False,
                    "format": _ANSWER_SCHEMA,
                    "options": {"temperature": 0},
                    "messages": [
                        {
                            "role": "system",
                            "content": SYSTEM_PROMPT + "\n\n" + _JSON_INSTRUCTIONS,
                        },
                        {
                            "role": "user",
                            "content": json.dumps(
                                {
                                    "question": question,
                                    "context": [
                                        {"chunk": s.chunk, "text": s.text}
                                        for s in context
                                    ],
                                },
                                ensure_ascii=False,
                            ),
                        },
                    ],
                },
            )
            response.raise_for_status()
            content = response.json()["message"]["content"]
            result = AnswerPayload.model_validate_json(content)
        except (
            httpx.HTTPError,
            KeyError,
            TypeError,
            ValueError,
            ValidationError,
        ) as exc:
            raise AIProviderError() from exc
        return GroundedAnswer(
            result.answer,
            [Citation(c.chunk, c.quote) for c in result.citations],
            result.supported,
        )


class OllamaEmbeddingProvider:
    def __init__(
        self, client: httpx.AsyncClient, model: str, batch_size: int = 16
    ) -> None:
        self.client = client
        self.model = model
        self.batch_size = batch_size

    @property
    def space(self) -> str:
        return f"ollama:{self.model}"

    async def embed(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        try:
            for offset in range(0, len(texts), self.batch_size):
                batch = texts[offset : offset + self.batch_size]
                response = await self.client.post(
                    "/api/embed", json={"model": self.model, "input": batch}
                )
                response.raise_for_status()
                embeddings = response.json()["embeddings"]
                if len(embeddings) != len(batch):
                    raise AIProviderError()
                vectors.extend(embeddings)
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
            raise AIProviderError() from exc
        dimensions = len(vectors[0]) if vectors else 0
        for vector in vectors:
            if (
                len(vector) != dimensions
                or not all(
                    isinstance(value, int | float) and math.isfinite(value)
                    for value in vector
                )
                or not any(vector)
            ):
                raise AIProviderError()
        return vectors
