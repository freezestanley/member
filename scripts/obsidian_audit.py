from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from frontmatter_utils import parse_frontmatter_text, split_frontmatter


WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:[#|][^\]]*)?\]\]")


def parse_note_metadata(path: Path, root: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    try:
        _, fm_text, suffix = split_frontmatter(text)
        fm = parse_frontmatter_text(fm_text)
        body = suffix.split("---\n", 1)[1] if suffix.startswith("---\n") else suffix
    except ValueError:
        fm = {}
        body = text
    outlinks = [match.strip() for match in WIKILINK_RE.findall(body)]
    fm["path"] = path
    fm["relative_path"] = str(path.relative_to(root))
    fm["outlinks"] = outlinks
    return fm


def _iter_notes(wiki_root: Path):
    for path in wiki_root.rglob("*.md"):
        if path.name in {"hot.md", "global_hot.md", "index.md", "log.md"}:
            continue
        yield path


def _is_active(meta: dict) -> bool:
    return str(meta.get("status", "active")).strip().strip("\"'") == "active"


def _aliases_empty(value) -> bool:
    if value is None:
        return True
    return str(value).strip() in {"", "[]"}


def find_alias_gaps(wiki_root: Path) -> list[dict]:
    root = wiki_root.parent
    results = []
    for path in _iter_notes(wiki_root):
        meta = parse_note_metadata(path, root)
        if _is_active(meta) and _aliases_empty(meta.get("aliases")):
            results.append(meta)
    return sorted(results, key=lambda item: str(item["path"]))


def _float(value, default: float = 1.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def find_low_weight_candidates(wiki_root: Path, threshold: float = 0.3) -> list[dict]:
    root = wiki_root.parent
    results = []
    for path in _iter_notes(wiki_root):
        meta = parse_note_metadata(path, root)
        if _is_active(meta) and _float(meta.get("current_weight")) < threshold:
            results.append(meta)
    return sorted(results, key=lambda item: _float(item.get("current_weight")))


def load_canvas_file_nodes(canvas_path: Path) -> list[str]:
    data = json.loads(canvas_path.read_text(encoding="utf-8"))
    return [
        node["file"]
        for node in data.get("nodes", [])
        if node.get("type") == "file" and node.get("file")
    ]


def _jsonable(items: list[dict]) -> list[dict]:
    output = []
    for item in items:
        copy = dict(item)
        copy["path"] = str(copy["path"])
        output.append(copy)
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--wiki-root", default="wiki")
    parser.add_argument("--canvas", default="canvases/LLM-Brain-OS.canvas")
    parser.add_argument("--threshold", type=float, default=0.3)
    args = parser.parse_args(argv)

    wiki_root = Path(args.wiki_root)
    canvas = Path(args.canvas)
    report = {
        "alias_gaps": _jsonable(find_alias_gaps(wiki_root)),
        "low_weight_candidates": _jsonable(find_low_weight_candidates(wiki_root, args.threshold)),
        "canvas_files": load_canvas_file_nodes(canvas) if canvas.exists() else [],
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
