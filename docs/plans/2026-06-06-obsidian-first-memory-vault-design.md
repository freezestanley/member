# Obsidian-first 记忆仓库改造设计

**日期**：2026-06-06  
**状态**：已获用户确认  
**目标阶段**：第一版按 B 方案实现 Core + Dataview + Templater，第二阶段接 C 方案让 Agent 读取 Obsidian-native 结构。  
**适用仓库**：`/Users/za-stanlexu/Documents/member/member`

## 1. 背景

当前记忆仓库已经具备 Markdown 笔记、frontmatter、BM25 检索、rg 精确检索、上下文脱水、激活写回、权重衰减、热记忆和 Git 同步能力。但使用方式仍偏“脚本读取 Markdown 文件夹”，没有充分发挥 Obsidian 作为知识操作界面的能力。

Obsidian 当前已启用核心插件：

- `graph`
- `backlink`
- `canvas`
- `tag-pane`
- `properties`
- `daily-notes`
- `templates`
- `bases`

用户确认的方向是：

1. 第一版接受社区插件能力，按 B 方案做 Core + Dataview + Templater。
2. 第二阶段接 C 方案，让 Agent 读取 Obsidian 视图、Canvas 和治理报告。

## 2. 设计目标

第一版目标：

- 让 Obsidian 成为记忆仓库的主要治理界面，而不仅是 Markdown 展示器。
- 用 Dataview 提供动态治理看板。
- 用 Templater 提供标准化入库模板。
- 用 Bases 提供 Obsidian 原生 properties 视图。
- 用 Canvas 提供系统地图和知识流转入口。
- 用 tags / cssclasses 增强 Obsidian graph、tag pane 和视觉分组能力。
- 不破坏现有 Python 脚本对 frontmatter 的读写。

第二阶段目标：

- 让 Agent 把 Obsidian-native 结构作为召回和维护依据。
- 让 Agent 能读取 Canvas 系统地图、Dataview 治理报告和 Bases 视图定义。
- 将“低权重、缺 aliases、孤儿笔记、弱连接、高权重无出链”等治理项转化为 Agent 维护任务。

## 3. 非目标

第一版不做以下事情：

- 不重写 BM25 / rg / 权重 / 归档核心链路。
- 不引入数据库。
- 不要求 Obsidian 插件自动执行 Python 脚本。
- 不让 Agent 直接依赖 Dataview 插件运行结果。
- 不删除 `wiki/index.md`、`global_hot.md` 或项目 `hot.md`。
- 不修改 `.obsidian/workspace.json`，避免污染用户当前工作区布局。
- 不自动迁移 archive 笔记。

## 4. 总体架构

```text
现有脚本引擎
  bm25_search.py
  rg_body_search.py
  context_dehydrator.py
  activation_writer.py
  weight_engine.py
  memory_manager.py
  hot_refresh.py
        │
        │ 写入 / 维护 frontmatter properties
        ▼
Obsidian UX Layer
  templates/      Templater 入库模板
  dashboards/     Dataview 治理看板
  bases/          Obsidian Bases 视图
  canvases/       Canvas 系统地图
  snippets/       可选 CSS 视觉增强
        │
        │ 人在 Obsidian 内治理知识
        ▼
Agent-native Layer（第二阶段）
  读取 dashboards / canvases / bases
  生成维护建议
  调用现有脚本执行激活、整理和同步
```

## 5. 第一版交付物

### 5.1 Templater 模板

新增目录：

```text
templates/
```

模板文件：

```text
templates/concept-global.md
templates/concept-project.md
templates/decision.md
templates/pitfall.md
templates/usage-manual.md
```

设计原则：

- 模板写完整 frontmatter。
- 保留现有脚本必需字段。
- 增加 Obsidian 友好的 `tags` 和 `cssclasses`。
- 使用 Templater 语法自动填充日期。
- 项目名仍允许手动填写，避免模板强依赖外部脚本。

建议字段：

```yaml
---
type: concept
created_at: <% tp.date.now("YYYY-MM-DD") %>
last_modified: <% tp.date.now("YYYY-MM-DD") %>
project: member
aliases: []
code_symbols: []
initial_weight: 1.0
current_weight: 1.0
last_activated: <% tp.date.now("YYYY-MM-DD") %>
access_count: 1
status: active
superseded_by: ""
weight_schema_version: 2
category: general
importance: 1
ewma_access: 0.0
last_boost: 1.0
last_boosted_at: ""
last_weight_migrated_at: <% tp.date.now("YYYY-MM-DD") %>
tags:
  - memory/active
  - type/concept
  - category/general
  - project/member
cssclasses:
  - memory-note
---
```

兼容性约束：

- Python 现有 frontmatter parser 是简单的行级 key/value 解析，不应依赖它理解嵌套列表。
- 新增 `tags` 和 `cssclasses` 可以被 Obsidian 使用，但现有脚本不应依赖解析它们。
- `upsert_frontmatter_fields()` 会保留未知字段；后续脚本更新权重字段时不应删除 Obsidian 字段。

### 5.2 Dataview 治理看板

新增目录：

```text
dashboards/
```

看板文件：

```text
dashboards/记忆治理总览.md
dashboards/低权重待处理.md
dashboards/最近激活.md
dashboards/缺少 aliases.md
dashboards/项目 member 记忆.md
dashboards/归档候选.md
dashboards/链接治理.md
```

看板定位：

- `记忆治理总览.md`：入口页，链接到其他视图、hot 文件、Canvas 和手册。
- `低权重待处理.md`：显示 active 且 `current_weight < 0.3` 的笔记。
- `最近激活.md`：按 `last_activated` 降序显示近期使用笔记。
- `缺少 aliases.md`：显示 `aliases` 为空或缺失的笔记。
- `项目 member 记忆.md`：只显示 `project = member` 的 active 笔记。
- `归档候选.md`：显示接近 `forget_threshold` 的笔记。
- `链接治理.md`：显示低出链、低入链、孤儿候选，第一版可先以人工说明和 Dataview 基础查询为主。

示例 Dataview：

```dataview
TABLE project, category, current_weight, access_count, last_activated
FROM "wiki"
WHERE status = "active"
SORT current_weight DESC
```

注意：

- Dataview 对 YAML 数字和字符串较敏感，当前字段应尽量保持数字字段为未加引号的数字。
- `aliases: []` 是合法 YAML，但查询空数组时需要在实际 Obsidian 中验证表达式。
- 第一版以文件落地和人工可用为目标，不要求自动化测试执行 Dataview 查询。

### 5.3 Obsidian Bases 视图

新增目录：

```text
bases/
```

视图文件：

```text
bases/active-memory.base
bases/project-memory.base
bases/archive-candidates.base
bases/recent-activations.base
bases/alias-needed.base
```

设计原则：

- Bases 作为 Obsidian 原生 properties 视图，与 Dataview 并存。
- Dataview 更适合 Markdown 看板；Bases 更适合 Obsidian 内排序、过滤和浏览。
- `.base` 文件格式需要严格按当前 Obsidian 版本验证。第一版实现时如果 schema 不确定，应优先生成嵌入式 Base 代码块或保守 `.base` 文件，并用 JSON/YAML 解析验证。

基础视图需求：

| 文件 | 过滤目标 | 排序 |
| --- | --- | --- |
| `active-memory.base` | `status = active` | `current_weight` 降序 |
| `project-memory.base` | `project = member` 且 active | `last_activated` 降序 |
| `archive-candidates.base` | active 且 `current_weight < 0.3` | `current_weight` 升序 |
| `recent-activations.base` | active | `last_activated` 降序 |
| `alias-needed.base` | aliases 缺失或为空 | `last_modified` 降序 |

### 5.4 Canvas 系统地图

新增目录：

```text
canvases/
```

新增文件：

```text
canvases/LLM-Brain-OS.canvas
```

Canvas 节点：

- `全局知识区` -> `wiki/global_concepts`
- `项目知识区` -> `wiki/project_exclusives/member`
- `热记忆` -> `wiki/global_hot.md`、`wiki/project_exclusives/member/hot.md`
- `BM25 召回` -> `wiki/project_exclusives/member/bm25-memory-retrieval-pipeline.md`
- `上下文脱水` -> `wiki/project_exclusives/member/context-dehydrator.md`
- `权重衰减` -> `wiki/project_exclusives/member/memory-weight-decay.md`
- `双轨热记忆` -> `wiki/project_exclusives/member/hot-memory-dual-track.md`
- `系统架构` -> `wiki/project_exclusives/member/llm-brain-os-architecture.md`
- `技术方案` -> `docs/memory-repository-technical-solution.md`
- `使用手册` -> `docs/memory-repository-user-manual.md`
- `治理总览` -> `dashboards/记忆治理总览.md`

Canvas 边：

```text
原始知识 -> 入库模板 -> wiki 笔记 -> 检索召回 -> 脱水 -> 激活 -> 权重 -> 热记忆 -> 归档/同步
```

实现约束：

- `.canvas` 是 JSON 文件，必须可被 `json.load()` 解析。
- 使用 file node 优先，减少纯文本节点。
- 节点位置固定，便于打开后直接看到完整系统图。

### 5.5 Tags 与 cssclasses

建议 tags：

```text
memory/active
memory/archived
type/concept
type/decision
type/pitfall
type/manual
project/member
project/global
category/general
category/strategy
category/fact
category/decision
category/log
category/spec
```

建议 cssclasses：

```text
memory-note
memory-hot
memory-cold
memory-decision
memory-pitfall
```

新增可选 CSS：

```text
.obsidian/snippets/memory-vault.css
```

CSS 只做轻量视觉提示，不改变功能：

- 对 `.memory-hot` 添加左边框。
- 对 `.memory-cold` 降低标题强调。
- 对 `.memory-decision` 使用决策色。

第一版不强制启用 snippet，避免修改 Obsidian 外观配置。

## 6. 第二阶段 Agent-native 设计

第二阶段在第一版稳定后进行。

新增能力：

1. Agent 读取 `dashboards/记忆治理总览.md`，理解当前治理入口。
2. Agent 读取 `canvases/LLM-Brain-OS.canvas`，获取系统结构地图。
3. Agent 读取 `bases/*.base`，理解 Obsidian 视图定义。
4. Agent 可执行治理任务：
   - 为缺 aliases 的笔记补 aliases。
   - 为孤儿笔记补出链。
   - 为高权重无出链笔记补关联。
   - 为低权重 active 笔记提出归档或保留建议。
5. Agent 不直接依赖 Dataview 插件运行结果，而是读取源 Markdown / properties 并复现必要查询逻辑。

第二阶段可新增脚本：

```text
scripts/obsidian_audit.py
scripts/canvas_export.py
scripts/dataview_like_queries.py
```

第一版不实现这些脚本，只保留设计接口。

## 7. 数据流

### 7.1 人在 Obsidian 中治理

```text
打开 dashboards/记忆治理总览.md
  -> 查看 Dataview 动态列表
  -> 打开 Bases 表格做筛选排序
  -> 打开 Canvas 理解系统和入口
  -> 使用 templates 创建新笔记
  -> 现有 watcher / memory_manager / activation_writer 继续维护权重
```

### 7.2 Agent 后续读取 Obsidian 结构

```text
用户提出治理任务
  -> Agent 读取 Canvas / dashboard / bases
  -> Agent 用本地脚本或文件扫描复现查询
  -> Agent 修改目标笔记 properties / 正文链接
  -> activation_writer 或 memory_manager 更新生命周期
  -> pytest 验证脚本兼容性
```

## 8. 错误处理

| 场景 | 处理 |
| --- | --- |
| Dataview 未安装 | 看板显示代码块，不影响现有脚本 |
| Templater 未安装 | 模板中的 Templater 表达式不会展开，用户可手动替换 |
| Bases schema 不兼容 | 保留 Markdown Dataview 看板作为 fallback |
| 新增 tags 影响脚本 | 现有 parser 应忽略未知字段；测试验证 |
| `.canvas` JSON 破损 | 用 `python3 -m json.tool` 或测试解析 |
| Obsidian snippet 未启用 | 只影响视觉，不影响功能 |

## 9. 测试策略

第一版验证：

```bash
python3 -m pytest
```

新增文件级验证建议：

- `templates/*.md` 包含完整必要 frontmatter 字段。
- `dashboards/*.md` 包含 Dataview 代码块。
- `canvases/LLM-Brain-OS.canvas` 可被 `json.load()` 解析。
- `bases/*.base` 文件存在，且格式按实现时确认的 Obsidian Bases schema 验证。
- 新增 `tags` / `cssclasses` 不影响 `frontmatter_utils.upsert_frontmatter_fields()`。

第二阶段验证：

- Agent audit 脚本能识别缺 aliases、低权重和孤儿笔记。
- Agent 能读取 canvas JSON 并列出系统节点。
- Agent 能从 dashboard 文件发现治理入口。

## 10. 参考资料

- Obsidian Bases: `https://help.obsidian.md/bases`
- Obsidian Properties: `https://help.obsidian.md/properties`
- Obsidian Canvas: `https://help.obsidian.md/plugins/canvas`
- Dataview: `https://blacksmithgu.github.io/obsidian-dataview/`
- Templater: `https://github.com/SilentVoid13/Templater`

## 11. 验收标准

第一版完成时：

- Obsidian 内有可打开的治理入口：`dashboards/记忆治理总览.md`。
- Obsidian 内有系统地图：`canvases/LLM-Brain-OS.canvas`。
- 有可复用入库模板：`templates/*.md`。
- 有 Bases 视图文件：`bases/*.base`。
- 现有 Python 测试仍全部通过。
- 未修改 `.obsidian/workspace.json`。
- 未破坏现有 `wiki/` 笔记 frontmatter schema。

第二阶段完成时：

- Agent 能读取 Obsidian 治理入口并生成维护建议。
- Agent 能读取 Canvas 系统图并引用其中节点。
- Agent 能用脚本复现核心治理查询，不依赖 Obsidian 插件运行时。
