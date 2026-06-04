---
type: concept
created_at: 2026-06-04
last_modified: 2026-06-04
project: member
aliases: [记忆权重公式, 冷启动修复, calculate_weight, current_weight, 频率奖励]
code_symbols: [memory_manager.py, calculate_weight]
initial_weight: 1.0
current_weight: 1.0
last_activated: 2026-06-04
access_count: 1
---

# 记忆权重计算公式与冷启动修复

## 结论

`memory_manager.py` 的 `calculate_weight()` 使用时间衰减 × 频率奖励复合公式。旧版公式在 `access_count=1`（新笔记）时语义错误，修复后新笔记奖励为零，符合设计意图。

## 正确公式

```
current_weight = initial_weight × decay(days) × frequency_bonus(access_count)

decay(days)            = e^(-λ × days)        λ ≈ 0.01（约 69 天半衰）
frequency_bonus(count) = 1.0 + 0.2 × ln(count)
```

- `access_count=1`（新笔记）：`ln(1) = 0`，无奖励，`bonus = 1.0`
- `access_count=5`：`bonus ≈ 1.32`（+32%）
- `access_count=0`（防御）：`count = max(1, count)` 保护，不产生负无穷

## 冷启动 Bug（旧版）

**旧公式：** `frequency_bonus = 1.0 + 0.2 × ln(max(0, access_count - 1))`

| access_count | 旧公式结果 | 问题 |
|---|---|---|
| 1 | `ln(0)` → `0`，bonus=1.0 | 逻辑无错，但语义错：新笔记不应有奖励 |
| 0 | `ln(-1)` → 负无穷 | **crash** / 污染 current_weight |

**修复：** 去掉 `-1` 偏移，改用 `ln(count)` 并在入口处 `count = max(1, count)`。

## 权重刷新时机

以下任一行为触发刷新（由脚本自动执行，不手动操作）：
- `/brain-query` 命中该笔记并用于回答
- 新笔记引用了该笔记
- 人工或自动更新笔记内容

刷新动作：`last_modified`、`last_activated` 改为当天；`access_count += 1`；重算 `current_weight`。

## 归档阈值

`current_weight < 0.15` → `memory_manager.py` 将笔记移入 `wiki/archive/`，更新 `index.md` 对应条目（不删除文件）。

## 适用边界

- 权重公式仅由 `memory_manager.py` 计算，其他脚本只读 `current_weight` 字段，不自行计算。
- `hot_refresh.py` 按 `current_weight` 降序排序，不重算权重。
- 衰减系数 λ 硬编码在 `memory_manager.py`，不可由外部传参覆盖。

## 相关概念

- [[brain-os-architecture]]
- [[bm25-cache-index]]
