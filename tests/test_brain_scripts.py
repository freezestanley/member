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
