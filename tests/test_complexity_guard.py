from __future__ import annotations

import json
from pathlib import Path

from src.infra.complexity_guard import (
    Finding,
    analyze_paths,
    build_baseline_payload,
    classify_path,
    detect_regressions,
)


def test_classify_path_applies_project_groups() -> None:
    assert classify_path(Path("src/agent/agent.py")) == "prod"
    assert classify_path(Path("scripts/devcoord/service.py")) == "scripts"
    assert classify_path(Path("tests/test_devcoord.py")) == "tests"
    assert classify_path(Path("src/frontend/src/stores/__tests__/chat.test.ts")) == "tests"
    assert classify_path(Path("alembic/versions/abc.py")) is None


def test_analyze_paths_reports_file_and_function_findings(tmp_path: Path) -> None:
    source_path = tmp_path / "src" / "sample.py"
    source_path.parent.mkdir(parents=True)
    source_path.write_text(_python_source(520), encoding="utf-8")

    report = analyze_paths([Path("src/sample.py")], tmp_path)

    block_metrics = {(item["metric"], item.get("symbol")) for item in report["block_findings"]}
    target_metrics = {(item["metric"], item.get("symbol")) for item in report["target_findings"]}

    assert ("function_lines", "too_long") in block_metrics
    assert ("function_branches", "branchy") in block_metrics
    assert ("function_nesting", "deep") in block_metrics
    assert ("file_lines", None) in target_metrics


def test_detect_regressions_flags_new_and_worsened_findings() -> None:
    baseline = [
        Finding(
            severity="block",
            group="prod",
            metric="file_lines",
            path="src/example.py",
            actual=810,
            limit=800,
        ).to_dict(),
        Finding(
            severity="block",
            group="prod",
            metric="function_lines",
            path="src/example.py",
            symbol="run",
            line=10,
            actual=55,
            limit=50,
        ).to_dict(),
    ]
    current = [
        Finding(
            severity="block",
            group="prod",
            metric="file_lines",
            path="src/example.py",
            actual=820,
            limit=800,
        ).to_dict(),
        Finding(
            severity="block",
            group="prod",
            metric="function_lines",
            path="src/example.py",
            symbol="run",
            line=10,
            actual=52,
            limit=50,
        ).to_dict(),
        Finding(
            severity="block",
            group="scripts",
            metric="file_lines",
            path="scripts/tool.py",
            actual=900,
            limit=800,
        ).to_dict(),
    ]

    regressions = detect_regressions(current, baseline)

    assert [item["fingerprint"] for item in regressions] == [
        "file_lines::scripts/tool.py",
        "file_lines::src/example.py",
    ]


def test_build_baseline_payload_keeps_block_findings_only() -> None:
    report = {
        "generated_at": "2026-03-08T00:00:00+00:00",
        "policy_version": 1,
        "thresholds": {"prod": {"file_block": 800}},
        "target_findings": [{"metric": "file_lines"}],
        "block_findings": [{"metric": "function_lines"}],
    }

    payload = build_baseline_payload(report)

    assert payload == {
        "generated_at": "2026-03-08T00:00:00+00:00",
        "policy_version": 1,
        "thresholds": {"prod": {"file_block": 800}},
        "block_findings": [{"metric": "function_lines"}],
    }
    assert json.loads(json.dumps(payload)) == payload


def _python_source(padding_lines: int) -> str:
    chunks = [
        "def short() -> int:\n    return 1\n",
        _too_long_function(),
        _branchy_function(),
        _deep_function(),
    ]
    chunks.extend("" for _ in range(padding_lines))
    return "\n".join(chunks)


def _too_long_function() -> str:
    lines = ["def too_long() -> int:"]
    for idx in range(55):
        lines.append(f"    value_{idx} = {idx}")
    lines.append("    return value_54")
    return "\n".join(lines)


def _branchy_function() -> str:
    return "\n".join(
        [
            "def branchy(value: int) -> int:",
            "    if value == 0:",
            "        return 0",
            "    if value == 1:",
            "        return 1",
            "    if value == 2:",
            "        return 2",
            "    if value == 3:",
            "        return 3",
            "    if value == 4:",
            "        return 4",
            "    if value == 5:",
            "        return 5",
            "    if value == 6:",
            "        return 6",
            "    return value",
        ]
    )


def _deep_function() -> str:
    return "\n".join(
        [
            "def deep(value: int) -> int:",
            "    if value > 0:",
            "        if value > 1:",
            "            if value > 2:",
            "                if value > 3:",
            "                    return value",
            "    return 0",
        ]
    )
