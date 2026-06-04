# Context Dehydration Pipeline 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在四个 brain-* 命令的召回层与上下文拼装层之间插入脱水管道，默认开启，加 `--dry` 参数跳过，token 消耗预期降低 80%+。

**Architecture:** 新建 `scripts/context_dehydrator.py` 作为纯函数库 + CLI 入口；BM25 路径使用全文摘要模式（无行号），rg 路径使用精准裁剪模式（有行号）；四个命令文件在解析参数时提取 `--dry` 标志，默认启用脱水。rtk 不引入，压榨步骤用纯 Python 正则降级实现。

**Tech Stack:** Python 3, re, subprocess（仅做 rtk 尝试，失败 fallback）, pytest, 四个 `~/.claude/commands/brain/*.md` 命令文件

---

## 文件变更清单

| 操作 | 路径 | 职责 |
|------|------|------|
| 新增 | `scripts/context_dehydrator.py` | 脱水管道核心逻辑 + CLI 入口 |
| 新增 | `tests/test_context_dehydrator.py` | 脱水管道测试 |
| 修改 | `~/.claude/commands/brain/brain-query.md` | 参数解析加 `--dry`，读取步骤加脱水分支 |
| 修改 | `~/.claude/commands/brain/brain-query-rg.md` | 同上 |
| 修改 | `~/.claude/commands/brain/brain-search.md` | 同上 |
| 修改 | `~/.claude/commands/brain/brain-search-rg.md` | 同上 |

---

## Task 1: context_dehydrator.py — 标题解析与面包屑

**Files:**
- Create: `scripts/context_dehydrator.py`
- Create: `tests/test_context_dehydrator.py`

- [ ] **Step 1: 写失败测试 — 标题解析**

```python
# tests/test_context_dehydrator.py
import sys
sys.path.insert(0, "scripts")

from context_dehydrator import _build_hierarchy_map

def test_heading_parser_h1_h2_h3():
    """标准 H1/H2/H3 应被正确解析，不需要行尾 $ 字符"""
    lines = [
        "# LLM-Brain OS 完整架构",
        "普通正文。",
        "## 分层结构",
        "更多内容。",
        "### 三级标题",
        "细节。",
    ]
    hmap = _build_hierarchy_map(lines)
    assert hmap[0] == {1: "LLM-Brain OS 完整架构", 2: None, 3: None}
    assert hmap[1] == {1: "LLM-Brain OS 完整架构", 2: None, 3: None}
    assert hmap[2] == {1: "LLM-Brain OS 完整架构", 2: "分层结构", 3: None}
    assert hmap[4] == {1: "LLM-Brain OS 完整架构", 2: "分层结构", 3: "三级标题"}

def test_heading_parser_with_dash_suffix():
    """标题含 — 后缀时只取前半部分"""
    lines = ["## 核心机制 — 权重衰减算法"]
    hmap = _build_hierarchy_map(lines)
    assert hmap[0][2] == "核心机制"

def test_heading_parser_no_heading():
    """无标题文件，hierarchy 全为 None"""
    lines = ["纯文本内容。", "第二行。"]
    hmap = _build_hierarchy_map(lines)
    assert hmap[0] == {1: None, 2: None, 3: None}
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
cd /Users/za-stanlexu/Documents/member/member
python -m pytest tests/test_context_dehydrator.py::test_heading_parser_h1_h2_h3 -v
```

预期：`ImportError: No module named 'context_dehydrator'`

- [ ] **Step 3: 实现 `_build_hierarchy_map`**

创建 `scripts/context_dehydrator.py`：

```python
"""
scripts/context_dehydrator.py
LLM-Brain OS 上下文脱水管道
"""
import re

# ─── 内部工具函数 ───────────────────────────────────────────────────────────

_HEADING_RE = re.compile(r"^(#{1,3})\s+(.+?)(?:\s+[—\-].+)?$")
_LINK_RE = re.compile(r"\[\[(.*?)\]\]")
_FRONTMATTER_RE = re.compile(r"^---\s*\n.*?\n---\s*\n", re.DOTALL)


def _build_hierarchy_map(lines: list[str]) -> list[dict]:
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
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
python -m pytest tests/test_context_dehydrator.py -k "heading_parser" -v
```

预期：3 个测试全部 PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/context_dehydrator.py tests/test_context_dehydrator.py
git commit -m "feat: add _build_hierarchy_map with correct heading regex"
```

---

## Task 2: 双链占位符保护

**Files:**
- Modify: `scripts/context_dehydrator.py`
- Modify: `tests/test_context_dehydrator.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_context_dehydrator.py 追加

from context_dehydrator import _protect_links, _restore_links

def test_protect_links_replaces_wikilinks():
    text = "参见 [[sdk_architecture]] 和 [[brain-os-architecture]]。"
    protected, cache = _protect_links(text)
    assert "[[sdk_architecture]]" not in protected
    assert "[[brain-os-architecture]]" not in protected
    assert "__BRAIN_LINK_0__" in protected
    assert "__BRAIN_LINK_1__" in protected
    assert cache == ["sdk_architecture", "brain-os-architecture"]

def test_restore_links_recovers_wikilinks():
    text = "参见 __BRAIN_LINK_0__ 和 __BRAIN_LINK_1__。"
    cache = ["sdk_architecture", "brain-os-architecture"]
    restored = _restore_links(text, cache)
    assert "[[sdk_architecture]]" in restored
    assert "[[brain-os-architecture]]" in restored

def test_protect_restore_roundtrip():
    original = "引用 [[概念A]] 和 [[概念B]]，结束。"
    protected, cache = _protect_links(original)
    restored = _restore_links(protected, cache)
    assert restored == original
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
python -m pytest tests/test_context_dehydrator.py -k "links" -v
```

预期：`ImportError: cannot import name '_protect_links'`

- [ ] **Step 3: 实现 `_protect_links` 和 `_restore_links`**

在 `scripts/context_dehydrator.py` 追加：

```python
def _protect_links(text: str) -> tuple[str, list[str]]:
    """提取所有 [[stem]] 并替换为占位符，防止后续处理打碎双链。"""
    cache = _LINK_RE.findall(text)
    protected = text
    for idx, link_text in enumerate(cache):
        protected = protected.replace(f"[[{link_text}]]", f"__BRAIN_LINK_{idx}__", 1)
    return protected, cache


def _restore_links(text: str, cache: list[str]) -> str:
    """将占位符还原为原始 [[stem]] 双链。"""
    result = text
    for idx, link_text in enumerate(cache):
        result = result.replace(f"__BRAIN_LINK_{idx}__", f"[[{link_text}]]")
    return result
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
python -m pytest tests/test_context_dehydrator.py -k "links" -v
```

预期：3 个测试全部 PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/context_dehydrator.py tests/test_context_dehydrator.py
git commit -m "feat: add wikilink placeholder protect/restore"
```

---

## Task 3: 代码块边界检测

**Files:**
- Modify: `scripts/context_dehydrator.py`
- Modify: `tests/test_context_dehydrator.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_context_dehydrator.py 追加

from context_dehydrator import _find_code_block_ranges

def test_code_block_ranges_single():
    lines = [
        "普通行。",
        "```python",
        "def foo(): pass",
        "```",
        "结束。",
    ]
    ranges = _find_code_block_ranges(lines)
    assert ranges == [(1, 3)]

def test_code_block_ranges_multiple():
    lines = [
        "```bash",
        "echo hi",
        "```",
        "间隔。",
        "```python",
        "x = 1",
        "```",
    ]
    ranges = _find_code_block_ranges(lines)
    assert ranges == [(0, 2), (4, 6)]

def test_code_block_unclosed_treated_to_eof():
    """未闭合的代码块应延伸到文件末尾，不崩溃"""
    lines = ["```python", "def bar(): pass"]
    ranges = _find_code_block_ranges(lines)
    assert ranges == [(0, 1)]
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
python -m pytest tests/test_context_dehydrator.py -k "code_block" -v
```

预期：`ImportError: cannot import name '_find_code_block_ranges'`

- [ ] **Step 3: 实现 `_find_code_block_ranges`**

在 `scripts/context_dehydrator.py` 追加：

```python
def _find_code_block_ranges(lines: list[str]) -> list[tuple[int, int]]:
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
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
python -m pytest tests/test_context_dehydrator.py -k "code_block" -v
```

预期：3 个测试全部 PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/context_dehydrator.py tests/test_context_dehydrator.py
git commit -m "feat: add code block range detection with unclosed block handling"
```

---

## Task 4: 精准裁剪模式（precise mode，rg 路径）

**Files:**
- Modify: `scripts/context_dehydrator.py`
- Modify: `tests/test_context_dehydrator.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_context_dehydrator.py 追加

from context_dehydrator import dehydrate_context

SAMPLE_MD = """\
---
type: concept
project: member
aliases: [BrainOS]
---
# LLM-Brain OS 完整架构

## 分层结构

L1 基础设施层内容。

## 三条数据流

摄入流描述。
"""

def test_precise_mode_extracts_hit_section():
    """精准模式：命中行所在段落应被保留，其他段落省略"""
    # "摄入流描述。" 在第 14 行（1-based）
    lines = SAMPLE_MD.split("\n")
    hit_line = next(i+1 for i, l in enumerate(lines) if "摄入流描述" in l)
    result = dehydrate_context(SAMPLE_MD, [hit_line], "brain-os-architecture")
    assert "摄入流描述" in result
    assert "L1 基础设施层内容" not in result

def test_precise_mode_breadcrumb_injected():
    """精准模式：面包屑路径应注入到 chunk 顶部"""
    lines = SAMPLE_MD.split("\n")
    hit_line = next(i+1 for i, l in enumerate(lines) if "摄入流描述" in l)
    result = dehydrate_context(SAMPLE_MD, [hit_line], "brain-os-architecture")
    assert "Context Scope" in result
    assert "三条数据流" in result

def test_precise_mode_preserves_wikilinks():
    """双链在精准模式下应完整保留"""
    md = "---\ntype: concept\n---\n# 标题\n\n## 节\n\n参见 [[sdk_architecture]]。\n"
    result = dehydrate_context(md, [8], "test")
    assert "[[sdk_architecture]]" in result

def test_precise_mode_alias_hit_lineno0_falls_back_to_summary():
    """lineno=0（alias命中）应 fallback 到全文摘要模式，不返回空字符串"""
    result = dehydrate_context(SAMPLE_MD, [0], "brain-os-architecture")
    assert len(result) > 0
    assert "LLM-Brain OS 完整架构" in result  # 全文摘要模式保留 H1

def test_precise_mode_empty_input():
    result = dehydrate_context("", [1], "empty")
    assert result == ""
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
python -m pytest tests/test_context_dehydrator.py -k "precise_mode or alias_hit or empty_input" -v
```

预期：`ImportError: cannot import name 'dehydrate_context'`

- [ ] **Step 3: 实现 `dehydrate_context` 精准裁剪路径**

在 `scripts/context_dehydrator.py` 追加：

```python
def _python_clean(text: str) -> str:
    """纯 Python 去噪：去除 HTML 注释、行尾死空格、多余空行。"""
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    text = re.sub(r"[ \t]+$", "", text, flags=re.MULTILINE)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


def _summary_mode(raw_md: str, file_stem: str) -> str:
    """
    全文摘要模式（BM25路径 / alias命中 fallback）：
    提取 frontmatter 后的所有 H1/H2 标题 + 每段首句。
    """
    body = _FRONTMATTER_RE.sub("", raw_md, count=1)
    lines = body.split("\n")
    segments = []
    breadcrumb_prefix = f"[📍 Summary: {file_stem}]"
    segments.append(breadcrumb_prefix)
    last_was_heading = False
    for line in lines:
        stripped = line.strip()
        if re.match(r"^#{1,2}\s+", stripped):
            segments.append(line)
            last_was_heading = True
        elif stripped and last_was_heading:
            segments.append(line)
            last_was_heading = False
        elif not stripped:
            last_was_heading = False
    return _python_clean("\n".join(segments)).strip()


def dehydrate_context(raw_md: str, hit_lines: list[int], file_stem: str) -> str:
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
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
python -m pytest tests/test_context_dehydrator.py -v
```

预期：Task 1-4 全部测试 PASS（共约 16 个）

- [ ] **Step 5: Commit**

```bash
git add scripts/context_dehydrator.py tests/test_context_dehydrator.py
git commit -m "feat: implement dehydrate_context with precise and summary modes"
```

---

## Task 5: assemble_final_context + CLI 入口

**Files:**
- Modify: `scripts/context_dehydrator.py`
- Modify: `tests/test_context_dehydrator.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_context_dehydrator.py 追加

from context_dehydrator import assemble_final_context

def test_assemble_bm25_path():
    """BM25路径：recalled_results 无 hit_lines 字段，走全文摘要模式"""
    results = [
        {"content": SAMPLE_MD, "stem": "brain-os-architecture", "score": 0.9},
    ]
    output = assemble_final_context(results, max_total_tokens=8000)
    assert "LLM-Brain OS 完整架构" in output
    assert "Summary" in output

def test_assemble_rg_path():
    """rg路径：recalled_results 有 hit_lines 字段，走精准裁剪模式"""
    lines = SAMPLE_MD.split("\n")
    hit_line = next(i+1 for i, l in enumerate(lines) if "摄入流描述" in l)
    results = [
        {"content": SAMPLE_MD, "stem": "brain-os", "hit_lines": [hit_line]},
    ]
    output = assemble_final_context(results, max_total_tokens=8000)
    assert "摄入流描述" in output
    assert "Context Scope" in output

def test_assemble_token_budget_truncates():
    """超出 max_total_tokens 时应截断并添加警告"""
    big_md = "# 标题\n\n" + ("这是很长的内容行。\n" * 500)
    results = [
        {"content": big_md, "stem": "doc1", "score": 0.9},
        {"content": big_md, "stem": "doc2", "score": 0.8},
        {"content": big_md, "stem": "doc3", "score": 0.7},
    ]
    output = assemble_final_context(results, max_total_tokens=100)
    assert "SYSTEM WARNING" in output

def test_assemble_empty_results():
    output = assemble_final_context([], max_total_tokens=8000)
    assert output == ""
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
python -m pytest tests/test_context_dehydrator.py -k "assemble" -v
```

预期：`ImportError: cannot import name 'assemble_final_context'`

- [ ] **Step 3: 实现 `assemble_final_context` 和 CLI 入口**

在 `scripts/context_dehydrator.py` 末尾追加：

```python
def assemble_final_context(
    recalled_results: list[dict],
    max_total_tokens: int = 8000,
) -> str:
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
        if used_tokens + chunk_tokens > max_total_tokens:
            chunks.append(
                "\n\n[⚠️ SYSTEM WARNING: Sub-topical documents truncated due to token limit budget.]"
            )
            break
        chunks.append(chunk)
        used_tokens += chunk_tokens

    return "\n\n=== SOURCE_DOCUMENT_BORDER ===\n".join(chunks)


# ─── CLI 入口 ──────────────────────────────────────────────────────────────

def _cli():
    """
    用法（BM25路径，summary模式）：
      python3 context_dehydrator.py --mode summary --files file1.md file2.md --max-tokens 8000

    用法（rg路径，precise模式）：
      python3 context_dehydrator.py --mode precise --hits file1.md:3,7 file2.md:12 --max-tokens 8000

    stdout 输出脱水后内容，供命令文件捕获。
    """
    import argparse, pathlib

    parser = argparse.ArgumentParser()
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
```

- [ ] **Step 4: 运行所有测试，确认通过**

```bash
python -m pytest tests/test_context_dehydrator.py -v
```

预期：全部 PASS（约 20 个测试）

- [ ] **Step 5: 手动验证 CLI**

```bash
python3 scripts/context_dehydrator.py \
  --mode summary \
  --files wiki/project_exclusives/member/brain-os-architecture.md \
  --max-tokens 8000
```

预期：输出包含 `[📍 Summary: brain-os-architecture]` 和标题文本，长度明显短于原文。

- [ ] **Step 6: Commit**

```bash
git add scripts/context_dehydrator.py tests/test_context_dehydrator.py
git commit -m "feat: add assemble_final_context and CLI entry point"
```

---

## Task 6: 改造四个命令文件 — 参数解析层

**Files:**
- Modify: `~/.claude/commands/brain/brain-query.md`
- Modify: `~/.claude/commands/brain/brain-query-rg.md`
- Modify: `~/.claude/commands/brain/brain-search.md`
- Modify: `~/.claude/commands/brain/brain-search-rg.md`

**改动规则：** 在每个文件的 `## 参数说明` 和步骤 2 的解析段落中，新增 `--dry` 标志处理。四个文件改动内容完全相同，逐个操作。

- [ ] **Step 1: 修改 brain-query.md 参数说明**

在 `## 参数说明` 段落，将原有内容替换为：

```markdown
## 参数说明

- `$ARGUMENTS` 格式：`<查询词> [--scope project|global] [--dry]`
- `--scope project`（默认）：仅搜索当前项目私有记忆 + 公共记忆（global_concepts）
- `--scope global`：搜索全库所有项目私有记忆 + 公共记忆，跨项目检索
- `--dry`：关闭脱水管道，直接读取笔记原文（调试用）。缺省时默认启用脱水。
```

- [ ] **Step 2: 修改 brain-query.md 步骤 2（参数解析）**

将步骤 2 替换为：

```markdown
2. 解析 `$ARGUMENTS`：
   - 提取 `--scope` 值（project 或 global），缺省为 `project`
   - 提取 `--dry` 标志：存在则 `DEHYDRATE=false`，缺省 `DEHYDRATE=true`
   - 剩余部分作为实际查询词
```

- [ ] **Step 3: 修改 brain-query.md 步骤 8（读取召回内容）**

将原步骤 8 `读取命中笔记全文。未读完之前，不要回答。` 替换为：

```markdown
8. 读取召回内容：
   - 若 `DEHYDRATE=false`（`--dry` 模式）：
     直接读取命中笔记全文，不做处理。
   - 若 `DEHYDRATE=true`（默认）：
     ```bash
     python3 /Users/za-stanlexu/Documents/member/member/scripts/context_dehydrator.py \
       --mode summary \
       --files <命中文件绝对路径1> <命中文件绝对路径2> <命中文件绝对路径3> \
       --max-tokens 8000
     ```
     将脚本 stdout 作为上下文，不再读取原文全文。
   - 未获得内容前，不要回答。
```

- [ ] **Step 4: 在 brain-query.md 输出模板中追加脱水状态行**

在输出模板 `补充说明：` 行后追加：

```markdown
脱水状态：<已启用 | 已关闭（--dry 模式）>
```

- [ ] **Step 5: 对 brain-query-rg.md 做相同修改**

参数说明与 brain-query.md 完全一致（Step 1、2、4 同上）。

步骤 8 使用 precise 模式（因为 rg 有行号）。rg 输出格式为 `文件路径:行号:内容`，需先收集命中文件与行号再调用脱水：

```markdown
8. 读取召回内容：
   - 若 `DEHYDRATE=false`（`--dry` 模式）：
     直接读取命中笔记全文，不做处理。
   - 若 `DEHYDRATE=true`（默认）：
     将步骤 6 的 rg 命中结果整理为 `文件路径:行号` 格式，去重同一文件的多个命中行，然后：
     ```bash
     python3 /Users/za-stanlexu/Documents/member/member/scripts/context_dehydrator.py \
       --mode precise \
       --hits <文件路径1>:<行号1,行号2> <文件路径2>:<行号3> \
       --max-tokens 8000
     ```
     将脚本 stdout 作为上下文，不再读取原文全文。
   - 未获得内容前，不要回答。
```

- [ ] **Step 6: 对 brain-search.md 做相同修改**

参数说明、步骤 2 同上。

brain-search 的召回步骤为步骤 6（BM25），对应 summary 模式。步骤 8 改为合并检索结果时对本地 Wiki 部分使用脱水输出，MemPalace 部分不变。将原步骤 8 的本地 Wiki 读取改为：

```markdown
8. 合并检索结果并输出审计报告：
   - 本地 Wiki 命中部分（BM25结果）：
     - 若 `DEHYDRATE=false`：读取命中笔记全文
     - 若 `DEHYDRATE=true`（默认）：
       ```bash
       python3 /Users/za-stanlexu/Documents/member/member/scripts/context_dehydrator.py \
         --mode summary \
         --files <命中文件路径...> \
         --max-tokens 4000
       ```
   - MemPalace 历史记忆部分：原样使用，不脱水
   - 输出"跨项目技术资产审计报告"（格式同原模板）
```

- [ ] **Step 7: 对 brain-search-rg.md 做相同修改**

参数说明、步骤 2 同上。步骤 8 rg 部分改为 precise 模式（与 brain-query-rg 相同写法），MemPalace 部分不变。

- [ ] **Step 8: Commit**

```bash
git add ~/.claude/commands/brain/
git commit -m "feat: add --dry flag and dehydration branch to all four brain commands"
```

---

## Task 7: 集成验证

**Files:** 无新增，验证已有文件行为

- [ ] **Step 1: 运行全量测试套件**

```bash
cd /Users/za-stanlexu/Documents/member/member
python -m pytest tests/ -v
```

预期：所有测试 PASS，无回归

- [ ] **Step 2: 手动验证 brain-query-rg 精准模式**

在 Claude Code 中执行：

```
/brain-query-rg BM25 检索
```

预期：脱水状态显示"已启用"，上下文包含面包屑 `[📍 Context Scope: ...]`，长度明显短于原文。

- [ ] **Step 3: 手动验证 --dry 跳过脱水**

```
/brain-query-rg BM25 检索 --dry
```

预期：脱水状态显示"已关闭（--dry 模式）"，输出原始笔记全文。

- [ ] **Step 4: 手动验证 alias 命中 fallback**

在任意含 `aliases: [BrainOS]` 的笔记上执行：

```
/brain-query-rg BrainOS
```

预期：不返回空内容，走全文摘要模式，输出包含 `[📍 Summary: ...]`。

- [ ] **Step 5: Final commit**

```bash
git add .
git commit -m "feat: context dehydration pipeline complete — Task 7 integration verified"
```

---

## 自查清单

**Spec coverage：**
- [x] 脱水管道覆盖四个命令 → Task 6
- [x] `--dry` 开关 → Task 6 Step 1/2
- [x] 标题解析 bug 修复 → Task 1
- [x] `lineno=0` alias 命中 fallback → Task 4 Step 1 test + Task 4 Step 3
- [x] rtk 不引入，Python 降级实现 → Task 4 Step 3 `_python_clean`
- [x] BM25 路径 summary 模式 → Task 5
- [x] rg 路径 precise 模式 → Task 4
- [x] token 预算分配 → Task 5
- [x] CLI 入口支持命令文件调用 → Task 5

**Placeholder scan：** 无 TBD/TODO，所有代码已写出完整实现。

**Type consistency：**
- `dehydrate_context(raw_md: str, hit_lines: list[int], file_stem: str) -> str` — Task 4 定义，Task 5 `assemble_final_context` 调用一致
- `assemble_final_context(recalled_results: list[dict], max_total_tokens: int) -> str` — Task 5 定义，CLI 调用一致
- `_build_hierarchy_map(lines: list[str]) -> list[dict]` — Task 1 定义，Task 4 调用一致
