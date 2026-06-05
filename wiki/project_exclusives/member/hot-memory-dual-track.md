---
type: concept
created_at: 2026-06-05
last_modified: 2026-06-05
project: member
aliases: [热记忆, 热记忆刷新, hot_refresh, 双轨路由, hot_watcher]
code_symbols: [hot_refresh.py, hot_watcher.sh, collect_notes, render_hot, atomic_write, GLOBAL_TOP_N, PROJECT_TOP_M]
initial_weight: 1.0
current_weight: 1.0
last_activated: 2026-06-05
access_count: 1
status: active
superseded_by: ""
---

# 热记忆双轨路由

## 结论

热记忆系统通过 `hot_watcher.sh`（fswatch）监听 wiki/ 变化，按路径自动路由到 `hot_refresh.py --global` 或 `--project <name>`。两条轨道独立加锁，互不干扰。

## 双轨路由逻辑

```bash
# hot_watcher.sh 路由判断
if changed_file =~ wiki/global_concepts/:
    → python3 hot_refresh.py --global
      写入 wiki/global_hot.md (TOP 8)

elif changed_file =~ wiki/project_exclusives/<NAME>/:
    → python3 hot_refresh.py --project <NAME>
      写入 wiki/project_exclusives/<NAME>/hot.md (TOP 20)
```

## 排序规则

```python
notes.sort(key=lambda n: (n["weight"], n["access"]), reverse=True)
# 主键：current_weight，次键：access_count
```

## 原子写入保障

```python
def atomic_write(target, content, lock_file):
    # 独占锁：fcntl.flock(LOCK_EX | LOCK_NB)，轮询等待最多10秒
    # 写入：target.write_text(content)
    # 释放：fcntl.flock(LOCK_UN)
```

**锁文件路径：**
- global 轨：`_inbox/.hot_refresh_global.lock`
- project 轨：`_inbox/.hot_refresh_<name>.lock`

两条轨道使用独立锁文件，并发写入互不阻塞。

## 防循环触发

`hot_watcher.sh` 排除 `hot.md` / `global_hot.md` 自身变化，避免刷新死循环。Cooldown 2秒防高频重复触发。

## 过滤规则

`collect_notes` 跳过以下文件：
- `hot.md`、`global_hot.md`（自身）
- `status: archived / deprecated / incomplete`（非活跃）

## vault_sync.sh 等待热记忆写完

```bash
any_hot_lock_held()  # 检查所有 .hot_refresh*.lock 是否被持有
# 最多等待 MAX_WAIT=10 秒，超时则中止同步
```

## 局限性

- `fswatch` 是 macOS 专属，Linux 需替换为 `inotifywait`
- watcher 进程退出后热记忆停止自动刷新（需手动重启或加入 launchd）

## 手动触发

```bash
python3 scripts/hot_refresh.py --global
python3 scripts/hot_refresh.py --project member
```

## 关联

- [[llm-brain-os-architecture]]
- [[memory-weight-decay]]
