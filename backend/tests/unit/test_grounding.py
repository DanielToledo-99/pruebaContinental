import pytest

from app.application.grounding import NOT_FOUND, validate_answer
from app.domain.entities import Citation, GroundedAnswer, Source
from app.infrastructure.repositories.sqlalchemy_repository import to_source

DOCUMENT = (
    "Proyecto Agua Clara\n\n"
    "El objetivo principal del proyecto Agua Clara es reducir el consumo de agua\n"
    "en un 20% durante 2026 en las oficinas de Lima.\n\n"
    "La responsable del proyecto es Ana Torres.\n\n"
    "El presupuesto aprobado es de 15 000 soles."
)
CONTEXT = [Source(1, DOCUMENT, 0.8)]


def answer(*quotes: str, text: str = "Respuesta.") -> GroundedAnswer:
    return GroundedAnswer(text, [Citation(1, quote) for quote in quotes], True)


def test_every_quote_of_a_fragment_is_kept_in_order_without_duplicates():
    result, sources = validate_answer(
        answer(
            "La responsable del proyecto es Ana Torres.",
            "El presupuesto aprobado es de 15 000 soles.",
            "La responsable del proyecto es Ana Torres.",
        ),
        CONTEXT,
    )
    assert result == "Respuesta."
    assert [source.chunk for source in sources] == [1]
    assert sources[0].quotes == [
        "La responsable del proyecto es Ana Torres.",
        "El presupuesto aprobado es de 15 000 soles.",
    ]


def test_quotes_show_the_document_wording_across_line_breaks():
    _, sources = validate_answer(
        answer("«reducir el consumo de agua EN UN 20% durante 2026»"), CONTEXT
    )
    assert sources[0].quotes == ["reducir el consumo de agua en un 20% durante 2026"]


def test_elided_quotes_must_keep_their_order():
    _, sources = validate_answer(
        answer("El objetivo principal … en un 20% durante 2026"), CONTEXT
    )
    assert sources[0].quotes == ["El objetivo principal […] en un 20% durante 2026"]
    assert validate_answer(
        answer("en un 20% durante 2026 … El objetivo principal"), CONTEXT
    ) == (NOT_FOUND, [])


@pytest.mark.parametrize(
    "result",
    [
        answer("La responsable del proyecto es Ana Torres.", "Cuesta 20 000 soles."),
        GroundedAnswer("Respuesta.", [Citation(2, "Ana Torres")], True),
        GroundedAnswer("Respuesta.", [Citation(1, "Ana Torres")], False),
        answer("Ana Torres", text=NOT_FOUND),
        answer("..."),
    ],
)
def test_unsupported_answers_become_not_found(result):
    assert validate_answer(result, CONTEXT) == (NOT_FOUND, [])


def test_legacy_single_quote_sources_are_read():
    stored = {"chunk": 1, "text": "Texto", "score": 0.9, "quote": "Texto"}
    assert to_source(stored).quotes == ["Texto"]
    assert to_source(stored | {"quote": ""}).quotes == []
    assert to_source(stored | {"quotes": ["A", "B"]}).quotes == ["A", "B"]
