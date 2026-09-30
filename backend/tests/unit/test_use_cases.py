import asyncio
from dataclasses import replace
from uuid import uuid4

import pytest

from app.application.grounding import NOT_FOUND
from app.domain.entities import Citation, GroundedAnswer
from app.domain.exceptions import (
    AIProviderError,
    DocumentNotFound,
    DocumentNotProcessed,
    EmbeddingConfigurationChanged,
    EmptyQuestion,
    InvalidDocument,
    NoProcessedDocument,
    SessionNotFound,
)


async def test_ask_question_success(loaded):
    services, db, llm, session, document = loaded
    result = await services.ask.execute(
        session.id, document.id, "  ¿Cuál es el objetivo?  "
    )
    assert "20%" in result.answer
    assert result.sources[0].chunk == 1
    assert llm.calls[0][0] == "¿Cuál es el objetivo?"
    assert len(llm.calls[0][1]) == 1
    assert [m.role for m in db.messages] == ["user", "assistant"]
    assert db.messages[1].sources == result.sources


async def test_question_without_document_uses_latest_processed(loaded):
    services, db, _, session, _ = loaded
    latest = await services.upload.execute(
        session.id, "otro.txt", "text/plain", b"El presupuesto es de 15 000 soles."
    )
    result = await services.ask.execute(session.id, None, "¿Presupuesto?")
    assert result.document_id == latest.id
    assert db.messages[0].document_id == latest.id


async def test_question_without_processed_document(setup_services):
    services, _, _ = setup_services
    session = await services.create_session.execute()
    with pytest.raises(NoProcessedDocument):
        await services.ask.execute(session.id, None, "Pregunta")


async def test_question_not_found_in_document(loaded):
    services, _, llm, session, document = loaded
    llm.result = GroundedAnswer(NOT_FOUND, [], False)
    result = await services.ask.execute(
        session.id, document.id, "¿Quién ganó el mundial?"
    )
    assert result.answer == NOT_FOUND
    assert result.sources == []


async def test_no_relevant_chunks_does_not_call_llm(loaded):
    services, db, llm, session, document = loaded
    db.relevant = False
    result = await services.ask.execute(session.id, document.id, "Pregunta ajena")
    assert result.answer == NOT_FOUND
    assert not llm.calls
    assert len(db.messages) == 2


@pytest.mark.parametrize(
    "citation", [Citation(999, "20%"), Citation(1, "dato inventado")]
)
async def test_fabricated_citations_are_rejected(loaded, citation):
    services, _, llm, session, document = loaded
    llm.result = GroundedAnswer("Una afirmación sin respaldo.", [citation], True)
    result = await services.ask.execute(session.id, document.id, "Pregunta")
    assert result.answer == NOT_FOUND


async def test_citation_matching_tolerates_case_and_typography(loaded):
    services, _, llm, session, document = loaded
    quote = "«Reducir el consumo de agua en un 20%.»"
    llm.result = GroundedAnswer(
        "Reducir el consumo de agua.", [Citation(1, quote)], True
    )
    result = await services.ask.execute(session.id, document.id, "Pregunta")
    assert result.answer == "Reducir el consumo de agua."
    assert result.sources[0].quote == quote


async def test_document_not_found(loaded):
    services, _, _, session, _ = loaded
    with pytest.raises(DocumentNotFound):
        await services.ask.execute(session.id, uuid4(), "Pregunta")


async def test_document_from_other_session_is_not_accessible(loaded):
    services, _, llm, _, document = loaded
    other = await services.create_session.execute()
    with pytest.raises(DocumentNotFound):
        await services.ask.execute(other.id, document.id, "Pregunta")
    assert not llm.calls


async def test_document_not_processed(loaded):
    services, db, _, session, document = loaded
    db.documents[document.id] = replace(document, status="failed")
    with pytest.raises(DocumentNotProcessed):
        await services.ask.execute(session.id, document.id, "Pregunta")


async def test_changed_embedding_space_requires_reupload(loaded):
    services, db, _, session, document = loaded
    db.documents[document.id] = replace(document, embedding_space="another-model")
    with pytest.raises(EmbeddingConfigurationChanged):
        await services.ask.execute(session.id, document.id, "Pregunta")


@pytest.mark.parametrize("question", ["", " \n ", "a" * 2001])
async def test_invalid_question(loaded, question):
    services, _, _, session, document = loaded
    with pytest.raises(EmptyQuestion):
        await services.ask.execute(session.id, document.id, question)


async def test_provider_failure_does_not_save_partial_turn(loaded):
    services, db, llm, session, document = loaded
    llm.error = AIProviderError()
    with pytest.raises(AIProviderError):
        await services.ask.execute(session.id, document.id, "Pregunta")
    assert db.messages == []


async def test_get_history(loaded):
    services, db, _, session, document = loaded
    await services.ask.execute(session.id, document.id, "Pregunta 1")
    await services.ask.execute(session.id, document.id, "Pregunta 2")
    db.messages.reverse()
    history = await services.history.execute(session.id)
    assert [m.sequence for m in history.messages] == [0, 1, 2, 3]
    assert history.documents == [document]
    other = await services.create_session.execute()
    assert (await services.history.execute(other.id)).messages == []


async def test_missing_session(setup_services):
    services, _, _ = setup_services
    with pytest.raises(SessionNotFound):
        await services.history.execute(uuid4())


async def test_invalid_text_marks_metadata_failed(setup_services):
    services, db, _ = setup_services
    session = await services.create_session.execute()
    with pytest.raises(InvalidDocument):
        await services.upload.execute(session.id, "bad.txt", "text/plain", b"\xff")
    assert [doc.status for doc in db.documents.values()] == ["failed"]
    assert not db.chunks


async def test_embedding_failure_does_not_leave_partial_index(setup_services):
    services, db, _ = setup_services
    session = await services.create_session.execute()

    async def broken_embed(texts):
        raise AIProviderError()

    services.upload.embeddings.embed = broken_embed
    with pytest.raises(AIProviderError):
        await services.upload.execute(
            session.id, "doc.txt", "text/plain", b"valid text"
        )
    assert not db.chunks
    assert [doc.status for doc in db.documents.values()] == ["failed"]


async def test_cancelled_upload_marks_metadata_failed(setup_services):
    services, db, _ = setup_services
    session = await services.create_session.execute()

    async def cancelled_extract(filename, content):
        raise asyncio.CancelledError()

    services.upload.processor.extract = cancelled_extract
    with pytest.raises(asyncio.CancelledError):
        await services.upload.execute(
            session.id, "doc.txt", "text/plain", b"valid text"
        )
    assert [doc.status for doc in db.documents.values()] == ["failed"]
