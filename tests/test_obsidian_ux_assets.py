from __future__ import annotations

import json
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parent.parent

TEMPLATES = [
    "templates/concept-global.md",
    "templates/concept-project.md",
    "templates/decision.md",
    "templates/pitfall.md",
    "templates/usage-manual.md",
]

DASHBOARDS = [
    "dashboards/记忆治理总览.md",
    "dashboards/低权重待处理.md",
    "dashboards/最近激活.md",
    "dashboards/缺少 aliases.md",
    "dashboards/项目 member 记忆.md",
    "dashboards/归档候选.md",
    "dashboards/链接治理.md",
]

BASES = [
    "bases/active-memory.base",
    "bases/project-memory.base",
    "bases/archive-candidates.base",
    "bases/recent-activations.base",
    "bases/alias-needed.base",
]

REQUIRED_FRONTMATTER_FIELDS = [
    "type:",
    "created_at:",
    "last_modified:",
    "project:",
    "aliases:",
    "code_symbols:",
    "initial_weight:",
    "current_weight:",
    "last_activated:",
    "access_count:",
    "status:",
    "superseded_by:",
    "weight_schema_version:",
    "category:",
    "importance:",
    "ewma_access:",
    "last_boost:",
    "last_boosted_at:",
    "last_weight_migrated_at:",
    "tags:",
    "cssclasses:",
]


def test_templates_exist_and_keep_memory_frontmatter_contract():
    for rel in TEMPLATES:
        path = ROOT / rel
        assert path.exists(), f"missing template: {rel}"
        text = path.read_text(encoding="utf-8")
        assert text.startswith("---\n"), f"{rel} must start with YAML frontmatter"
        for field in REQUIRED_FRONTMATTER_FIELDS:
            assert field in text, f"{rel} missing {field}"
        assert "<% tp.date.now(" in text, f"{rel} should use Templater dates"
        assert "memory/" in text, f"{rel} should include memory tags"


def test_dashboards_exist_and_contain_dataview_blocks():
    for rel in DASHBOARDS:
        path = ROOT / rel
        assert path.exists(), f"missing dashboard: {rel}"
        text = path.read_text(encoding="utf-8")
        assert "```dataview" in text, f"{rel} must contain a Dataview block"
        assert "wiki" in text, f"{rel} should query wiki notes"


def test_bases_are_valid_yaml_with_table_views():
    for rel in BASES:
        path = ROOT / rel
        assert path.exists(), f"missing base: {rel}"
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert isinstance(data, dict), f"{rel} must parse as YAML mapping"
        assert "filters" in data, f"{rel} missing filters"
        assert "properties" in data, f"{rel} missing properties"
        assert "views" in data, f"{rel} missing views"
        assert isinstance(data["views"], list) and data["views"], f"{rel} must define views"
        assert data["views"][0]["type"] == "table", f"{rel} first view should be table"


def test_canvas_is_valid_json_and_links_core_memory_files():
    path = ROOT / "canvases/LLM-Brain-OS.canvas"
    assert path.exists(), "missing LLM-Brain-OS.canvas"
    data = json.loads(path.read_text(encoding="utf-8"))
    nodes = data.get("nodes", [])
    edges = data.get("edges", [])
    assert len(nodes) >= 10
    assert len(edges) >= 8
    files = {node.get("file") for node in nodes if node.get("type") == "file"}
    for expected in [
        "wiki/global_hot.md",
        "wiki/project_exclusives/member/hot.md",
        "wiki/project_exclusives/member/llm-brain-os-architecture.md",
        "dashboards/记忆治理总览.md",
        "docs/memory-repository-technical-solution.md",
        "docs/memory-repository-user-manual.md",
    ]:
        assert expected in files


def test_memory_snippet_exists_without_forcing_appearance_config():
    snippet = ROOT / ".obsidian/snippets/memory-vault.css"
    assert snippet.exists()
    text = snippet.read_text(encoding="utf-8")
    assert ".memory-hot" in text
    assert ".memory-cold" in text
    appearance = ROOT / ".obsidian/appearance.json"
    if appearance.exists():
        appearance_text = appearance.read_text(encoding="utf-8")
        assert "memory-vault" not in appearance_text
