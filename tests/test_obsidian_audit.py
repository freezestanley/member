from __future__ import annotations

from pathlib import Path

import sys

sys.path.insert(0, "scripts")

from obsidian_audit import (  # noqa: E402
    find_alias_gaps,
    find_low_weight_candidates,
    load_canvas_file_nodes,
    parse_note_metadata,
)


def _note(path: Path, frontmatter: str, body: str = "# Note\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\n{frontmatter}---\n{body}", encoding="utf-8")
    return path


def test_parse_note_metadata_extracts_frontmatter_and_links(tmp_path):
    note = _note(
        tmp_path / "wiki" / "global_concepts" / "a.md",
        "status: active\naliases: [A]\ncurrent_weight: 1.0\n",
        "# A\n参见 [[b]]。\n",
    )

    meta = parse_note_metadata(note, tmp_path)

    assert meta["status"] == "active"
    assert meta["aliases"] == "[A]"
    assert meta["current_weight"] == "1.0"
    assert meta["outlinks"] == ["b"]


def test_find_alias_gaps_only_active_notes_without_aliases(tmp_path):
    _note(tmp_path / "wiki" / "global_concepts" / "missing.md", "status: active\naliases: []\n")
    _note(tmp_path / "wiki" / "global_concepts" / "ok.md", "status: active\naliases: [OK]\n")
    _note(tmp_path / "wiki" / "global_concepts" / "archived.md", "status: archived\naliases: []\n")

    gaps = find_alias_gaps(tmp_path / "wiki")

    assert [item["path"].name for item in gaps] == ["missing.md"]


def test_find_low_weight_candidates_filters_active_notes(tmp_path):
    _note(tmp_path / "wiki" / "global_concepts" / "cold.md", "status: active\ncurrent_weight: 0.12\n")
    _note(tmp_path / "wiki" / "global_concepts" / "warm.md", "status: active\ncurrent_weight: 0.8\n")

    candidates = find_low_weight_candidates(tmp_path / "wiki", threshold=0.3)

    assert [item["path"].name for item in candidates] == ["cold.md"]


def test_load_canvas_file_nodes_reads_canvas_json(tmp_path):
    canvas = tmp_path / "canvases" / "map.canvas"
    canvas.parent.mkdir(parents=True)
    canvas.write_text(
        '{"nodes":[{"id":"a","type":"file","file":"wiki/a.md"},{"id":"b","type":"text","text":"B"}],"edges":[]}',
        encoding="utf-8",
    )

    files = load_canvas_file_nodes(canvas)

    assert files == ["wiki/a.md"]
