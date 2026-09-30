import json

import httpx
import pytest
from openai import AsyncOpenAI

from app.domain.entities import Source
from app.domain.exceptions import AIProviderError
from app.infrastructure.llm.openai_provider import (
    OpenAIEmbeddingProvider,
    OpenAILLMProvider,
)


async def test_llm_structured_output_contract():
    def handler(request: httpx.Request):
        body = json.loads(request.content)
        assert body["store"] is False
        assert body["text"]["format"]["type"] == "json_schema"
        assert "No utilices conocimiento externo" in body["instructions"]
        assert json.loads(body["input"])["context"] == [
            {"chunk": 1, "text": "El objetivo es ahorrar agua."}
        ]
        return httpx.Response(
            200,
            json={
                "id": "resp_test",
                "object": "response",
                "created_at": 1,
                "model": "gpt-4o-mini",
                "status": "completed",
                "output": [
                    {
                        "type": "message",
                        "id": "msg_test",
                        "role": "assistant",
                        "status": "completed",
                        "content": [
                            {
                                "type": "output_text",
                                "text": json.dumps(
                                    {
                                        "answer": "Ahorrar agua.",
                                        "supported": True,
                                        "citations": [
                                            {"chunk": 1, "quote": "ahorrar agua"}
                                        ],
                                    }
                                ),
                                "annotations": [],
                            }
                        ],
                    }
                ],
            },
        )

    async with AsyncOpenAI(
        api_key="test-key",
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    ) as client:
        result = await OpenAILLMProvider(client, "gpt-4o-mini").answer(
            "¿Objetivo?", [Source(1, "El objetivo es ahorrar agua.", 0.9)]
        )
        assert result.supported
        assert result.answer == "Ahorrar agua."
        assert result.citations[0].chunk == 1


async def test_embeddings_reorder_results_and_send_dimensions():
    def handler(request: httpx.Request):
        body = json.loads(request.content)
        assert body["dimensions"] == 3
        return httpx.Response(
            200,
            json={
                "object": "list",
                "model": "test",
                "data": [
                    {"index": 1, "embedding": [0, 1, 0], "object": "embedding"},
                    {"index": 0, "embedding": [1, 0, 0], "object": "embedding"},
                ],
                "usage": {"prompt_tokens": 2, "total_tokens": 2},
            },
        )

    async with AsyncOpenAI(
        api_key="test-key",
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    ) as client:
        assert await OpenAIEmbeddingProvider(client, "test", 3).embed(
            ["first", "second"]
        ) == [[1, 0, 0], [0, 1, 0]]


async def test_provider_errors_do_not_expose_response_details():
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            401, json={"error": {"message": "sensitive details", "type": "auth_error"}}
        )
    )
    async with AsyncOpenAI(
        api_key="test-key",
        max_retries=0,
        http_client=httpx.AsyncClient(transport=transport),
    ) as client:
        with pytest.raises(AIProviderError, match="proveedor de IA"):
            await OpenAIEmbeddingProvider(client, "test").embed(["text"])


async def test_missing_key_is_actionable():
    with pytest.raises(AIProviderError, match="OPENAI_API_KEY"):
        await OpenAILLMProvider(None, "test").answer("question", [])
