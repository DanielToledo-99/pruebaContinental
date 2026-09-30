from typing import Protocol, Self
from uuid import UUID

from app.domain.entities import (
    Chunk,
    Document,
    GroundedAnswer,
    Message,
    Session,
    Source,
)


class LLMProvider(Protocol):
    async def answer(self, question: str, context: list[Source]) -> GroundedAnswer: ...


class EmbeddingProvider(Protocol):
    @property
    def space(self) -> str: ...

    async def embed(self, texts: list[str]) -> list[list[float]]: ...


class DocumentParser(Protocol):
    def parse(self, content: bytes, max_chars: int) -> str: ...


class DocumentProcessor(Protocol):
    def validate(self, filename: str, content_type: str, content: bytes) -> str: ...

    async def extract(self, filename: str, content: bytes) -> str: ...


class Repository(Protocol):
    async def create_session(self, session: Session) -> None: ...

    async def session_exists(self, session_id: UUID) -> bool: ...

    async def get_document(self, document_id: UUID) -> Document | None: ...

    async def save_document(self, document: Document) -> None: ...

    async def list_documents(self, session_id: UUID) -> list[Document]: ...

    async def history(self, session_id: UUID) -> list[Message]: ...

    async def append_turn(
        self,
        session_id: UUID,
        document_id: UUID,
        question: str,
        answer: str,
        sources: list[Source],
    ) -> list[Message]: ...


class VectorStore(Protocol):
    async def add(self, chunks: list[Chunk]) -> None: ...

    async def search(
        self, document_id: UUID, embedding: list[float], top_k: int, min_score: float
    ) -> list[Source]: ...


class UnitOfWork(Protocol):
    repository: Repository
    vectors: VectorStore

    async def __aenter__(self) -> Self: ...

    async def __aexit__(self, *args: object) -> None: ...

    async def commit(self) -> None: ...
