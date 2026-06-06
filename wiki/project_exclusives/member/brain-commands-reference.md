---
type: concept
created_at: 2026-06-06
last_modified: 2026-06-06
project: member
aliases: [命令参考, brain命令, 对外命令, brain-query, brain-ingest, brain-consolidate, brain-search]
code_symbols: [bm25_search.py, rg_body_search.py, activation_writer.py, memory_manager.py, log_append.py, context_dehydrator.py, vault_sync.sh]
initial_weight: 1.0
current_weight: 1.0
last_activated: 2026-06-06
access_count: 1
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

# 记忆仓库对外命令参考

## 结论

记忆仓库对外暴露 6 条命令，分两组：query/search 系列负责检索召回，ingest/consolidate 负责写入与整理。所有命令都遵循"先查会话热记忆，不足时才降级到中央知识库"的漏斗模型。

## 命令总览

| 命令 | 目标 | 引擎 | 默认 scope |
| --- | --- | --- | --- |
| `/brain-query` | 回答问题 | BM25 | project |
| `/brain-query-rg` | 回答问题 | rg 精确匹配 | project |
| `/brain-search` | 审计资产分布 | BM25 | global |
| `/brain-search-rg` | 审计资产分布 | rg 精确匹配 | global |
| `/brain-ingest` | 写入知识库 | — | — |
| `/brain-consolidate` | 权重衰减归档 | — | — |

## 核心区分

**query vs search**：query 输出确定性结论；search 输出资产分布报告，不给确定性结论。

**BM25 vs rg**：BM25 适合自然语言/模糊主题；rg 适合精确关键词/代码符号/需要行号的场景。

**scope 默认值差异**：query 系列默认 `project`；search 系列默认 `global`。

## 参数速查

```
/brain-query <词> [--scope project|global] [--dry]
/brain-query-rg <词> [--scope project|global] [--dry]
/brain-search <词> [--scope project|global] [--dry]        # 默认 global
/brain-search-rg <词> [--scope project|global] [--dry]     # 默认 global
/brain-ingest
/brain-consolidate
```

`--dry`：关闭脱水管道，直接读原文。适合短笔记（<50行）、需逐字引用、调试脱水时。

## 底层调用链（简要）

```
query/query-rg
  → bm25_search.py 或 rg_body_search.py
  → context_dehydrator.py (summary | precise 模式)
  → activation_writer.py （命中笔记激活）
  → log_append.py

search/search-rg
  → bm25_search.py 或 rg_body_search.py
  → context_dehydrator.py
  → mempalace search （wing_global_shared + wing_project_<name>）
  → activation_writer.py
  → log_append.py

ingest
  → .tmp 原子写入 wiki/
  → fcntl.LOCK_EX 保护
  → index.md 更新
  → vault_sync.sh

consolidate
  → memory_manager.py
  → weight_engine.py （V2 公式）
  → archive/ 归档（weight < 0.15，非首次迁移）
  → wiki/index.md 刷新
```

## ingest 同名文件行为

同主题文件已存在时：覆盖正文，`last_modified` 更新，`access_count`/`ewma_access`/`current_weight` **保留不重置**。1 条记录原地更新，无版本历史。

## consolidate 归档宽限

V1→V2 首次迁移：只更新字段，不立即归档（即使 weight < 0.15）。下次扫描仍低于阈值才归档。

## 关联

- [[llm-brain-os-architecture]]
- [[bm25-memory-retrieval-pipeline]]
- [[memory-weight-decay]]
- [[obsidian-ux-layer]]
