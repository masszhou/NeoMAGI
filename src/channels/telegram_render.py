"""Telegram response rendering: message splitting, formatting, error mapping."""

from __future__ import annotations

import re

# ── Error code → user-friendly message ──────────────────────────────────────

_ERROR_MESSAGES: dict[str, str] = {
    "SESSION_BUSY": "当前正在处理中，请稍后重试",
    "BUDGET_EXCEEDED": "预算额度已用完",
    "PROVIDER_NOT_AVAILABLE": "模型服务暂不可用",
}

_DEFAULT_ERROR = "处理消息时遇到了问题，请稍后重试"


def friendly_error_message(code: str | None) -> str:
    """Map GatewayError code to user-friendly Chinese message."""
    if code and code in _ERROR_MESSAGES:
        return _ERROR_MESSAGES[code]
    return _DEFAULT_ERROR


# ── Message splitting ────────────────────────────────────────────────────────

_CODE_BLOCK_RE = re.compile(r"```[^\n]*\n[\s\S]*?```")
_SENTENCE_BOUNDARY_RE = re.compile(r"(?<=[.!?。！？])\s+")


def split_message(text: str, max_length: int = 4096) -> list[str]:
    """Split text into chunks within Telegram's message length limit.

    Split priority: code-block boundaries → paragraphs → sentences → hard cut.
    Code blocks (```) are kept intact when possible.
    """
    if not text:
        return []
    if len(text) <= max_length:
        return [text]

    result: list[str] = []
    buf = ""
    for seg in _split_preserving_code_blocks(text):
        buf = _consume_segment(seg, buf, result, max_length)

    if buf:
        result.append(buf)

    return [c for c in result if c.strip()]


def _split_preserving_code_blocks(text: str) -> list[str]:
    """Split text into alternating regular-text / code-block segments."""
    parts: list[str] = []
    last = 0
    for m in _CODE_BLOCK_RE.finditer(text):
        if m.start() > last:
            parts.append(text[last : m.start()])
        parts.append(m.group())
        last = m.end()
    if last < len(text):
        parts.append(text[last:])
    return parts


def _consume_segment(seg: str, buf: str, result: list[str], max_length: int) -> str:
    if _can_append_segment(buf, seg, max_length):
        return buf + seg
    if buf:
        result.append(buf)
    if len(seg) <= max_length:
        return seg
    return _consume_oversized_segment(seg, result, max_length)


def _can_append_segment(buf: str, seg: str, max_length: int) -> bool:
    return bool(buf) and len(buf) + len(seg) <= max_length


def _consume_oversized_segment(seg: str, result: list[str], max_length: int) -> str:
    sub = _split_oversized_segment(seg, max_length)
    if not sub:
        return ""
    result.extend(sub[:-1])
    return sub[-1]


def _split_oversized_segment(seg: str, max_length: int) -> list[str]:
    if seg.startswith("```"):
        return _split_code_block(seg, max_length)
    return _split_paragraphs(seg, max_length)


def _hard_cut_chunks(text: str, max_length: int) -> list[str]:
    return [text[i : i + max_length] for i in range(0, len(text), max_length)]


def _parse_code_block(block: str) -> tuple[str, str, str] | None:
    try:
        first_nl = block.index("\n")
    except ValueError:
        return None

    header = block[:first_nl]
    body = block[first_nl + 1 :]
    if body.endswith("```"):
        body = body[:-3]
    body = body.rstrip("\n")
    if not body:
        return None
    return header, body, "```"


def _effective_code_length(header: str, footer: str, max_length: int) -> int:
    return max_length - len(header) - len(footer) - 2


def _wrap_code_lines(header: str, lines: list[str], footer: str) -> str:
    return header + "\n" + "\n".join(lines) + "\n" + footer


def _split_long_code_line(line: str, effective: int, header: str, footer: str) -> list[str]:
    return [
        _wrap_code_lines(header, [line[i : i + effective]], footer)
        for i in range(0, len(line), effective)
    ]


def _flush_code_lines(chunks: list[str], header: str, current: list[str], footer: str) -> None:
    if current:
        chunks.append(_wrap_code_lines(header, current, footer))


def _append_code_line(
    line: str,
    current: list[str],
    current_len: int,
    chunks: list[str],
    *,
    effective: int,
    header: str,
    footer: str,
) -> tuple[list[str], int]:
    line_len = len(line) + 1
    if line_len > effective:
        _flush_code_lines(chunks, header, current, footer)
        chunks.extend(_split_long_code_line(line, effective, header, footer))
        return [], 0
    if current and current_len + line_len > effective:
        _flush_code_lines(chunks, header, current, footer)
        current = []
        current_len = 0
    current.append(line)
    return current, current_len + line_len


def _split_wrapped_code_lines(
    body_lines: list[str],
    *,
    effective: int,
    header: str,
    footer: str,
) -> list[str]:
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0
    for line in body_lines:
        current, current_len = _append_code_line(
            line,
            current,
            current_len,
            chunks,
            effective=effective,
            header=header,
            footer=footer,
        )
    _flush_code_lines(chunks, header, current, footer)
    return chunks


def _split_code_block(block: str, max_length: int) -> list[str]:
    """Split an oversized code block by lines, re-wrapping with ``` fences."""
    parsed = _parse_code_block(block)
    if parsed is None:
        return _hard_cut_chunks(block, max_length)

    header, body, footer = parsed
    effective = _effective_code_length(header, footer, max_length)
    if effective <= 0:
        return _hard_cut_chunks(block, max_length)

    chunks = _split_wrapped_code_lines(
        body.split("\n"),
        effective=effective,
        header=header,
        footer=footer,
    )
    return chunks or _hard_cut_chunks(block, max_length)


def _split_paragraphs(text: str, max_length: int) -> list[str]:
    """Split on paragraph boundaries (\\n\\n), falling back to sentences."""
    paragraphs = text.split("\n\n")
    chunks: list[str] = []
    current = ""

    for para in paragraphs:
        candidate = current + "\n\n" + para if current else para
        if len(candidate) <= max_length:
            current = candidate
            continue
        if current:
            chunks.append(current)
            current = ""
        if len(para) <= max_length:
            current = para
        else:
            sub = _split_sentences(para, max_length)
            for s in sub[:-1]:
                chunks.append(s)
            current = sub[-1] if sub else ""

    if current:
        chunks.append(current)
    return chunks


def _split_sentences(text: str, max_length: int) -> list[str]:
    """Split on sentence boundaries, falling back to hard cut."""
    parts = _SENTENCE_BOUNDARY_RE.split(text)
    chunks: list[str] = []
    current = ""

    for part in parts:
        candidate = current + " " + part if current else part
        if len(candidate) <= max_length:
            current = candidate
            continue
        if current:
            chunks.append(current)
            current = ""
        if len(part) <= max_length:
            current = part
        else:
            for i in range(0, len(part), max_length):
                chunks.append(part[i : i + max_length])
            current = ""

    if current:
        chunks.append(current)
    return chunks


# ── MarkdownV2 formatting ───────────────────────────────────────────────────

_HAS_MARKDOWN_RE = re.compile(r"```|`[^`]+`|\*\*")
_MD2_ESCAPE_RE = re.compile(r"([_*\[\]()~`>#+\-=|{}.!\\])")
_CODE_OR_INLINE_RE = re.compile(r"```[^\n]*\n[\s\S]*?```|`[^`\n]+`")


def format_for_telegram(text: str) -> tuple[str, str | None]:
    """Format LLM response for Telegram. Returns (text, parse_mode).

    Attempts MarkdownV2 when markdown patterns are detected.
    Falls back to plain text (parse_mode=None) on failure or absence of markdown.
    """
    if not text:
        return ("", None)

    if not _HAS_MARKDOWN_RE.search(text):
        return (text, None)

    try:
        formatted = _to_markdownv2(text)
        return (formatted, "MarkdownV2")
    except Exception:
        return (text, None)


def _to_markdownv2(text: str) -> str:
    """Convert standard Markdown to Telegram MarkdownV2.

    Preserves code blocks and inline code. Converts **bold** → *bold*.
    Escapes all other MarkdownV2 special characters.
    """
    tokens: list[str] = []
    last = 0

    for m in _CODE_OR_INLINE_RE.finditer(text):
        before = text[last : m.start()]
        tokens.append(_format_plain(before))

        code = m.group()
        if code.startswith("```"):
            tokens.append(_escape_code_block_content(code))
        else:
            inner = code[1:-1].replace("\\", "\\\\").replace("`", "\\`")
            tokens.append(f"`{inner}`")

        last = m.end()

    tokens.append(_format_plain(text[last:]))
    return "".join(tokens)


def _format_plain(text: str) -> str:
    """Format a non-code text segment for MarkdownV2.

    Converts **bold** → *bold* and escapes remaining special characters.
    """
    if not text:
        return ""

    protected: dict[str, str] = {}
    counter = [0]

    def _protect(val: str) -> str:
        key = f"\x00P{counter[0]}\x00"
        protected[key] = val
        counter[0] += 1
        return key

    def _bold(m: re.Match[str]) -> str:
        inner = _MD2_ESCAPE_RE.sub(r"\\\1", m.group(1))
        return _protect(f"*{inner}*")

    result = re.sub(r"\*\*(.+?)\*\*", _bold, text)
    result = _MD2_ESCAPE_RE.sub(r"\\\1", result)

    for key, val in protected.items():
        result = result.replace(key, val)

    return result


def _escape_code_block_content(block: str) -> str:
    """Escape fenced code block content for MarkdownV2 (only \\\\ and `)."""
    try:
        nl = block.index("\n")
    except ValueError:
        return block

    header = block[:nl]
    content = block[nl + 1 : -3]  # between first \\n and closing ```
    content = content.replace("\\", "\\\\").replace("`", "\\`")
    return f"{header}\n{content}```"
