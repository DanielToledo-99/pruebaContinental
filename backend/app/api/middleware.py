import logging
import traceback

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.api.exception_handlers import error_response

logger = logging.getLogger(__name__)


class UnhandledErrors:
    """Answer unexpected failures with the JSON contract, inside CORS.

    Starlette's default 500 handler runs outside CORSMiddleware and re-raises, so
    the server would log the exception message, which may contain document text.
    Only the exception type and code frames are logged here.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        started = False

        async def tracked_send(message: Message) -> None:
            nonlocal started
            started = started or message["type"] == "http.response.start"
            await send(message)

        try:
            await self.app(scope, receive, tracked_send)
        except Exception as exc:
            logger.error(
                "unhandled_error type=%s path=%s\n%s",
                type(exc).__name__,
                scope["path"],
                "".join(traceback.format_tb(exc.__traceback__)).rstrip(),
            )
            if not started:
                response = error_response(
                    500,
                    "INTERNAL_ERROR",
                    "Ocurrió un error interno. Inténtalo nuevamente.",
                )
                await response(scope, receive, send)


class RequestSizeLimit:
    """Bound the entire body before multipart parsing, including chunked uploads."""

    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] not in {"POST", "PUT", "PATCH"}:
            await self.app(scope, receive, send)
            return
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            body.extend(message.get("body", b""))
            if len(body) > self.max_bytes:
                response = error_response(
                    413,
                    "DOCUMENT_TOO_LARGE",
                    "El archivo supera el tamaño máximo permitido.",
                )
                await response(scope, receive, send)
                return
            if not message.get("more_body", False):
                break
        delivered = False

        async def bounded_receive() -> Message:
            nonlocal delivered
            if delivered:
                return await receive()
            delivered = True
            return {"type": "http.request", "body": bytes(body), "more_body": False}

        await self.app(scope, bounded_receive, send)
