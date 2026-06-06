# 记忆仓库使用说明手册

**适用项目**：member 记忆仓库  
**适用日期**：2026-06-06  
**使用对象**：本地 Agent、知识维护者、Obsidian 使用者

## 1. 快速理解

这是一个本地 Markdown 记忆库。你把稳定的知识写成单主题笔记，系统通过 BM25、正文精确检索、aliases、权重衰减和热记忆文件，在后续对话中把相关笔记召回给 LLM 使用。

最常用的动作只有五个：

| 需求 | 使用方式 |
| --- | --- |
| 问一个知识库问题 | `/brain-query <问题>` |
| 用精确词定位笔记 | `/brain-query-rg <关键词>` |
| 审计某个词在哪些资产里出现 | `/brain-search <关键词>` 或 `/brain-search-rg <关键词>` |
| 把稳定结论写入知识库 | `/brain-ingest` |
| 执行权重衰减和归档 | `/brain-consolidate` |

## 2. 环境准备

### 2.1 Python 依赖

在仓库根目录执行：

```bash
python3 -m venv membervenv
source membervenv/bin/activate
pip install -r requirements.txt
```

`requirements.txt` 当前包含：

```text
rank-bm25
jieba
requests
PyYAML
```

### 2.2 可选外部工具

| 工具 | 用途 | 是否必需 |
| --- | --- | --- |
| Obsidian | 浏览 wiki、双链和热榜 | 推荐 |
| fswatch | 自动监听 wiki 变化并刷新 hot 文件 | 自动热榜需要 |
| Git | 同步知识库 | 同步需要 |
| MemPalace CLI | 挖掘历史会话 | 历史会话导入需要 |

macOS 安装 `fswatch`：

```bash
brew install fswatch
```

### 2.3 路径要求

当前脚本写死了仓库绝对路径：

```text
/Users/za-stanlexu/Documents/member/member
```

如果移动仓库，需要同步修改以下脚本中的 `BRAIN_DIR` 或相关常量：

- `scripts/bm25_search.py`
- `scripts/memory_manager.py`
- `scripts/activation_writer.py`
- `scripts/palace_bridge.sh`
- `scripts/vault_sync.sh`

## 3. 目录怎么用

```text
wiki/global_concepts/
```

放跨项目通用知识，例如通用架构原则、技术规范、库用法。

```text
wiki/project_exclusives/<project>/
```

放项目专属知识，例如当前项目的实现细节、架构决策、踩坑记录。

```text
archive/
```

放被冷冻归档的笔记。当前默认检索不会扫描归档区。

```text
_inbox/
```

放原始材料、MemPalace 导出的历史会话和 BM25 缓存。

```text
wiki/global_hot.md
wiki/project_exclusives/<project>/hot.md
```

自动生成的热记忆文件，不要手动编辑。

```text
wiki/index.md
wiki/log.md
```

`index.md` 是中央索引，`log.md` 是查询日志。

## 4. 新增一篇记忆笔记

### 4.1 通过 Agent 命令入库

当当前对话已经形成稳定、可复用、单主题结论时，使用：

```text
/brain-ingest
```

入库规则：

- 一篇笔记只写一个主题。
- 通用知识写入 `wiki/global_concepts/`。
- 项目知识写入 `wiki/project_exclusives/<当前项目>/`。
- 正文先写结论，再写边界、细节、示例。
- 相关概念尽量使用 `[[概念名]]`。

### 4.2 手动创建笔记模板

```markdown
---
type: concept
created_at: 2026-06-06
last_modified: 2026-06-06
project: member
aliases: [别名A, AliasB]
code_symbols: []
initial_weight: 1.0
current_weight: 1.0
last_activated: 2026-06-06
access_count: 1
status: active
superseded_by: ""
weight_schema_version: 2
category: general
importance: 1
ewma_access: 0.0
last_boost: 1.0
last_boosted_at: ""
last_weight_migrated_at: 2026-06-06
---

# 笔记标题

## 结论

写一句可独立复用的核心结论。

## 边界

说明什么时候适用，什么时候不适用。

## 细节

补充必要实现、命令、代码符号或经验。

## 关联

- [[相关概念]]
```

字段建议：

| 字段 | 建议 |
| --- | --- |
| `aliases` | 放中文名、英文名、缩写、内部俗称，提升检索召回 |
| `category` | 可选 `strategy`、`fact`、`decision`、`log`、`spec`、`general` |
| `importance` | `1..5`，越重要半衰期越长 |
| `status` | 正常为 `active`，不要手动把归档笔记改回 active |

## 5. 查询知识库

### 5.1 默认查询：BM25 加权召回

```text
/brain-query <查询词>
```

适合：

- 不确定笔记标题。
- 想问一个自然语言问题。
- 想让系统找最相关的三篇笔记。

流程：

1. Agent 先检查当前会话和热记忆。
2. 当前上下文不足时，执行 `bm25_search.py`。
3. 命中 Top 3 后执行 `context_dehydrator.py --mode summary`。
4. 回答后通过 `activation_writer.py` 激活命中笔记。
5. 通过 `log_append.py` 写入查询日志。

常用脚本命令：

```bash
python3 scripts/bm25_search.py "上下文脱水" --project member
python3 scripts/bm25_search.py "上下文脱水"
```

### 5.2 精确查询：正文/别名匹配

```text
/brain-query-rg <关键词>
```

适合：

- 已知道准确关键词。
- 要定位代码符号、英文名、固定术语。
- BM25 没搜到，但你确定笔记里有这个词。

常用脚本命令：

```bash
python3 scripts/rg_body_search.py "BrainOS" \
  wiki/global_concepts \
  wiki/project_exclusives/member
```

命中后会进入 `context_dehydrator.py --mode precise`，只保留命中段落和必要上下文。

### 5.3 资产审计

```text
/brain-search <关键词>
/brain-search-rg <关键词>
```

适合：

- 想知道某个主题存在于哪些公共规范、项目笔记或历史会话中。
- 想区分“通用知识”还是“项目专属经验”。
- 想做跨项目资产盘点。

## 6. 激活、权重和热记忆

### 6.1 什么是激活

当一篇笔记被查询命中并用于回答时，系统会激活它：

- `last_activated` 改为当天。
- `last_modified` 改为当天。
- `access_count + 1`。
- `ewma_access` 增加并按半衰期衰减。
- `current_weight` 重新计算。

手动执行激活：

```bash
python3 scripts/activation_writer.py \
  --path "/Users/za-stanlexu/Documents/member/member/wiki/project_exclusives/member/context-dehydrator.md" \
  --context "上下文脱水"
```

带 boost：

```bash
python3 scripts/activation_writer.py \
  --path "/Users/za-stanlexu/Documents/member/member/wiki/project_exclusives/member/context-dehydrator.md" \
  --context "重要 上线前复习" \
  --boost 1.4
```

### 6.2 热记忆文件

全局热记忆：

```text
wiki/global_hot.md
```

项目热记忆：

```text
wiki/project_exclusives/member/hot.md
```

自动刷新 watcher：

```bash
bash scripts/hot_watcher.sh
```

手动刷新：

```bash
python3 scripts/hot_refresh.py --global
python3 scripts/hot_refresh.py --project member
```

不要手动编辑 hot 文件，它们会被脚本覆盖。

## 7. 执行记忆整理和归档

### 7.1 Dry-run 预览

```bash
python3 scripts/memory_manager.py --dry-run
```

会输出 JSON 汇总，不写文件、不刷新索引。

### 7.2 实际整理

```text
/brain-consolidate
```

或直接执行：

```bash
python3 scripts/memory_manager.py
```

整理动作包括：

- 给缺 frontmatter 的笔记补齐 schema。
- 补齐 `status` 和 `superseded_by`。
- 迁移 V2 权重字段。
- 计算 `current_weight`。
- 标记孤儿 `.tmp` 为 `status: incomplete`。
- 将低于 `forget_threshold` 的旧笔记移入 `archive/`。
- 刷新 `wiki/index.md`。

首次 V2 迁移有归档宽限：第一次扫描只更新字段和权重，不立刻归档；下一次扫描仍低于阈值才会移动到 `archive/`。

## 8. 导入历史会话

使用：

```bash
bash scripts/palace_bridge.sh
```

它会：

- 根据当前 Git 项目名生成 `wing_project_<project>`。
- 从 `~/.claude/projects/` 挖掘历史会话到 MemPalace。
- 将原始会话材料导出到 `_inbox/palace_raw/`。
- 将 `_inbox/global_shared_raw/` 中的公共规范注入 `wing_global_shared`。

导入后仍需要人工或 Agent 提炼稳定结论，再通过 `/brain-ingest` 写成结构化笔记。

## 9. 同步到 Git

```bash
bash scripts/vault_sync.sh
```

同步前确认：

- 当前分支等于 `BRAIN_SYNC_BRANCH`，未设置时默认为 `main`。
- 没有 hot refresh 写入锁持续占用。
- 本地 Git 状态符合预期。

可指定发布分支：

```bash
BRAIN_SYNC_BRANCH=feat0602 bash scripts/vault_sync.sh
```

注意：该脚本会 rebase，并在有变更时自动 commit 和 `push --force-with-lease`。更适合个人私有知识库。

## 10. 常见问题

### 10.1 查不到明明存在的内容

处理顺序：

1. 确认笔记在 `wiki/global_concepts/` 或 `wiki/project_exclusives/<project>/`。
2. 确认 `status: active`。
3. 用精确查询：

```bash
python3 scripts/rg_body_search.py "关键词" wiki/global_concepts wiki/project_exclusives/member
```

4. 给笔记补充 `aliases`。
5. 重建 BM25 缓存：

```bash
python3 scripts/bm25_search.py --rebuild-cache
```

### 10.2 hot 文件没有更新

检查 watcher 是否运行：

```bash
ps ax | grep hot_watcher
```

手动刷新：

```bash
python3 scripts/hot_refresh.py --global
python3 scripts/hot_refresh.py --project member
```

### 10.3 笔记被标记 incomplete

通常是写入时留下了同名 `.tmp` 文件。先检查该 `.tmp` 内容，确认是否需要恢复；不要直接让 incomplete 笔记参与查询。处理完后再手动修正状态或重新入库。

### 10.4 激活失败

常见原因：

- 文件不在 `wiki/global_concepts` 或 `wiki/project_exclusives`。
- 文件是 `hot.md`、`global_hot.md`、`index.md` 或 `log.md`。
- 文件没有 frontmatter。
- `status` 是 `archived/deprecated/incomplete`。
- 路径是逃逸出 wiki 的软链。

### 10.5 归档笔记怎么恢复

当前系统没有自动复活流程。建议手动确认归档笔记仍有价值后：

1. 从 `archive/` 找到对应笔记。
2. 复制或移动回正确的 `wiki/global_concepts/` 或 `wiki/project_exclusives/<project>/`。
3. 将 `status` 改为 `active`。
4. 更新日期和权重字段。
5. 运行：

```bash
python3 scripts/memory_manager.py --dry-run
python3 scripts/memory_manager.py
```

## 11. 日常维护建议

每天或每次大量写入后：

```bash
python3 scripts/bm25_search.py --rebuild-cache
python3 scripts/hot_refresh.py --global
python3 scripts/hot_refresh.py --project member
```

每周：

```bash
python3 scripts/memory_manager.py --dry-run
python3 scripts/memory_manager.py
```

同步前：

```bash
git status --short
bash scripts/vault_sync.sh
```

## 12. 使用原则

- 稳定结论才入库，临时想法不要污染知识库。
- 一篇笔记只承载一个概念。
- `aliases` 要主动维护，它直接影响召回率。
- 不手动编辑自动生成文件：`global_hot.md`、项目 `hot.md`、`log.md`。
- 归档不是删除，是降低默认召回噪音。
- 查询命中后让 `activation_writer.py` 写回，不要手动改访问计数。
- 技术方案、历史草稿和最终可执行文档要分开放，避免规格旧文覆盖当前实现事实。
