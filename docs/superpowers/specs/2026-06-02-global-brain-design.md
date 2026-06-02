# 全局中央记忆大脑 — 设计规范

**日期**: 2026-06-02  
**状态**: 已批准  
**作者**: Claude + za-stanleyxu

---

## 1. 目标

将 `member/member` vault 从单项目私有知识库升级为跨项目全局中央记忆大脑，使所有 Claude Code 会话（无论在哪个项目目录下）均可检索、写入、维护这个统一知识库。

---

## 2. 架构

```
~/.claude/
├── CLAUDE.md                    ← 全局规则层（被动注入）
│   └── 声明 vault 路径、分区规则、写入时机
└── commands/
    ├── brain-query.md           ← /brain-query <词> — BM25 检索
    ├── brain-ingest.md          ← /brain-ingest — 摄取当前项目知识
    └── brain-consolidate.md     ← /brain-consolidate — 衰减归档

/Users/za-stanlexu/Documents/member/member/   ← 中央知识 vault
├── wiki/
│   ├── concepts/               ← 全局通用概念（跨项目共享）
│   ├── projects/               ← 项目专属知识（按项目名分目录）
│   │   ├── demo/
│   │   ├── openclaw/
│   │   └── member/
│   └── archive/                ← 低权重冷冻区（current_weight < 0.15）
├── scripts/
│   ├── bm25_search.py          ← BM25 检索（覆盖 concepts/ + projects/）
│   ├── memory_manager.py       ← 衰减归档
│   ├── palace_bridge.sh        ← MemPalace 桥接
│   └── vault_sync.sh           ← Git 同步推送
└── _inbox/                     ← 原始材料暂存（只读输入）
    ├── palace_raw/
    └── global_shared_raw/
```

---

## 3. 组件详述

### 3.1 `~/.claude/CLAUDE.md` 新增节（被动规则）

新增 `## 全局中央记忆大脑` 节，包含：

- **vault 绝对路径**：`/Users/za-stanlexu/Documents/member/member`
- **分区路由规则**：
  - 跨项目通用概念、工程规范、方法论 → `wiki/concepts/`
  - 项目专属决策、模块设计、业务逻辑 → `wiki/projects/<当前项目名>/`
- **写入时机**：完成一个功能模块、做出重要技术决策、总结调试结论时，主动执行 `/brain-ingest`
- **检索时机**：遇到历史决策、通用规范、跨项目参考时，主动执行 `/brain-query`
- **禁令**：
  - 禁止把项目专属知识写入 `wiki/concepts/`
  - 禁止绕过 BM25 直接 Grep 全局扫描 vault
  - 禁止在未读 Top 3 结果前回答 `/brain-query`

### 3.2 `~/.claude/commands/brain-query.md`

触发：`/brain-query <检索词>`

执行步骤：
1. 调用 `python3 /Users/za-stanlexu/Documents/member/member/scripts/bm25_search.py "$ARGUMENTS"`
2. 读取返回的 Top 3 文件路径
3. 精准读取这三个文件内容
4. 以文件内容为依据回答
5. 刷新命中文件：`last_activated` = 今天，`access_count` += 1

### 3.3 `~/.claude/commands/brain-ingest.md`

触发：`/brain-ingest`

执行步骤：
1. 从 `git rev-parse --show-toplevel` 获取当前项目名
2. 判断待写内容：
   - 通用规范 → `wiki/concepts/`
   - 项目专属 → `wiki/projects/<项目名>/`
3. 原子化提炼，写入或更新对应目录
4. 补齐 `[[双向链接]]`，刷新 frontmatter
5. 运行 `bash /Users/za-stanlexu/Documents/member/member/scripts/vault_sync.sh`

### 3.4 `~/.claude/commands/brain-consolidate.md`

触发：`/brain-consolidate`

执行步骤：
1. 运行 `python3 /Users/za-stanlexu/Documents/member/member/scripts/memory_manager.py`
2. 读取输出
3. 汇报归档清单

---

## 4. 需改动的现有文件

| 文件 | 改动内容 |
|------|---------|
| `~/.claude/CLAUDE.md` | 新增 `## 全局中央记忆大脑` 节 |
| `scripts/bm25_search.py` | 扩展检索范围：覆盖 `wiki/projects/` 所有子目录 |
| `member/member/CLAUDE.md` | 移除指令定义段（`/brain-query`、`/brain-ingest`、`/brain-consolidate`），保留 vault 结构说明和 frontmatter schema |
| `wiki/projects/` | 新建目录，按项目名创建子目录 |

---

## 5. Frontmatter Schema（不变）

```markdown
---
type: concept
created_at: YYYY-MM-DD
last_modified: YYYY-MM-DD
project: <项目名 或 global>
code_symbols: []
initial_weight: 1.0
current_weight: 1.0
last_activated: YYYY-MM-DD
access_count: 1
---
```

新增字段 `project`：`global` 表示通用概念，项目名表示专属知识。

---

## 6. 执行边界

- `bm25_search.py` 改动前，检索范围仅限 `wiki/concepts/`；改动后覆盖全部 `wiki/`。
- `vault_sync.sh` 当前推送到 `origin/main`，跨项目写入依赖 vault 所在 git remote 可达。
- Commands 文件放置在 `~/.claude/commands/`，对所有项目全局生效。
