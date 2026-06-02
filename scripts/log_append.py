#!/usr/bin/env python3
"""
log_append.py — 向 wiki/log.md 追加查询日志，并保持最多 50 条记录。

用法：
    python3 log_append.py "<命令名>" "<查询词>" "<结果摘要，不超过30字>"

示例：
    python3 log_append.py "brain-query" "OpenClaw SDK 架构" "命中2条：架构与差异对比笔记"

规则：
- 按日期分组，当天无标题则新建
- 每次写入后，若全文总记录条数超过 50，从最早的记录开始删除
- 空日期组（标题下无记录）自动清除
"""

import sys
import re
from datetime import datetime
from pathlib import Path

LOG_PATH = Path(__file__).parent.parent / "wiki" / "log.md"
MAX_ENTRIES = 50


def parse_log(text: str) -> list[dict]:
    """
    解析 log.md，返回结构化列表。
    每个元素：{"date": "2026-06-02", "entries": ["- 2026-06-02 ...", ...]}
    顺序与文件一致（最新在前）。
    """
    groups = []
    current_date = None
    current_entries = []

    for line in text.splitlines():
        m = re.match(r'^## (\d{4}-\d{2}-\d{2})\s*$', line)
        if m:
            if current_date is not None:
                groups.append({"date": current_date, "entries": current_entries})
            current_date = m.group(1)
            current_entries = []
        elif line.startswith("- ") and current_date:
            current_entries.append(line)
        # 空行和其他行忽略

    if current_date is not None:
        groups.append({"date": current_date, "entries": current_entries})

    return groups


def render_log(groups: list[dict]) -> str:
    lines = []
    for g in groups:
        if not g["entries"]:
            continue  # 跳过空日期组
        lines.append(f"## {g['date']}")
        lines.extend(g["entries"])
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def trim_to_limit(groups: list[dict], max_entries: int) -> list[dict]:
    """从最旧的记录开始删除，直到总条数 <= max_entries。"""
    total = sum(len(g["entries"]) for g in groups)
    if total <= max_entries:
        return groups

    # 从末尾（最旧）往前删
    groups = [{"date": g["date"], "entries": list(g["entries"])} for g in groups]
    while sum(len(g["entries"]) for g in groups) > max_entries:
        # 找最后一个有记录的组
        for i in range(len(groups) - 1, -1, -1):
            if groups[i]["entries"]:
                groups[i]["entries"].pop()
                break

    # 清除空组
    groups = [g for g in groups if g["entries"]]
    return groups


def append_entry(cmd: str, query: str, summary: str) -> None:
    today = datetime.now().strftime("%Y-%m-%d")
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    new_entry = f"- {now} {cmd} \"{query}\" {summary}"

    # 读取现有内容
    if LOG_PATH.exists():
        text = LOG_PATH.read_text(encoding="utf-8")
    else:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        text = ""

    groups = parse_log(text)

    # 找当天的组，没有则在顶部插入
    today_group = next((g for g in groups if g["date"] == today), None)
    if today_group is None:
        groups.insert(0, {"date": today, "entries": [new_entry]})
    else:
        today_group["entries"].append(new_entry)

    # 修剪到 50 条
    groups = trim_to_limit(groups, MAX_ENTRIES)

    LOG_PATH.write_text(render_log(groups), encoding="utf-8")
    print(f"[log_append] 已写入: {new_entry}")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("用法: python3 log_append.py <命令名> <查询词> <结果摘要>", file=sys.stderr)
        sys.exit(1)

    cmd_name = sys.argv[1]
    query_text = sys.argv[2]
    result_summary = sys.argv[3]

    append_entry(cmd_name, query_text, result_summary)
