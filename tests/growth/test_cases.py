"""Tests for growth case catalog (P2-M1c em2.4.3)."""

from __future__ import annotations

from src.growth.cases import GROWTH_CASE_CATALOG, get_case_spec, list_case_specs


class TestCatalog:
    """GROWTH_CASE_CATALOG should contain the expected entries."""

    def test_gc1_exists(self) -> None:
        assert "gc-1" in GROWTH_CASE_CATALOG

    def test_gc2_exists(self) -> None:
        assert "gc-2" in GROWTH_CASE_CATALOG

    def test_gc1_fields(self) -> None:
        spec = GROWTH_CASE_CATALOG["gc-1"]
        assert spec.case_id == "gc-1"
        assert spec.title == "Human-Taught Skill Reuse"
        assert spec.source_kind == "skill_spec"
        assert spec.target_kind is None
        assert spec.contract_id == "skill_spec_eval_v1"
        assert spec.contract_version == 1
        assert len(spec.entry_conditions) == 2
        assert len(spec.required_artifacts) == 3

    def test_gc2_fields(self) -> None:
        spec = GROWTH_CASE_CATALOG["gc-2"]
        assert spec.case_id == "gc-2"
        assert spec.title == "Skill-to-Wrapper-Tool Promotion"
        assert spec.source_kind == "skill_spec"
        assert spec.target_kind == "wrapper_tool"
        assert spec.contract_id == "wrapper_tool_eval_v1"
        assert spec.contract_version == 1
        assert len(spec.entry_conditions) == 4
        assert len(spec.required_artifacts) == 4

    def test_gc2_promote_conditions(self) -> None:
        spec = GROWTH_CASE_CATALOG["gc-2"]
        assert "usage_count_gte_3" in spec.entry_conditions
        assert "success_rate_gte_0.8" in spec.entry_conditions

    def test_all_specs_have_success_rule(self) -> None:
        for spec in GROWTH_CASE_CATALOG.values():
            assert spec.success_rule, f"{spec.case_id} missing success_rule"

    def test_all_specs_have_rollback_rule(self) -> None:
        for spec in GROWTH_CASE_CATALOG.values():
            assert spec.rollback_rule, f"{spec.case_id} missing rollback_rule"


class TestGetCaseSpec:
    """get_case_spec should return specs or None."""

    def test_existing(self) -> None:
        spec = get_case_spec("gc-1")
        assert spec is not None
        assert spec.case_id == "gc-1"

    def test_nonexistent(self) -> None:
        assert get_case_spec("gc-999") is None


class TestListCaseSpecs:
    """list_case_specs should return all specs."""

    def test_returns_all(self) -> None:
        specs = list_case_specs()
        assert len(specs) == len(GROWTH_CASE_CATALOG)
        ids = {s.case_id for s in specs}
        assert ids == set(GROWTH_CASE_CATALOG.keys())
