import asyncio
import os
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.dependencies import Services
from app.application.use_cases import (
    AskQuestion,
    CreateSession,
    GetHistory,
    UploadDocument,
)
from app.core.config import Settings
from app.domain.entities import Chunk, Document, Session
from app.infrastructure.database.uow import SQLAlchemyUnitOfWork
from app.infrastructure.document_processing.parsers import FileDocumentProcessor
from app.main import create_app
from tests.fakes import FakeEmbeddingProvider, FakeLLMProvider

pytestmark = pytest.mark.postgres


@pytest_asyncio.fixture
async def uow_factory():
    url = os.getenv("TEST_DATABASE_URL", "")
    if not url:
        pytest.skip("Set TEST_DATABASE_URL for PostgreSQL integration tests")
    if not url.rsplit("/", 1)[-1].endswith("_test"):
        raise RuntimeError(
            "TEST_DATABASE_URL must point to a dedicated *_test database"
        )
    engine = create_async_engine(url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.execute(text("TRUNCATE sessions CASCADE"))
    yield lambda: SQLAlchemyUnitOfWork(factory)
    await engine.dispose()


async def create_document(uow_factory):
    session = Session()
    document = Document(
        uuid4(), session.id, "file.txt", "text/plain", "processed", 1, "fake:3"
    )
    async with uow_factory() as work:
        await work.repository.create_session(session)
        await work.repository.save_document(document)
        await work.commit()
    return session, document


async def test_concurrent_turns_are_atomic_and_ordered(uow_factory):
    session, document = await create_document(uow_factory)

    async def append(number):
        async with uow_factory() as work:
            await work.repository.append_turn(
                session.id, document.id, f"q{number}", f"a{number}", []
            )
            await work.commit()

    await asyncio.gather(*(append(number) for number in range(8)))
    async with uow_factory() as work:
        messages = await work.repository.history(session.id)
    assert [message.sequence for message in messages] == list(range(16))
    for user, assistant in zip(messages[::2], messages[1::2], strict=True):
        assert user.role == "user" and assistant.role == "assistant"
        assert user.content[1:] == assistant.content[1:]


async def test_transaction_rollback_leaves_no_partial_turn(uow_factory):
    session, document = await create_document(uow_factory)
    with pytest.raises(RuntimeError):
        async with uow_factory() as work:
            await work.repository.append_turn(session.id, document.id, "q", "a", [])
            raise RuntimeError("simulate failure before commit")
    async with uow_factory() as work:
        assert await work.repository.history(session.id) == []


async def test_vector_search_is_scoped_and_thresholded(uow_factory):
    _, first = await create_document(uow_factory)
    _, second = await create_document(uow_factory)
    async with uow_factory() as work:
        await work.vectors.add(
            [
                Chunk(first.id, 1, "first relevant", [1, 0, 0]),
                Chunk(first.id, 2, "irrelevant", [0, 1, 0]),
                Chunk(second.id, 1, "private other document", [1, 0, 0]),
            ]
        )
        await work.commit()
    async with uow_factory() as work:
        sources = await work.vectors.search(first.id, [1, 0, 0], 4, 0.25)
    assert [source.text for source in sources] == ["first relevant"]
    assert sources[0].score == pytest.approx(1)


async def test_http_roundtrip_persists_across_app_restart(uow_factory):
    embeddings, llm = FakeEmbeddingProvider(), FakeLLMProvider()
    services = Services(
        CreateSession(uow_factory),
        UploadDocument(uow_factory, FileDocumentProcessor(), embeddings),
        AskQuestion(uow_factory, embeddings, llm),
        GetHistory(uow_factory),
    )
    app = create_app(Settings(_env_file=None), services)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as client:
            session_id = (await client.post("/sessions")).json()["session_id"]
            response = await client.post(
                "/documents",
                data={"session_id": session_id},
                files={
                    "file": (
                        "project.txt",
                        b"El objetivo es ahorrar agua.",
                        "text/plain",
                    )
                },
            )
            assert response.status_code == 201
            document_id = response.json()["document_id"]
            response = await client.post(
                "/ask",
                json={
                    "session_id": session_id,
                    "document_id": document_id,
                    "question": "Objetivo",
                },
            )
            assert response.status_code == 200
            assert response.json()["sources"][0]["quotes"] == [
                "El objetivo es ahorrar agua."
            ]
    restarted = create_app(Settings(_env_file=None), services)
    async with restarted.router.lifespan_context(restarted):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(restarted), base_url="http://test"
        ) as client:
            response = await client.get(f"/history/{session_id}")
            assert [message["role"] for message in response.json()["messages"]] == [
                "user",
                "assistant",
            ]
            assert response.json()["documents"][0]["document_id"] == document_id
