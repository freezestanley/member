---
type: concept
created_at: 2026-06-03
last_modified: 2026-06-03
project: member
aliases: [LLM-Brain OS, Brain OS, 记忆仓库架构, 知识图谱架构]
code_symbols: [memory_manager, bm25_search, hot_refresh, vault_sync, log_append, extract_aliases]
initial_weight: 1.0
current_weight: 1.0
last_activated: 2026-06-03
access_count: 1
---

# LLM-Brain OS 完整架构

## 结论

LLM-Brain OS 是一套 5 层本地知识图谱系统，核心分层为：Skill 层 → 检索引擎层 → 知识管理层 → 存储层（Obsidian Vault） → 基础设施层。三条主数据流：摄入（brain-ingest）、检索（brain-query）、衰减（brain-consolidate）。所有写入 `hot.md` 的权限唯一属于 `hot_refresh.py`。

## 分层结构

```
L5 Skill 层        brain-query · brain-ingest · brain-consolidate · brain-search · brain-search-rg · brain-query-rg
L4 检索引擎层      bm25_search.py（BM25Okapi + jieba + aliases注入 + 缓存）· rg_body_search.py
L3 知识管理层      memory_manager.py · hot_refresh.py · log_append.py · vault_sync.sh
L2 存储层          wiki/global_concepts/ · wiki/project_exclusives/ · wiki/archive/ · hot.md · index.md · _inbox/
L1 基础设施层      Git · hot_watcher.sh（fswatch守护）· utils.py · Frontmatter Schema
```

## 三条数据流

**摄入**：对话结论 → brain-ingest → 写 .md + frontmatter → 更新 index.md → vault_sync.sh → watcher → hot_refresh.py

**检索**：brain-query → L1 自查（会话/claude-mem）→ 失败后 → bm25_search.py → 读全文 → 回写 frontmatter（activated+1）→ log_append.py → watcher → hot.md

**衰减**：brain-consolidate → memory_manager.py → 计算 `initial_w × 2^(−d/30) × (1+0.2×ln(n))` → weight < 0.15 → archive_with_backlink_update()（先改双链再移文件）

## 核心脚本职责

| 脚本 | 唯一写入权 |
|------|------------|
| `memory_manager.py` | `current_weight` + 归档移动 |
| `bm25_search.py` | `_inbox/.bm25_cache.pkl` |
| `hot_refresh.py` | `wiki/hot.md` |
| `log_append.py` | `wiki/log.md` |
| `vault_sync.sh` | remote（仅 `BRAIN_SYNC_BRANCH`）|

## Frontmatter 关键字段

- `initial_weight`：人工设定，不自动更改
- `current_weight`：memory_manager.py 维护
- `last_activated` / `access_count`：brain-query 命中时回写
- `aliases`：BM25 + rg 两路 token 注入，防缩写搜不到

## 关键约束

- `hot.md` 只能由 `hot_refresh.py` 写，所有 skill 禁止手动写入
- `vault_sync.sh` fail-close：非 `BRAIN_SYNC_BRANCH` 分支拒绝推送
- `archive_with_backlink_update()` 必须先改双链再移文件（顺序锁定）
- brain-query L1 命中即停，禁止继续检索中央库
- 项目专属知识禁止写入 `global_concepts/`

## 已知风险及修复

| 风险 | 修复 |
|------|------|
| `access_count=0` 导致 `ln(0)` | `max(1, access_count)` |
| 并发写 hot.md | fcntl 文件锁（`_inbox/.hot_refresh.lock`）|
| 归档后双链断链 | `archive_with_backlink_update()` 先全库替换再移文件 |
| vault_sync 分支硬编码 | 动态读 `BRAIN_SYNC_BRANCH` 环境变量 |
| aliases 缩写搜不到 | `extract_aliases()` 注入 BM25 token 流 |

## 相关文档

详细技术方案见：`docs/superpowers/specs/2026-06-03-llm-brain-os-design.md`

## 相关概念

- [[wiki-hot-watcher]]
- [[wiki-log-format]]
- [[frontmatter-aliases-检索增强]]
