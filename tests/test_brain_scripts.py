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
