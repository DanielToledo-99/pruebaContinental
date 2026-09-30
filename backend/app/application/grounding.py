import re
import unicodedata
from dataclasses import replace

from app.domain.entities import GroundedAnswer, Source

NOT_FOUND = "No encuentro esa información en el documento cargado."
_TYPOGRAPHY = str.maketrans("“”„«»‘’‚–—", '"""""\'\'\'--')
# Models often wrap exact excerpts in quotes or add a final period.
_EDGES = " \"'.,;:!?¡¿"
# After folding, "…" becomes "..."; models use it to elide part of a sentence.
_ELLIPSIS = re.compile(r"\.{3,}")
_GAP = " […] "


def _fold(text: str) -> tuple[str, list[int]]:
    """Fold case, width, typography and whitespace, keeping each char's position."""
    chars: list[str] = []
    positions: list[int] = []
    for index, char in enumerate(text):
        for folded in (
            unicodedata.normalize("NFKC", char).translate(_TYPOGRAPHY).casefold()
        ):
            if folded.isspace():
                if not chars or chars[-1] == " ":
                    continue
                folded = " "
            chars.append(folded)
            positions.append(index)
    if chars and chars[-1] == " ":
        chars.pop()
        positions.pop()
    return "".join(chars), positions


def locate_quote(quote: str, text: str) -> str | None:
    """Return the document's own wording for a model quote, or None if absent.

    Both strings must be NFC. Elided parts ("...") must appear in order.
    """
    folded, positions = _fold(text)
    pieces: list[str] = []
    cursor = 0
    for part in _ELLIPSIS.split(_fold(quote)[0]):
        part = part.strip(_EDGES)
        if not part:
            continue
        start = folded.find(part, cursor)
        if start < 0:
            return None
        cursor = start + len(part)
        end = positions[cursor - 1] + 1
        if end < len(text) and text[end] in ".!?":
            end += 1
        pieces.append(" ".join(text[positions[start] : end].split()))
    return _GAP.join(pieces) or None


def validate_answer(
    result: GroundedAnswer, context: list[Source]
) -> tuple[str, list[Source]]:
    answer = result.answer.strip()
    if (
        not result.supported
        or not answer
        or not result.citations
        or _fold(answer)[0] == _fold(NOT_FOUND)[0]
    ):
        return NOT_FOUND, []
    texts = {
        source.chunk: unicodedata.normalize("NFC", source.text) for source in context
    }
    quotes: dict[int, list[str]] = {}
    for citation in result.citations:
        text = texts.get(citation.chunk)
        excerpt = (
            locate_quote(unicodedata.normalize("NFC", citation.quote), text)
            if text is not None
            else None
        )
        if excerpt is None:
            return NOT_FOUND, []
        found = quotes.setdefault(citation.chunk, [])
        if excerpt not in found:
            found.append(excerpt)
    by_index = {source.chunk: source for source in context}
    # Every quote is kept, in citation order, with the document's exact wording.
    return answer, [
        replace(by_index[chunk], text=texts[chunk], quotes=items)
        for chunk, items in quotes.items()
    ]
