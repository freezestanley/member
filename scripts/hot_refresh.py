#!/usr/bin/env python3
"""
hot_refresh.py — 扫描全库笔记，按 current_weight 降序取 Top 30，重写 wiki/hot.md。

输出格式（大纲树模式）：
  ### [[笔记文件名]] — 笔记标题  ·  🧠 weight: 1.139  ·  📊 access: 5
  - 一级标题内容
    - 二级标题内容
      - 三级标题内容

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


HEADING_RE = re.compile(r'^(#{1,3})\s+(.+)$')


def extract_outline(text: str) -> list[str]:
    """从正文提取 H1-H3 标题，返回缩进大纲行列表。
    H1 → "- 标题"，H2 → "  - 标题"，H3 → "    - 标题"
    跳过 Frontmatter 中的内容（只处理 --- 之后的正文）。
    """
    # 剥离 Frontmatter，只对正文提取标题
    body = re.sub(r'^---[\s\S]+?---\n', '', text, count=1, flags=re.MULTILINE)
    lines = []
    for line in body.splitlines():
        m = HEADING_RE.match(line)
        if m:
            level = len(m.group(1))          # 1, 2, 3
            title = m.group(2).strip()
            indent = "  " * (level - 1)      # H1="", H2="  ", H3="    "
            lines.append(f"{indent}- {title}")
    return lines


def collect_notes() -> list[dict]:
    """遍历扫描目录，收集所有 .md 笔记的元数据（含原始正文，用于大纲提取）。"""
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
                "stem": md_file.stem,        # 用于 [[双链]] 锚点
                "path": str(rel_path),
                "weight": weight,
                "access": access,
                "outline": extract_outline(text),  # 预提取大纲，render 时直接用
            })

    return notes


def render_hot(notes: list[dict]) -> str:
    """将热度 Top N 笔记渲染为大纲树格式。

    格式（每篇笔记）：
        ### [[文件名]] — 笔记标题  ·  🧠 weight: 1.139  ·  📊 access: 5
        - 一级标题
          - 二级标题
            - 三级标题
        （空行分隔）
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        f"# 知识热度榜 Top {TOP_N}",
        f"> 更新时间：{now}　　数据来源：全库笔记 current_weight + access_count",
        "",
    ]
    for i, note in enumerate(notes, 1):
        # 条目标题行：序号 + 双链锚点 + 可读标题 + 权重/调用数
        header = (
            f"### {i}. [[{note['stem']}]] — {note['title']}"
            f"  ·  🧠 {note['weight']:.3f}  ·  📊 {note['access']} 次"
        )
        lines.append(header)

        if note["outline"]:
            lines.extend(note["outline"])
        else:
            lines.append("- *(无标题大纲)*")

        lines.append("")   # 笔记间空行

    return "\n".join(lines)


def main():
    import fcntl

    LOCK_FILE = Path(__file__).parent.parent / "_inbox" / ".hot_refresh.lock"
    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)

    _lock_fh = open(LOCK_FILE, "w")
    try:
        fcntl.flock(_lock_fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("[hot_refresh] 另一进程正在刷新，本次跳过。", file=sys.stderr)
        _lock_fh.close()
        sys.exit(0)

    try:
        notes = collect_notes()
        if not notes:
            print("[hot_refresh] 未找到任何笔记，hot.md 未更新。", file=sys.stderr)
            sys.exit(0)

        notes.sort(key=lambda n: (n["weight"], n["access"]), reverse=True)
        top = notes[:TOP_N]

        HOT_MD.write_text(render_hot(top), encoding="utf-8")
        print(f"[hot_refresh] 已更新 hot.md，共 {len(top)} 条记录（全库 {len(notes)} 篇笔记）。")
    finally:
        fcntl.flock(_lock_fh, fcntl.LOCK_UN)
        _lock_fh.close()
        # 注意：故意不删除 LOCK_FILE，锁文件是持久标记。
        # 进程持有 flock 期间 vault_sync.sh 通过 flock -n 探测锁状态，
        # 而非通过文件是否存在来判断。


if __name__ == "__main__":
    main()
