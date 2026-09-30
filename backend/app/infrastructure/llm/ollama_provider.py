import json

import httpx
from pydantic import ValidationError

from app.domain.entities import Citation, GroundedAnswer, Source
from app.domain.exceptions import AIProviderError
from app.infrastructure.llm.openai_provider import AnswerPayload
from app.infrastructure.llm.prompts import SYSTEM_PROMPT

_JSON_INSTRUCTIONS = (
    'Responde EXCLUSIVAMENTE con un JSON válido de forma exacta: '
    '{"answer": string, "supported": boolean, '
    '"citations": [{"chunk": integer, "quote": string}]}. '
    "No agregues texto fuera del JSON."
)


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
                    "format": "json",
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
        except (httpx.HTTPError, KeyError, ValueError, ValidationError) as exc:
            raise AIProviderError() from exc
        return GroundedAnswer(
            result.answer,
            [Citation(c.chunk, c.quote) for c in result.citations],
            result.supported,
        )
