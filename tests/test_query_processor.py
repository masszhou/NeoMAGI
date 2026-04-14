"""Tests for memory query processor (P2-M3c, Slice B).

Covers CJK segmentation, English lowercase, mixed language, empty input,
punctuation handling, and warmup_jieba idempotency.
"""

from __future__ import annotations

from src.memory.query_processor import normalize_query, segment_for_index, warmup_jieba


class TestNormalizeQuery:
    def test_empty_string(self) -> None:
        assert normalize_query("") == ""

    def test_whitespace_only(self) -> None:
        assert normalize_query("   ") == ""

    def test_english_lowercase(self) -> None:
        result = normalize_query("PostgreSQL Search")
        assert "postgresql" in result
        assert "search" in result

    def test_cjk_segmentation(self) -> None:
        result = normalize_query("记忆架构")
        # Jieba should segment into at least "记忆" and "架构"
        assert "记忆" in result
        assert "架构" in result

    def test_cjk_compound(self) -> None:
        result = normalize_query("数据库连接")
        assert "数据库" in result or "数据" in result
        assert "连接" in result

    def test_mixed_cjk_english(self) -> None:
        result = normalize_query("异步 HTTP 请求")
        assert "异步" in result or "异" in result
        assert "http" in result
        assert "请求" in result

    def test_punctuation_removed(self) -> None:
        result = normalize_query("hello, world! 你好？")
        assert "," not in result
        assert "!" not in result
        assert "？" not in result

    def test_preserves_content(self) -> None:
        result = normalize_query("tsvector search")
        assert "tsvector" in result
        assert "search" in result


class TestSegmentForIndex:
    def test_empty_string(self) -> None:
        assert segment_for_index("") == ""

    def test_whitespace_only(self) -> None:
        assert segment_for_index("   ") == ""

    def test_cjk_content(self) -> None:
        result = segment_for_index("NeoMAGI 的记忆架构基于 PostgreSQL")
        assert "记忆" in result
        assert "架构" in result
        assert "postgresql" in result

    def test_english_content(self) -> None:
        result = segment_for_index("Memory search uses tsvector")
        assert "memory" in result
        assert "search" in result
        assert "tsvector" in result

    def test_returns_lowercase(self) -> None:
        result = segment_for_index("PostgreSQL TSVECTOR")
        assert result == result.lower()


class TestWarmupJieba:
    def test_warmup_is_idempotent(self) -> None:
        # Should not raise on repeated calls
        warmup_jieba()
        warmup_jieba()

    def test_warmup_enables_segmentation(self) -> None:
        warmup_jieba()
        result = normalize_query("数据库连接")
        assert len(result) > 0
