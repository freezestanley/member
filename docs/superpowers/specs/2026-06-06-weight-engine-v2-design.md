# WeightEngine v2 设计规范

**日期**：2026-06-06  
**状态**：已确认，待实现  
**关联文件**：`scripts/memory_manager.py`、`scripts/weight_engine.py`（新建）、`config/weight_config.yml`（新建）

---

## 1. 背景与动机

现有 `calculate_weight()` 存在以下已知问题：

| 问题 | 具体表现 |
|------|---------|
| frequency_bonus 无上界 | `access_count=10⁶` 时奖励因子达 3.76，过度补偿 |
| 半衰期固定 | 高频访问记忆的遗忘速率与低频记忆相同，不符合长期记忆特性 |
| 归档后无复活路径 | weight 降到阈值后单向归档，主动访问无法反向激活 |
| access_count 虚假膨胀 | 日志类笔记频繁写入拉高累积计数，权重虚高 |
| 所有笔记同等衰减 | 策略类笔记与日志类笔记使用相同半衰期，不合理 |
| initial_weight 固定 | 无法标记重要性更高的笔记 |

目标：引入 **WeightEngine 插件式架构**，每个维度解耦为独立 Module，同时保持旧笔记零迁移成本。

---

## 2. 数据层变更

### 2.1 新增 frontmatter 字段（全部可选，缺省降级为现有行为）

```yaml
category: strategy      # 类别，缺省 "general"
importance: 3           # 1-5 整数，缺省 1（无加成）
ewma_access: 1.0        # 浮点，每次激活时更新，缺省由 access_count 估算
last_boost: 0.0         # 最近一次 context_boost 值，仅用于审计
```

### 2.2 保留字段（不变）

```yaml
access_count      # 保留历史审计，不再参与权重计算
initial_weight    # 支持用户自定义重要笔记起点（如 2.0）
current_weight    # 由引擎写入
last_activated    # 保留
last_modified     # 保留
```

### 2.3 旧笔记迁移规则

- `ewma_access` 缺失时，`scan_and_clean` 首次扫描时自动补全：
  ```python
  ewma_access = round(math.log(1 + access_count), 2)  # 保守估算，不夸大历史
  ```
- `category` 缺失时默认 `"general"`，使用配置表中 `general` 的半衰期（30天）。
- `importance` 缺失时默认 `1`，effective_half_life 加成为零。
- 旧 `access_count` 字段**不删除**，永久保留作历史审计。

---

## 3. 配置文件：`config/weight_config.yml`

```yaml
# 默认半衰期表（天）——用户可覆盖任意类别
category_half_life:
  strategy: 90
  fact: 60
  decision: 75
  log: 7
  spec: 120
  general: 30       # 缺省兜底

# EWMA 平滑系数（0~1，越大越偏重最近访问）
ewma_alpha: 0.3

# importance 半衰期加成系数：effective_hl = base_hl × (1 + importance × k)
importance_k: 0.6

# context_boost 关键词推断表
boost_keywords:
  high: ["重要", "紧急", "开会", "决策", "上线"]
  medium: ["参考", "复习", "回顾"]

boost_values:
  high: 1.4
  medium: 1.2
  default: 1.0

# 权重输出上下界（防溢出）
weight_min: 0.01
weight_max: 5.0

# 归档阈值（不变）
forget_threshold: 0.15
```

---

## 4. WeightEngine 架构（`scripts/weight_engine.py`，新建）

### 4.1 数据对象

```python
@dataclass
class NoteMetadata:
    initial_weight: float = 1.0
    importance: int = 1           # 1-5
    category: str = "general"
    days_idle: int = 0
    ewma_access: float = 1.0
    last_query_context: str = ""  # 由调用方注入，用于 boost 推断
```

### 4.2 Module 划分

```python
class DecayModule:
    """指数衰减 + 动态半衰期（category + importance 联动）"""
    def apply(self, days: int, half_life: float,
              importance: int, k: float) -> float:
        effective_hl = half_life * (1 + importance * k)
        return 2 ** (-days / effective_hl)

class EWMAModule:
    """EWMA 频率奖励，替代原始 access_count"""
    def apply(self, ewma_access: float) -> float:
        # log(1+n) 保证 n=0 时为 1.0，上界受对数约束
        return 1.0 + 0.15 * math.log(1 + ewma_access)

    def update(self, prev_ewma: float, alpha: float) -> float:
        return alpha * 1.0 + (1 - alpha) * prev_ewma

class BoostModule:
    """context_boost：关键词推断 + --boost 手动覆盖"""
    def infer(self, context: str, boost_keywords: dict,
              boost_values: dict) -> float:
        context_lower = context.lower()
        for kw in boost_keywords.get("high", []):
            if kw in context_lower:
                return boost_values["high"]
        for kw in boost_keywords.get("medium", []):
            if kw in context_lower:
                return boost_values["medium"]
        return boost_values["default"]

class WeightEngine:
    def __init__(self, config_path: str):
        self.cfg = load_yaml(config_path)

    def compute(self, meta: NoteMetadata) -> float:
        half_life = self.cfg["category_half_life"].get(
            meta.category,
            self.cfg["category_half_life"]["general"]
        )
        decay = DecayModule().apply(
            meta.days_idle, half_life,
            meta.importance, self.cfg["importance_k"]
        )
        freq = EWMAModule().apply(meta.ewma_access)
        boost = BoostModule().infer(
            meta.last_query_context,
            self.cfg["boost_keywords"],
            self.cfg["boost_values"]
        )
        raw = meta.initial_weight * decay * freq * boost
        return round(
            max(self.cfg["weight_min"],
                min(self.cfg["weight_max"], raw)),
            3
        )

    def update_ewma(self, prev_ewma: float) -> float:
        return self.update_ewma_with_alpha(
            prev_ewma, self.cfg["ewma_alpha"]
        )
```

### 4.3 归档复活机制

`archive_with_backlink_update` 现有逻辑不变。新增**复活路径**：

- 触发条件：`/brain-query` 命中了 `archive/` 下的笔记（`status: archived`）。
- 动作：
  1. `os.rename(archive_path, wiki_path)`，路径按原 `wiki/` 层级还原。
  2. frontmatter 写入：`status: active`，`last_activated` = 今天，`access_count +1`，`ewma_access` 按 `update_ewma()` 刷新。
  3. `current_weight` 重置为 `FORGET_THRESHOLD + 0.05`（0.20），避免下次 `scan_and_clean` 立即再次归档。
- 实现位置：`bm25_search.py` 的 `collect_md_paths()` 扩展为也扫 `archive/`，命中时返回路径并标记 `is_archived=True`，调用方负责触发复活。

---

## 5. `memory_manager.py` 改动范围

| 函数 | 改动 |
|------|------|
| `calculate_weight()` | **整体替换**为 `WeightEngine.compute()` 调用 |
| `scan_and_clean()` | 新增：扫描时若 `ewma_access` 缺失则补全（见 §2.3）；激活刷新时调用 `engine.update_ewma()` 更新 `ewma_access` |
| `_build_frontmatter()` | 新增 4 个字段：`category: general`、`importance: 1`、`ewma_access: 1.0`、`last_boost: 0.0` |
| `archive_with_backlink_update()` | 零改动 |
| `_ensure_status_fields()` | 零改动 |
| `render_global_indices()` | 零改动 |

---

## 6. `bm25_search.py` 改动范围

| 位置 | 改动 |
|------|------|
| `collect_md_paths()` | 扩展扫描路径：新增 `archive/` 目录，返回时标记 `is_archived` |
| 激活回写段 | 命中 `is_archived=True` 时触发复活逻辑（见 §4.3） |
| status 过滤 | 现有 `status: archived/deprecated/incomplete` 过滤**保留**，但 `archived` 改为"可召回但标注来源为归档" |

---

## 7. 公式对比总结

| 维度 | v1（现有） | v2（本设计） |
|------|-----------|-------------|
| 衰减 | `2^(-days/30)` 固定半衰期 | `2^(-days / hl*(1+imp*0.6))` 动态半衰期 |
| 频率奖励 | `1 + 0.2*log(access_count)` 累积计数 | `1 + 0.15*log(1+ewma)` EWMA，近期访问权重更高 |
| 重要性 | 无 | `initial_weight` 可配置 + 半衰期加成 |
| 类别 | 无 | `category_half_life` 可配置表 |
| 情境加成 | 无 | `BoostModule` 关键词推断 + `--boost` 覆盖 |
| 归档复活 | 无 | 命中归档笔记时自动 unarchive + 权重重置 |
| 上下界 | 无 | `clamp(0.01, 5.0)` |

---

## 8. 实现顺序建议

1. 新建 `config/weight_config.yml`（默认配置表）
2. 新建 `scripts/weight_engine.py`（NoteMetadata + 4个Module + WeightEngine）
3. 改 `memory_manager.py`：替换 `calculate_weight()`，更新 `_build_frontmatter()`，补 `ewma_access` 迁移逻辑
4. 改 `bm25_search.py`：扩展 `collect_md_paths()` 扫 `archive/`，加复活触发
5. 补单元测试：`tests/test_weight_engine.py`，覆盖边界值（`days=0`、`importance=5`、`ewma=0`、`boost=high`）
6. 跑 `memory_manager.py` 对现有笔记做一次 dry-run，确认 `ewma_access` 补全结果合理
