import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.dependencies import Services
from app.api.exception_handlers import install_exception_handlers
from app.api.middleware import RequestSizeLimit, UnhandledErrors
from app.api.routes import router
from app.application.use_cases import (
    AskQuestion,
    CreateSession,
    GetHistory,
    UploadDocument,
)
from app.core.config import Settings, get_settings
from app.infrastructure.database.uow import SQLAlchemyUnitOfWork
from app.infrastructure.document_processing.parsers import FileDocumentProcessor
from app.infrastructure.llm.ollama_provider import (
    OllamaEmbeddingProvider,
    OllamaLLMProvider,
)
from app.infrastructure.llm.openai_provider import (
    OpenAIEmbeddingProvider,
    OpenAILLMProvider,
)

logger = logging.getLogger(__name__)


def create_app(
    settings: Settings | None = None, services: Services | None = None
) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        logging.basicConfig(
            level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s"
        )
        logging.getLogger("httpx").setLevel(logging.WARNING)
        if services is not None:
            app.state.services = services
            yield
            return
        engine = create_async_engine(
            settings.database_url, pool_pre_ping=True, hide_parameters=True
        )
        factory = async_sessionmaker(engine, expire_on_commit=False)
        app.state.engine = engine
        key = settings.openai_api_key.get_secret_value()
        client = (
            AsyncOpenAI(api_key=key, timeout=settings.ai_timeout_seconds, max_retries=1)
            if key
            else None
        )
        providers = {settings.llm_provider, settings.embedding_backend}
        if "openai" in providers and client is None:
            logger.warning(
                "openai_api_key_missing llm=%s embeddings=%s: uploads or questions "
                "will fail until OPENAI_API_KEY is set or LLM_PROVIDER=ollama",
                settings.llm_provider,
                settings.embedding_backend,
            )
        ollama_client = (
            httpx.AsyncClient(
                base_url=settings.ollama_base_url, timeout=settings.ai_timeout_seconds
            )
            if "ollama" in providers
            else None
        )
        embeddings = (
            OllamaEmbeddingProvider(ollama_client, settings.ollama_embedding_model)
            if ollama_client is not None and settings.embedding_backend == "ollama"
            else OpenAIEmbeddingProvider(
                client, settings.openai_embedding_model, settings.embedding_dimensions
            )
        )
        llm_provider = (
            OllamaLLMProvider(ollama_client, settings.ollama_model)
            if ollama_client is not None and settings.llm_provider == "ollama"
            else OpenAILLMProvider(client, settings.openai_model)
        )
        logger.info(
            "ai_providers llm=%s embeddings=%s",
            settings.llm_provider,
            embeddings.space,
        )

        def uow() -> SQLAlchemyUnitOfWork:
            return SQLAlchemyUnitOfWork(factory)

        app.state.services = Services(
            CreateSession(uow),
            UploadDocument(
                uow,
                FileDocumentProcessor(
                    settings.max_upload_mb * 1024 * 1024,
                    settings.max_text_chars,
                    settings.max_pdf_pages,
                ),
                embeddings,
                settings.chunk_size,
                settings.chunk_overlap,
            ),
            AskQuestion(
                uow,
                embeddings,
                llm_provider,
                settings.retrieval_top_k,
                settings.retrieval_min_score,
            ),
            GetHistory(uow),
        )
        try:
            yield
        finally:
            if client:
                await client.close()
            if ollama_client:
                await ollama_client.aclose()
            await engine.dispose()

    app = FastAPI(title="Document AI Assistant", version="1.0.0", lifespan=lifespan)
    app.state.settings = settings
    app.add_middleware(UnhandledErrors)
    app.add_middleware(
        RequestSizeLimit, max_bytes=settings.max_upload_mb * 1024 * 1024 + 65536
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )
    install_exception_handlers(app)
    app.include_router(router)
    return app


app = create_app()
