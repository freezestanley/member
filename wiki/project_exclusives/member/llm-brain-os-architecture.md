---
type: concept
created_at: 2026-06-05
last_modified: 2026-06-06
project: member
aliases: [LLM操作系统, BrainOS, 知识图谱OS, brain-os]
code_symbols: [memory_manager.py, bm25_search.py, hot_refresh.py, context_dehydrator.py, rg_body_search.py, palace_bridge.sh, vault_sync.sh, obsidian_audit.py]
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

# LLM-Brain OS 系统架构

## 核心定位

本地优先的个人知识图谱自动化操作系统。把 LLM 对话产生的一次性上下文，持久化为带衰减权重的可检索 Obsidian Wiki，在后续对话中以最低 token 成本精准召回。Obsidian 作为知识治理界面，Python 脚本作为引擎。

## 分层架构（7层）

```
USER INTERFACE LAYER
  Claude Skill (/brain-query /brain-ingest /brain-consolidate) + Obsidian Vault UI

OBSIDIAN UX LAYER（新增）
  templates/        Templater 入库模板（5种类型）
  dashboards/       Dataview 治理看板（7个）
  bases/            Obsidian Bases 属性视图（5个）
  canvases/         Canvas 系统地图
  obsidian_audit.py Agent 审计脚本（alias_gaps/low_weight/canvas_files）
  .obsidian/snippets/memory-vault.css  CSS 视觉增强

RETRIEVAL LAYER
  bm25_search.py (语义召回 + 权重排序)
  rg_body_search.py (正文精准行号匹配)
  └── context_dehydrator.py (脱水：frontmatter剥离/面包屑/token限制)

HOT MEMORY LAYER
  hot_watcher.sh (fswatch触发)
  └── hot_refresh.py (双轨：global/project，fcntl独占锁+原子写)

KNOWLEDGE STORE
  wiki/global_concepts/       (跨项目通用知识)
  wiki/project_exclusives/    (项目隔离知识)
  archive/                    (冷冻归档，vault同级，镜像子目录)
  _inbox/                     (原始暂存，.bm25_cache.pkl)

LIFECYCLE ENGINE
  memory_manager.py + weight_engine.py + activation_writer.py
  V2权重模型：类别半衰期 + importance + EWMA + boost
  孤儿.tmp检测 + frontmatter补全 + weight<0.15→归档

SYNC / BRIDGE LAYER
  palace_bridge.sh (MemPalace → _inbox)
  vault_sync.sh    (Git原子推送，fcntl锁等待)
  frontmatter_utils.py  (原子写入公共函数)
```

## 业务流程（全链路）

```
原始输入 (_inbox/palace_raw/ 或 LLM对话)
  ↓ /brain-ingest（通过 templates/ 选模板）
wiki/project_exclusives/<project>/ 或 wiki/global_concepts/
  ↓ fswatch触发 hot_watcher.sh
hot_refresh.py → hot.md / global_hot.md
  ↓ 用户 /brain-query
bm25_search.py 或 rg_body_search.py
  ↓
context_dehydrator.py → 注入LLM上下文
  ↓ activation_writer.py 更新 ewma/access_count/current_weight
  ↓ 定期 /brain-consolidate
memory_manager.py + weight_engine.py → 权重衰减 → archive/
  ↓
vault_sync.sh → Git推送
```

## 技术特性

| 特性 | 实现 |
|------|------|
| 原子写入 | `fcntl.flock(LOCK_EX)` + `.tmp` rename |
| BM25增量缓存 | pickle + mtime对比，仅变化文件重建 |
| 双链零死链 | archive/ 在vault同级目录，stem自动解析 |
| 双轨热记忆路由 | fswatch → 路径正则 → global/project分流 |
| Token预算管理 | `len(chunk)/3.5`估算，首文档截断不丢弃 |
| Git原子同步 | fcntl锁等待 + rebase线性历史 + force-with-lease |
| V2权重模型 | 类别半衰期+importance_k+EWMA+boost，可配置 |
| Obsidian UX层 | templates/dashboards/bases/canvas解耦治理界面 |

## frontmatter V2 schema 关键字段

新增字段：`weight_schema_version: 2`、`category`、`importance`、`ewma_access`、`last_boost`、`last_boosted_at`、`last_weight_migrated_at`、`tags`、`cssclasses`。

config 文件：`config/weight_config.yml`，包含各 category 半衰期、boost 关键词、ewma 参数。

## 关联

- [[bm25-memory-retrieval-pipeline]]
- [[context-dehydrator]]
- [[memory-weight-decay]]
- [[hot-memory-dual-track]]
- [[obsidian-ux-layer]]
