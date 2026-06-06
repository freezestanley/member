---
type: concept
created_at: 2026-06-06
last_modified: 2026-06-06
project: member
aliases: [Obsidian UX层, UX层, obsidian-first, Obsidian治理层]
code_symbols: [obsidian_audit.py, templates, dashboards, bases, canvases]
initial_weight: 1.0
current_weight: 1.0
last_activated: 2026-06-06
access_count: 1
status: active
superseded_by: ""
weight_schema_version: 2
category: spec
importance: 3
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

# Obsidian UX 层

## 结论

记忆仓库在 Python 脚本引擎之上增加了一个 Obsidian 原生 UX 层，通过 `templates/`、`dashboards/`、`bases/`、`canvases/` 和 `obsidian_audit.py` 让人工治理和 Agent 审计不依赖命令行。该层只读取 frontmatter properties 和文件系统，不干预脚本引擎，与核心链路完全解耦。

## 边界

- 适用：人工在 Obsidian 内治理知识（补 aliases、查低权重、看系统地图）。
- 适用：Agent 通过 `obsidian_audit.py` 程序化读取 alias 缺口、低权重候选和 Canvas 结构。
- 不适用：Dataview 看板不能被 Agent 直接依赖（渲染依赖 Obsidian 插件运行时）。
- 不适用：Templater 模板只在 Obsidian 内使用，手动创建笔记时需要人工填充日期。

## 细节

### 目录与职责

| 目录/文件 | 职责 |
| --- | --- |
| `templates/` | Templater 入库模板，5 种类型：concept-global、concept-project、decision、pitfall、usage-manual |
| `dashboards/` | Dataview 治理看板，7 个：记忆治理总览、低权重待处理、最近激活、缺少 aliases、项目 member 记忆、归档候选、链接治理 |
| `bases/` | Obsidian Bases 属性视图，5 个：active-memory、project-memory、archive-candidates、recent-activations、alias-needed |
| `canvases/LLM-Brain-OS.canvas` | 系统架构可视化，≥10 节点、≥8 条边，必须链接 6 个核心文件 |
| `scripts/obsidian_audit.py` | Agent 审计脚本，输出 alias_gaps / low_weight_candidates / canvas_files |
| `.obsidian/snippets/memory-vault.css` | CSS 视觉增强，需手动在 Obsidian Appearance 中启用 |

### frontmatter 新增字段（V2 扩展）

- `tags`：格式 `memory/<status>`、`type/<type>`、`project/<project>`、`category/<category>`，增强 graph 和 tag pane。
- `cssclasses`：`memory-note`（默认）；可叠加 `memory-hot`、`memory-cold`、`memory-decision`、`memory-pitfall`。

### obsidian_audit.py 用法

```bash
python3 scripts/obsidian_audit.py \
  --wiki-root wiki \
  --canvas canvases/LLM-Brain-OS.canvas \
  --threshold 0.3
```

输出：

```json
{
  "alias_gaps": [...],
  "low_weight_candidates": [...],
  "canvas_files": [...]
}
```

### CSS snippet 类名

| 类名 | 效果 |
| --- | --- |
| `.memory-note` | accent 颜色标注 |
| `.memory-hot` | 左绿色边框 |
| `.memory-cold` | 降透明度 0.78 |
| `.memory-decision` | 左蓝色边框 |
| `.memory-pitfall` | 左红色边框 |

### 设计约束

- 不破坏 Python 脚本对 frontmatter 的读写。
- 不修改 `.obsidian/workspace.json`。
- 不让 Agent 直接依赖 Dataview 运行结果。
- CSS snippet 不强制写入 `.obsidian/appearance.json`，由用户手动启用。

## 关联

- [[llm-brain-os-architecture]]
- [[memory-weight-decay]]
- [[hot-memory-dual-track]]
- [[bm25-memory-retrieval-pipeline]]
