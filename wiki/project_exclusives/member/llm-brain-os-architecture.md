---
type: concept
created_at: 2026-06-05
last_modified: 2026-06-05
project: member
aliases: [LLM操作系统, BrainOS, 知识图谱OS, brain-os]
code_symbols: [memory_manager.py, bm25_search.py, hot_refresh.py, context_dehydrator.py, rg_body_search.py, palace_bridge.sh, vault_sync.sh]
initial_weight: 1.0
current_weight: 1.0
last_activated: 2026-06-05
access_count: 1
status: active
superseded_by: ""
---

# LLM-Brain OS 系统架构

## 核心定位

本地优先的个人知识图谱自动化操作系统。把 LLM 对话产生的一次性上下文，持久化为带衰减权重的可检索 Obsidian Wiki，在后续对话中以最低 token 成本精准召回。

## 分层架构（6层）

```
USER INTERFACE LAYER
  Claude Skill (/brain-query /brain-ingest /brain-consolidate) + Obsidian Vault UI

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
  archive/                    (冷冻归档，vault内，链接零死链)
  _inbox/                     (原始暂存，.bm25_cache.pkl)

LIFECYCLE ENGINE
  memory_manager.py
  权重衰减 + 孤儿.tmp检测 + frontmatter补全 + weight<0.15→归档

SYNC / BRIDGE LAYER
  palace_bridge.sh (MemPalace → _inbox)
  vault_sync.sh    (Git原子推送，fcntl锁等待)
  utils.py         (aliases提取公共函数)
```

## 业务流程（全链路）

```
原始输入 (_inbox/palace_raw/ 或 LLM对话)
  ↓ /brain-ingest
wiki/project_exclusives/<project>/ 或 wiki/global_concepts/
  ↓ fswatch触发 hot_watcher.sh
hot_refresh.py → hot.md / global_hot.md
  ↓ 用户 /brain-query
bm25_search.py 或 rg_body_search.py
  ↓
context_dehydrator.py → 注入LLM上下文
  ↓ 定期 /brain-consolidate
memory_manager.py → 权重衰减 → archive/
  ↓
vault_sync.sh → Git推送
```

## 技术特性

| 特性 | 实现 |
|------|------|
| 原子写入 | `fcntl.flock(LOCK_EX)` + `.tmp` rename |
| BM25增量缓存 | pickle + mtime对比，仅变化文件重建 |
| 双链零死链 | archive/ 在vault内，stem自动解析 |
| 双轨热记忆路由 | fswatch → 路径正则 → global/project分流 |
| Token预算管理 | `len(chunk)/3.5`估算，首文档截断不丢弃 |
| Git原子同步 | fcntl锁等待 + rebase线性历史 + force-with-lease |

## 关联

- [[bm25-memory-retrieval-pipeline]]
- [[context-dehydrator]]
- [[memory-weight-decay]]
- [[hot-memory-dual-track]]
