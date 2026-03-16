"""Tests for src/infra/init_workspace.py."""

from __future__ import annotations

from pathlib import Path

from src.infra import init_workspace as module


def test_init_workspace_skips_soul_and_prints_guidance(
    tmp_path: Path, capsys, monkeypatch
) -> None:
    """Workspace init should not create SOUL.md implicitly."""
    workspace_dir = tmp_path / "workspace"
    monkeypatch.setattr(module, "WORKSPACE_DIR", workspace_dir)
    monkeypatch.setattr(module, "MEMORY_DIR", workspace_dir / "memory")

    module.init_workspace()

    assert (workspace_dir / "AGENTS.md").is_file()
    assert (workspace_dir / "USER.md").is_file()
    assert not (workspace_dir / "SOUL.md").exists()
    out = capsys.readouterr().out
    assert "just init-soul" in out
