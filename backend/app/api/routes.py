from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from sqlalchemy import text

from app.api.dependencies import Services, get_services
from app.api.schemas import (
    AskRequest,
    AskResponse,
    DocumentResponse,
    ErrorResponse,
    HistoryResponse,
    SessionResponse,
)
from app.domain.entities import Document
from app.domain.exceptions import DocumentTooLarge

router = APIRouter(
    responses={
        status: {"model": ErrorResponse}
        for status in (400, 404, 409, 413, 415, 422, 500, 502)
    }
)
ServicesDep = Annotated[Services, Depends(get_services)]


def document_response(document: Document) -> DocumentResponse:
    return DocumentResponse(
        document_id=document.id,
        session_id=document.session_id,
        filename=document.filename,
        status=document.status,
        chunk_count=document.chunk_count,
    )


@router.post(
    "/sessions", response_model=SessionResponse, status_code=201, tags=["Sessions"]
)
async def create_session(services: ServicesDep) -> SessionResponse:
    session = await services.create_session.execute()
    return SessionResponse(session_id=session.id)


@router.post(
    "/documents", response_model=DocumentResponse, status_code=201, tags=["Documents"]
)
async def upload_document(
    request: Request,
    services: ServicesDep,
    session_id: Annotated[UUID, Form()],
    file: Annotated[UploadFile, File()],
) -> DocumentResponse:
    try:
        limit = request.app.state.settings.max_upload_mb * 1024 * 1024
        content = await file.read(limit + 1)
        if len(content) > limit:
            raise DocumentTooLarge()
        document = await services.upload.execute(
            session_id, file.filename or "", file.content_type or "", content
        )
        return document_response(document)
    finally:
        await file.close()


@router.post("/ask", response_model=AskResponse, tags=["Chat"])
async def ask(body: AskRequest, services: ServicesDep) -> AskResponse:
    result = await services.ask.execute(
        body.session_id, body.document_id, body.question
    )
    return AskResponse.model_validate(result)


@router.get("/history/{session_id}", response_model=HistoryResponse, tags=["Sessions"])
async def history(session_id: UUID, services: ServicesDep) -> HistoryResponse:
    result = await services.history.execute(session_id)
    return HistoryResponse(
        session_id=result.session_id,
        messages=result.messages,
        documents=[document_response(document) for document in result.documents],
    )


@router.get("/health", tags=["Health"])
async def health(request: Request) -> dict[str, str]:
    engine = getattr(request.app.state, "engine", None)
    if engine is not None:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    return {"status": "ok"}
