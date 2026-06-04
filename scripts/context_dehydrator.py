"""
scripts/context_dehydrator.py
LLM-Brain OS 上下文脱水管道

用法（BM25路径，summary模式）：
  python3 context_dehydrator.py --mode summary --files file1.md file2.md --max-tokens 8000

用法（rg路径，precise模式）：
  python3 context_dehydrator.py --mode precise --hits file1.md:3,7 file2.md:12 --max-tokens 8000
"""
import re

# ─── 正则常量 ───────────────────────────────────────────────────────────────

_HEADING_RE = re.compile(r"^(#{1,3})\s+(.+?)(?:\s+[—\-].+)?$")
_LINK_RE = re.compile(r"\[\[(.*?)\]\]")
_FRONTMATTER_RE = re.compile(r"^---\s*\n.*?\n---\s*\n", re.DOTALL)


# ─── 内部工具函数 ───────────────────────────────────────────────────────────


def _build_hierarchy_map(lines: list) -> list:
    """
    扫描行列表，返回每行对应的标题层级快照。
    返回值：[{1: H1文本|None, 2: H2文本|None, 3: H3文本|None}, ...]
    """
    stack = {1: None, 2: None, 3: None}
    result = []
    for line in lines:
        stripped = line.strip()
        m = _HEADING_RE.match(stripped)
        if m:
            level = len(m.group(1))
            title = m.group(2).strip()
            stack[level] = title
            for l in range(level + 1, 4):
                stack[l] = None
        result.append(dict(stack))
    return result


def _protect_links(text: str) -> tuple:
    """提取所有 [[stem]] 并替换为占位符，防止后续处理打碎双链。"""
    cache = _LINK_RE.findall(text)
    protected = text
    for idx, link_text in enumerate(cache):
        protected = protected.replace(f"[[{link_text}]]", f"__BRAIN_LINK_{idx}__", 1)
    return protected, cache


def _restore_links(text: str, cache: list) -> str:
    """将占位符还原为原始 [[stem]] 双链。"""
    result = text
    for idx, link_text in enumerate(cache):
        result = result.replace(f"__BRAIN_LINK_{idx}__", f"[[{link_text}]]")
    return result


def _find_code_block_ranges(lines: list) -> list:
    """返回代码块的行号范围列表 [(start, end), ...]，行号为 0-based 闭区间。"""
    ranges = []
    in_block = False
    start_idx = 0
    for idx, line in enumerate(lines):
        if line.strip().startswith("```"):
            if not in_block:
                in_block = True
                start_idx = idx
            else:
                in_block = False
                ranges.append((start_idx, idx))
    if in_block:
        # 未闭合：延伸到最后一行
        ranges.append((start_idx, len(lines) - 1))
    return ranges


def _python_clean(text: str) -> str:
    """纯 Python 去噪：去除 HTML 注释、行尾死空格、多余空行。"""
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    text = re.sub(r"[ \t]+$", "", text, flags=re.MULTILINE)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


def _summary_mode(raw_md: str, file_stem: str) -> str:
    """
    全文摘要模式（BM25路径 / alias命中 fallback）：
    剥离 frontmatter + 去噪，保留完整正文内容。
    脱水收益来自去除 frontmatter（通常占 15-25%）、HTML 注释、死空格，
    而不是截断内容——BM25 只知道"哪篇文档相关"，不知道哪行，完整正文是最安全的上下文。
    """
    body = _FRONTMATTER_RE.sub("", raw_md, count=1)
    header = f"[📍 Source: {file_stem}]\n"
    return (header + _python_clean(body)).strip()


def dehydrate_context(raw_md: str, hit_lines: list, file_stem: str) -> str:
    """
    LLM-Brain OS 上下文脱水核心管道。

    hit_lines=[]  → 全文摘要模式（BM25路径）
    hit_lines=[0] → alias 命中 fallback → 全文摘要模式
    hit_lines=[n] → 精准裁剪模式（n 为 1-based 行号，rg路径）
    """
    if not raw_md.strip():
        return ""

    # alias 命中 (lineno=0) 或无行号 → 全文摘要模式
    real_hits = [h for h in hit_lines if h > 0]
    if not real_hits:
        return _summary_mode(raw_md, file_stem)

    # 精准裁剪模式
    protected_md, link_cache = _protect_links(raw_md)
    p_lines = protected_md.split("\n")
    total = len(p_lines)

    hierarchy_map = _build_hierarchy_map(p_lines)
    code_ranges = _find_code_block_ranges(p_lines)

    keep_mask = [False] * total

    for hit in real_hits:
        idx = hit - 1
        if not (0 <= idx < total):
            continue

        # 判断是否在代码块内
        in_code = False
        for start, end in code_ranges:
            if start <= idx <= end:
                for k in range(start, end + 1):
                    keep_mask[k] = True
                in_code = True
                break

        if in_code:
            continue

        # 普通段落：向上找最近标题，向下找下一标题
        start_bound = idx
        for u in range(idx, -1, -1):
            start_bound = u
            if p_lines[u].strip().startswith("#"):
                break

        end_bound = total - 1
        for d in range(idx + 1, total):
            if p_lines[d].strip().startswith("#"):
                end_bound = d - 1
                break

        for k in range(start_bound, end_bound + 1):
            keep_mask[k] = True

    # 组装带面包屑的 chunk
    segments = []
    last_crumb = ""
    in_chunk = False

    for idx, keep in enumerate(keep_mask):
        if keep:
            h = hierarchy_map[idx]
            nodes = [file_stem]
            for level in [1, 2, 3]:
                if h.get(level):
                    nodes.append(h[level])
            crumb = " ➔ ".join(nodes)
            if crumb != last_crumb or not in_chunk:
                segments.append(f"\n[📍 Context Scope: {crumb}]")
                last_crumb = crumb
                in_chunk = True
            segments.append(p_lines[idx])
        else:
            if in_chunk:
                segments.append("\n// ... [Omitted] ...\n")
                in_chunk = False

    body = _python_clean("\n".join(segments))
    return _restore_links(body, link_cache).strip()


def assemble_final_context(recalled_results: list, max_total_tokens: int = 8000) -> str:
    """
    recalled_results 格式（二选一）：
      BM25路径: [{"content": raw_md, "stem": "...", "score": 0.85}]
      rg路径:   [{"content": raw_md, "stem": "...", "hit_lines": [n, ...]}]

    按 score 降序排列（rg路径无 score 则视为 1.0），超出 max_total_tokens 截断。
    token 估算：len(text) // 3.5（中英混合仓合理粗估）。
    """
    if not recalled_results:
        return ""

    sorted_results = sorted(
        recalled_results,
        key=lambda x: x.get("score", 1.0),
        reverse=True,
    )

    chunks = []
    used_tokens = 0

    for item in sorted_results:
        hit_lines = item.get("hit_lines", [])
        chunk = dehydrate_context(item["content"], hit_lines, item["stem"])
        chunk_tokens = len(chunk) / 3.5
        remaining_tokens = max_total_tokens - used_tokens
        if chunk_tokens > remaining_tokens:
            if not chunks:
                # 首个文档超出预算：截断到剩余配额，保证至少返回部分内容
                max_chars = int(remaining_tokens * 3.5)
                chunk = chunk[:max_chars] + "\n[...截断：文档超出 token 预算]"
                chunks.append(chunk)
            else:
                chunks.append(
                    "\n\n[⚠️ SYSTEM WARNING: Sub-topical documents truncated due to token limit budget.]"
                )
            break
        chunks.append(chunk)
        used_tokens += chunk_tokens

    return "\n\n=== SOURCE_DOCUMENT_BORDER ===\n".join(chunks)


# ─── CLI 入口 ──────────────────────────────────────────────────────────────


def _cli():
    import argparse
    import pathlib

    parser = argparse.ArgumentParser(description="LLM-Brain OS 上下文脱水管道")
    parser.add_argument("--mode", choices=["summary", "precise"], required=True)
    parser.add_argument("--files", nargs="*", default=[])
    parser.add_argument("--hits", nargs="*", default=[])
    parser.add_argument("--max-tokens", type=int, default=8000)
    args = parser.parse_args()

    recalled = []

    if args.mode == "summary":
        for f in args.files:
            p = pathlib.Path(f)
            if p.exists():
                recalled.append({
                    "content": p.read_text(encoding="utf-8"),
                    "stem": p.stem,
                    "score": 1.0,
                })

    elif args.mode == "precise":
        # --hits 格式：filepath:lineno1,lineno2
        for entry in args.hits:
            if ":" not in entry:
                continue
            filepath, linenos_str = entry.rsplit(":", 1)
            p = pathlib.Path(filepath)
            if not p.exists():
                continue
            hit_lines = [int(n) for n in linenos_str.split(",") if n.strip().isdigit()]
            recalled.append({
                "content": p.read_text(encoding="utf-8"),
                "stem": p.stem,
                "hit_lines": hit_lines,
            })

    print(assemble_final_context(recalled, max_total_tokens=args.max_tokens))


if __name__ == "__main__":
    _cli()
