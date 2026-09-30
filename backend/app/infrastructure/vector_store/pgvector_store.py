from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import Chunk, Source
from app.infrastructure.database.models import ChunkRow


class PgVectorStore:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, chunks: list[Chunk]) -> None:
        self.session.add_all(
            [
                ChunkRow(
                    id=uuid4(),
                    document_id=chunk.document_id,
                    chunk_index=chunk.index,
                    content=chunk.text,
                    embedding=chunk.embedding,
                )
                for chunk in chunks
            ]
        )
        await self.session.flush()

    async def search(
        self, document_id: UUID, embedding: list[float], top_k: int, min_score: float
    ) -> list[Source]:
        distance = ChunkRow.embedding.cosine_distance(embedding).label("distance")
        rows = await self.session.execute(
            select(ChunkRow, distance)
            .where(ChunkRow.document_id == document_id)
            .where(distance <= 1 - min_score)
            .order_by(distance, ChunkRow.chunk_index)
            .limit(top_k)
        )
        return [
            Source(row.chunk_index, row.content, max(-1.0, min(1.0, 1 - score)))
            for row, score in rows
        ]
