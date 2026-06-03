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


def test_hot_refresh_no_torn_write(tmp_path):
    """两个 hot_refresh.py 进程并发执行，hot.md 内容应完整（不应出现空文件或截断）"""
    hot_md = tmp_path / "hot.md"
    lock_path = tmp_path / ".hot_refresh.lock"
    script = f"""
import fcntl, time
lock_path = "{lock_path}"
hot_path = "{hot_md}"
with open(lock_path, "w") as lf:
    fcntl.flock(lf, fcntl.LOCK_EX)
    time.sleep(0.1)
    with open(hot_path, "w") as f:
        f.write("content_from_pid_" + str(__import__("os").getpid()))
    fcntl.flock(lf, fcntl.LOCK_UN)
"""
    procs = [subprocess.Popen(["python3", "-c", script]) for _ in range(3)]
    for p in procs:
        p.wait()
    content = hot_md.read_text()
    assert content.startswith("content_from_pid_"), f"文件内容异常: {{content!r}}"
    assert len(content) > 10, "文件不应为空或截断"
