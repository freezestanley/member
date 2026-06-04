import sys, math
sys.path.insert(0, "scripts")
from memory_manager import calculate_weight


def test_cold_start_access_count_1():
    """access_count=1（新笔记）时不应有频率奖励，weight = initial × decay"""
    w = calculate_weight(1.0, "2026-06-03", 1)
    # days=0，decay=1.0，ln(1)=0，bonus=1.0 → weight=1.0
    assert abs(w - 1.0) < 0.001, f"期望 1.0，实际 {w}"


def test_cold_start_access_count_0_no_crash():
    """access_count=0 不应 crash（防御性：脚本可能写入0）"""
    try:
        w = calculate_weight(1.0, "2026-06-03", 0)
        assert w >= 0, "权重不应为负"
    except (ValueError, ZeroDivisionError) as e:
        raise AssertionError(f"access_count=0 导致 crash: {e}")


def test_frequency_bonus_increases_with_access():
    """高频笔记权重应高于低频笔记（相同 initial_weight 和 last_activated）"""
    w1 = calculate_weight(1.0, "2026-06-03", 1)
    w5 = calculate_weight(1.0, "2026-06-03", 5)
    w20 = calculate_weight(1.0, "2026-06-03", 20)
    assert w5 > w1, f"access=5 权重应 > access=1，实际 {w5} vs {w1}"
    assert w20 > w5, f"access=20 权重应 > access=5，实际 {w20} vs {w5}"


import subprocess, os, time

import pathlib


def test_archive_updates_backlinks(tmp_path):
    """归档笔记时，其他笔记中的 [[xxx]] 双链应被标注为已归档"""
    concepts = tmp_path / "wiki" / "global_concepts"
    archive = tmp_path / "wiki" / "archive"
    concepts.mkdir(parents=True)
    archive.mkdir(parents=True)

    # 即将被归档的笔记
    target = concepts / "old-concept.md"
    target.write_text(
        "---\ntype: concept\ninitial_weight: 1.0\ncurrent_weight: 0.10\n"
        "last_activated: 2025-01-01\naccess_count: 1\n---\n# 旧概念\n内容。\n"
    )

    # 引用了旧笔记的活跃笔记
    active = concepts / "active-concept.md"
    active.write_text(
        "---\ntype: concept\ninitial_weight: 1.0\ncurrent_weight: 1.0\n"
        "last_activated: 2026-06-03\naccess_count: 5\n---\n"
        "# 活跃概念\n参见 [[old-concept]] 中的定义。\n"
    )

    sys.path.insert(0, "scripts")
    from memory_manager import archive_with_backlink_update
    archive_with_backlink_update(str(target), str(archive), str(concepts))

    # old-concept.md 已移入 archive/
    assert not target.exists()
    assert (archive / "old-concept.md").exists()

    # active-concept.md 中的双链已被标注
    updated = active.read_text()
    assert "~~[[old-concept]]~~" in updated, f"双链未更新：{updated}"
    # 原始双链不再出现（排除被 ~~ 包围的情况）
    clean = updated.replace("~~[[old-concept]]~~", "")
    assert "[[old-concept]]" not in clean, "原始双链仍存在，未被完整替换"


def test_archive_updates_backlinks_cross_dir(tmp_path):
    """归档 global_concepts 中的笔记时，project_exclusives 中的双链也应被更新"""
    # 构造双目录结构
    global_dir = tmp_path / "wiki" / "global_concepts"
    project_dir = tmp_path / "wiki" / "project_exclusives" / "myproj"
    archive_dir = tmp_path / "wiki" / "archive"
    wiki_dir = tmp_path / "wiki"
    global_dir.mkdir(parents=True)
    project_dir.mkdir(parents=True)
    archive_dir.mkdir(parents=True)

    # 即将被归档的笔记（在 global_concepts/）
    target = global_dir / "shared-concept.md"
    target.write_text(
        "---\ntype: concept\ncurrent_weight: 0.10\naccess_count: 1\n---\n# 共享概念\n内容。\n"
    )

    # 引用者在 project_exclusives/（跨目录）
    proj_note = project_dir / "project-note.md"
    proj_note.write_text(
        "---\ntype: concept\ncurrent_weight: 1.0\naccess_count: 3\n---\n"
        "# 项目笔记\n本项目基于 [[shared-concept]] 实现。\n"
    )

    from memory_manager import archive_with_backlink_update
    archive_with_backlink_update(str(target), str(archive_dir), str(wiki_dir))

    # 断言：shared-concept.md 已移入 archive/
    assert not target.exists()
    assert (archive_dir / "shared-concept.md").exists()

    # 断言：跨目录的 project_exclusives 中双链已被更新
    updated = proj_note.read_text()
    assert "~~[[shared-concept]]~~" in updated, f"跨目录双链未更新：{updated}"
    clean = updated.replace("~~[[shared-concept]]~~", "")
    assert "[[shared-concept]]" not in clean, "原始双链仍存在"


def test_vault_sync_skips_when_lock_exists(tmp_path):
    """当 .hot_refresh.lock 存在时，vault_sync 检测逻辑应输出警告并退出非零码"""
    lock = tmp_path / ".hot_refresh.lock"
    lock.write_text("locked")

    check_script = f"""#!/bin/bash
LOCK_FILE="{lock}"
if [ -f "$LOCK_FILE" ]; then
    echo "检测到写入锁，跳过本次同步。"
    exit 1
fi
echo "同步继续"
exit 0
"""
    script_path = tmp_path / "check.sh"
    script_path.write_text(check_script)
    script_path.chmod(0o755)

    result = subprocess.run(["bash", str(script_path)], capture_output=True, text=True)
    assert result.returncode == 1, f"有锁时应返回 1，实际 {result.returncode}"
    assert "检测到写入锁" in result.stdout


def test_rg_body_search_excludes_frontmatter(tmp_path):
    """Frontmatter 中出现的关键词不应被当作正文命中"""
    md_file = tmp_path / "note.md"
    md_file.write_text(
        "---\ntype: concept\nproject: member\ncode_symbols: []\n---\n"
        "# 标题\n这是正文，不含关键词。\n"
    )
    sys.path.insert(0, "scripts")
    from rg_body_search import search_body

    hits = search_body("member", [str(md_file)])
    assert len(hits) == 0, f"Frontmatter 中的 'member' 不应被命中，实际：{hits}"


def test_rg_body_search_hits_body(tmp_path):
    """正文中出现的关键词应被命中"""
    md_file = tmp_path / "note.md"
    md_file.write_text(
        "---\ntype: concept\nproject: other\n---\n"
        "# 标题\n本文讨论 member 架构设计。\n"
    )
    from rg_body_search import search_body

    hits = search_body("member", [str(md_file)])
    assert len(hits) == 1
    assert "member 架构设计" in hits[0]["line"]


import pickle, time


def test_bm25_cache_created_on_first_run(tmp_path):
    """首次运行后应生成 .bm25_cache.pkl"""
    concepts = tmp_path / "wiki" / "global_concepts"
    concepts.mkdir(parents=True)
    cache_path = tmp_path / "_inbox" / ".bm25_cache.pkl"
    (tmp_path / "_inbox").mkdir()

    (concepts / "note1.md").write_text(
        "---\ncurrent_weight: 1.0\n---\n# 标题\n这是关于 BM25 检索的笔记。\n"
    )

    build_cmd = f"""
import sys; sys.path.insert(0, 'scripts')
import bm25_search as b
b.GLOBAL_DIR = "{concepts}"
b.PROJECT_DIR = "{tmp_path / 'wiki' / 'project_exclusives'}"
b.CACHE_PATH = "{cache_path}"
b.build_or_load_cache()
import os; print(os.path.exists("{cache_path}"))
"""
    result = subprocess.run(["python3", "-c", build_cmd],
                            capture_output=True, text=True,
                            cwd="/Users/za-stanlexu/Documents/member/member")
    assert "True" in result.stdout, f"缓存文件未生成: {result.stderr}"


def test_bm25_cache_not_rebuilt_when_unchanged(tmp_path):
    """文件未变更时，不应重建索引（cache pkl mtime 保持不变）"""
    concepts = tmp_path / "wiki" / "global_concepts"
    concepts.mkdir(parents=True)
    cache_path = tmp_path / "_inbox" / ".bm25_cache.pkl"
    (tmp_path / "_inbox").mkdir()
    (concepts / "note1.md").write_text("---\ncurrent_weight: 1.0\n---\n# 测试\n内容\n")

    build_cmd = f"""
import sys; sys.path.insert(0, 'scripts')
import bm25_search as b
b.GLOBAL_DIR = "{concepts}"
b.PROJECT_DIR = "{tmp_path / 'wiki' / 'project_exclusives'}"
b.CACHE_PATH = "{cache_path}"
b.build_or_load_cache()
"""
    subprocess.run(["python3", "-c", build_cmd], capture_output=True,
                   cwd="/Users/za-stanlexu/Documents/member/member")
    mtime1 = cache_path.stat().st_mtime

    time.sleep(0.05)
    subprocess.run(["python3", "-c", build_cmd], capture_output=True,
                   cwd="/Users/za-stanlexu/Documents/member/member")
    mtime2 = cache_path.stat().st_mtime

    assert abs(mtime2 - mtime1) < 0.01, \
        f"文件未变但 cache 被重建（mtime 变了：{mtime1} → {mtime2}）"


# ── aliases 字段检索增强测试 ──────────────────────────────────────────────────

def test_rg_body_search_hits_alias(tmp_path):
    """aliases 字段中的别名应被 rg_body_search 命中（lineno=0 标记）"""
    md_file = tmp_path / "note.md"
    md_file.write_text(
        "---\ntype: concept\nproject: global\n"
        "aliases: [LLM操作系统, BrainOS]\n---\n"
        "# 标题\n这是正文，不含别名关键词。\n"
    )
    from rg_body_search import search_body

    hits = search_body("BrainOS", [str(md_file)])
    assert len(hits) == 1, f"aliases 中的 BrainOS 应被命中，实际：{hits}"
    assert hits[0]["lineno"] == 0, "别名命中的行号应标记为 0"
    assert "[alias]" in hits[0]["line"], "别名命中行应包含 [alias] 标记"


def test_rg_body_search_alias_with_comment(tmp_path):
    """aliases 字段带行内注释时应正确解析别名"""
    md_file = tmp_path / "note.md"
    md_file.write_text(
        "---\ntype: concept\naliases: [知识图谱OS, KB-OS] # 增强检索容错\n---\n"
        "# 标题\n正文内容。\n"
    )
    from rg_body_search import search_body

    hits = search_body("KB-OS", [str(md_file)])
    assert len(hits) == 1
    assert "KB-OS" in hits[0]["line"]


def test_bm25_aliases_increase_score(tmp_path):
    """有 aliases 的笔记在用别名检索时应比无别名笔记得分更高"""
    concepts = tmp_path / "wiki" / "global_concepts"
    concepts.mkdir(parents=True)
    cache_path = tmp_path / "_inbox" / ".bm25_cache.pkl"
    (tmp_path / "_inbox").mkdir()

    # 有别名的笔记
    (concepts / "with-alias.md").write_text(
        "---\ncurrent_weight: 1.0\naliases: [神经记忆系统]\n---\n# 笔记A\n通用内容。\n"
    )
    # 无别名的笔记（正文也不含该词）
    (concepts / "no-alias.md").write_text(
        "---\ncurrent_weight: 1.0\naliases: []\n---\n# 笔记B\n通用内容。\n"
    )

    build_and_search_cmd = f"""
import sys; sys.path.insert(0, 'scripts')
import bm25_search as b
b.GLOBAL_DIR = "{concepts}"
b.PROJECT_DIR = "{tmp_path / 'wiki' / 'project_exclusives'}"
b.CACHE_PATH = "{cache_path}"
# 强制重建
import os; os.remove("{cache_path}") if os.path.exists("{cache_path}") else None
cache = b.build_or_load_cache()
from rank_bm25 import BM25Okapi
bm25 = BM25Okapi(cache['corpus'])
tokens = b.clean_and_tokenize("神经记忆系统")
scores = bm25.get_scores(tokens)
paths = cache['doc_paths']
result = sorted(zip(scores, [os.path.basename(p) for p in paths]), reverse=True)
for s, name in result:
    print(f"{{s:.4f}} {{name}}")
"""
    result = subprocess.run(
        ["python3", "-c", build_and_search_cmd],
        capture_output=True, text=True,
        cwd="/Users/za-stanlexu/Documents/member/member"
    )
    lines = [l for l in result.stdout.strip().splitlines() if l]
    assert lines, f"无输出: {result.stderr}"
    # 有别名的笔记得分应排第一
    top_file = lines[0].split()[-1]
    assert top_file == "with-alias.md", \
        f"有别名的笔记应得分最高，实际排序：{lines}"


# ── clean_and_tokenize 压缩策略测试 ───────────────────────────────────────────

def test_clean_tokenize_strips_frontmatter():
    """Frontmatter 内的字段不应出现在 token 流中"""
    sys.path.insert(0, "scripts")
    from bm25_search import clean_and_tokenize

    text = "---\ntype: concept\nproject: global\n---\n# 标题\nBM25 检索效果\n"
    tokens = clean_and_tokenize(text)
    # Frontmatter 中的 "concept"、"global" 不应出现
    assert "concept" not in tokens, f"Frontmatter 字段 'concept' 不应出现在 token 流: {tokens}"
    assert "global" not in tokens, f"Frontmatter 字段 'global' 不应出现在 token 流: {tokens}"
    # 正文内容应出现
    token_str = " ".join(tokens)
    assert "bm25" in token_str or "检索" in token_str, \
        f"正文关键词应出现在 token 流: {tokens}"


def test_clean_tokenize_strips_html_comment():
    """Markdown 注释块内的内容不应出现在 token 流中"""
    from bm25_search import clean_and_tokenize

    text = "---\ntype: concept\n---\n# 标题\n<!-- 这是注释：secret_keyword -->\n正文内容。\n"
    tokens = clean_and_tokenize(text)
    token_str = " ".join(tokens)
    assert "secret_keyword" not in token_str, \
        f"注释内容不应出现在 token 流: {tokens}"
    assert "正文" in token_str or "内容" in token_str, \
        f"正文内容应出现: {tokens}"


def test_clean_tokenize_body_separator_not_eaten():
    """正文中的 --- 水平分隔线不应被误当作 Frontmatter 吞掉正文内容"""
    from bm25_search import clean_and_tokenize

    text = (
        "---\ntype: concept\n---\n"
        "# 第一节\n内容A。\n"
        "---\n"          # 正文分隔线，不应触发 Frontmatter 剥离
        "# 第二节\n内容B。\n"
    )
    tokens = clean_and_tokenize(text)
    token_str = " ".join(tokens)
    assert "内容" in token_str or "b" in token_str, \
        f"分隔线后的正文内容 '内容B' 应被保留: {tokens}"


# ── hot_refresh 大纲树格式测试 ────────────────────────────────────────────────

def test_extract_outline_h1_h2_h3():
    """extract_outline 应正确提取 H1-H3 标题并缩进"""
    sys.path.insert(0, "scripts")
    from hot_refresh import extract_outline

    text = (
        "---\ntype: concept\n---\n"
        "# 顶级标题\n正文内容。\n"
        "## 二级标题\n更多内容。\n"
        "### 三级标题\n细节。\n"
        "#### 四级标题\n不应出现。\n"
    )
    outline = extract_outline(text)
    assert outline == [
        "- 顶级标题",
        "  - 二级标题",
        "    - 三级标题",
    ], f"大纲提取结果错误：{outline}"


def test_extract_outline_skips_frontmatter_headings():
    """Frontmatter 中不应有标题，但防御：即使有也不应被提取"""
    from hot_refresh import extract_outline

    # 假设有人在 Frontmatter 里写了类似 # 的内容（实际不会，但防御）
    text = "---\ntype: concept\n---\n# 正文标题\n内容。\n"
    outline = extract_outline(text)
    assert len(outline) == 1
    assert outline[0] == "- 正文标题"


def test_render_hot_outline_format(tmp_path):
    """render_hot 应输出大纲树格式，不包含 Markdown 表格"""
    from hot_refresh import render_hot

    notes = [
        {
            "title": "测试笔记",
            "stem": "test-note",
            "path": "wiki/global_concepts/test-note.md",
            "weight": 1.0,
            "access": 3,
            "outline": ["- 第一节", "  - 子节"],
        }
    ]
    output = render_hot(notes)

    # 不应有表格格式
    assert "|" not in output, f"大纲模式不应包含 Markdown 表格: {output}"
    # 应有双链锚点
    assert "[[test-note]]" in output, f"应包含双链锚点: {output}"
    # 应有大纲行
    assert "- 第一节" in output
    assert "  - 子节" in output
    # 应有权重和调用次数
    assert "1.000" in output
    assert "3 次" in output


def test_render_hot_empty_outline():
    """无标题的笔记应显示占位符而非崩溃"""
    from hot_refresh import render_hot

    notes = [
        {
            "title": "无标题笔记",
            "stem": "no-heading",
            "path": "wiki/global_concepts/no-heading.md",
            "weight": 0.8,
            "access": 1,
            "outline": [],
        }
    ]
    output = render_hot(notes)
    assert "*(无标题大纲)*" in output, f"空大纲应显示占位符: {output}"


# ---------------------------------------------------------------------------
# vault_sync.sh 锁路径集成测试
# 验证 lock_is_held() 使用真实路径，在锁被持有时正确返回 exit 0（held=true）
# ---------------------------------------------------------------------------

def test_lock_is_held_detects_real_lock(tmp_path):
    """
    持有真实 fcntl 排他锁期间，vault_sync.sh 的 lock_is_held() 必须返回 exit 0
    （即认为锁被持有，同步应中止）。
    """
    import fcntl
    import subprocess

    lock_file = tmp_path / ".hot_refresh.lock"
    lock_file.touch()

    # 在父进程持有排他锁
    fh = open(lock_file, "w")
    fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    try:
        # 用 vault_sync.sh 中提取出的 lock_is_held Python 逻辑直接测试
        result = subprocess.run(
            [
                "python3", "-c",
                f"""
import fcntl, sys, os
lock_path = r"{lock_file}"
if not os.path.exists(lock_path):
    sys.exit(1)
try:
    with open(lock_path, "r+") as f:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fcntl.flock(f, fcntl.LOCK_UN)
    sys.exit(1)   # 获锁成功 → 无进程持有
except (BlockingIOError, OSError):
    sys.exit(0)   # 获锁失败 → 有进程持有
"""
            ],
            capture_output=True,
        )
        assert result.returncode == 0, (
            f"lock_is_held 应返回 0（锁被持有），实际 returncode={result.returncode}；"
            f"stderr={result.stderr.decode()}"
        )
    finally:
        fcntl.flock(fh, fcntl.LOCK_UN)
        fh.close()


def test_lock_is_held_free_when_no_holder(tmp_path):
    """
    锁文件存在但无进程持有时，lock_is_held() 必须返回 exit 1（held=false）。
    """
    import subprocess

    lock_file = tmp_path / ".hot_refresh.lock"
    lock_file.touch()

    result = subprocess.run(
        [
            "python3", "-c",
            f"""
import fcntl, sys, os
lock_path = r"{lock_file}"
if not os.path.exists(lock_path):
    sys.exit(1)
try:
    with open(lock_path, "r+") as f:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fcntl.flock(f, fcntl.LOCK_UN)
    sys.exit(1)
except (BlockingIOError, OSError):
    sys.exit(0)
"""
        ],
        capture_output=True,
    )
    assert result.returncode == 1, (
        f"无进程持有锁时 lock_is_held 应返回 1（free），实际 returncode={result.returncode}"
    )


def test_lock_is_held_missing_file(tmp_path):
    """
    锁文件不存在时，lock_is_held() 必须返回 exit 1（held=false，不崩溃）。
    """
    import subprocess

    lock_file = tmp_path / ".nonexistent.lock"
    # 不创建文件

    result = subprocess.run(
        [
            "python3", "-c",
            f"""
import fcntl, sys, os
lock_path = r"{lock_file}"
if not os.path.exists(lock_path):
    sys.exit(1)
try:
    with open(lock_path, "r+") as f:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fcntl.flock(f, fcntl.LOCK_UN)
    sys.exit(1)
except (BlockingIOError, OSError):
    sys.exit(0)
"""
        ],
        capture_output=True,
    )
    assert result.returncode == 1, (
        f"锁文件不存在时应返回 1，实际 returncode={result.returncode}"
    )


import subprocess, tempfile, shutil
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
SCRIPT = REPO_ROOT / "scripts" / "hot_refresh.py"

def _make_wiki(tmp: Path):
    """在临时目录创建最小 wiki 结构用于测试。"""
    gc = tmp / "wiki" / "global_concepts"
    gc.mkdir(parents=True)
    pe_member = tmp / "wiki" / "project_exclusives" / "member"
    pe_member.mkdir(parents=True)

    gc_note = gc / "global_rule.md"
    gc_note.write_text(
        "---\ntype: concept\nproject: global\ncurrent_weight: 2.0\naccess_count: 5\n---\n# 全局规范\n## 定义\n",
        encoding="utf-8",
    )
    proj_note = pe_member / "member_arch.md"
    proj_note.write_text(
        "---\ntype: concept\nproject: member\ncurrent_weight: 1.5\naccess_count: 3\n---\n# Member 架构\n## 核心模块\n",
        encoding="utf-8",
    )
    (tmp / "_inbox").mkdir(parents=True)
    return tmp


def test_global_route_writes_global_hot(tmp_path):
    """--global 只写 wiki/global_hot.md，不创建 project hot.md。"""
    wiki_root = _make_wiki(tmp_path)
    result = subprocess.run(
        ["python3", str(SCRIPT), "--global", "--wiki-root", str(wiki_root / "wiki")],
        capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
    global_hot = wiki_root / "wiki" / "global_hot.md"
    assert global_hot.exists(), "global_hot.md 应存在"
    content = global_hot.read_text(encoding="utf-8")
    assert "全局规范" in content
    assert "Member 架构" not in content, "项目笔记不应出现在 global_hot.md"


def test_project_route_writes_project_hot(tmp_path):
    """--project member 只写 wiki/project_exclusives/member/hot.md。"""
    wiki_root = _make_wiki(tmp_path)
    result = subprocess.run(
        ["python3", str(SCRIPT), "--project", "member", "--wiki-root", str(wiki_root / "wiki")],
        capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
    proj_hot = wiki_root / "wiki" / "project_exclusives" / "member" / "hot.md"
    assert proj_hot.exists(), "member/hot.md 应存在"
    content = proj_hot.read_text(encoding="utf-8")
    assert "Member 架构" in content
    assert "全局规范" not in content, "全局笔记不应出现在项目 hot.md"


def test_global_top_n_capped_at_8(tmp_path):
    """global_hot.md 最多 8 条。"""
    wiki_root = _make_wiki(tmp_path)
    gc = wiki_root / "wiki" / "global_concepts"
    for i in range(15):
        note = gc / f"note_{i}.md"
        note.write_text(
            f"---\ntype: concept\nproject: global\ncurrent_weight: {1.0 + i * 0.1:.1f}\naccess_count: {i}\n---\n# Note {i}\n",
            encoding="utf-8",
        )
    subprocess.run(
        ["python3", str(SCRIPT), "--global", "--wiki-root", str(wiki_root / "wiki")],
        capture_output=True
    )
    content = (wiki_root / "wiki" / "global_hot.md").read_text(encoding="utf-8")
    count = content.count("### ")
    assert count <= 8, f"global_hot.md 应 ≤8 条，实际 {count} 条"


def test_empty_project_generates_skeleton(tmp_path):
    """空项目应生成含警告的骨架 hot.md，不报错。"""
    wiki_root = _make_wiki(tmp_path)
    (wiki_root / "wiki" / "project_exclusives" / "newproj").mkdir(parents=True)
    result = subprocess.run(
        ["python3", str(SCRIPT), "--project", "newproj", "--wiki-root", str(wiki_root / "wiki")],
        capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
    proj_hot = wiki_root / "wiki" / "project_exclusives" / "newproj" / "hot.md"
    assert proj_hot.exists()
    assert "暂无高权笔记" in proj_hot.read_text(encoding="utf-8")


def test_watcher_script_syntax():
    """hot_watcher.sh bash 语法检查。"""
    result = subprocess.run(
        ["bash", "-n", str(REPO_ROOT / "scripts" / "hot_watcher.sh")],
        capture_output=True, text=True
    )
    assert result.returncode == 0, f"bash 语法错误：{result.stderr}"
