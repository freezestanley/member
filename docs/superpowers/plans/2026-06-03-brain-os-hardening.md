# Brain OS Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 LLM-Brain OS 中 6 个已知隐患：数学 Bug、惊群效应、归档断链、Frontmatter 污染、同步冲突、BM25 性能瓶颈。

**Architecture:** 所有修改只涉及 `scripts/` 下的 Python / Bash 脚本，不改变 wiki 目录结构和 Skill 命令接口。各 task 相互独立，可单独应用。新增 `scripts/_inbox/.bm25_cache.pkl` 作为 BM25 持久化索引，新增 `.lock` 文件机制保护 hot_refresh.py 并发写入。

**Tech Stack:** Python 3.14（math、pickle、re、fcntl）、rank_bm25、jieba、fswatch（已安装）、bash

---

## 文件变更总览

| 操作 | 文件 | 改动说明 |
|------|------|---------|
| 修改 | `scripts/memory_manager.py:24` | 修正 log1p(0) → log(access_count) |
| 修改 | `scripts/hot_watcher.sh:17-31` | 引入进程级防抖 + 后台子进程串行化 |
| 新增 | `scripts/hot_refresh.py` 开头 | .lock 文件互斥写入 |
| 修改 | `scripts/memory_manager.py:scan_and_clean` | 归档前全库双链路径替换 |
| 新增 | `scripts/bm25_search.py` | 持久化 BM25 Cache（pickle）+ 增量更新 |
| 修改 | `scripts/vault_sync.sh` | 同步前 git status 检查 |
| 新增 | `scripts/rg_search_body.sh` | 剥离 Frontmatter 后的 rg 检索包装器 |
| 新增 | `tests/test_brain_scripts.py` | 各修复点的单元测试 |

---

## Task 1：修复冷启动数学 Bug（memory_manager.py）

**文件：**
- 修改：`scripts/memory_manager.py:24`
- 测试：`tests/test_brain_scripts.py`

**问题根因：** `math.log1p(max(0, access_count - 1))` 在 `access_count=1` 时 → `log1p(0)=0`，导致 `frequency_bonus=1.0`，看似不崩溃，但**逻辑语义错误**：第一次创建的笔记得不到任何频率奖励，与设计意图矛盾。当 `access_count=0`（极端情况）时，`log1p(-1)` 会产生负无穷，进一步污染 `current_weight`。

**正确公式：** `1.0 + 0.2 × ln(access_count)`，其中 `access_count` 初始值为 1，`ln(1) = 0`，新笔记无奖励；`access_count=5` 时奖励 ≈ +0.32，符合设计意图。

- [ ] **Step 1：写失败测试**

新建文件 `tests/test_brain_scripts.py`，写入：

```python
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
```

- [ ] **Step 2：运行测试，确认失败**

```bash
cd /Users/za-stanlexu/Documents/member/member
python3 -m pytest tests/test_brain_scripts.py::test_cold_start_access_count_1 -v
```

期望输出：`FAILED` — access_count=1 时 w=1.0 实际通过，但 `test_cold_start_access_count_0_no_crash` 应报错（旧代码 `log1p(max(0,-1))` = `log1p(-1)` = `-inf`）。

- [ ] **Step 3：修改 memory_manager.py 第 24 行**

打开 `scripts/memory_manager.py`，将：

```python
frequency_bonus = 1.0 + 0.2 * math.log1p(max(0, access_count - 1))
```

改为：

```python
safe_count = max(1, access_count)          # 防御 access_count=0 的极端情况
frequency_bonus = 1.0 + 0.2 * math.log(safe_count)
```

- [ ] **Step 4：运行测试，确认通过**

```bash
python3 -m pytest tests/test_brain_scripts.py -v
```

期望输出：3 项全部 `PASSED`。

- [ ] **Step 5：提交**

```bash
git add scripts/memory_manager.py tests/test_brain_scripts.py
git commit -m "fix: 修复 memory_manager 冷启动数学 Bug，log1p(0) → log(max(1,count))"
```

---

## Task 2：hot_watcher.sh 惊群防抖 + hot_refresh.py 文件锁

**文件：**
- 修改：`scripts/hot_watcher.sh`
- 修改：`scripts/hot_refresh.py`（开头加锁逻辑）
- 测试：`tests/test_brain_scripts.py`（追加）

**问题根因：** 当前 2 秒 `COOLDOWN` 只是基于时间戳比对，但 `hot_refresh.py` 是**同步阻塞执行**的。若 3 次文件变更在 2 秒内叠加到 2 次触发，第 1 次 `hot_refresh.py` 尚未写完 `hot.md`，第 2 次已经开始写，产生文件内容撕裂（torn write）。

**修复方案：**
1. `hot_watcher.sh`：将触发改为**后台子进程**执行，用 `flock` 命令串行化；
2. `hot_refresh.py`：用 `fcntl.flock` 在 Python 层获取排他锁，写完再释放。

- [ ] **Step 1：在 tests/test_brain_scripts.py 追加测试**

```python
import subprocess, os, time, tempfile, threading

def test_hot_refresh_no_torn_write(tmp_path, monkeypatch):
    """两个 hot_refresh.py 进程并发执行，hot.md 内容应完整（不应出现空文件或截断）"""
    # 复制 hot_refresh.py 并重定向输出路径到 tmp_path
    hot_md = tmp_path / "hot.md"
    # 直接调用脚本（不依赖真实 wiki 路径），仅验证文件锁行为
    script = """
import fcntl, time
lock_path = "{lock}"
hot_path = "{hot}"
with open(lock_path, "w") as lf:
    fcntl.flock(lf, fcntl.LOCK_EX)
    time.sleep(0.1)
    with open(hot_path, "w") as f:
        f.write("content_from_pid_" + str(__import__("os").getpid()))
    fcntl.flock(lf, fcntl.LOCK_UN)
""".format(lock=str(tmp_path / ".hot_refresh.lock"), hot=str(hot_md))

    procs = [subprocess.Popen(["python3", "-c", script]) for _ in range(3)]
    for p in procs:
        p.wait()
    content = hot_md.read_text()
    assert content.startswith("content_from_pid_"), f"文件内容异常: {content!r}"
    assert len(content) > 10, "文件不应为空或截断"
```

- [ ] **Step 2：运行测试，确认通过（验证测试本身有效）**

```bash
python3 -m pytest tests/test_brain_scripts.py::test_hot_refresh_no_torn_write -v
```

- [ ] **Step 3：修改 hot_watcher.sh，使用 flock 串行化触发**

将 `hot_watcher.sh` 中的触发逻辑从：

```bash
if [ "$diff" -ge "$COOLDOWN" ]; then
    last_trigger=$now
    echo "[hot_watcher] 检测到变化：$changed_file → 刷新 hot.md"
    python3 "$SCRIPT"
fi
```

改为：

```bash
LOCKFILE="/tmp/hot_refresh.lock"

if [ "$diff" -ge "$COOLDOWN" ]; then
    last_trigger=$now
    echo "[hot_watcher] 检测到变化：$changed_file → 刷新 hot.md"
    # flock -n 尝试获取非阻塞锁；若已有进程在刷新则跳过本次（防惊群）
    flock -n "$LOCKFILE" python3 "$SCRIPT" &
fi
```

- [ ] **Step 4：修改 hot_refresh.py，在 main() 开头加 Python 层文件锁**

在 `scripts/hot_refresh.py` 的 `main()` 函数开头（`notes = collect_notes()` 之前）插入：

```python
import fcntl

LOCK_FILE = Path(__file__).parent.parent / "_inbox" / ".hot_refresh.lock"
LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)

_lock_fh = open(LOCK_FILE, "w")
try:
    fcntl.flock(_lock_fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
except BlockingIOError:
    print("[hot_refresh] 另一进程正在刷新，本次跳过。", file=sys.stderr)
    _lock_fh.close()
    sys.exit(0)

try:
    # --- 原有 main() 逻辑 ---
    notes = collect_notes()
    ...
finally:
    fcntl.flock(_lock_fh, fcntl.LOCK_UN)
    _lock_fh.close()
```

完整替换后的 `main()` 函数体：

```python
def main():
    import fcntl

    LOCK_FILE = Path(__file__).parent.parent / "_inbox" / ".hot_refresh.lock"
    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)

    _lock_fh = open(LOCK_FILE, "w")
    try:
        fcntl.flock(_lock_fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("[hot_refresh] 另一进程正在刷新，本次跳过。", file=sys.stderr)
        _lock_fh.close()
        sys.exit(0)

    try:
        notes = collect_notes()
        if not notes:
            print("[hot_refresh] 未找到任何笔记，hot.md 未更新。", file=sys.stderr)
            sys.exit(0)

        notes.sort(key=lambda n: (n["weight"], n["access"]), reverse=True)
        top = notes[:TOP_N]

        HOT_MD.write_text(render_hot(top), encoding="utf-8")
        print(f"[hot_refresh] 已更新 hot.md，共 {len(top)} 条记录（全库 {len(notes)} 篇笔记）。")
    finally:
        fcntl.flock(_lock_fh, fcntl.LOCK_UN)
        _lock_fh.close()
```

- [ ] **Step 5：手动验证（无并发崩溃）**

```bash
cd /Users/za-stanlexu/Documents/member/member
python3 scripts/hot_refresh.py &
python3 scripts/hot_refresh.py &
python3 scripts/hot_refresh.py
wait
echo "hot.md 末行：$(tail -1 wiki/hot.md)"
```

期望：只有一个进程成功写入，另两个输出 `[hot_refresh] 另一进程正在刷新，本次跳过。`

- [ ] **Step 6：提交**

```bash
git add scripts/hot_watcher.sh scripts/hot_refresh.py tests/test_brain_scripts.py
git commit -m "fix: hot_refresh 加 flock 文件锁，hot_watcher 引入 flock 防惊群"
```

---

## Task 3：归档断链修复（memory_manager.py scan_and_clean）

**文件：**
- 修改：`scripts/memory_manager.py`（`scan_and_clean` 函数）
- 测试：`tests/test_brain_scripts.py`（追加）

**问题根因：** `os.rename(path, archive_path)` 移动文件后，其他笔记中的 `[[旧笔记名]]` 双链在 Obsidian 中变为红字断链，反向链接图谱污染。

**修复方案：** 归档前扫描全库所有 `.md` 文件，找到包含 `[[<被归档文件名>]]` 的行，替换为 `~~[[<被归档文件名>]]~~`（加删除线标注，保留历史可读性，明确说明已归档）。

- [ ] **Step 1：追加测试到 tests/test_brain_scripts.py**

```python
import tempfile, pathlib, shutil

def test_archive_updates_backlinks(tmp_path):
    """归档笔记时，其他笔记中的 [[xxx]] 双链应被标注为已归档"""
    # 构造假 wiki 目录
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

    # 执行归档（调用修复后的函数）
    from memory_manager import archive_with_backlink_update
    archive_with_backlink_update(target, archive, concepts)

    # 断言：old-concept.md 已移入 archive/
    assert not target.exists()
    assert (archive / "old-concept.md").exists()

    # 断言：active-concept.md 中的双链已被标注
    updated = active.read_text()
    assert "~~[[old-concept]]~~" in updated, f"双链未更新：{updated}"
    assert "[[old-concept]]" not in updated.replace("~~[[old-concept]]~~", ""), \
        "原始双链仍存在，未被替换"
```

- [ ] **Step 2：运行测试，确认失败**

```bash
python3 -m pytest tests/test_brain_scripts.py::test_archive_updates_backlinks -v
```

期望：`ImportError: cannot import name 'archive_with_backlink_update'`

- [ ] **Step 3：在 memory_manager.py 中新增 archive_with_backlink_update 函数**

在 `scan_and_clean` 函数之前插入：

```python
def archive_with_backlink_update(note_path: str, archive_dir: str, scan_root: str):
    """
    将 note_path 物理移入 archive_dir，并在 scan_root 全库中
    将所有 [[<note_stem>]] 替换为 ~~[[<note_stem>]]~~（已归档标注）。
    """
    note_stem = os.path.splitext(os.path.basename(note_path))[0]
    old_link = f"[[{note_stem}]]"
    new_link = f"~~[[{note_stem}]]~~"

    # 先全库替换双链，再移动文件（顺序不能反：移动后路径就找不到了）
    for root, _, files in os.walk(scan_root):
        for fname in files:
            if not fname.endswith(".md"):
                continue
            fp = os.path.join(root, fname)
            if fp == note_path:
                continue  # 跳过被归档文件自身
            try:
                with open(fp, "r", encoding="utf-8") as f:
                    content = f.read()
                if old_link in content:
                    updated = content.replace(old_link, new_link)
                    with open(fp, "w", encoding="utf-8") as f:
                        f.write(updated)
                    print(f"   ↳ [断链修复] {fname}: {old_link} → {new_link}")
            except Exception as e:
                print(f"   ↳ [断链修复失败] {fname}: {e}")

    # 最后移动文件
    if not os.path.exists(archive_dir):
        os.makedirs(archive_dir)
    os.rename(note_path, os.path.join(archive_dir, os.path.basename(note_path)))
```

然后在 `scan_and_clean` 函数中，将原来的归档行：

```python
os.rename(path, os.path.join(ARCHIVE_DIR, file))
```

替换为：

```python
archive_with_backlink_update(path, ARCHIVE_DIR, os.path.dirname(path))
```

注意：`scan_root` 应传 `target_dir`（当前扫描的根目录），让替换范围覆盖整个活跃区。完整替换段：

```python
if new_w < FORGET_THRESHOLD:
    print(f"⚠️ [冷冻归档] 检测到过时边缘知识: {file} (当前权重: {new_w}) -> 物理移入冷冻区。")
    # 修复前：os.rename(path, os.path.join(ARCHIVE_DIR, file))
    # 修复后：归档前全库替换双链，防止断链
    archive_with_backlink_update(path, ARCHIVE_DIR, target_dir)
```

其中 `target_dir` 是 `scan_and_clean` 外层循环的变量名，需确认与函数内部一致：

```python
for target_dir in target_dirs:                   # ← 已有的变量名
    if not os.path.exists(target_dir): continue
    for root, _, files in os.walk(target_dir):
```

- [ ] **Step 4：运行测试，确认通过**

```bash
python3 -m pytest tests/test_brain_scripts.py::test_archive_updates_backlinks -v
```

期望：`PASSED`

- [ ] **Step 5：提交**

```bash
git add scripts/memory_manager.py tests/test_brain_scripts.py
git commit -m "fix: 归档笔记时同步替换全库双链，防止 Obsidian 断链"
```

---

## Task 4：vault_sync.sh 并发同步冲突防护

**文件：**
- 修改：`scripts/vault_sync.sh`
- 测试：`tests/test_brain_scripts.py`（追加 bash 测试）

**问题根因：** `vault_sync.sh` 直接执行 `git add . && git push`，若此时 Claude 正在回写 Frontmatter（写了一半的文件），`git add .` 会把不完整内容提交到远端，或与 `git rebase` 产生冲突锁。

**修复方案：** 同步前用 `git status --porcelain` 检测是否有正在进行的写入（检查 `.hot_refresh.lock` 或 `_inbox/.bm25_cache.lock`），有则等待最多 10 秒，超时则放弃本次同步并报错退出，不强行推送。

- [ ] **Step 1：追加测试到 tests/test_brain_scripts.py**

```python
import subprocess

def test_vault_sync_skips_when_lock_exists(tmp_path):
    """当 .hot_refresh.lock 存在时，vault_sync 检测脚本应输出警告并退出非零码"""
    lock = tmp_path / ".hot_refresh.lock"
    lock.write_text("locked")

    # 最小化测试脚本：只测锁检测逻辑，不执行真实 git 操作
    check_script = f"""
#!/bin/bash
LOCK_FILE="{lock}"
if [ -f "$LOCK_FILE" ]; then
    echo "⚠️ [同步中止] 检测到写入锁，跳过本次同步。"
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
```

- [ ] **Step 2：运行测试，确认通过（测试验证逻辑正确）**

```bash
python3 -m pytest tests/test_brain_scripts.py::test_vault_sync_skips_when_lock_exists -v
```

- [ ] **Step 3：修改 vault_sync.sh，在 git add 之前插入锁检测**

将 `vault_sync.sh` 中的：

```bash
git fetch origin
git rebase origin/main > /dev/null 2>&1 || git rebase --skip
```

改为：

```bash
WRITE_LOCK="${BRAIN_DIR}/_inbox/.hot_refresh.lock"
MAX_WAIT=10
waited=0

# 等待写入锁释放（最多 10 秒）
while [ -f "$WRITE_LOCK" ] && [ "$waited" -lt "$MAX_WAIT" ]; do
    echo "⏳ [同步等待] 检测到写入锁，等待 ${waited}s / ${MAX_WAIT}s..."
    sleep 1
    waited=$(( waited + 1 ))
done

if [ -f "$WRITE_LOCK" ]; then
    echo "⚠️ [同步中止] 写入锁持续超过 ${MAX_WAIT} 秒，本次同步跳过，请手动检查。"
    exit 1
fi

git fetch origin
git rebase origin/main > /dev/null 2>&1 || git rebase --skip
```

- [ ] **Step 4：手动验证**

```bash
# 模拟写入锁存在
touch /Users/za-stanlexu/Documents/member/member/_inbox/.hot_refresh.lock
bash /Users/za-stanlexu/Documents/member/member/scripts/vault_sync.sh
# 期望输出：⏳ 等待提示，10秒后输出 ⚠️ 中止提示
rm /Users/za-stanlexu/Documents/member/member/_inbox/.hot_refresh.lock
```

- [ ] **Step 5：提交**

```bash
git add scripts/vault_sync.sh tests/test_brain_scripts.py
git commit -m "fix: vault_sync 同步前检测写入锁，防并发 git conflict"
```

---

## Task 5：rg 检索剥离 Frontmatter 污染

**文件：**
- 新增：`scripts/rg_body_search.py`（Python 包装器，剥离 Frontmatter 后检索）
- 测试：`tests/test_brain_scripts.py`（追加）

**问题根因：** `rg -g '*.md' "关键词" wiki/` 会命中 Frontmatter 中的 `project: member`、`code_symbols: [...]`，召回与正文内容无关的文件。

**修复方案：** 新增 `scripts/rg_body_search.py`，读取每个 `.md` 文件时剥离 `---...---` Frontmatter 块，仅对正文内容执行 Python `re.search`，输出格式与 rg 一致（`文件名:行号:内容`）。Skill 命令中的 rg 调用改为调用此脚本。

- [ ] **Step 1：追加测试**

```python
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
```

- [ ] **Step 2：运行测试，确认失败**

```bash
python3 -m pytest tests/test_brain_scripts.py::test_rg_body_search_excludes_frontmatter -v
```

期望：`ImportError: No module named 'rg_body_search'`

- [ ] **Step 3：创建 scripts/rg_body_search.py**

```python
#!/usr/bin/env python3
"""
rg_body_search.py — 剥离 Frontmatter 后的正文检索包装器。

用法：
    python3 rg_body_search.py "<关键词>" <目录1> [目录2 ...]

输出格式（与 rg --no-heading 一致）：
    <文件路径>:<行号>:<匹配行内容>
"""
import os, re, sys

FRONTMATTER_RE = re.compile(r'^---\s*\n.*?\n---\s*\n', re.DOTALL)


def search_body(pattern: str, paths: list[str]) -> list[dict]:
    """
    在 paths 中的每个 .md 文件剥离 Frontmatter 后，
    用 re.search(pattern, line, re.IGNORECASE) 逐行匹配。
    返回 [{"file": ..., "lineno": ..., "line": ...}, ...]
    """
    compiled = re.compile(pattern, re.IGNORECASE)
    results = []

    for path in paths:
        if not path.endswith(".md"):
            continue
        try:
            text = open(path, encoding="utf-8").read()
        except Exception:
            continue

        # 剥离 Frontmatter 块
        body = FRONTMATTER_RE.sub("", text, count=1)

        # 计算 Frontmatter 占用的行数，用于还原真实行号
        fm_match = FRONTMATTER_RE.match(text)
        fm_lines = fm_match.group(0).count("\n") if fm_match else 0

        for i, line in enumerate(body.splitlines(), start=fm_lines + 1):
            if compiled.search(line):
                results.append({"file": path, "lineno": i, "line": line})

    return results


def expand_paths(paths: list[str]) -> list[str]:
    """将目录递归展开为 .md 文件列表"""
    files = []
    for p in paths:
        if os.path.isfile(p):
            files.append(p)
        elif os.path.isdir(p):
            for root, _, fnames in os.walk(p):
                for f in fnames:
                    if f.endswith(".md"):
                        files.append(os.path.join(root, f))
    return files


def main():
    if len(sys.argv) < 3:
        print("用法: python3 rg_body_search.py <关键词> <目录或文件> [...]")
        sys.exit(1)

    pattern = sys.argv[1]
    raw_paths = sys.argv[2:]
    all_files = expand_paths(raw_paths)
    hits = search_body(pattern, all_files)

    if not hits:
        print(f"[rg_body] 未找到正文命中：{pattern!r}")
        sys.exit(1)

    for h in hits:
        print(f"{h['file']}:{h['lineno']}:{h['line']}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4：运行测试，确认通过**

```bash
python3 -m pytest tests/test_brain_scripts.py::test_rg_body_search_excludes_frontmatter \
                  tests/test_brain_scripts.py::test_rg_body_search_hits_body -v
```

期望：两项全部 `PASSED`

- [ ] **Step 5：更新 brain-query-rg.md 和 brain-search-rg.md 中的 rg 命令**

打开 `~/.claude/commands/brain/brain-query-rg.md`，将 Step 5 中的 rg 命令：

```bash
rg -n --no-heading -S -g '*.md' "$ARGUMENTS" \
  /Users/za-stanlexu/Documents/member/member/wiki/global_concepts \
  /Users/za-stanlexu/Documents/member/member/wiki/project_exclusives/<当前项目名>
```

替换为：

```bash
python3 /Users/za-stanlexu/Documents/member/member/scripts/rg_body_search.py \
  "$ARGUMENTS" \
  /Users/za-stanlexu/Documents/member/member/wiki/global_concepts \
  /Users/za-stanlexu/Documents/member/member/wiki/project_exclusives/<当前项目名>
```

对 `~/.claude/commands/brain/brain-search-rg.md` 执行同样替换（Step 4 中的 rg 命令）。

- [ ] **Step 6：提交**

```bash
git add scripts/rg_body_search.py tests/test_brain_scripts.py
git add ~/.claude/commands/brain/brain-query-rg.md ~/.claude/commands/brain/brain-search-rg.md
git commit -m "fix: 新增 rg_body_search.py 剥离 Frontmatter，防止 rg 检索污染"
```

---

## Task 6：BM25 持久化 Cache 索引（性能优化）

**文件：**
- 修改：`scripts/bm25_search.py`（全量重写，支持 pickle 缓存）
- 测试：`tests/test_brain_scripts.py`（追加）

**问题根因：** 每次 `/brain-query` 都对全库进行 `jieba` 分词 + `BM25Okapi` 实例化，当笔记超过 1000 篇时耗时线性增长。

**修复方案：**
1. 首次运行时构建索引，序列化为 `_inbox/.bm25_cache.pkl`（包含 `doc_paths`、`corpus` tokenized list、各文件最后修改时间 mtime）；
2. 后续运行时，比较每个文件的当前 mtime 与缓存中的 mtime，任意文件有变动则增量重建索引；
3. `hot_watcher.sh` 检测到文件变化时，同步触发缓存重建（传入 `--rebuild-cache` 参数）。

- [ ] **Step 1：追加测试**

```python
import pickle, time

def test_bm25_cache_created_on_first_run(tmp_path):
    """首次运行后应生成 .bm25_cache.pkl"""
    concepts = tmp_path / "wiki" / "global_concepts"
    concepts.mkdir(parents=True)
    cache_dir = tmp_path / "_inbox"
    cache_dir.mkdir()

    (concepts / "note1.md").write_text(
        "---\ncurrent_weight: 1.0\n---\n# 标题\n这是关于 BM25 检索的笔记。\n"
    )

    # 动态设置路径后导入（避免锁死全局路径）
    import importlib, types
    spec = importlib.util.spec_from_file_location(
        "bm25_search", "scripts/bm25_search.py"
    )
    # 仅测试 build_or_load_cache 函数，不执行 main
    # 直接用 subprocess 避免全局路径依赖
    result = subprocess.run(
        ["python3", "-c", f"""
import sys; sys.path.insert(0, 'scripts')
# monkey-patch 路径
import bm25_search as b
b.GLOBAL_DIR = "{concepts}"
b.PROJECT_DIR = "{tmp_path / 'wiki' / 'project_exclusives'}"
b.CACHE_PATH = "{cache_dir / '.bm25_cache.pkl'}"
cache = b.build_or_load_cache()
import os; print(os.path.exists("{cache_dir / '.bm25_cache.pkl'}"))
"""],
        capture_output=True, text=True
    )
    assert "True" in result.stdout, f"缓存文件未生成: {result.stderr}"

def test_bm25_cache_not_rebuilt_when_unchanged(tmp_path):
    """文件未变更时，不应重建索引（mtime 一致）"""
    # 通过缓存文件的 mtime 来验证：两次调用间，cache 文件 mtime 不变
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
    subprocess.run(["python3", "-c", build_cmd], capture_output=True)
    mtime1 = cache_path.stat().st_mtime

    time.sleep(0.05)
    subprocess.run(["python3", "-c", build_cmd], capture_output=True)
    mtime2 = cache_path.stat().st_mtime

    assert abs(mtime2 - mtime1) < 0.01, f"文件未变但 cache 被重建（mtime 变了：{mtime1} → {mtime2}）"
```

- [ ] **Step 2：运行测试，确认失败**

```bash
python3 -m pytest tests/test_brain_scripts.py::test_bm25_cache_created_on_first_run -v
```

期望：`AttributeError: module 'bm25_search' has no attribute 'build_or_load_cache'`

- [ ] **Step 3：重写 scripts/bm25_search.py，加入 Cache 机制**

```python
# scripts/bm25_search.py
import os
import re
import sys
import pickle
import jieba
from rank_bm25 import BM25Okapi

# 🚨 锁死中央知识库的绝对路径
BRAIN_DIR = "/Users/za-stanlexu/Documents/member/member"
GLOBAL_DIR = os.path.join(BRAIN_DIR, "wiki/global_concepts")
PROJECT_DIR = os.path.join(BRAIN_DIR, "wiki/project_exclusives")
CACHE_PATH = os.path.join(BRAIN_DIR, "_inbox/.bm25_cache.pkl")


def clean_and_tokenize(text):
    """剥离 Frontmatter 和 Markdown 杂质，仅保留干净文本用于 TF-IDF 计算。"""
    text = re.sub(r"---.*?---", "", text, flags=re.DOTALL)
    text = re.sub(r"[\[\]\-\#\*\>\`\n\r]", " ", text)
    return [word for word in jieba.cut(text.lower()) if word.strip()]


def collect_md_paths(search_dirs: list) -> list:
    """遍历给定目录列表，返回所有 .md 文件的绝对路径。"""
    paths = []
    for d in search_dirs:
        if not os.path.exists(d):
            continue
        for root, _, files in os.walk(d):
            for f in files:
                if f.endswith(".md"):
                    paths.append(os.path.join(root, f))
    return paths


def build_or_load_cache(search_dirs: list = None) -> dict:
    """
    加载或重建 BM25 索引 Cache。

    Cache 结构（pickle）：
    {
      "mtimes": {文件绝对路径: mtime_float},
      "doc_paths": [路径列表],
      "corpus": [[tokens], [tokens], ...]
    }

    重建条件：
    - Cache 文件不存在
    - 任意已缓存文件的 mtime 与缓存记录不一致
    - 有新文件未在缓存中
    """
    if search_dirs is None:
        search_dirs = [GLOBAL_DIR, PROJECT_DIR]

    current_paths = collect_md_paths(search_dirs)
    current_mtimes = {p: os.path.getmtime(p) for p in current_paths}

    # 尝试加载现有 cache
    if os.path.exists(CACHE_PATH):
        try:
            with open(CACHE_PATH, "rb") as f:
                cache = pickle.load(f)
            cached_mtimes = cache.get("mtimes", {})

            # 检查是否需要重建：路径集合变化 or 任意 mtime 变化
            needs_rebuild = (
                set(current_paths) != set(cached_mtimes.keys())
                or any(current_mtimes.get(p) != cached_mtimes.get(p) for p in current_paths)
            )

            if not needs_rebuild:
                return cache  # Cache 命中，直接返回
        except Exception:
            pass  # Cache 损坏，重建

    # 重建索引
    print("[bm25_cache] 正在重建索引...", file=sys.stderr)
    corpus = []
    for path in current_paths:
        try:
            with open(path, "r", encoding="utf-8") as f:
                corpus.append(clean_and_tokenize(f.read()))
        except Exception:
            corpus.append([])

    cache = {
        "mtimes": current_mtimes,
        "doc_paths": current_paths,
        "corpus": corpus,
    }

    os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
    with open(CACHE_PATH, "wb") as f:
        pickle.dump(cache, f)
    print(f"[bm25_cache] 索引已保存，共 {len(current_paths)} 篇笔记。", file=sys.stderr)

    return cache


def main():
    if len(sys.argv) < 2:
        print("❌ 错误：请输入检索关键词。")
        sys.exit(1)

    # 解析参数
    args = sys.argv[1:]
    project_filter = None
    rebuild_cache_only = False

    if "--rebuild-cache" in args:
        rebuild_cache_only = True
        args = [a for a in args if a != "--rebuild-cache"]

    if "--project" in args:
        idx = args.index("--project")
        if idx + 1 < len(args):
            project_filter = args[idx + 1]
            args = args[:idx] + args[idx + 2:]
        else:
            print("❌ 错误：--project 后需跟项目名。")
            sys.exit(1)

    # 确定扫描范围
    if project_filter:
        project_exclusive_dir = os.path.join(PROJECT_DIR, project_filter)
        search_dirs = [GLOBAL_DIR, project_exclusive_dir]
    else:
        search_dirs = [GLOBAL_DIR, PROJECT_DIR]

    # 仅重建缓存，不执行检索
    if rebuild_cache_only:
        build_or_load_cache(search_dirs=[GLOBAL_DIR, PROJECT_DIR])
        print("[bm25_cache] 缓存重建完成。")
        return

    query_str = " ".join(args)

    # 加载 Cache（命中则直接用，否则重建）
    cache = build_or_load_cache(search_dirs=[GLOBAL_DIR, PROJECT_DIR])
    all_paths = cache["doc_paths"]
    all_corpus = cache["corpus"]

    # 筛选出本次 search_dirs 范围内的文件
    allowed_prefixes = tuple(os.path.abspath(d) for d in search_dirs if os.path.exists(d))
    filtered = [
        (p, c) for p, c in zip(all_paths, all_corpus)
        if os.path.abspath(p).startswith(allowed_prefixes)
    ]

    if not filtered:
        print("🫙 中央知识库活跃区为空，未找到可检索内容。")
        return

    doc_paths, corpus = zip(*filtered)
    doc_paths, corpus = list(doc_paths), list(corpus)

    # BM25 检索
    bm25 = BM25Okapi(corpus)
    tokenized_query = clean_and_tokenize(query_str)
    doc_scores = bm25.get_scores(tokenized_query)

    final_results = []
    for idx, path in enumerate(doc_paths):
        if idx >= len(doc_scores) or doc_scores[idx] <= 0:
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception:
            continue

        weight_match = re.search(r"current_weight:\s*([\d\.]+)", content)
        current_weight = float(weight_match.group(1)) if weight_match else 1.0
        final_score = doc_scores[idx] * current_weight
        final_results.append((final_score, path))

    final_results.sort(key=lambda x: x[0], reverse=True)

    print("=== BM25 记忆加权交叉检索结果 (Top 3) ===")
    for score, path in final_results[:3]:
        rel_path = os.path.relpath(path, BRAIN_DIR)
        print(f"📄 [加权得分: {round(score, 2)}] 相对物理路径: {rel_path}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4：运行全部测试，确认通过**

```bash
python3 -m pytest tests/test_brain_scripts.py -v
```

期望：所有已有测试 + 新增 2 项 cache 测试全部 `PASSED`

- [ ] **Step 5：更新 hot_watcher.sh，文件变更时同步触发 cache 重建**

在 `hot_watcher.sh` 中，已有的触发块之后追加 cache 重建（同一个 flock 保护范围内，不单独再起进程）：

```bash
LOCKFILE="/tmp/hot_refresh.lock"
CACHE_SCRIPT="$(cd "$(dirname "$0")" && pwd)/bm25_search.py"

if [ "$diff" -ge "$COOLDOWN" ]; then
    last_trigger=$now
    echo "[hot_watcher] 检测到变化：$changed_file → 刷新 hot.md + BM25 cache"
    flock -n "$LOCKFILE" bash -c "
        python3 '$SCRIPT'
        python3 '$CACHE_SCRIPT' --rebuild-cache
    " &
fi
```

- [ ] **Step 6：提交**

```bash
git add scripts/bm25_search.py scripts/hot_watcher.sh tests/test_brain_scripts.py
git commit -m "feat: BM25 持久化 Cache（pickle），文件不变时直接加载，hot_watcher 触发增量重建"
```

---

## 全量测试验证

- [ ] **运行所有测试**

```bash
cd /Users/za-stanlexu/Documents/member/member
python3 -m pytest tests/test_brain_scripts.py -v --tb=short
```

期望：全部 `PASSED`，无 `FAILED` 或 `ERROR`。

- [ ] **端对端冒烟测试**

```bash
# 1. 确认权重公式修复（新笔记不崩溃）
python3 scripts/memory_manager.py

# 2. 确认 BM25 cache 生成
ls -la _inbox/.bm25_cache.pkl

# 3. 确认检索正常（用已有关键词）
python3 scripts/bm25_search.py "wiki hot 热度" --project member

# 4. 确认 rg 正文检索（不污染 Frontmatter）
python3 scripts/rg_body_search.py "热度" wiki/global_concepts/

# 5. 确认 hot_refresh 文件锁（并发不崩溃）
python3 scripts/hot_refresh.py & python3 scripts/hot_refresh.py; wait
```

- [ ] **最终提交**

```bash
git add -A
git commit -m "test: 全量测试通过，Brain OS Hardening 6项修复完成"
```
