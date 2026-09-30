import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from app.domain import exceptions as errors

logger = logging.getLogger(__name__)
STATUS_CODES: dict[type[errors.ApplicationError], int] = {
    errors.SessionNotFound: 404,
    errors.DocumentNotFound: 404,
    errors.DocumentNotProcessed: 409,
    errors.NoProcessedDocument: 409,
    errors.InvalidDocument: 400,
    errors.UnsupportedDocumentType: 415,
    errors.DocumentTooLarge: 413,
    errors.EmptyQuestion: 400,
    errors.AIProviderError: 502,
    errors.EmbeddingConfigurationChanged: 409,
}


def error_response(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status, content={"error": {"code": code, "message": message}}
    )


def install_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(errors.ApplicationError)
    async def application_error(
        request: Request, exc: errors.ApplicationError
    ) -> JSONResponse:
        logger.warning("request_error code=%s path=%s", exc.code, request.url.path)
        return error_response(STATUS_CODES.get(type(exc), 400), exc.code, str(exc))

    @app.exception_handler(RequestValidationError)
    async def validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return error_response(
            422,
            "VALIDATION_ERROR",
            "Revisa los campos enviados y los identificadores de sesión y documento.",
        )

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException) -> JSONResponse:
        return error_response(exc.status_code, "HTTP_ERROR", str(exc.detail))

    # Unexpected exceptions are handled by app.api.middleware.UnhandledErrors.
