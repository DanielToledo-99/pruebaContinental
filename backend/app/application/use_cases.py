import asyncio
import logging
from collections.abc import Callable
from dataclasses import replace
from time import perf_counter
from uuid import UUID, uuid4

from app.application.chunking import split_text
from app.application.grounding import NOT_FOUND, validate_answer
from app.application.ports import (
    DocumentProcessor,
    EmbeddingProvider,
    LLMProvider,
    UnitOfWork,
)
from app.domain.entities import AnswerResult, Chunk, Document, History, Session
from app.domain.exceptions import (
    AIProviderError,
    DocumentNotFound,
    DocumentNotProcessed,
    EmbeddingConfigurationChanged,
    EmptyQuestion,
    InvalidDocument,
    SessionNotFound,
)

logger = logging.getLogger(__name__)
UowFactory = Callable[[], UnitOfWork]


class CreateSession:
    def __init__(self, uow: UowFactory) -> None:
        self.uow = uow

    async def execute(self) -> Session:
        session = Session()
        async with self.uow() as work:
            await work.repository.create_session(session)
            await work.commit()
        return session


class GetHistory:
    def __init__(self, uow: UowFactory) -> None:
        self.uow = uow

    async def execute(self, session_id: UUID) -> History:
        async with self.uow() as work:
            if not await work.repository.session_exists(session_id):
                raise SessionNotFound()
            return History(
                session_id,
                await work.repository.history(session_id),
                await work.repository.list_documents(session_id),
            )


class UploadDocument:
    def __init__(
        self,
        uow: UowFactory,
        processor: DocumentProcessor,
        embeddings: EmbeddingProvider,
        chunk_size: int = 800,
        chunk_overlap: int = 100,
    ) -> None:
        self.uow = uow
        self.processor = processor
        self.embeddings = embeddings
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    async def execute(
        self, session_id: UUID, filename: str, content_type: str, content: bytes
    ) -> Document:
        started = perf_counter()
        filename = self.processor.validate(filename, content_type, content)
        document = Document(
            uuid4(),
            session_id,
            filename,
            content_type,
            embedding_space=self.embeddings.space,
        )
        async with self.uow() as work:
            if not await work.repository.session_exists(session_id):
                raise SessionNotFound()
            await work.repository.save_document(document)
            await work.commit()
        try:
            text = await self.processor.extract(filename, content)
            texts = split_text(text, self.chunk_size, self.chunk_overlap)
            if not texts:
                raise InvalidDocument()
            vectors = await self.embeddings.embed(texts)
            if len(vectors) != len(texts):
                raise AIProviderError()
            chunks = [
                Chunk(document.id, index + 1, text, vector)
                for index, (text, vector) in enumerate(zip(texts, vectors, strict=True))
            ]
            document = replace(document, status="processed", chunk_count=len(chunks))
            async with self.uow() as work:
                await work.vectors.add(chunks)
                await work.repository.save_document(document)
                await work.commit()
        except (Exception, asyncio.CancelledError):
            # CancelledError (shutdown, timeout) would otherwise leave "processing".
            async with self.uow() as work:
                await work.repository.save_document(replace(document, status="failed"))
                await work.commit()
            raise
        logger.info(
            "document_processed document_id=%s session_id=%s "
            "chunks=%s duration_ms=%.0f",
            document.id,
            session_id,
            len(chunks),
            (perf_counter() - started) * 1000,
        )
        return document


class AskQuestion:
    def __init__(
        self,
        uow: UowFactory,
        embeddings: EmbeddingProvider,
        llm: LLMProvider,
        top_k: int = 4,
        min_score: float = 0.25,
    ) -> None:
        self.uow = uow
        self.embeddings = embeddings
        self.llm = llm
        self.top_k = top_k
        self.min_score = min_score

    async def execute(
        self, session_id: UUID, document_id: UUID, question: str
    ) -> AnswerResult:
        question = question.strip()
        if not 1 <= len(question) <= 2000:
            raise EmptyQuestion()
        async with self.uow() as work:
            if not await work.repository.session_exists(session_id):
                raise SessionNotFound()
            document = await work.repository.get_document(document_id)
            if not document or document.session_id != session_id:
                raise DocumentNotFound()
            if document.status != "processed":
                raise DocumentNotProcessed()
            if document.embedding_space != self.embeddings.space:
                raise EmbeddingConfigurationChanged()
        vectors = await self.embeddings.embed([question])
        if len(vectors) != 1:
            raise AIProviderError()
        async with self.uow() as work:
            context = await work.vectors.search(
                document_id, vectors[0], self.top_k, self.min_score
            )
        answer, sources = NOT_FOUND, []
        if context:
            generated = await self.llm.answer(question, context)
            answer, sources = validate_answer(generated, context)
        async with self.uow() as work:
            messages = await work.repository.append_turn(
                session_id, document_id, question, answer, sources
            )
            await work.commit()
        logger.info(
            "question_answered session_id=%s document_id=%s", session_id, document_id
        )
        return AnswerResult(session_id, answer, sources, messages)
