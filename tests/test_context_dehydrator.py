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


# ─── Task 2: 双链占位符保护 ────────────────────────────────────────────────

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


# ─── Task 3: 代码块边界检测 ────────────────────────────────────────────────

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


# ─── Task 4: 精准裁剪模式 ──────────────────────────────────────────────────

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
    lines = SAMPLE_MD.split("\n")
    hit_line = next(i + 1 for i, l in enumerate(lines) if "摄入流描述" in l)
    result = dehydrate_context(SAMPLE_MD, [hit_line], "brain-os-architecture")
    assert "摄入流描述" in result
    assert "L1 基础设施层内容" not in result


def test_precise_mode_breadcrumb_injected():
    """精准模式：面包屑路径应注入到 chunk 顶部"""
    lines = SAMPLE_MD.split("\n")
    hit_line = next(i + 1 for i, l in enumerate(lines) if "摄入流描述" in l)
    result = dehydrate_context(SAMPLE_MD, [hit_line], "brain-os-architecture")
    assert "Context Scope" in result
    assert "三条数据流" in result


def test_precise_mode_preserves_wikilinks():
    """双链在精准模式下应完整保留"""
    md = "---\ntype: concept\n---\n# 标题\n\n## 节\n\n参见 [[sdk_architecture]]。\n"
    result = dehydrate_context(md, [8], "test")
    assert "[[sdk_architecture]]" in result


def test_precise_mode_alias_hit_lineno0_falls_back_to_summary():
    """lineno=0（alias命中）应 fallback 到全文正文模式，不返回空字符串，内容完整"""
    result = dehydrate_context(SAMPLE_MD, [0], "brain-os-architecture")
    assert len(result) > 0
    assert "LLM-Brain OS 完整架构" in result
    # 全文正文模式：摘要内容不应只有标题，应包含正文
    assert "摄入流描述" in result


def test_precise_mode_empty_input():
    result = dehydrate_context("", [1], "empty")
    assert result == ""


# ─── Task 5: assemble_final_context ───────────────────────────────────────

from context_dehydrator import assemble_final_context


def test_assemble_bm25_path():
    """BM25路径：recalled_results 无 hit_lines 字段，走全文正文模式"""
    results = [
        {"content": SAMPLE_MD, "stem": "brain-os-architecture", "score": 0.9},
    ]
    output = assemble_final_context(results, max_total_tokens=8000)
    assert "LLM-Brain OS 完整架构" in output
    assert "Source" in output


def test_assemble_rg_path():
    """rg路径：recalled_results 有 hit_lines 字段，走精准裁剪模式"""
    lines = SAMPLE_MD.split("\n")
    hit_line = next(i + 1 for i, l in enumerate(lines) if "摄入流描述" in l)
    results = [
        {"content": SAMPLE_MD, "stem": "brain-os", "hit_lines": [hit_line]},
    ]
    output = assemble_final_context(results, max_total_tokens=8000)
    assert "摄入流描述" in output
    assert "Context Scope" in output


def test_assemble_token_budget_truncates():
    """第二个文档超出预算时应追加 SYSTEM WARNING 并停止。
    预算设为足够容纳第一个小文档、但不够容纳第二个大文档，触发警告路径。"""
    small_md = "# 标题\n\n内容\n"
    big_md = "# 标题\n\n" + ("这是很长的内容行。\n" * 500)
    results = [
        {"content": small_md, "stem": "doc1", "score": 0.9},
        {"content": big_md, "stem": "doc2", "score": 0.8},
    ]
    output = assemble_final_context(results, max_total_tokens=50)
    assert "SYSTEM WARNING" in output


def test_assemble_empty_results():
    output = assemble_final_context([], max_total_tokens=8000)
    assert output == ""


def test_assemble_oversized_top_hit_is_truncated_not_dropped():
    """首个文档超出 token 预算时，应截断包含而非完全丢弃。"""
    from scripts.context_dehydrator import assemble_final_context
    # 构造一个约 700 字符（~200 token）的大文档
    big_content = "---\ntype: concept\n---\n# 大笔记\n\n" + "内容行\n" * 100
    results = [{"content": big_content, "stem": "big_note", "score": 1.0}]
    # 设置极小预算（50 token），强制触发截断路径
    output = assemble_final_context(results, max_total_tokens=50)
    assert output, "超出预算的首个文档不应返回空字符串"
    assert "big_note" in output or "大笔记" in output or "截断" in output, \
        "输出应包含截断内容而非仅有警告"
    assert "[...截断" in output, "应有截断标记"


def test_assemble_second_oversized_doc_appends_warning():
    """第二个文档超出预算时，追加警告后停止，不影响第一个文档的完整输出。"""
    from scripts.context_dehydrator import assemble_final_context
    small_content = "---\ntype: concept\n---\n# 小笔记\n\n内容\n"
    big_content = "---\ntype: concept\n---\n# 大笔记\n\n" + "内容行\n" * 200
    results = [
        {"content": small_content, "stem": "small_note", "score": 1.0},
        {"content": big_content, "stem": "big_note", "score": 0.5},
    ]
    output = assemble_final_context(results, max_total_tokens=100)
    assert "small_note" in output or "小笔记" in output, "第一个文档应完整输出"
    assert "SYSTEM WARNING" in output, "应有截断警告"
