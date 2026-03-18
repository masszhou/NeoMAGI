"""Tests for WrapperToolSpec domain type (P2-M1c).

Covers: construction, frozen immutability, field defaults, validation.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.wrappers.types import WrapperToolSpec


def _make_spec(**overrides: object) -> WrapperToolSpec:
    defaults = {
        "id": "wt-001",
        "capability": "file_summarizer",
        "version": 1,
        "summary": "Summarizes a file",
        "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}},
        "output_schema": {"type": "object", "properties": {"summary": {"type": "string"}}},
        "implementation_ref": "src.wrappers.builtins:file_summarizer_factory",
        "deny_semantics": ("no_write", "no_delete"),
    }
    defaults.update(overrides)
    return WrapperToolSpec(**defaults)  # type: ignore[arg-type]


class TestConstruction:
    def test_basic_construction(self) -> None:
        spec = _make_spec()
        assert spec.id == "wt-001"
        assert spec.capability == "file_summarizer"
        assert spec.version == 1
        assert spec.summary == "Summarizes a file"
        assert isinstance(spec.input_schema, dict)
        assert isinstance(spec.output_schema, dict)

    def test_defaults(self) -> None:
        spec = _make_spec()
        assert spec.bound_atomic_tools == ()
        assert spec.scope_claim == "local"
        assert spec.disabled is False

    def test_deny_semantics(self) -> None:
        spec = _make_spec(deny_semantics=("no_write", "no_execute"))
        assert spec.deny_semantics == ("no_write", "no_execute")

    def test_bound_atomic_tools_tuple(self) -> None:
        spec = _make_spec(bound_atomic_tools=("read_file", "memory_search"))
        assert spec.bound_atomic_tools == ("read_file", "memory_search")

    def test_scope_claim_values(self) -> None:
        for claim in ("local", "reusable", "promotable"):
            spec = _make_spec(scope_claim=claim)
            assert spec.scope_claim == claim


class TestFrozen:
    def test_frozen_prevents_mutation(self) -> None:
        spec = _make_spec()
        with pytest.raises(ValidationError):
            spec.id = "wt-changed"  # type: ignore[misc]

    def test_frozen_prevents_field_assignment(self) -> None:
        spec = _make_spec()
        with pytest.raises(ValidationError):
            spec.disabled = True  # type: ignore[misc]


class TestFieldValidation:
    def test_missing_required_field_raises(self) -> None:
        with pytest.raises(ValidationError):
            WrapperToolSpec(
                id="wt-001",
                capability="test",
                version=1,
                summary="test",
                input_schema={},
                output_schema={},
                # missing implementation_ref
            )  # type: ignore[call-arg]

    def test_implementation_ref_stored_as_string(self) -> None:
        spec = _make_spec(implementation_ref="my.module:my_factory")
        assert spec.implementation_ref == "my.module:my_factory"

    def test_input_schema_accepts_any_dict(self) -> None:
        spec = _make_spec(input_schema={"type": "string"})
        assert spec.input_schema == {"type": "string"}

    def test_output_schema_accepts_any_dict(self) -> None:
        spec = _make_spec(output_schema={"type": "array", "items": {"type": "number"}})
        assert spec.output_schema["type"] == "array"


class TestModelDump:
    def test_model_dump_roundtrip(self) -> None:
        spec = _make_spec()
        dumped = spec.model_dump()
        restored = WrapperToolSpec(**dumped)
        assert restored == spec

    def test_model_dump_includes_all_fields(self) -> None:
        spec = _make_spec()
        dumped = spec.model_dump()
        expected_keys = {
            "id",
            "capability",
            "version",
            "summary",
            "input_schema",
            "output_schema",
            "bound_atomic_tools",
            "implementation_ref",
            "deny_semantics",
            "scope_claim",
            "disabled",
        }
        assert set(dumped.keys()) == expected_keys
