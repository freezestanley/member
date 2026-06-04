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
