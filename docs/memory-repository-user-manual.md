# 记忆仓库使用说明手册

**适用项目**：member 记忆仓库  
**适用日期**：2026-06-06  
**使用对象**：本地 Agent、知识维护者、Obsidian 使用者

## 1. 快速理解

这是一个本地 Markdown 记忆库，以 Obsidian 作为治理界面。你把稳定的知识写成单主题笔记，系统通过 BM25、正文精确检索、aliases、权重衰减和热记忆文件，在后续对话中把相关笔记召回给 LLM 使用。Obsidian 提供 Dataview 看板、Templater 入库模板、Bases 属性视图和 Canvas 系统地图，让人工治理不依赖命令行。

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
| Obsidian | 浏览 wiki、看板、双链和热榜 | 推荐 |
| Obsidian Dataview 插件 | 动态治理看板 | 看板功能需要 |
| Obsidian Templater 插件 | 标准化入库模板 | 模板功能需要 |
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

### 2.4 Obsidian CSS snippet 启用

视觉增强（热笔记绿色边框、冷笔记降透明等）需要手动启用 CSS snippet：

1. 打开 Obsidian > 设置 > Appearance > CSS snippets。
2. 找到 `memory-vault`，切换为启用状态。

该文件位于 `.obsidian/snippets/memory-vault.css`，不会被脚本自动激活。

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

放被冷冻归档的笔记（根目录下，含 `global_concepts/` 和 `project_exclusives/` 子目录镜像）。当前默认检索不会扫描归档区。

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

`index.md` 是中央索引，`log.md` 是查询日志，均由脚本维护，不要手动编辑。

```text
templates/
```

Templater 入库模板，Obsidian 中通过 Templater 插件使用。可选五种类型：concept-global、concept-project、decision、pitfall、usage-manual。

```text
dashboards/
```

Dataview 治理看板，Obsidian 中打开可查看动态表格。包含：记忆治理总览、低权重待处理、最近激活、缺少 aliases、项目 member 记忆、归档候选、链接治理。

```text
bases/
```

Obsidian Bases 属性视图（需 Obsidian 1.6+）。包含 active-memory、project-memory、archive-candidates、recent-activations、alias-needed 五个视图。

```text
canvases/LLM-Brain-OS.canvas
```

系统架构 Canvas，展示各模块关系和核心文件链接。在 Obsidian 中打开可视化浏览。

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

### 4.2 通过 Obsidian Templater 入库

在 Obsidian 中选择模板快速创建标准格式笔记：

1. 打开 Command Palette（`Cmd+P`）。
2. 输入 `Templater: Create new note from template`。
3. 选择对应模板：

| 场景 | 模板 |
| --- | --- |
| 跨项目通用概念 | `concept-global.md` |
| 当前项目专属概念 | `concept-project.md` |
| 技术或产品决策 | `decision.md` |
| 踩坑记录 | `pitfall.md` |
| 使用说明 | `usage-manual.md` |

模板自动填充创建日期和修改日期，正文含标准结构（结论/边界/细节/关联）。

### 4.3 手动创建笔记模板

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
tags:
  - memory/active
  - type/concept
  - project/member
  - category/general
cssclasses:
  - memory-note
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
| `importance` | `1..5`，越重要半衰期越长（影响权重衰减速度） |
| `tags` | 格式 `memory/<status>`、`type/<type>`、`project/<project>`、`category/<category>` |
| `cssclasses` | `memory-note` 为默认；可叠加 `memory-hot`、`memory-cold`、`memory-decision`、`memory-pitfall` |
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
- 想区分"通用知识"还是"项目专属经验"。
- 想做跨项目资产盘点。

## 6. Obsidian 治理界面

### 6.1 看板入口

在 Obsidian 中打开 `dashboards/记忆治理总览.md`，可跳转到所有治理看板：

- **低权重待处理**：`current_weight < 0.3` 的 active 笔记，需补充 aliases 或提升重要性。
- **最近激活**：过去 7 天被查询命中的笔记。
- **缺少 aliases**：没有设置别名的笔记，影响检索召回率。
- **项目 member 记忆**：当前项目全部 active 笔记。
- **归档候选**：`current_weight < 0.15`，下次 `brain-consolidate` 会被移入 `archive/`。
- **链接治理**：孤儿笔记（无出链）和弱连接笔记。

### 6.2 Canvas 系统地图

打开 `canvases/LLM-Brain-OS.canvas`，可视化浏览系统各模块关系、核心文件链接和数据流向。

### 6.3 Bases 属性视图

打开 `bases/` 下任意 `.base` 文件，Obsidian 会以表格形式展示笔记属性。支持排序、过滤、列定制。

### 6.4 Agent 审计脚本

Agent 可程序化运行 `obsidian_audit.py` 检查 alias 缺口和低权重候选：

```bash
python3 scripts/obsidian_audit.py \
  --wiki-root wiki \
  --canvas canvases/LLM-Brain-OS.canvas \
  --threshold 0.3
```

输出 JSON，包含：

- `alias_gaps`：缺少 aliases 的 active 笔记列表。
- `low_weight_candidates`：权重低于阈值的 active 笔记，按权重升序。
- `canvas_files`：Canvas 中所有 file 节点路径。

## 7. 激活、权重和热记忆

### 7.1 什么是激活

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

boost 关键词（来自 `config/weight_config.yml`）：

| 类型 | 关键词 | boost 值 |
| --- | --- | --- |
| high | 重要、紧急、开会、决策、上线 | 1.4 |
| medium | 参考、复习、回顾 | 1.2 |
| default | 其他 | 1.0 |

boost 有效期为 7 天（`boost_ttl_days`）。

### 7.2 热记忆文件

全局热记忆：

```text
wiki/global_hot.md
```

项目热记忆：

```text
wiki/project_exclusives/member/hot.md
```

自动刷新 watcher（需 macOS `fswatch`）：

```bash
bash scripts/hot_watcher.sh
```

手动刷新：

```bash
python3 scripts/hot_refresh.py --global
python3 scripts/hot_refresh.py --project member
```

不要手动编辑 hot 文件，它们会被脚本覆盖。

### 7.3 权重衰减规则

权重由 `category` 和 `importance` 决定的半衰期驱动：

| category | 默认半衰期 |
| --- | --- |
| `spec` | 120 天 |
| `strategy` | 90 天 |
| `decision` | 75 天 |
| `fact` | 60 天 |
| `general` | 30 天 |
| `log` | 7 天 |

`importance` 为 1~5，值越高，实际半衰期越长（`importance_k = 0.6`）。  
`forget_threshold = 0.15`，低于该值在下次整理时被归档。

## 8. 执行记忆整理和归档

### 8.1 Dry-run 预览

```bash
python3 scripts/memory_manager.py --dry-run
```

会输出 JSON 汇总，不写文件、不刷新索引。

### 8.2 实际整理

```text
/brain-consolidate
```

或直接执行：

```bash
python3 scripts/memory_manager.py
```

整理动作包括：

- 给缺 frontmatter 的笔记补齐 V2 schema（含 `tags`、`cssclasses`）。
- 补齐 `status` 和 `superseded_by`。
- 迁移 V2 权重字段。
- 计算 `current_weight`。
- 标记孤儿 `.tmp` 为 `status: incomplete`。
- 将低于 `forget_threshold` 的旧笔记移入 `archive/`。
- 刷新 `wiki/index.md`。

首次 V2 迁移有归档宽限：第一次扫描只更新字段和权重，不立刻归档；下一次扫描仍低于阈值才会移动到 `archive/`。

## 9. 导入历史会话

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

## 10. 同步到 Git

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

## 11. 常见问题

### 11.1 查不到明明存在的内容

处理顺序：

1. 确认笔记在 `wiki/global_concepts/` 或 `wiki/project_exclusives/<project>/`。
2. 确认 `status: active`。
3. 用精确查询：

```bash
python3 scripts/rg_body_search.py "关键词" wiki/global_concepts wiki/project_exclusives/member
```

4. 给笔记补充 `aliases`（中文名、英文名、缩写都加）。
5. 重建 BM25 缓存：

```bash
python3 scripts/bm25_search.py --rebuild-cache
```

### 11.2 hot 文件没有更新

检查 watcher 是否运行：

```bash
ps ax | grep hot_watcher
```

手动刷新：

```bash
python3 scripts/hot_refresh.py --global
python3 scripts/hot_refresh.py --project member
```

### 11.3 笔记被标记 incomplete

通常是写入时留下了同名 `.tmp` 文件。先检查该 `.tmp` 内容，确认是否需要恢复；不要直接让 incomplete 笔记参与查询。处理完后再手动修正状态或重新入库。

### 11.4 激活失败

常见原因：

- 文件不在 `wiki/global_concepts` 或 `wiki/project_exclusives`。
- 文件是 `hot.md`、`global_hot.md`、`index.md` 或 `log.md`。
- 文件没有 frontmatter。
- `status` 是 `archived/deprecated/incomplete`。
- 路径是逃逸出 wiki 的软链。

### 11.5 归档笔记怎么恢复

当前系统没有自动复活流程。建议手动确认归档笔记仍有价值后：

1. 从 `archive/` 找到对应笔记。
2. 复制或移动回正确的 `wiki/global_concepts/` 或 `wiki/project_exclusives/<project>/`。
3. 将 `status` 改为 `active`，同步更新 `tags: [memory/active, ...]`。
4. 更新日期和权重字段。
5. 运行：

```bash
python3 scripts/memory_manager.py --dry-run
python3 scripts/memory_manager.py
```

### 11.6 Dataview 看板不显示

确认：

- Obsidian 已安装并启用 Dataview 插件。
- 插件设置中 `Enable JavaScript Queries` 和 `Inline Query Prefix` 已打开。
- 笔记存放路径与 dashboard 查询路径一致（均以 `wiki` 为前缀）。

### 11.7 Templater 模板中的日期不生效

确认：

- Obsidian 已安装并启用 Templater 插件。
- 使用 `Templater: Create new note from template` 命令创建笔记，而不是直接复制粘贴模板内容。

## 12. 日常维护建议

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

或在 Obsidian 中打开 `dashboards/记忆治理总览.md` 检查治理看板，按需补充 aliases、提升重要性或手动归档。

同步前：

```bash
git status --short
bash scripts/vault_sync.sh
```

## 13. 命令完整参考

### 13.1 命令总览

| 命令 | 作用 | 默认 scope |
| --- | --- | --- |
| `/brain-query` | BM25 加权召回，基于知识库回答问题 | project |
| `/brain-query-rg` | rg 精确全文匹配，基于知识库回答问题 | project |
| `/brain-search` | BM25 跨库审计，看某词在哪些资产里出现 | global |
| `/brain-search-rg` | rg 精确跨库审计，看某词完整出现位置 | global |
| `/brain-ingest` | 把当前对话的稳定结论写入知识库 | — |
| `/brain-consolidate` | 执行权重衰减与归档整理 | — |

**query 和 search 的本质区别**：

- `query` 系列目标是"回答问题"，输出是基于命中笔记的确定性结论。
- `search` 系列目标是"审计分布"，输出是资产出现位置报告，不直接给出确定性结论。

**BM25 和 rg 的本质区别**：

- BM25（无 `-rg` 后缀）：词频语义召回，适合自然语言问题或不确定笔记标题的场景。
- rg（有 `-rg` 后缀）：正文正则精确匹配，适合已知准确关键词、代码符号、技术术语、需要定位行号的场景。

---

### 13.2 `/brain-query` — BM25 召回问答

**作用**：先查当前会话热记忆；热记忆不足时，用 BM25 检索知识库，取 Top 3 笔记脱水后回答，并激活命中笔记。

**调用方式**：

```text
/brain-query <查询词> [--scope project|global] [--dry]
```

**参数说明**：

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `<查询词>` | 必填 | 自然语言问题或关键词 |
| `--scope project` | 默认 | 当前项目私有笔记 + global_concepts |
| `--scope global` | — | 全库所有项目笔记 + global_concepts |
| `--dry` | 关闭 | 关闭脱水管道，直接读原文；适合短笔记、需逐字引用、调试脱水时 |

**底层调用链**：

```
bm25_search.py "<查询词>" [--project <name>]
  → Top 3 路径
  → context_dehydrator.py --mode summary（默认）/ 直接 Read（--dry）
  → 激活：activation_writer.py --path <file> --context "<查询词>"
  → 日志：log_append.py "brain-query" "<查询词>" "<摘要>"
```

**案例**：

```text
# 基础用法
/brain-query 权重衰减公式

# 跨项目检索
/brain-query 记忆检索管道 --scope global

# 关闭脱水，直接读原文
/brain-query EWMA --dry
```

执行后输出：
```
回答：<基于命中笔记的答案>
依据笔记：wiki/project_exclusives/member/memory-weight-decay.md
回写结果：已更新
激活摘要：current_weight=1.021, ewma_access=1.0, boost=1.0
```

---

### 13.3 `/brain-query-rg` — rg 精确匹配问答

**作用**：与 `/brain-query` 流程完全相同，检索引擎换为 rg 正文正则匹配。命中带行号，脱水使用 precise 模式（按标题段落裁剪，保留代码块完整性）。

**调用方式**：

```text
/brain-query-rg <关键词> [--scope project|global] [--dry]
```

**参数说明**：同 `/brain-query`，参数含义一致。

**底层调用链**：

```
rg_body_search.py "<关键词>" <目录...>
  → 命中文件:行号
  → context_dehydrator.py --mode precise --hits <file>:<lines>（默认）/ 直接 Read（--dry）
  → 激活：activation_writer.py
  → 日志：log_append.py "brain-query-rg" ...
```

**与 `/brain-query` 的选择依据**：

| 场景 | 推荐命令 |
| --- | --- |
| 自然语言问题，不知道笔记标题 | `/brain-query` |
| 已知准确关键词、函数名、配置项 | `/brain-query-rg` |
| BM25 没搜到但确定笔记里有这个词 | `/brain-query-rg` |
| 需要定位到具体行号 | `/brain-query-rg` |

**案例**：

```text
# 精确查代码符号
/brain-query-rg activation_writer

# 精确查配置项
/brain-query-rg forget_threshold

# 跨全库精确查
/brain-query-rg WeightEngine --scope global
```

---

### 13.4 `/brain-search` — BM25 跨库资产审计

**作用**：盘点某个关键词在公共规范（global_concepts）、项目专属笔记（project_exclusives）和 MemPalace 历史会话中的分布，输出"跨项目技术资产审计报告"。不直接给确定性答案。

**调用方式**：

```text
/brain-search <检索词> [--scope project|global] [--dry]
```

**参数说明**：

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `<检索词>` | 必填 | 关键词或主题 |
| `--scope global` | **默认** | 全库所有项目笔记 + global_concepts + MemPalace 公共规范域 |
| `--scope project` | — | 当前项目 + global_concepts + MemPalace 当前项目域 |
| `--dry` | 关闭 | 关闭脱水管道 |

注意：`/brain-search` 默认 scope 是 `global`，与 `query` 系列（默认 `project`）相反。

**底层调用链**：

```
bm25_search.py "<检索词>" [--project <name>]
  → Top N 路径 → context_dehydrator.py --mode summary
mempalace search "<检索词>" --wing "wing_global_shared" --limit 3
mempalace search "<检索词>" --wing "wing_project_<name>" --limit 3（--scope project 时）
  → 合并输出审计报告
  → 激活：activation_writer.py（仅本地 wiki 命中笔记）
  → 日志：log_append.py "brain-search" ...
```

**案例**：

```text
# 审计"记忆权重"在全库的分布
/brain-search 记忆权重

# 只审计当前项目范围
/brain-search EWMA --scope project

# 要看原文，关闭脱水
/brain-search hot_refresh --dry
```

输出格式：
```
跨项目技术资产审计报告

公共规范沉淀：
- wiki/global_concepts/xxx.md：通用权重衰减原则

历史项目独占实例：
- member：wiki/project_exclusives/member/memory-weight-decay.md | V2 权重公式实现

历史会话记忆：
- wing_project_member：2026-06-04 讨论 EWMA 参数调整

结论：该词为项目专属经验，建议用 /brain-query 深读
```

---

### 13.5 `/brain-search-rg` — rg 精确跨库资产审计

**作用**：与 `/brain-search` 流程完全相同，检索引擎换为 rg 正文正则匹配，命中带行号，脱水使用 precise 模式。适合需要审计某个精确词汇的所有出现位置。

**调用方式**：

```text
/brain-search-rg <检索词> [--scope project|global] [--dry]
```

**参数说明**：同 `/brain-search`，参数含义一致。

**与 `/brain-search` 的选择依据**：

| 场景 | 推荐命令 |
| --- | --- |
| 模糊主题审计 | `/brain-search` |
| 精确词汇/符号的所有出现位置 | `/brain-search-rg` |
| 需要行号定位 | `/brain-search-rg` |

**案例**：

```text
# 审计函数名在全库的所有出现位置
/brain-search-rg upsert_frontmatter_fields

# 审计配置项在当前项目的出现位置
/brain-search-rg boost_ttl_days --scope project
```

---

### 13.6 `/brain-ingest` — 写入知识库

**作用**：把当前对话中已经稳定、可复用的单一知识点写成笔记，原子写入知识库，更新索引，同步到 Git 远端。

**调用方式**：

```text
/brain-ingest
```

无需参数，Agent 从当前对话中自动提炼稳定结论。

**执行流程**：

1. 判断对话是否已形成稳定结论，没有则停止。
2. 判断通用知识（写入 `global_concepts/`）还是项目专属（写入 `project_exclusives/<project>/`）。
3. 一文一议，文件名为名词化主题（如 `memory-weight-decay.md`）。
4. 写入完整 V2 frontmatter + 结构化正文。
5. 原子写入：先写 `.tmp`，加 `fcntl.LOCK_EX` 锁，`os.rename` 原子移动。
6. 更新 `wiki/index.md` 对应分区。
7. 手动执行一次 `hot_refresh.py`（watcher 未运行时）。
8. 执行 `vault_sync.sh` 同步。

**笔记写入禁令**：

- 禁止把项目知识写入 `global_concepts`。
- 禁止多主题合并到同一文件。
- 禁止原样搬运整段对话。

**案例**：

场景：当前对话确定了「EWMA 访问频率衰减公式」，结论稳定可复用。

```text
/brain-ingest
```

输出：
```
已新增笔记：/Users/za-stanlexu/Documents/member/member/wiki/project_exclusives/member/ewma-access-decay.md
知识归属：member
核心结论：EWMA 以 14 天为半衰期衰减历史访问频率，每次激活增加 1.0，上限 20
同步结果：成功
```

**同名文件行为**：若同主题笔记已存在，Agent 会覆盖更新正文，`access_count`/`ewma_access`/`current_weight` 等激活字段**保留不重置**，`last_modified` 更新为今天。这是"1 条记录原地更新"，不产生历史版本。

---

### 13.7 `/brain-consolidate` — 权重衰减与归档

**作用**：扫描全库所有 active 笔记，计算最新权重，对低于 `forget_threshold=0.15` 的笔记执行冷冻归档（移入 `archive/`）。

**调用方式**：

```text
/brain-consolidate
```

无需参数。底层执行：

```bash
python3 scripts/memory_manager.py
```

预览不写文件：

```bash
python3 scripts/memory_manager.py --dry-run
```

**执行动作**：

| 动作 | 条件 |
| --- | --- |
| 补全 V2 frontmatter | 无 frontmatter 或 `weight_schema_version != 2` |
| 标记 `status: incomplete` | 发现同名 `.tmp` 孤儿文件 |
| 更新 `current_weight` | 所有 active 笔记 |
| 首次迁移宽限 | V1→V2 升级时不立即归档，只更新字段 |
| 冷冻归档 | 非首次迁移且 `current_weight < 0.15` |
| 刷新 `wiki/index.md` | 非 dry-run 时 |

**归档位置**：`archive/global_concepts/` 或 `archive/project_exclusives/<project>/`（镜像原路径结构）。

**案例**：

```text
# 先预览
/brain-consolidate --dry-run
→ 脚本输出 JSON：{ "scanned": 12, "archived": 2, "updated": 8, ... }

# 实际执行
/brain-consolidate
→ 输出：
  归档结果：
  - wiki/project_exclusives/member/old-note.md | 权重=0.08
  保留汇总：10
  异常项：无
```

**注意**：已归档笔记不能被自动复活，需手动从 `archive/` 移回并修改 `status: active`。

---

### 13.8 共用参数速查

| 参数 | 适用命令 | 作用 |
| --- | --- | --- |
| `--scope project` | query/query-rg/search/search-rg | 限定当前项目 + global_concepts |
| `--scope global` | query/query-rg/search/search-rg | 全库所有项目 |
| `--dry` | query/query-rg/search/search-rg | 关闭脱水，读笔记原文 |
| `--dry-run` | consolidate（脚本层） | 预览归档结果，不写文件 |
| `--boost 1.4` | 激活脚本（手动调用） | 高优先级 boost，有效期 7 天 |

---

## 14. 使用原则

- 稳定结论才入库，临时想法不要污染知识库。
- 一篇笔记只承载一个概念。
- `aliases` 要主动维护，它直接影响召回率。
- 不手动编辑自动生成文件：`global_hot.md`、项目 `hot.md`、`log.md`、`index.md`。
- 归档不是删除，是降低默认召回噪音。
- 查询命中后让 `activation_writer.py` 写回，不要手动改访问计数。
- 技术方案、历史草稿和最终可执行文档要分开放，避免规格旧文覆盖当前实现事实。
- `tags` 和 `cssclasses` 由 templates 自动填充，保持格式一致，不要随意改动规范值。
