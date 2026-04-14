"""Query preprocessing for memory search (P2-M3c, D2a/D2b).

Pure functions — CJK segmentation via Jieba, noise removal, index-time tokenization.
No I/O side effects. Gateway lifespan and CLI should call warmup_jieba() at startup.
"""

from __future__ import annotations

import re
import unicodedata

# CJK Unicode ranges (CJK Unified Ideographs + common extensions)
_CJK_RE = re.compile(
    r"[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff"
    r"\U00020000-\U0002a6df\U0002a700-\U0002b73f"
    r"\U0002b740-\U0002b81f\U0002b820-\U0002ceaf]"
)

# Punctuation / noise to strip (keep alphanumeric, CJK, whitespace)
_NOISE_RE = re.compile(
    r"[^\w\s\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]",
    re.UNICODE,
)


def _has_cjk(text: str) -> bool:
    """Return True if text contains any CJK character."""
    return bool(_CJK_RE.search(text))


def _segment_cjk(text: str) -> str:
    """Segment CJK text using Jieba cut_for_search, preserving non-CJK parts."""
    import jieba

    tokens: list[str] = []
    for token in jieba.cut_for_search(text):
        stripped = token.strip()
        if stripped:
            tokens.append(stripped)
    return " ".join(tokens)


def normalize_query(query: str) -> str:
    """Normalize a search query for plainto_tsquery.

    1. Strip excess whitespace and punctuation noise
    2. Detect CJK characters → Jieba cut_for_search → join with space
    3. Non-CJK parts: lowercase, preserve as-is
    4. Return normalized query string
    """
    if not query or not query.strip():
        return ""

    # Normalize unicode (NFC for consistent CJK handling)
    text = unicodedata.normalize("NFC", query.strip())

    # Remove noise punctuation
    text = _NOISE_RE.sub(" ", text)

    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()

    if not text:
        return ""

    if _has_cjk(text):
        text = _segment_cjk(text)

    # Lowercase for consistency (Jieba preserves case; tsquery 'simple' is case-sensitive)
    return text.lower()


def segment_for_index(text: str) -> str:
    """Produce space-separated tokens for index-time tsvector.

    Used to populate memory_entries.search_text column.
    Always applies Jieba segmentation (CJK) + lowercase.
    """
    if not text or not text.strip():
        return ""

    normalized = unicodedata.normalize("NFC", text.strip())
    normalized = _NOISE_RE.sub(" ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()

    if not normalized:
        return ""

    # Always segment — even pure English text benefits from consistent tokenization
    segmented = _segment_cjk(normalized)
    return segmented.lower()


def warmup_jieba() -> None:
    """Preload Jieba dictionary to avoid first-search latency (~1-2s).

    Safe to call multiple times (no-op after first load).
    """
    import jieba

    jieba.initialize()
