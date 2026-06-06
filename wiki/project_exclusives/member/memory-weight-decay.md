---
type: concept
created_at: 2026-06-05
last_modified: 2026-06-06
project: member
aliases: [记忆衰减, 权重衰减, 遗忘曲线, memory_decay, V2权重, WeightEngine]
code_symbols: [memory_manager.py, weight_engine.py, activation_writer.py, WeightEngine, compute, migrate_weight_fields, scan_and_clean, config/weight_config.yml]
initial_weight: 1.0
current_weight: 1.0
last_activated: 2026-06-06
access_count: 4
status: active
superseded_by: ""
weight_schema_version: 2
category: spec
importance: 4
ewma_access: 0.0
last_boost: 1.0
last_boosted_at: ""
last_weight_migrated_at: 2026-06-06
tags:
  - memory/active
  - type/concept
  - project/member
  - category/spec
cssclasses:
  - memory-note
---

# 记忆权重衰减公式（V2）

## 结论

记忆权重由「类别半衰期 × importance 修正」驱动指数衰减，叠加 EWMA 访问频率奖励和临时 boost。权重低于 `forget_threshold=0.15` 时，笔记在下次 `brain-consolidate` 非首次迁移后自动冷冻归档到 `archive/`。

## V2 权重公式

```python
effective_half_life = category_half_life * (1 + (importance - 1) * importance_k)
decay = 2 ^ (-days_idle / effective_half_life)
freq_bonus = min(1 + freq_k * log1p(ewma_access), freq_bonus_max)
boost = last_boost if boost_age_days <= boost_ttl_days else 1.0
current_weight = clamp(initial_weight * decay * freq_bonus * boost, weight_min, weight_max)
```

各项含义：
- `category_half_life`：按笔记类别差异化衰减速度（spec=120天，strategy=90天，decision=75天，fact=60天，general=30天，log=7天）
- `importance_k=0.6`：importance 越高，实际半衰期越长
- `ewma_access`：EWMA 访问频率，半衰期 14 天，防历史访问过度累积
- `boost`：查询时 context 含特定关键词触发（高档 1.4，中档 1.2），有效期 7 天
- 结果 clamp 到 `[weight_min=0.01, weight_max=5.0]`

## 配置文件

`config/weight_config.yml`（关键字段）：

```yaml
category_half_life:
  spec: 120
  strategy: 90
  decision: 75
  fact: 60
  general: 30
  log: 7
importance_k: 0.6
freq_k: 0.15
freq_bonus_max: 1.6
ewma_half_life_days: 14
boost_ttl_days: 7
boost_keywords:
  high: [重要, 紧急, 开会, 决策, 上线]
  medium: [参考, 复习, 回顾]
boost_values:
  high: 1.4
  medium: 1.2
forget_threshold: 0.15
revive_weight_margin: 0.05
```

## EWMA 更新公式

```python
decayed = previous_ewma * 2 ^ (-days_since_activation / ewma_half_life_days)
ewma_access = min(ewma_max, decayed + 1.0)
```

每次激活（`activation_writer.py`）触发，`ewma_max=20.0`，迁移时存量 `access_count` 折算上限 `ewma_migration_cap=5.0`。

## 生命周期状态机

```
active → 衰减 → current_weight < 0.15
       → memory_manager 非首次迁移
       → status: archived（写回原文件 frontmatter）
       → os.rename(wiki/..., archive/...)  保留完整子目录层级
```

首次迁移宽限：只更新字段和 current_weight，不立刻归档，防止 V2 升级时批量移动旧笔记。

## 激活刷新（activation_writer.py）

笔记被 `/brain-query` 命中后自动执行：
1. 拒绝 `archived/deprecated/incomplete` 状态。
2. `access_count + 1`，EWMA 更新，boost 判断。
3. 重新计算 `current_weight`。
4. `atomic_write_text()` 一次写回全部字段。

手动激活可附带 boost：
```bash
python3 scripts/activation_writer.py \
  --path "<笔记绝对路径>" \
  --context "重要 上线前复习" \
  --boost 1.4
```

## 孤儿 .tmp 检测

写入过程异常中断会留下 `<目标>.md.tmp`，`scan_and_clean` 检测到后标记原文件 `status: incomplete`，阻止其参与检索。

## 自动生成文件豁免

`hot.md`、`global_hot.md`、`index.md`、`log.md` 不参与衰减计算，也不补 frontmatter。

## 已知局限

- archive 无自动复活：`revive_weight_margin` 字段已预留，功能尚未实现。
- 归档后需手动修改 status + 移回 wiki/ 目录才能恢复检索。
- BM25 cache 无锁，并发写有风险（个人单机场景可接受）。

## 关联

- [[llm-brain-os-architecture]]
- [[bm25-memory-retrieval-pipeline]]
- [[hot-memory-dual-track]]
- [[obsidian-ux-layer]]
