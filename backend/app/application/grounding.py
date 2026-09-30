import unicodedata
from dataclasses import replace

from app.domain.entities import GroundedAnswer, Source

NOT_FOUND = "No encuentro esa información en el documento cargado."
_TYPOGRAPHY = str.maketrans("“”„«»‘’‚–—", '"""""\'\'\'--')
# Models often add quotes, a final period or an ellipsis around exact excerpts.
_EDGES = " \"'.,;:!?¡¿"


def normalize(text: str) -> str:
    """Compare excerpts ignoring case, whitespace and typographic variants."""
    text = unicodedata.normalize("NFKC", text).translate(_TYPOGRAPHY)
    return " ".join(text.casefold().split())


def validate_answer(
    result: GroundedAnswer, context: list[Source]
) -> tuple[str, list[Source]]:
    if not result.supported or not result.answer.strip() or not result.citations:
        return NOT_FOUND, []
    by_index = {source.chunk: source for source in context}
    verified: list[Source] = []
    for citation in result.citations:
        source = by_index.get(citation.chunk)
        quote = normalize(citation.quote).strip(_EDGES)
        if not source or not quote or quote not in normalize(source.text):
            return NOT_FOUND, []
        if source.chunk not in {item.chunk for item in verified}:
            verified.append(replace(source, quote=citation.quote))
    return result.answer.strip(), verified
