from dataclasses import asdict
from datetime import timedelta
from typing import Literal, cast
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import Document, Message, Session, Source, now
from app.domain.exceptions import SessionNotFound
from app.infrastructure.database.models import DocumentRow, MessageRow, SessionRow


def to_document(row: DocumentRow) -> Document:
    return Document(
        id=row.id,
        session_id=row.session_id,
        filename=row.filename,
        content_type=row.content_type,
        status=cast("DocumentStatus", row.status),
        chunk_count=row.chunk_count,
        embedding_space=row.embedding_space,
        created_at=row.created_at,
    )


type DocumentStatus = Literal["processing", "processed", "failed"]


def to_source(data: dict) -> Source:
    # Messages saved before multi-quote sources stored a single "quote".
    legacy = [data["quote"]] if data.get("quote") else []
    return Source(
        chunk=data["chunk"],
        text=data["text"],
        score=data["score"],
        quotes=data.get("quotes", legacy),
    )


def to_message(row: MessageRow) -> Message:
    return Message(
        id=row.id,
        session_id=row.session_id,
        document_id=row.document_id,
        role=cast("MessageRole", row.role),
        content=row.content,
        sequence=row.sequence,
        created_at=row.created_at,
        sources=[to_source(source) for source in row.sources],
    )


type MessageRole = Literal["user", "assistant"]


class SQLAlchemyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_session(self, session: Session) -> None:
        self.session.add(SessionRow(**asdict(session), next_sequence=0))
        await self.session.flush()

    async def session_exists(self, session_id: UUID) -> bool:
        return await self.session.get(SessionRow, session_id) is not None

    async def get_document(self, document_id: UUID) -> Document | None:
        row = await self.session.get(DocumentRow, document_id)
        return to_document(row) if row else None

    async def save_document(self, document: Document) -> None:
        await self.session.merge(DocumentRow(**asdict(document)))
        await self.session.flush()

    async def list_documents(self, session_id: UUID) -> list[Document]:
        rows = await self.session.scalars(
            select(DocumentRow)
            .where(DocumentRow.session_id == session_id)
            .order_by(DocumentRow.created_at, DocumentRow.id)
        )
        return [to_document(row) for row in rows]

    async def history(self, session_id: UUID) -> list[Message]:
        rows = await self.session.scalars(
            select(MessageRow)
            .where(MessageRow.session_id == session_id)
            .order_by(MessageRow.sequence)
        )
        return [to_message(row) for row in rows]

    async def append_turn(
        self,
        session_id: UUID,
        document_id: UUID,
        question: str,
        answer: str,
        sources: list[Source],
    ) -> list[Message]:
        session = await self.session.scalar(
            select(SessionRow).where(SessionRow.id == session_id).with_for_update()
        )
        if session is None:
            raise SessionNotFound()
        timestamp = now()
        rows = [
            MessageRow(
                id=uuid4(),
                session_id=session_id,
                document_id=document_id,
                role=role,
                content=content,
                sequence=session.next_sequence + offset,
                created_at=timestamp + timedelta(microseconds=offset),
                sources=(
                    [asdict(source) for source in sources]
                    if role == "assistant"
                    else []
                ),
            )
            for offset, (role, content) in enumerate(
                [("user", question), ("assistant", answer)]
            )
        ]
        session.next_sequence += 2
        self.session.add_all(rows)
        await self.session.flush()
        return [to_message(row) for row in rows]
