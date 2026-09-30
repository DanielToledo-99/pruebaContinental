from io import BytesIO

import pytest
from pypdf import PdfReader, PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from app.application.chunking import split_text
from app.domain.exceptions import (
    DocumentTooLarge,
    InvalidDocument,
    UnsupportedDocumentType,
)
from app.infrastructure.document_processing.parsers import FileDocumentProcessor


def make_pdf(text: str = "El proyecto reduce el consumo de agua.") -> bytes:
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {
            NameObject("/Font"): DictionaryObject({NameObject("/F1"): font}),
        }
    )
    stream = DecodedStreamObject()
    stream.set_data(f"BT /F1 12 Tf 50 700 Td ({text}) Tj ET".encode("ascii"))
    page[NameObject("/Contents")] = stream
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


@pytest.mark.parametrize(
    "name,mime,content,error",
    [
        ("bad.exe", "application/octet-stream", b"data", UnsupportedDocumentType),
        ("doc.pdf", "text/plain", b"%PDF-", UnsupportedDocumentType),
        ("doc.pdf", "application/pdf", b"fake", InvalidDocument),
        ("doc.txt", "text/plain", b"", InvalidDocument),
    ],
)
def test_validate_document(name, mime, content, error):
    with pytest.raises(error):
        FileDocumentProcessor().validate(name, mime, content)


def test_size_and_filename():
    processor = FileDocumentProcessor(max_bytes=4)
    assert processor.validate("../../my\\file.TXT", "text/plain", b"text") == "file.txt"
    with pytest.raises(DocumentTooLarge):
        processor.validate("a.txt", "text/plain", b"12345")


async def test_parse_pdf():
    result = await FileDocumentProcessor().extract("doc.pdf", make_pdf())
    assert "reduce el consumo" in result


def encrypt_pdf(content: bytes, user_password: str) -> bytes:
    writer = PdfWriter(clone_from=PdfReader(BytesIO(content)))
    writer.encrypt(
        user_password=user_password, owner_password="owner", algorithm="AES-128"
    )
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


async def test_pdf_with_only_owner_password_is_readable():
    processor = FileDocumentProcessor()
    result = await processor.extract("doc.pdf", encrypt_pdf(make_pdf(), ""))
    assert "reduce el consumo" in result
    with pytest.raises(InvalidDocument, match="contraseña"):
        await processor.extract("doc.pdf", encrypt_pdf(make_pdf(), "secreta"))


async def test_empty_pdf_and_binary_text():
    processor = FileDocumentProcessor()
    with pytest.raises(InvalidDocument):
        await processor.extract("doc.pdf", make_pdf(""))
    with pytest.raises(InvalidDocument):
        await processor.extract("doc.txt", b"abc\x00def")


async def test_extracted_text_limit():
    with pytest.raises(DocumentTooLarge):
        await FileDocumentProcessor(max_chars=5).extract("doc.pdf", make_pdf())


def test_chunks_preserve_text_and_have_overlap():
    text = "".join(str(i % 10) for i in range(2500))
    chunks = split_text(text, 800, 100)
    assert all(0 < len(chunk) <= 800 for chunk in chunks)
    assert chunks[0][-100:] == chunks[1][:100]
    reconstructed = chunks[0] + "".join(chunk[100:] for chunk in chunks[1:])
    assert reconstructed == text


@pytest.mark.parametrize("size,overlap", [(0, 0), (100, 100), (100, -1)])
def test_invalid_chunk_parameters(size, overlap):
    with pytest.raises(ValueError):
        split_text("text", size, overlap)
