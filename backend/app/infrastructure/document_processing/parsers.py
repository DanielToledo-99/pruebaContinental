import asyncio
import re
from io import BytesIO
from pathlib import PurePosixPath

from pypdf import PdfReader

from app.application.ports import DocumentParser
from app.domain.exceptions import (
    DocumentTooLarge,
    InvalidDocument,
    UnsupportedDocumentType,
)


class TextParser:
    def parse(self, content: bytes, max_chars: int) -> str:
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise InvalidDocument(
                "El archivo TXT debe usar codificación UTF-8."
            ) from exc
        if len(text) > max_chars:
            raise DocumentTooLarge()
        if any(ord(char) < 32 and char not in "\n\r\t\f" for char in text):
            raise InvalidDocument("El archivo TXT contiene datos binarios.")
        return text


class PDFParser:
    def __init__(self, max_pages: int = 200) -> None:
        self.max_pages = max_pages

    def parse(self, content: bytes, max_chars: int) -> str:
        try:
            reader = PdfReader(BytesIO(content))
            # Many PDFs only carry an owner password (print/copy restrictions)
            # and open without one; only a required user password is rejected.
            if reader.is_encrypted and not reader.decrypt(""):
                raise InvalidDocument("No se admiten PDF protegidos con contraseña.")
            if len(reader.pages) > self.max_pages:
                raise DocumentTooLarge()
            parts: list[str] = []
            length = 0
            for page in reader.pages:
                text = page.extract_text() or ""
                length += len(text) + 1
                if length > max_chars:
                    raise DocumentTooLarge()
                parts.append(text)
            return "\n".join(parts)
        except (InvalidDocument, DocumentTooLarge):
            raise
        except Exception as exc:
            raise InvalidDocument("No se pudo leer el PDF.") from exc


class FileDocumentProcessor:
    def __init__(
        self,
        max_bytes: int = 10 * 1024 * 1024,
        max_chars: int = 200_000,
        max_pages: int = 200,
    ) -> None:
        self.max_bytes = max_bytes
        self.max_chars = max_chars
        self.parsers: dict[str, DocumentParser] = {
            ".txt": TextParser(),
            ".pdf": PDFParser(max_pages),
        }

    def validate(self, filename: str, content_type: str, content: bytes) -> str:
        name = PurePosixPath(filename.replace("\\", "/")).name
        extension = PurePosixPath(name).suffix.lower()
        mime = content_type.split(";", 1)[0].lower().strip()
        expected = {".pdf": "application/pdf", ".txt": "text/plain"}
        if extension not in expected or mime not in {
            expected.get(extension),
            "application/octet-stream",
            "",
        }:
            raise UnsupportedDocumentType()
        if not content:
            raise InvalidDocument()
        if len(content) > self.max_bytes:
            raise DocumentTooLarge()
        if extension == ".pdf" and not content.startswith(b"%PDF-"):
            raise InvalidDocument("El contenido del archivo no corresponde a un PDF.")
        stem = re.sub(r"[^\w. -]", "_", PurePosixPath(name).stem).strip(" .")
        return (stem or "documento")[:170] + extension

    async def extract(self, filename: str, content: bytes) -> str:
        parser = self.parsers[PurePosixPath(filename).suffix.lower()]
        text = await asyncio.to_thread(parser.parse, content, self.max_chars)
        text = re.sub(r"\s+", " ", text.replace("\x00", " ")).strip()
        if not text:
            raise InvalidDocument(
                "No se encontró texto. Los PDF escaneados requieren OCR."
            )
        return text
