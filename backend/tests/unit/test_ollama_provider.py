import json

import httpx

from app.domain.entities import Source
from app.infrastructure.llm.ollama_provider import OllamaLLMProvider


async def test_llm_structured_output_contract():
    def handler(request: httpx.Request):
        body = json.loads(request.content)
        assert body["model"] == "qwen2.5-coder:7b"
        assert body["format"] == "json"
        assert body["messages"][0]["role"] == "system"
        user_content = json.loads(body["messages"][1]["content"])
        assert user_content["context"] == [
            {"chunk": 1, "text": "El objetivo es ahorrar agua."}
        ]
        return httpx.Response(
            200,
            json={
                "message": {
                    "role": "assistant",
                    "content": json.dumps(
                        {
                            "answer": "Ahorrar agua.",
                            "supported": True,
                            "citations": [{"chunk": 1, "quote": "ahorrar agua"}],
                        }
                    ),
                }
            },
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://ollama.local"
    ) as client:
        result = await OllamaLLMProvider(client, "qwen2.5-coder:7b").answer(
            "¿Objetivo?", [Source(1, "El objetivo es ahorrar agua.", 0.9)]
        )
        assert result.supported
        assert result.answer == "Ahorrar agua."
        assert result.citations[0].chunk == 1
