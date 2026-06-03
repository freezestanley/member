#!/usr/bin/env python3
"""
rg_body_search.py — 剥离 Frontmatter 后的正文检索包装器。

用法：
    python3 rg_body_search.py "<关键词>" <目录1> [目录2 ...]

输出格式（与 rg --no-heading 一致）：
    <文件路径>:<行号>:<匹配行内容>
"""
import os
import re
import sys

FRONTMATTER_RE = re.compile(r'^---\s*\n.*?\n---\s*\n', re.DOTALL)


def search_body(pattern: str, paths: list) -> list:
    """
    在 paths 中的每个 .md 文件剥离 Frontmatter 后，
    用 re.search(pattern, line, re.IGNORECASE) 逐行匹配。
    返回 [{"file": ..., "lineno": ..., "line": ...}, ...]
    """
    compiled = re.compile(pattern, re.IGNORECASE)
    results = []

    for path in paths:
        if not path.endswith(".md"):
            continue
        try:
            text = open(path, encoding="utf-8").read()
        except Exception:
            continue

        # 剥离 Frontmatter 块
        body = FRONTMATTER_RE.sub("", text, count=1)

        # 计算 Frontmatter 占用的行数，用于还原真实行号
        fm_match = FRONTMATTER_RE.match(text)
        fm_lines = fm_match.group(0).count("\n") if fm_match else 0

        for i, line in enumerate(body.splitlines(), start=fm_lines + 1):
            if compiled.search(line):
                results.append({"file": path, "lineno": i, "line": line})

    return results


def expand_paths(paths: list) -> list:
    """将目录递归展开为 .md 文件列表"""
    files = []
    for p in paths:
        if os.path.isfile(p):
            files.append(p)
        elif os.path.isdir(p):
            for root, _, fnames in os.walk(p):
                for f in fnames:
                    if f.endswith(".md"):
                        files.append(os.path.join(root, f))
    return files


def main():
    if len(sys.argv) < 3:
        print("用法: python3 rg_body_search.py <关键词> <目录或文件> [...]")
        sys.exit(1)

    pattern = sys.argv[1]
    raw_paths = sys.argv[2:]
    all_files = expand_paths(raw_paths)
    hits = search_body(pattern, all_files)

    if not hits:
        print(f"[rg_body] 未找到正文命中：{pattern!r}")
        sys.exit(1)

    for h in hits:
        print(f"{h['file']}:{h['lineno']}:{h['line']}")


if __name__ == "__main__":
    main()
