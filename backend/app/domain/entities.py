from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID, uuid4


def now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class Session:
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=now)


@dataclass(frozen=True)
class Document:
    id: UUID
    session_id: UUID
    filename: str
    content_type: str
    status: Literal["processing", "processed", "failed"] = "processing"
    chunk_count: int = 0
    embedding_space: str = ""
    created_at: datetime = field(default_factory=now)


@dataclass(frozen=True)
class Chunk:
    document_id: UUID
    index: int
    text: str
    embedding: list[float]


@dataclass(frozen=True)
class Source:
    chunk: int
    text: str
    score: float
    quotes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Citation:
    chunk: int
    quote: str


@dataclass(frozen=True)
class GroundedAnswer:
    answer: str
    citations: list[Citation]
    supported: bool


@dataclass(frozen=True)
class Message:
    id: UUID
    session_id: UUID
    document_id: UUID
    role: Literal["user", "assistant"]
    content: str
    sequence: int
    created_at: datetime
    sources: list[Source] = field(default_factory=list)


@dataclass(frozen=True)
class History:
    session_id: UUID
    messages: list[Message]
    documents: list[Document]


@dataclass(frozen=True)
class AnswerResult:
    session_id: UUID
    document_id: UUID
    answer: str
    sources: list[Source]
    messages: list[Message]
