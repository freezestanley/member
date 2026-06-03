#!/usr/bin/env python3
"""
scripts/utils.py — LLM-Brain OS 公共工具函数

目前提供：
  - extract_aliases(text)  从 Frontmatter aliases 字段提取别名字符串
  - extract_aliases_as_line(text)  同上，别名用空格连接为单行（供 rg 检索注入）

被以下脚本共用：
  - bm25_search.py
  - rg_body_search.py
"""

import re

_ALIASES_RE = re.compile(r'aliases:\s*\[([^\]]*)\]')


def extract_aliases(text: str) -> str:
    """从 Frontmatter 的 aliases 字段提取别名，返回空格拼接的字符串。

    支持格式：
        aliases: [A, B, C]
        aliases: [A, B]  # 行内注释

    必须在 Frontmatter 剥离之前调用（剥离后字段消失）。
    若无 aliases 字段或列表为空，返回空字符串。
    """
    m = _ALIASES_RE.search(text)
    if not m:
        return ""
    # 去掉行内注释，逗号分割，过滤空项
    raw = re.sub(r'#.*', '', m.group(1))
    return " ".join(part.strip() for part in raw.split(",") if part.strip())


# rg_body_search.py 用同名函数但语义相同，提供别名保持向后兼容
extract_aliases_as_line = extract_aliases
