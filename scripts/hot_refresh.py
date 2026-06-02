#!/usr/bin/env python3
"""
hot_refresh.py — 扫描全库笔记，按 current_weight 降序取 Top 30，重写 wiki/hot.md。

输出格式（每行一条）：
  - [笔记标题](相对路径) | weight: 1.139 | access: 5

用法：
    python3 hot_refresh.py
"""

import re
import sys
from datetime import datetime
from pathlib import Path

WIKI_ROOT = Path(__file__).parent.parent / "wiki"
HOT_MD = WIKI_ROOT / "hot.md"
TOP_N = 30

# 扫描范围：公共概念 + 所有项目专属
SCAN_DIRS = [
    WIKI_ROOT / "global_concepts",
    WIKI_ROOT / "project_exclusives",
]


def parse_frontmatter(text: str) -> dict:
    """提取 YAML frontmatter 中的关键字段，解析失败返回空 dict。"""
    m = re.match(r'^---\s*\n(.*?)\n---\s*\n', text, re.DOTALL)
    if not m:
        return {}
    fm_text = m.group(1)
    result = {}
    for line in fm_text.splitlines():
        kv = re.match(r'^(\w+):\s*(.+)$', line.strip())
        if kv:
            result[kv.group(1)] = kv.group(2).strip()
    return result


def extract_title(text: str) -> str:
    """从正文提取第一个 # 标题，没有则返回文件名。"""
    for line in text.splitlines():
        m = re.match(r'^#+\s+(.+)$', line)
        if m:
            return m.group(1).strip()
    return ""


def collect_notes() -> list[dict]:
    """遍历扫描目录，收集所有 .md 笔记的元数据。"""
    notes = []
    for scan_dir in SCAN_DIRS:
        if not scan_dir.exists():
            continue
        for md_file in scan_dir.rglob("*.md"):
            # 跳过 hot.md / log.md / index.md 等顶级管理文件
            if md_file.parent == WIKI_ROOT:
                continue
            try:
                text = md_file.read_text(encoding="utf-8")
            except Exception:
                continue

            fm = parse_frontmatter(text)
            if not fm:
                continue

            title = extract_title(text) or md_file.stem
            rel_path = md_file.relative_to(WIKI_ROOT.parent)  # 相对于 member 根目录

            try:
                weight = float(fm.get("current_weight", fm.get("initial_weight", "1.0")))
            except ValueError:
                weight = 1.0

            try:
                access = int(fm.get("access_count", "0"))
            except ValueError:
                access = 0

            notes.append({
                "title": title,
                "path": str(rel_path),
                "weight": weight,
                "access": access,
            })

    return notes


def render_hot(notes: list[dict]) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        f"# 知识热度榜 Top {TOP_N}",
        f"> 更新时间：{now}　　数据来源：全库笔记 current_weight + access_count",
        "",
        "| # | 笔记 | 权重 | 调用次数 |",
        "|---|------|------|----------|",
    ]
    for i, note in enumerate(notes, 1):
        link = f"[{note['title']}]({note['path']})"
        lines.append(f"| {i} | {link} | {note['weight']:.3f} | {note['access']} |")

    lines.append("")
    return "\n".join(lines)


def main():
    notes = collect_notes()
    if not notes:
        print("[hot_refresh] 未找到任何笔记，hot.md 未更新。", file=sys.stderr)
        sys.exit(0)

    # 按 current_weight 降序，同权重按 access_count 降序
    notes.sort(key=lambda n: (n["weight"], n["access"]), reverse=True)
    top = notes[:TOP_N]

    HOT_MD.write_text(render_hot(top), encoding="utf-8")
    print(f"[hot_refresh] 已更新 hot.md，共 {len(top)} 条记录（全库 {len(notes)} 篇笔记）。")


if __name__ == "__main__":
    main()
