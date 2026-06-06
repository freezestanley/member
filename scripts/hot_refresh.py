#!/usr/bin/env python3
"""
hot_refresh.py — 双轨路由热记忆刷新。

用法：
    python3 hot_refresh.py --global [--wiki-root PATH]
    python3 hot_refresh.py --project <name> [--wiki-root PATH]

--global   : 扫描 global_concepts/，写入 wiki/global_hot.md（TOP_N=8）
--project  : 扫描 project_exclusives/<name>/，写入其下 hot.md（TOP_M=20）
--wiki-root: 指定 wiki 根目录（测试时覆盖，默认自动推导）
"""

import argparse
import fcntl
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

# 确保 scripts/ 目录在 sys.path 中，以便导入 config
_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from config import GLOBAL_TOP_N, PROJECT_TOP_M, SKIP_STATUSES, GENERATED_FILES

HEADING_RE = re.compile(r'^(#{1,3})\s+(.+)$')


def parse_frontmatter(text: str) -> dict:
    m = re.match(r'^---\s*\n(.*?)\n---\s*\n', text, re.DOTALL)
    if not m:
        return {}
    result = {}
    for line in m.group(1).splitlines():
        kv = re.match(r'^(\w+):\s*(.+)$', line.strip())
        if kv:
            result[kv.group(1)] = kv.group(2).strip()
    return result


def extract_title(text: str) -> str:
    for line in text.splitlines():
        m = re.match(r'^#+\s+(.+)$', line)
        if m:
            return m.group(1).strip()
    return ""


def extract_outline(text: str) -> list[str]:
    body = re.sub(r'^---[\s\S]+?---\n', '', text, count=1, flags=re.MULTILINE)
    lines = []
    for line in body.splitlines():
        m = HEADING_RE.match(line)
        if m:
            level = len(m.group(1))
            title = m.group(2).strip()
            indent = "  " * (level - 1)
            lines.append(f"{indent}- {title}")
    return lines


def collect_notes(scan_dir: Path) -> list[dict]:
    """扫描指定目录，收集所有 .md 笔记元数据。"""
    notes = []
    if not scan_dir.exists():
        return notes
    for md_file in scan_dir.rglob("*.md"):
        # 跳过自身（hot.md）
        if md_file.name in GENERATED_FILES:
            continue
        try:
            text = md_file.read_text(encoding="utf-8")
        except Exception:
            continue
        fm = parse_frontmatter(text)
        if not fm:
            continue
        if fm.get("status") in SKIP_STATUSES:
            continue
        title = extract_title(text) or md_file.stem
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
            "stem": md_file.stem,
            "weight": weight,
            "access": access,
            "outline": extract_outline(text),
        })
    return notes


def render_hot(notes: list[dict], top_k: int = None, label: str = "") -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    if top_k is None:
        top_k = len(notes)
    lines = [
        f"# 知识热度榜 Top {top_k} — {label}",
        f"> 更新时间：{now}　　数据来源：current_weight + access_count",
        "> [!WARNING]",
        "> 本文件由 `hot_refresh.py` 自动生成，禁止手动编辑。",
        "",
    ]
    for i, note in enumerate(notes, 1):
        header = (
            f"### {i}. [[{note['stem']}]] — {note['title']}"
            f"  ·  🧠 {note['weight']:.3f}  ·  📊 {note['access']} 次"
        )
        lines.append(header)
        if note["outline"]:
            lines.extend(note["outline"])
        else:
            lines.append("- *(无标题大纲)*")
        lines.append("")
    return "\n".join(lines)


def render_skeleton(project_name: str) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    return (
        f"# 知识热度榜 — {project_name}\n"
        f"> 更新时间：{now}\n"
        "> [!WARNING]\n"
        "> 本文件由 `hot_refresh.py` 自动生成，禁止手动编辑。\n\n"
        "暂无高权笔记（该项目尚未有带 frontmatter 的 .md 笔记）。\n"
    )


def atomic_write(target: Path, content: str, lock_file: Path) -> None:
    """带 fcntl 独占锁的原子写入。"""
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    with open(lock_file, "w") as lf:
        start = time.time()
        while True:
            try:
                fcntl.flock(lf, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.time() - start > 10.0:
                    raise RuntimeError(f"获取锁超时（>10s）：{lock_file}")
                time.sleep(0.3)
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            target.write_text(content, encoding="utf-8")
        finally:
            fcntl.flock(lf, fcntl.LOCK_UN)


def main():
    parser = argparse.ArgumentParser(description="hot_refresh 双轨路由")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--global", dest="global_mode", action="store_true",
                       help="刷新全局热记忆 wiki/global_hot.md")
    group.add_argument("--project", metavar="NAME",
                       help="刷新指定项目热记忆 wiki/project_exclusives/<NAME>/hot.md")
    parser.add_argument("--wiki-root", metavar="PATH",
                        help="覆盖 wiki 根目录（测试用）")
    args = parser.parse_args()

    if args.wiki_root:
        wiki_root = Path(args.wiki_root)
    else:
        wiki_root = Path(__file__).parent.parent / "wiki"

    inbox = wiki_root.parent / "_inbox"

    if args.global_mode:
        scan_dir = wiki_root / "global_concepts"
        target = wiki_root / "global_hot.md"
        lock_file = inbox / ".hot_refresh_global.lock"
        notes = collect_notes(scan_dir)
        notes.sort(key=lambda n: (n["weight"], n["access"]), reverse=True)
        top = notes[:GLOBAL_TOP_N]
        if not top:
            content = render_skeleton("global")
            print("[hot_refresh] --global: 全局无笔记，写骨架。", file=sys.stderr)
        else:
            content = render_hot(top, GLOBAL_TOP_N, "全局通用知识")
            print(f"[hot_refresh] --global: 写入 {len(top)} 条 → {target}")
        atomic_write(target, content, lock_file)

    else:
        project_name = args.project
        scan_dir = wiki_root / "project_exclusives" / project_name
        target = scan_dir / "hot.md"
        lock_file = inbox / f".hot_refresh_{project_name}.lock"
        notes = collect_notes(scan_dir)
        notes.sort(key=lambda n: (n["weight"], n["access"]), reverse=True)
        top = notes[:PROJECT_TOP_M]
        if not top:
            content = render_skeleton(project_name)
            print(f"[hot_refresh] --project {project_name}: 无笔记，写骨架。", file=sys.stderr)
        else:
            content = render_hot(top, PROJECT_TOP_M, f"项目 {project_name}")
            print(f"[hot_refresh] --project {project_name}: 写入 {len(top)} 条 → {target}")
        atomic_write(target, content, lock_file)


if __name__ == "__main__":
    main()
