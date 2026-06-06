---
type: concept
created_at: 2026-06-05
last_modified: 2026-06-06
project: member
aliases: [记忆衰减, 权重衰减, 遗忘曲线, memory_decay]
code_symbols: [memory_manager.py, calculate_weight, scan_and_clean, archive_with_backlink_update, HALF_LIFE_DAYS, FORGET_THRESHOLD]
initial_weight: 1.0
current_weight: 1.0
last_activated: 2026-06-06
access_count: 3
status: active
superseded_by: ""
---

# 记忆权重衰减公式

## 结论

记忆权重随时间指数衰减，但访问频率给予对数奖励。权重低于0.15时，笔记自动冷冻归档到 `archive/`，双链保持有效（Obsidian stem解析，零死链）。

## 衰减公式

```python
HALF_LIFE_DAYS = 30       # 半衰期：30天不访问，权重减半
FORGET_THRESHOLD = 0.15   # 归档阈值

w = initial_weight × 2^(-days_since_last_active / 30) × (1 + 0.2 × log(max(1, access_count)))
```

**各项含义：**
- `2^(-days/30)`：指数衰减，30天减半，符合记忆遗忘曲线
- `(1 + 0.2 × log(n))`：频率奖励，访问越多衰减越慢（对数防止无限增长）
- 结果四舍五入保留3位小数

## 生命周期状态机

```
active → (time decay) → current_weight < 0.15
       → archive_with_backlink_update()
       → status: archived (写回原文件 frontmatter)
       → os.rename(wiki/..., archive/...) 保留子目录层级
```

## 原子归档流程（archive_with_backlink_update）

1. 计算 `archive/` 内对应子路径（保留完整层级）
2. 向原文件写 `status: archived`
3. `os.rename(src, dst)` — POSIX 原子移动
4. 双链不改写：`archive/` 在 Obsidian vault 内，`[[stem]]` 自动解析

## 孤儿 .tmp 检测

写入过程异常中断会留下 `<目标>.md.tmp`，`scan_and_clean` 检测到后标记原文件 `status: incomplete`，阻止其参与检索。

## 激活刷新触发时机

笔记发生以下任一行为需刷新 frontmatter：
- 被 `/brain-query` 命中并用于回答
- 被新笔记引用（反向链接追加）
- 被人工或自动更新内容

刷新字段：`last_modified`、`last_activated` 改为当天，`access_count +1`。

## 自动生成文件豁免

`_GENERATED_FILES = {"hot.md", "global_hot.md", "index.md", "log.md"}` 不参与衰减计算，也不补 frontmatter。

## 已知局限

- 衰减不区分"主动被引用"和"被动经过时间"
- 频繁写入类笔记会虚假提升 access_count
- 归档后无反向激活路径（weight不自动恢复）

## 关联

- [[llm-brain-os-architecture]]
- [[bm25-memory-retrieval-pipeline]]
