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
