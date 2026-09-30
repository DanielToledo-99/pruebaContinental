import pytest

from app.api.dependencies import Services
from app.application.use_cases import (
    AskQuestion,
    CreateSession,
    GetHistory,
    UploadDocument,
)
from app.infrastructure.document_processing.parsers import FileDocumentProcessor
from tests.fakes import (
    FakeEmbeddingProvider,
    FakeLLMProvider,
    FakeUnitOfWork,
    MemoryDatabase,
)


@pytest.fixture
def setup_services():
    db = MemoryDatabase()
    embeddings = FakeEmbeddingProvider()
    llm = FakeLLMProvider()

    def uow():
        return FakeUnitOfWork(db)

    services = Services(
        CreateSession(uow),
        UploadDocument(uow, FileDocumentProcessor(), embeddings),
        AskQuestion(uow, embeddings, llm),
        GetHistory(uow),
    )
    return services, db, llm


@pytest.fixture
async def loaded(setup_services):
    services, db, llm = setup_services
    session = await services.create_session.execute()
    document = await services.upload.execute(
        session.id,
        "proyecto.txt",
        "text/plain",
        b"El objetivo principal es reducir el consumo de agua en un 20%.",
    )
    return services, db, llm, session, document
