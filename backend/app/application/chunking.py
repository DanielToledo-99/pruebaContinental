# Preferred cut points, best first; the offset keeps a sentence's period.
_BOUNDARIES = (("\n\n", 0), ("\n", 0), (". ", 1), (" ", 0))


def split_text(text: str, size: int = 800, overlap: int = 100) -> list[str]:
    if size <= 0 or not 0 <= overlap < size:
        raise ValueError("Chunk size must be positive and overlap smaller than size")
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            for separator, keep in _BOUNDARIES:
                boundary = text.rfind(separator, start + size // 2, end)
                if boundary > start + overlap:
                    end = boundary + keep
                    break
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end == len(text):
            break
        start = end - overlap
    return chunks
