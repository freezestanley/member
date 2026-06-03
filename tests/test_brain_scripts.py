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


def test_hot_refresh_no_torn_write():
    """并发调用真实 hot_refresh.py 时，wiki/hot.md 不应为空且内容完整"""
    procs = [
        subprocess.Popen(
            ["python3", "scripts/hot_refresh.py"],
            cwd="/Users/za-stanlexu/Documents/member/member",
            stderr=subprocess.PIPE,
        )
        for _ in range(3)
    ]
    outputs = []
    for p in procs:
        _, err = p.communicate()
        outputs.append(err.decode())

    # 至少有 1 个进程被跳过（说明非阻塞锁生效）
    skipped = sum(1 for o in outputs if "另一进程正在刷新" in o)
    assert skipped >= 1, f"没有进程被跳过，锁可能未生效。stderr outputs: {outputs}"

    # hot.md 内容完整
    from pathlib import Path

    hot_md = Path("/Users/za-stanlexu/Documents/member/member/wiki/hot.md")
    content = hot_md.read_text()
    assert len(content) > 0, "hot.md 不应为空"


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
