---
type: concept
created_at: 2026-06-05
last_modified: 2026-06-05
project: test
aliases: [前端技术栈, 前端开发规范]
code_symbols: []
initial_weight: 1.0
current_weight: 1.0
last_activated: 2026-06-05
access_count: 1
status: active
superseded_by: ""
---

# 前端开发规范 — 技术栈

## 结论

- 技术框架：**必须使用 React**
- 组件库：**必须使用 Ant Design（antd）**

## 边界

- 禁止使用 `@ant-design/icons`，图标统一用 `lucide-react` 替代（见全局 CLAUDE.md）
- 不允许引入其他 UI 组件库（如 MUI、Chakra UI）与 antd 混用

## 相关概念

- [[react-component-standards]]
