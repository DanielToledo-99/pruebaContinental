from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ResponseModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class SessionResponse(ResponseModel):
    session_id: UUID


class DocumentResponse(ResponseModel):
    document_id: UUID
    session_id: UUID
    filename: str
    status: Literal["processing", "processed", "failed"]
    chunk_count: int


class AskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_id: UUID
    document_id: UUID
    question: str = Field(min_length=1, max_length=2000)

    @field_validator("question", mode="before")
    @classmethod
    def strip_question(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class SourceResponse(ResponseModel):
    chunk: int
    text: str
    score: float
    quote: str


class MessageResponse(ResponseModel):
    id: UUID
    document_id: UUID
    role: Literal["user", "assistant"]
    content: str
    sequence: int
    created_at: datetime
    sources: list[SourceResponse]


class HistoryResponse(ResponseModel):
    session_id: UUID
    messages: list[MessageResponse]
    documents: list[DocumentResponse]


class AskResponse(ResponseModel):
    session_id: UUID
    answer: str
    sources: list[SourceResponse]
    messages: list[MessageResponse]


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail
