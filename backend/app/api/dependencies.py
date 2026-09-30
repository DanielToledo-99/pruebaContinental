from dataclasses import dataclass

from fastapi import Request

from app.application.use_cases import (
    AskQuestion,
    CreateSession,
    GetHistory,
    UploadDocument,
)


@dataclass
class Services:
    create_session: CreateSession
    upload: UploadDocument
    ask: AskQuestion
    history: GetHistory


def get_services(request: Request) -> Services:
    return request.app.state.services
