import json

import httpx
import pytest

from app.domain.entities import Source
from app.domain.exceptions import AIProviderError
from app.infrastructure.llm.ollama_provider import (
    OllamaEmbeddingProvider,
    OllamaLLMProvider,
)


async def test_llm_structured_output_contract():
    def handler(request: httpx.Request):
        body = json.loads(request.content)
        assert body["model"] == "qwen2.5-coder:7b"
        assert body["format"]["required"] == ["answer", "supported", "citations"]
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


async def test_embeddings_are_batched_in_order():
    requests: list[list[str]] = []

    def handler(request: httpx.Request):
        body = json.loads(request.content)
        assert request.url.path == "/api/embed"
        assert body["model"] == "bge-m3"
        requests.append(body["input"])
        return httpx.Response(
            200,
            json={"embeddings": [[float(len(text)), 1.0] for text in body["input"]]},
        )

    texts = [str(number) * (number + 1) for number in range(5)]
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://ollama.local"
    ) as client:
        provider = OllamaEmbeddingProvider(client, "bge-m3", batch_size=2)
        vectors = await provider.embed(texts)
    assert provider.space == "ollama:bge-m3"
    assert requests == [texts[0:2], texts[2:4], texts[4:5]]
    assert vectors == [[float(number + 1), 1.0] for number in range(5)]


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(404, json={"error": "model 'bge-m3' not found"}),
        httpx.Response(200, json={"embeddings": [[1.0, 0.0]]}),
        httpx.Response(200, json={"embeddings": [[1.0, 0.0], [1.0]]}),
        httpx.Response(200, json={"embeddings": [[0.0, 0.0], [1.0, 0.0]]}),
        httpx.Response(200, json={"unexpected": True}),
    ],
)
async def test_invalid_embedding_responses_raise_provider_error(response):
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: response),
        base_url="http://ollama.local",
    ) as client:
        with pytest.raises(AIProviderError):
            await OllamaEmbeddingProvider(client, "bge-m3").embed(["uno", "dos"])
