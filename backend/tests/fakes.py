from copy import deepcopy
from dataclasses import dataclass, field
from uuid import UUID, uuid4

from app.domain.entities import (
    Chunk,
    Citation,
    Document,
    GroundedAnswer,
    Message,
    Session,
    Source,
    now,
)


@dataclass
class MemoryDatabase:
    sessions: dict[UUID, Session] = field(default_factory=dict)
    documents: dict[UUID, Document] = field(default_factory=dict)
    messages: list[Message] = field(default_factory=list)
    chunks: list[Chunk] = field(default_factory=list)
    relevant: bool = True


class FakeRepository:
    def __init__(self, db: MemoryDatabase) -> None:
        self.db = db

    async def create_session(self, session: Session) -> None:
        self.db.sessions[session.id] = session

    async def session_exists(self, session_id: UUID) -> bool:
        return session_id in self.db.sessions

    async def get_document(self, document_id: UUID) -> Document | None:
        return self.db.documents.get(document_id)

    async def save_document(self, document: Document) -> None:
        self.db.documents[document.id] = document

    async def list_documents(self, session_id: UUID) -> list[Document]:
        return [
            doc for doc in self.db.documents.values() if doc.session_id == session_id
        ]

    async def history(self, session_id: UUID) -> list[Message]:
        return sorted(
            [
                message
                for message in self.db.messages
                if message.session_id == session_id
            ],
            key=lambda message: message.sequence,
        )

    async def append_turn(
        self,
        session_id: UUID,
        document_id: UUID,
        question: str,
        answer: str,
        sources: list[Source],
    ) -> list[Message]:
        sequence = len(await self.history(session_id))
        pair = [
            Message(
                uuid4(), session_id, document_id, "user", question, sequence, now()
            ),
            Message(
                uuid4(),
                session_id,
                document_id,
                "assistant",
                answer,
                sequence + 1,
                now(),
                sources,
            ),
        ]
        self.db.messages.extend(pair)
        return pair


class FakeVectorStore:
    def __init__(self, db: MemoryDatabase) -> None:
        self.db = db

    async def add(self, chunks: list[Chunk]) -> None:
        self.db.chunks.extend(chunks)

    async def search(
        self, document_id: UUID, embedding: list[float], top_k: int, min_score: float
    ) -> list[Source]:
        if not self.db.relevant:
            return []
        return [
            Source(chunk.index, chunk.text, 0.9)
            for chunk in self.db.chunks
            if chunk.document_id == document_id
        ][:top_k]


class FakeUnitOfWork:
    def __init__(self, db: MemoryDatabase) -> None:
        self.db = db

    async def __aenter__(self):
        self.working = deepcopy(self.db)
        self.repository = FakeRepository(self.working)
        self.vectors = FakeVectorStore(self.working)
        return self

    async def __aexit__(self, *args: object) -> None:
        pass

    async def commit(self) -> None:
        self.db.sessions = self.working.sessions
        self.db.documents = self.working.documents
        self.db.messages = self.working.messages
        self.db.chunks = self.working.chunks


class FakeEmbeddingProvider:
    space = "fake:3"

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0, 0.0] for _ in texts]


class FakeLLMProvider:
    def __init__(self) -> None:
        self.calls: list[tuple[str, list[Source]]] = []
        self.result: GroundedAnswer | None = None
        self.error: Exception | None = None

    async def answer(self, question: str, context: list[Source]) -> GroundedAnswer:
        self.calls.append((question, context))
        if self.error:
            raise self.error
        return self.result or GroundedAnswer(
            context[0].text, [Citation(context[0].chunk, context[0].text)], True
        )
