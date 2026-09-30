from dataclasses import replace

from app.domain.entities import GroundedAnswer, Source

NOT_FOUND = "No encuentro esa información en el documento cargado."


def validate_answer(
    result: GroundedAnswer, context: list[Source]
) -> tuple[str, list[Source]]:
    if not result.supported or not result.answer.strip() or not result.citations:
        return NOT_FOUND, []
    by_index = {source.chunk: source for source in context}
    verified: list[Source] = []
    for citation in result.citations:
        source = by_index.get(citation.chunk)
        quote = " ".join(citation.quote.split())
        if not source or not quote or quote not in " ".join(source.text.split()):
            return NOT_FOUND, []
        if source.chunk not in {item.chunk for item in verified}:
            verified.append(replace(source, quote=citation.quote))
    return result.answer.strip(), verified
