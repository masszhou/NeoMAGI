"""Domain types for the wrapper tool runtime layer (P2-M1c).

Defines: WrapperToolSpec — the current-state store record for a
governed single-turn capability unit (ADR 0056).

Design notes:
- WrapperToolSpec is the current-state store record; it has NO ``status``
  field.  Lifecycle status lives exclusively in the governance ledger
  (``wrapper_tool_versions``), preserving the current-state / ledger split.
- Frozen Pydantic model for immutability.
- ``implementation_ref`` uses ``<module>:<factory>`` V1 syntax.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class WrapperToolSpec(BaseModel):
    """Immutable wrapper tool specification record.

    Maps 1:1 with the ``wrapper_tools`` DB table.
    No ``status`` field — lifecycle governance is in ``wrapper_tool_versions``.
    """

    model_config = ConfigDict(frozen=True)

    id: str
    capability: str
    version: int
    summary: str
    input_schema: dict
    output_schema: dict
    bound_atomic_tools: tuple[str, ...] = ()
    implementation_ref: str  # "<module>:<factory>" Python entrypoint
    deny_semantics: tuple[str, ...] = ()
    scope_claim: str = "local"  # local / reusable / promotable
    disabled: bool = False
