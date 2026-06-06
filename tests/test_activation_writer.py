from datetime import date
from pathlib import Path
import sys

import pytest

sys.path.insert(0, "scripts")

from activation_writer import ActivationError, activate_note  # noqa: E402
from weight_engine import DEFAULT_CONFIG  # noqa: E402


def _note(path: Path, frontmatter: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\n{frontmatter}---\n# Note\nBody\n", encoding="utf-8")
    return path


def test_activate_note_updates_access_ewma_weight_and_full_v2_schema(tmp_path, monkeypatch):
    wiki = tmp_path / "wiki"
    note = _note(
        wiki / "project_exclusives" / "member" / "old.md",
        "initial_weight: 1.0\n"
        "current_weight: 1.0\n"
        "last_activated: 2026-06-05\n"
        "last_modified: 2026-06-05\n"
        "access_count: 1\n"
        "status: active\n",
    )
    monkeypatch.setattr("activation_writer.BRAIN_DIR", tmp_path)
    monkeypatch.setattr("activation_writer.WIKI_ROOT", wiki)
    monkeypatch.setattr("activation_writer.GLOBAL_DIR", wiki / "global_concepts")
    monkeypatch.setattr("activation_writer.PROJECT_DIR", wiki / "project_exclusives")

    result = activate_note(str(note), DEFAULT_CONFIG.copy(), today=date(2026, 6, 6))

    text = note.read_text(encoding="utf-8")
    assert result["access_count"] == 2
    assert result["ewma_access"] > 0.0
    assert result["current_weight"] > 0
    for field in [
        "weight_schema_version: 2",
        "category: general",
        "importance: 1",
        "last_weight_migrated_at: 2026-06-06",
        "last_activated: 2026-06-06",
        "last_modified: 2026-06-06",
    ]:
        assert field in text


def test_activate_note_rejects_quoted_or_commented_inactive_status(tmp_path, monkeypatch):
    wiki = tmp_path / "wiki"
    note = _note(
        wiki / "global_concepts" / "archived.md",
        "initial_weight: 1.0\n"
        "current_weight: 1.0\n"
        "last_activated: 2026-06-05\n"
        "access_count: 1\n"
        "status: \"archived\" # old\n",
    )
    monkeypatch.setattr("activation_writer.BRAIN_DIR", tmp_path)
    monkeypatch.setattr("activation_writer.WIKI_ROOT", wiki)
    monkeypatch.setattr("activation_writer.GLOBAL_DIR", wiki / "global_concepts")
    monkeypatch.setattr("activation_writer.PROJECT_DIR", wiki / "project_exclusives")

    with pytest.raises(ActivationError) as exc:
        activate_note(str(note), DEFAULT_CONFIG.copy(), today=date(2026, 6, 6))

    assert exc.value.exit_code == 3
    assert "last_activated: 2026-06-05" in note.read_text(encoding="utf-8")


def test_activate_note_rejects_symlink_escape(tmp_path, monkeypatch):
    wiki = tmp_path / "wiki"
    allowed = wiki / "project_exclusives" / "member"
    outside = _note(
        tmp_path / "outside.md",
        "initial_weight: 1.0\n"
        "current_weight: 1.0\n"
        "last_activated: 2026-06-05\n"
        "access_count: 1\n"
        "status: active\n",
    )
    allowed.mkdir(parents=True)
    link = allowed / "link.md"
    link.symlink_to(outside)
    monkeypatch.setattr("activation_writer.BRAIN_DIR", tmp_path)
    monkeypatch.setattr("activation_writer.WIKI_ROOT", wiki)
    monkeypatch.setattr("activation_writer.GLOBAL_DIR", wiki / "global_concepts")
    monkeypatch.setattr("activation_writer.PROJECT_DIR", wiki / "project_exclusives")

    with pytest.raises(ActivationError) as exc:
        activate_note(str(link), DEFAULT_CONFIG.copy(), today=date(2026, 6, 6))

    assert exc.value.exit_code == 3
