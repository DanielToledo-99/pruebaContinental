class ApplicationError(Exception):
    code = "APPLICATION_ERROR"
    message = "No se pudo completar la operación."

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.message)


class SessionNotFound(ApplicationError):
    code = "SESSION_NOT_FOUND"
    message = "La sesión no existe."


class DocumentNotFound(ApplicationError):
    code = "DOCUMENT_NOT_FOUND"
    message = "El documento no existe en esta sesión."


class NoProcessedDocument(ApplicationError):
    code = "NO_PROCESSED_DOCUMENT"
    message = "Sube un documento a esta sesión antes de preguntar."


class DocumentNotProcessed(ApplicationError):
    code = "DOCUMENT_NOT_PROCESSED"
    message = "El documento todavía no está procesado."


class InvalidDocument(ApplicationError):
    code = "INVALID_DOCUMENT"
    message = "El documento está vacío, dañado o no contiene texto legible."


class UnsupportedDocumentType(ApplicationError):
    code = "UNSUPPORTED_DOCUMENT_TYPE"
    message = "Solo se admiten archivos PDF y TXT con tipo de contenido compatible."


class DocumentTooLarge(ApplicationError):
    code = "DOCUMENT_TOO_LARGE"
    message = "El documento supera los límites de tamaño o texto permitidos."


class EmptyQuestion(ApplicationError):
    code = "EMPTY_QUESTION"
    message = "Escribe una pregunta de entre 1 y 2000 caracteres."


class AIProviderError(ApplicationError):
    code = "AI_PROVIDER_ERROR"
    message = "El proveedor de IA no está disponible. Inténtalo nuevamente."


class EmbeddingConfigurationChanged(ApplicationError):
    code = "EMBEDDING_CONFIGURATION_CHANGED"
    message = "Cambió el modelo de embeddings. Vuelve a cargar el documento."
