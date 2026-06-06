# Obsidian-first 记忆仓库使用说明

## 入口

- `dashboards/记忆治理总览.md`
- `canvases/LLM-Brain-OS.canvas`
- `bases/active-memory.base`
- `templates/concept-project.md`

## 人工治理流程

1. 打开 `dashboards/记忆治理总览.md`。
2. 查看低权重、缺 aliases、最近激活和链接治理视图。
3. 使用 `templates/` 创建新笔记。
4. 使用 `bases/` 做筛选和排序。
5. 使用 `canvases/LLM-Brain-OS.canvas` 理解系统结构。

## Agent 治理流程

1. 读取 `canvases/LLM-Brain-OS.canvas`。
2. 读取 `dashboards/记忆治理总览.md`。
3. 执行 `python3 scripts/obsidian_audit.py --wiki-root wiki --canvas canvases/LLM-Brain-OS.canvas`。
4. 根据 JSON 报告维护 aliases、链接和低权重笔记。

## 注意事项

- 不手动编辑 `global_hot.md` 或项目 `hot.md`。
- 不强制启用 CSS snippet。
- 不用 Dataview 结果替代 Python 脚本权重计算。
