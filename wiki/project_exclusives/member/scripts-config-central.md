---
type: concept
created_at: 2026-06-06
last_modified: 2026-06-06
project: member
aliases: [脚本配置中心, config.py, 常量中心]
code_symbols: [BRAIN_DIR, WIKI_ROOT, GLOBAL_DIR, PROJECT_DIR, ARCHIVE_DIR, INBOX_DIR, GENERATED_FILES, BM25_CACHE_PATH, LOG_PATH, GLOBAL_HOT_PATH, GLOBAL_TOP_N, PROJECT_TOP_M, BM25_TOP_K, HALF_LIFE_DAYS, FORGET_THRESHOLD, SKIP_STATUSES, STATUS_ARCHIVED, WEIGHT_CONFIG_PATH]
initial_weight: 1.0
current_weight: 1.0
last_activated: 2026-06-06
access_count: 1
status: active
superseded_by: ""
weight_schema_version: "2"
category: decision
importance: 3
ewma_access: 0.0
last_boost: 1.0
last_boosted_at: ""
last_weight_migrated_at: 2026-06-06
---

# scripts/config.py — 脚本层公共常量中心

## 结论

`scripts/config.py` 是所有脚本的唯一常量来源。所有路径、枚举、阈值从此处导入，禁止在业务脚本中重复定义相同的值。

## 覆盖范围

| 分区 | 常量 | 说明 |
|---|---|---|
| 根路径 | `BRAIN_DIR` | Vault 根目录，所有路径的起点 |
| 目录路径 | `WIKI_ROOT / GLOBAL_DIR / PROJECT_DIR / ARCHIVE_DIR / INBOX_DIR` | 由 `BRAIN_DIR` 推导 |
| 生成文件集合 | `GENERATED_FILES` | `frozenset`，不参与检索/衰减/审计 |
| 缓存/索引 | `BM25_CACHE_PATH / LOG_PATH / GLOBAL_HOT_PATH` | 固定文件路径 |
| Hot-Refresh | `GLOBAL_TOP_N=8 / PROJECT_TOP_M=20 / BM25_TOP_K=3` | 榜单与检索条数 |
| 旧衰减引擎 | `HALF_LIFE_DAYS=30 / FORGET_THRESHOLD=0.15` | 与 weight_config.yml 默认值对齐 |
| Status 枚举 | `SKIP_STATUSES / STATUS_ARCHIVED` | BM25/衰减/审计跳过条件 |
| WeightEngine | `WEIGHT_CONFIG_PATH` | `config/weight_config.yml` 的 Path 对象 |

## 使用规则

- 路径类：只改 `BRAIN_DIR`，其余路径自动推导。
- 阈值/Top-N：直接改对应常量，无需触碰业务脚本。
- 枚举类：统一在 config.py 新增/删除，不在业务代码中散写字面量。

## 各脚本迁移方式

```python
# 脚本与 config.py 同目录时
from config import BRAIN_DIR, GLOBAL_DIR, ...

# 从项目根调用时
from scripts.config import BRAIN_DIR, GLOBAL_DIR, ...
```

`weight_engine.py` 用 `try/except ImportError` 兜底，保持向后兼容：

```python
try:
    from config import WEIGHT_CONFIG_PATH as DEFAULT_CONFIG_PATH
except ImportError:
    DEFAULT_CONFIG_PATH = Path(__file__).parent.parent / "config" / "weight_config.yml"
```

## 已迁移脚本

`activation_writer.py` / `bm25_search.py` / `memory_manager.py` / `hot_refresh.py` / `log_append.py` / `obsidian_audit.py` / `weight_engine.py`

## 边界

- `HALF_LIFE_DAYS` 和 `FORGET_THRESHOLD` 仅供旧衰减引擎（`memory_manager.py`）使用；新引擎（`WeightEngine`）的参数来自 `weight_config.yml`，通过 `WEIGHT_CONFIG_PATH` 加载。
- `GENERATED_FILES` 与 `SKIP_STATUSES` 均为 `frozenset`，不可变，可安全用于 `in` 判断。

## 关联

- [[memory-weight-decay]] — 旧衰减引擎使用 `HALF_LIFE_DAYS` / `FORGET_THRESHOLD`
- [[bm25-memory-retrieval-pipeline]] — BM25 检索使用 `GLOBAL_DIR` / `PROJECT_DIR` / `BM25_CACHE_PATH` / `BM25_TOP_K`
- [[llm-brain-os-architecture]] — 整体架构定义了 config.py 所管理的目录分区
