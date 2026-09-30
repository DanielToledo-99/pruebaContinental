from typing import Self

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.infrastructure.repositories.sqlalchemy_repository import SQLAlchemyRepository
from app.infrastructure.vector_store.pgvector_store import PgVectorStore


class SQLAlchemyUnitOfWork:
    def __init__(self, factory: async_sessionmaker[AsyncSession]) -> None:
        self.factory = factory

    async def __aenter__(self) -> Self:
        self.session = self.factory()
        self.repository = SQLAlchemyRepository(self.session)
        self.vectors = PgVectorStore(self.session)
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.session.rollback()
        await self.session.close()

    async def commit(self) -> None:
        await self.session.commit()
